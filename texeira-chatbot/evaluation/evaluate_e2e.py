import json, sys, os, time, re, warnings
from collections import defaultdict
warnings.filterwarnings("ignore")

sys.path.insert(0, r"C:\Users\HP\Desktop\Chat bot\texeira-chatbot")
os.chdir(r"C:\Users\HP\Desktop\Chat bot\texeira-chatbot")

from src.retriever import build_hybrid_retriever
from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException
DetectorFactory.seed = 0

DATASET_PATH = r"C:\Users\HP\Desktop\Chat bot\texeira-chatbot\evaluation\eval_dataset.json"
OUTPUT_PATH = r"C:\Users\HP\Desktop\Chat bot\texeira-chatbot\evaluation\baseline_e2e_results.json"
CATALOG_PATH = r"C:\Users\HP\Desktop\Chat bot\texeira-chatbot\data\tours_catalog.json"

with open(DATASET_PATH, "r", encoding="utf-8") as f:
    dataset = json.load(f)

with open(CATALOG_PATH, "r", encoding="utf-8") as f:
    catalog = json.load(f)

_tour_images_map = {}
for tour in catalog.get("tours", []):
    if tour.get("images"):
        _tour_images_map[tour["id"]] = tour["images"]
_filename_to_tour_id = {
    "tour_city_tour.txt": "city-tour-cusco",
    "tour_machu_picchu.txt": "machu-picchu-clasico",
    "tour_montana_colores.txt": "montana-7-colores",
    "tour_valle_sagrado.txt": "valle-sagrado",
    "tour_laguna_humantay.txt": "laguna-humantay",
    "tour_salkantay.txt": "",
}
_source_to_tour_id = {}
_source_to_tour_id.update(_filename_to_tour_id)

from dotenv import load_dotenv
load_dotenv()

retriever = build_hybrid_retriever(persist_directory="./chroma_hybrid_db")

from app import get_llm, SYSTEM_PROMPT

llm = get_llm()

FALLBACK_TAIL = "contacta a un asesor humano de la agencia"
FALLBACK_KEYWORDS_ES = [
    "no dispongo", "no tengo información", "no se encuentra",
    "no cuento con", "información no disponible",
    "contacta a un asesor", "consulte con un asesor",
    "no está disponible", "no está en el catálogo",
]
FALLBACK_KEYWORDS_EN = [
    "i don't have", "i do not have", "not available",
    "contact an advisor", "speak to a human", "human advisor",
    "not in the catalog", "i don't have information",
]

def detect_language_simple(text):
    try:
        lang = detect(text)
        return lang if lang in ("es", "en", "pt", "fr") else "unknown"
    except LangDetectException:
        return "unknown"

def is_fallback(text):
    if not text:
        return False
    lowered = text.lower()
    if FALLBACK_TAIL in lowered and "dispongo" in lowered:
        return True
    for kw in FALLBACK_KEYWORDS_ES:
        if kw in lowered:
            return True
    for kw in FALLBACK_KEYWORDS_EN:
        if kw in lowered:
            return True
    return False

def build_context(docs):
    context_parts = []
    context_tour_ids = []
    for doc in docs:
        meta = doc.metadata
        header_lines = []
        if meta.get("tour_name"):
            header_lines.append(f"Tour: {meta['tour_name']}")
        if meta.get("tour_id"):
            header_lines.append(f"ID: {meta['tour_id']}")
        if meta.get("price_usd"):
            header_lines.append(f"Precio USD: {meta['price_usd']}")
        if meta.get("price_pen"):
            header_lines.append(f"Precio PEN: {meta['price_pen']}")
        if meta.get("category"):
            header_lines.append(f"Categoría: {meta['category']}")
        if header_lines:
            context_parts.append("[Información del tour]")
            context_parts.extend(header_lines)
            context_parts.append("")
        context_parts.append(doc.page_content)
        source = meta.get("source", "")
        filename = os.path.basename(source) if source else ""
        tour_id = _source_to_tour_id.get(filename, meta.get("tour_id", ""))
        if tour_id:
            context_tour_ids.append(tour_id)
        images = _tour_images_map.get(tour_id, [])
        if images:
            context_parts.append("Imágenes disponibles:")
            for img in images:
                context_parts.append(f"  - ![img]({img['url']}): {img.get('caption', img.get('alt', ''))}")
    return "\n\n".join(context_parts), context_tour_ids

def check_keywords(answer, expected_keywords):
    found = []
    answer_lower = answer.lower()
    for kw in expected_keywords:
        kw_lower = kw.lower()
        if kw_lower in answer_lower:
            found.append(kw)
    return found

def check_language_match(query_lang, response_text):
    resp_lang = detect_language_simple(response_text)
    if query_lang == "es":
        return resp_lang == "es"
    elif query_lang == "en":
        return resp_lang == "en"
    return True

def save_checkpoint(results_dict):
    class SetEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, set):
                return sorted(obj)
            return super().default(obj)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results_dict, f, ensure_ascii=False, indent=2, cls=SetEncoder)

def load_existing_results():
    if not os.path.exists(OUTPUT_PATH):
        return {}
    try:
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        existing = {}
        for r in data.get("results", []):
            if r.get("evaluation_status") == "completed":
                existing[r["id"]] = r
        return existing
    except (json.JSONDecodeError, KeyError):
        return {}

# ============================================================
# LOAD CHECKPOINT
# ============================================================
existing_completed = load_existing_results()
completed_ids = set(existing_completed.keys())
pending = [item for item in dataset if item["id"] not in completed_ids]

print(f"Checkpoint: {len(completed_ids)} completed, {len(pending)} pending")

# ============================================================
# MAIN LOOP
# ============================================================
results = list(existing_completed.values())
total_queries = len(dataset)
rate_limit_hit = False

for idx, item in enumerate(pending):
    qid = item["id"]
    query = item["query"]
    relevant = item.get("relevant_tour_ids", [])
    answerable = item.get("answerable", True)
    expected_keywords = item.get("expected_keywords", [])
    query_lang = item.get("language", "es")

    dataset_idx = next(i for i, d in enumerate(dataset) if d["id"] == qid)
    print(f"[{dataset_idx+1}/{total_queries}] {qid}: {query[:60]}...", end=" ", flush=True)

    # Retrieval
    t0 = time.perf_counter()
    docs = retriever.invoke(query)
    t_retrieval = time.perf_counter() - t0

    retrieved = []
    for i, doc in enumerate(docs):
        m = doc.metadata
        retrieved.append({
            "rank": i + 1,
            "tour_id": m.get("tour_id", "unknown"),
            "chunk_index": m.get("chunk_index", -1),
            "rrf_score": m.get("rrf_score", 0),
        })

    retrieved_tour_ids = [r["tour_id"] for r in retrieved]
    relevant_set = set(relevant) if relevant else set()
    retrieved_set = set(retrieved_tour_ids)
    intersection = relevant_set & retrieved_set
    first_relevant_rank = None
    for r in retrieved:
        if r["tour_id"] in relevant_set:
            first_relevant_rank = r["rank"]
            break

    context, context_tour_ids = build_context(docs)
    expected_tour_in_context = None
    if relevant and answerable:
        expected_tour_in_context = any(tid in context_tour_ids for tid in relevant)

    # Generation
    final_answer = None
    evaluation_status = None
    error_info = None
    t_generation = 0.0

    if not context.strip():
        final_answer = "No dispongo de esa información exacta. Por favor, contacta a un asesor humano de la agencia para ayudarte."
        evaluation_status = "completed"
        t_generation = 0.0
    else:
        system_msg = SYSTEM_PROMPT.format(context=context, question=query)
        messages = [("system", system_msg), ("human", query)]
        t0 = time.perf_counter()

        # Attempt 1
        try:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(llm.invoke, messages)
                result_llm = future.result(timeout=60)
                final_answer = result_llm.content
                evaluation_status = "completed"
        except concurrent.futures.TimeoutError:
            final_answer = "No dispongo de esa información exacta. Por favor, contacta a un asesor humano de la agencia para ayudarte."
            evaluation_status = "completed"
            print("[TIMEOUT]", end=" ", flush=True)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate_limit" in err_str.lower():
                # Save checkpoint before waiting
                result_entry_tmp = {"id": qid, "evaluation_status": "provider_rate_limit"}
                results.append(result_entry_tmp)
                _cfg = {
                    "retriever": "HybridRetriever", "vector_store": "./chroma_hybrid_db",
                    "final_k": 5, "max_chunks_per_tour": 2, "rrf_k": 60,
                    "llm_provider": os.getenv("LLM_PROVIDER", "groq"),
                    "llm_model": os.getenv("LLM_MODEL", "qwen/qwen3.8-27b"),
                    "temperature": 0.1, "max_tokens": 900,
                }
                checkpoint = {"config": _cfg, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "partial_evaluation": True, "results": results}
                save_checkpoint(checkpoint)
                results.pop()  # remove tmp entry

                # Extract retry-after
                import re as _re
                ra_match = _re.search(r'try again in (\d+)m(\d+\.?\d*)s', err_str)
                if ra_match:
                    wait = int(ra_match.group(1)) * 60 + float(ra_match.group(2)) + 2
                else:
                    wait = 47
                print(f"[429] Retry-after: {wait:.0f}s. Guardado. Esperando...", end=" ", flush=True)
                time.sleep(wait)

                # Attempt 2
                try:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(llm.invoke, messages)
                        result_llm = future.result(timeout=60)
                        final_answer = result_llm.content
                        evaluation_status = "completed"
                        print("[retry OK]", end=" ", flush=True)
                except Exception as e2:
                    err_str2 = str(e2)
                    if "429" in err_str2 or "rate_limit" in err_str2.lower():
                        evaluation_status = "provider_rate_limit"
                        error_info = "HTTP 429: quota exhausted after retry"
                        rate_limit_hit = True
                        print("[429 again]", end=" ", flush=True)
                    else:
                        evaluation_status = "provider_error"
                        error_info = err_str2[:200]
                        print("[ERROR retry]", end=" ", flush=True)
            else:
                evaluation_status = "provider_error"
                error_info = err_str[:200]
                print(f"[ERROR]", end=" ", flush=True)

        t_generation = time.perf_counter() - t0

    t_total = t_retrieval + t_generation

    # Post-generation evaluation (only for completed)
    if evaluation_status == "completed":
        fallback_detected = is_fallback(final_answer)
        lang_match = check_language_match(query_lang, final_answer)
        response_lang = detect_language_simple(final_answer)
        keyword_found = check_keywords(final_answer, expected_keywords) if answerable and expected_keywords else []
        keyword_coverage = len(keyword_found) / len(expected_keywords) if answerable and expected_keywords else None
        contains_price = bool(re.search(r'\$\s*\d+|USD|PEN|S/\s*\d+', final_answer)) if not answerable else None
        contains_itinerary = bool(re.search(r'día|day|noche|night|visita|visit|incluye|include', final_answer.lower())) if not answerable else None
        contains_duration = bool(re.search(r'\d+\s*(días?|days?|noches?|nights?|horas?|hours?)', final_answer.lower())) if not answerable else None
    else:
        fallback_detected = None
        lang_match = None
        response_lang = None
        keyword_found = []
        keyword_coverage = None
        contains_price = None
        contains_itinerary = None
        contains_duration = None
        final_answer = None

    result_entry = {
        "id": qid,
        "category": item["category"],
        "language": query_lang,
        "query_style": item.get("query_style", "standard"),
        "query": query,
        "expected_tour_id": item.get("expected_tour_id"),
        "expected_answer": item.get("expected_answer"),
        "expected_keywords": expected_keywords,
        "answerable": answerable,
        "relevant_tour_ids": relevant,
        "evaluation_status": evaluation_status,
        "retrieval": {
            "top5": retrieved,
            "relevant_tour_found": sorted(intersection),
            "first_relevant_rank": first_relevant_rank,
        },
        "context": {
            "tour_ids": context_tour_ids,
            "expected_tour_in_context": expected_tour_in_context,
        },
        "generation": {
            "final_answer": final_answer,
            "fallback_detected": fallback_detected,
            "response_language": response_lang,
            "language_match": lang_match,
        },
        "evaluation": {
            "keyword_found": keyword_found,
            "keyword_coverage": keyword_coverage,
            "contains_price": contains_price,
            "contains_itinerary": contains_itinerary,
            "contains_duration": contains_duration,
        },
        "latency": {
            "retrieval_latency_seconds": round(t_retrieval, 4),
            "generation_latency_seconds": round(t_generation, 4),
            "total_latency_seconds": round(t_total, 4),
        },
        "error": error_info,
    }
    results.append(result_entry)

    # Save checkpoint immediately after each query
    status_label = "completed" if evaluation_status == "completed" else evaluation_status
    print(f"{status_label} ({t_total:.2f}s)")

    checkpoint = {
        "config": {
            "retriever": "HybridRetriever",
            "vector_store": "./chroma_hybrid_db",
            "final_k": 5,
            "max_chunks_per_tour": 2,
            "rrf_k": 60,
            "llm_provider": os.getenv("LLM_PROVIDER", "groq"),
            "llm_model": os.getenv("LLM_MODEL", "qwen/qwen3.8-27b"),
            "temperature": 0.1,
            "max_tokens": 900,
        },
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "partial_evaluation": True,
        "results": results,
    }
    save_checkpoint(checkpoint)
    print("Checkpoint guardado.")

    # If rate limit hit after retry, stop cleanly
    if rate_limit_hit:
        print()
        print("Evaluacion pausada por rate limit. Puede reanudarse posteriormente.")
        print(f"Completed: {sum(1 for r in results if r['evaluation_status'] == 'completed')}")
        print(f"Pending:   {sum(1 for r in results if r['evaluation_status'] != 'completed')}")
        break

    # Pace successful queries to avoid 429
    if evaluation_status == "completed" and idx < len(pending) - 1:
        print("Esperando 40s por limite de Groq...")
        time.sleep(40)

# ============================================================
# AGGREGATED STATISTICS (only from completed)
# ============================================================
completed = [r for r in results if r["evaluation_status"] == "completed"]
pending_count = sum(1 for r in results if r["evaluation_status"] != "completed")
provider_errors = sum(1 for r in results if r["evaluation_status"] in ("provider_rate_limit", "provider_error"))

answerable_completed = [r for r in completed if r["answerable"]]
non_answerable_completed = [r for r in completed if not r["answerable"]]

# expected_tour_in_context (from completed answerable only)
etc_true = sum(1 for r in answerable_completed if r["context"]["expected_tour_in_context"] is True)
etc_false = sum(1 for r in answerable_completed if r["context"]["expected_tour_in_context"] is False)
etc_rate = etc_true / len(answerable_completed) if answerable_completed else 0

# keyword coverage (from completed answerable only)
kc_vals = [r["evaluation"]["keyword_coverage"] for r in answerable_completed if r["evaluation"]["keyword_coverage"] is not None]
avg_kc = sum(kc_vals) / len(kc_vals) if kc_vals else 0

# language match (from completed only)
lm_true = sum(1 for r in completed if r["generation"]["language_match"])
lm_rate = lm_true / len(completed) if completed else 0

# latency (from completed only)
ret_lats = [r["latency"]["retrieval_latency_seconds"] for r in completed]
gen_lats = [r["latency"]["generation_latency_seconds"] for r in completed if r["latency"]["generation_latency_seconds"] > 0]
tot_lats = [r["latency"]["total_latency_seconds"] for r in completed]

avg_ret = sum(ret_lats) / len(ret_lats) if ret_lats else 0
avg_gen = sum(gen_lats) / len(gen_lats) if gen_lats else 0
avg_tot = sum(tot_lats) / len(tot_lats) if tot_lats else 0

# out-of-catalog (from completed non-answerable only)
fb_detected = sum(1 for r in non_answerable_completed if r["generation"]["fallback_detected"])
spo_price = sum(1 for r in non_answerable_completed if r["evaluation"]["contains_price"])
spo_itin = sum(1 for r in non_answerable_completed if r["evaluation"]["contains_itinerary"])
spo_dur = sum(1 for r in non_answerable_completed if r["evaluation"]["contains_duration"])

# review cases (from completed only)
review_a = [r for r in answerable_completed if r["context"]["expected_tour_in_context"] is False]
review_b = [r for r in answerable_completed if r["context"]["expected_tour_in_context"] is True and r["evaluation"]["keyword_coverage"] is not None and r["evaluation"]["keyword_coverage"] < 0.5]
review_c = [r for r in completed if not r["generation"]["language_match"]]
review_d = [r for r in non_answerable_completed if r["evaluation"]["contains_price"] or r["evaluation"]["contains_itinerary"] or r["evaluation"]["contains_duration"]]
review_e = [r for r in completed if r["error"]]

all_done = pending_count == 0 and provider_errors == 0

output = {
    "config": {
        "retriever": "HybridRetriever",
        "vector_store": "./chroma_hybrid_db",
        "final_k": 5,
        "max_chunks_per_tour": 2,
        "rrf_k": 60,
        "llm_provider": os.getenv("LLM_PROVIDER", "groq"),
        "llm_model": os.getenv("LLM_MODEL", "qwen/qwen3.8-27b"),
        "temperature": 0.1,
        "max_tokens": 900,
    },
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    "partial_evaluation": not all_done,
    "summary": {
        "total_queries": len(dataset),
        "completed_queries": len(completed),
        "pending_queries": pending_count,
        "provider_errors": provider_errors,
    },
    "expected_tour_in_context": {
        "true": etc_true,
        "false": etc_false,
        "rate": round(etc_rate, 4) if answerable_completed else None,
    },
    "keyword_coverage": {
        "queries_with_keywords": len(kc_vals),
        "mean_coverage": round(avg_kc, 4) if kc_vals else None,
    },
    "language_match": {
        "total_match": lm_true,
        "total_mismatch": len(completed) - lm_true,
        "rate": round(lm_rate, 4) if completed else None,
    },
    "latency": {
        "mean_retrieval_s": round(avg_ret, 4) if completed else None,
        "mean_generation_s": round(avg_gen, 4) if completed else None,
        "mean_total_s": round(avg_tot, 4) if completed else None,
    },
    "out_of_catalog": {
        "count": len(non_answerable_completed),
        "fallback_detected": fb_detected,
        "contains_price": spo_price,
        "contains_itinerary": spo_itin,
        "contains_duration": spo_dur,
    },
    "review_cases": {
        "A_expected_tour_not_in_context": [{"id": r["id"], "query": r["query"], "relevant": r["relevant_tour_ids"], "context_tour_ids": r["context"]["tour_ids"]} for r in review_a],
        "B_in_context_low_keyword_coverage": [{"id": r["id"], "query": r["query"], "keyword_coverage": r["evaluation"]["keyword_coverage"], "keyword_found": r["evaluation"]["keyword_found"], "expected": r["expected_keywords"]} for r in review_b],
        "C_language_mismatch": [{"id": r["id"], "query": r["query"], "query_lang": r["language"], "response_lang": r["generation"]["response_language"]} for r in review_c],
        "D_non_answerable_with_specific_data": [{"id": r["id"], "query": r["query"], "contains_price": r["evaluation"]["contains_price"], "contains_itinerary": r["evaluation"]["contains_itinerary"], "contains_duration": r["evaluation"]["contains_duration"]} for r in review_d],
        "E_errors": [{"id": r["id"], "error": r["error"]} for r in review_e],
    },
    "results": results,
}

save_checkpoint(output)

# ============================================================
# REPORT
# ============================================================
print(f"\n{'='*60}")
print(f"COMPLETED: {len(completed)}/{len(dataset)}")
print(f"PENDING:   {pending_count}")
print(f"429 ERRORS: {provider_errors}")
print(f"{'='*60}")

if completed:
    print(f"EXPECTED_TOUR_IN_CONTEXT: {etc_true}/{len(answerable_completed)} = {etc_rate:.4f}")
    print(f"KEYWORD COVERAGE promedio: {round(avg_kc, 4) if kc_vals else 'N/A'}")
    print(f"LANGUAGE MATCH: {lm_true}/{len(completed)} = {lm_rate:.4f}")
    print(f"LATENCIAS:")
    print(f"  Retrieval:  {avg_ret:.4f}s")
    print(f"  Generation: {avg_gen:.4f}s")
    print(f"  Total:      {avg_tot:.4f}s")
    print(f"OUT OF CATALOG ({len(non_answerable_completed)}):")
    print(f"  fallback: {fb_detected}, precio: {spo_price}, itin: {spo_itin}, dur: {spo_dur}")
    print(f"CASOS REVISION:")
    print(f"  A: {len(review_a)}, B: {len(review_b)}, C: {len(review_c)}, D: {len(review_d)}, E: {len(review_e)}")
else:
    print("No completed queries yet.")

if not all_done:
    print(f"\nEvaluacion PAUSADA ({pending_count} queries pendientes).")
    print("Re-ejecutar este script para continuar.")
