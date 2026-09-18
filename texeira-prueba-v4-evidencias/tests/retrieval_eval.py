"""
Evaluación del Retriever v4-evidencias (BASELINE).
Mide calidad de recuperación SIN LLM.
BM25, Vector, RRF por separado y combinado.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(__file__))

os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['ANONYMIZED_TELEMETRY'] = 'False'

from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever
from trial_support import documents, ENTITY_IDS, NAMES

# ============================================================
# GROUND TRUTH: 25 consultas + entity_ids relevantes
# ============================================================

GROUND_TRUTH = [
    # --- CULTURA / ARQUEOLOGÍA ---
    {
        "query": "Quiero conocer lugares arqueológicos cerca de Cusco",
        "relevant": ["city-tour-cusco", "valle-sur", "valle-sagrado"],
    },
    {
        "query": "Somos una pareja y queremos conocer algo cultural en Cusco, qué alternativas de la agencia podrían ser relevantes?",
        "relevant": ["city-tour-cusco", "valle-sagrado", "tour-mistico", "valle-sur"],
    },
    {
        "query": "Qué tours históricos ofrecen en la ciudad?",
        "relevant": ["city-tour-cusco"],
    },
    {
        "query": "Quiero visitar Ollantaytambo y Pisac",
        "relevant": ["valle-sagrado"],
    },
    {
        "query": "Hay algún tour que incluya Chinchero y Moray?",
        "relevant": ["valle-sagrado", "valle-sur"],
    },
    # --- AVENTURA / TREKKING ---
    {
        "query": "Quiero hacer trekking, qué opciones tienen?",
        "relevant": ["salkantay-trek", "camino-inka", "inka-jungle", "choquequirao"],
    },
    {
        "query": "Busco una caminata de varios días hasta Machu Picchu",
        "relevant": ["salkantay-trek", "camino-inka", "inka-jungle"],
    },
    {
        "query": "Qué es el Inka Jungle?",
        "relevant": ["inka-jungle"],
    },
    {
        "query": "Tienen tours de aventura para adictos a la adrenalina?",
        "relevant": ["inka-jungle", "salkantay-trek", "maras-moray-cuatrimoto"],
    },
    # --- MACHU PICCHU ---
    {
        "query": "Quiero ir a Machu Picchu, qué opciones hay?",
        "relevant": ["machu-picchu-tren", "machu-picchu-car", "salkantay-trek", "camino-inka", "inka-jungle"],
    },
    {
        "query": "Machu Picchu en tren, qué incluye?",
        "relevant": ["machu-picchu-tren"],
    },
    {
        "query": "Machu Picchu por carretera, es posible?",
        "relevant": ["machu-picchu-car"],
    },
    # --- NATURALEZA / PAISAJES ---
    {
        "query": "Quiero ver paisajes impresionantes cerca de Cusco",
        "relevant": ["valle-sagrado", "valle-sur", "laguna-humantay", "montana-7-colores"],
    },
    {
        "query": "Hay algún tour para ver la laguna Humantay?",
        "relevant": ["laguna-humantay"],
    },
    {
        "query": "La montaña de 7 colores queda lejos?",
        "relevant": ["montana-7-colores"],
    },
    {
        "query": "Quiero ver Vinicunca, la montaña de colores",
        "relevant": ["montana-7-colores"],
    },
    # --- MEDIO DÍA / FULL DAY ---
    {
        "query": "Qué puedo hacer solo medio día en Cusco?",
        "relevant": ["city-tour-cusco", "valle-sur", "maras-moray"],
    },
    {
        "query": "Tienen algún tour de full day?",
        "relevant": ["valle-sagrado", "valle-sur", "laguna-humantay", "montana-7-colores", "waqra-pukara"],
    },
    {
        "query": "Algo rápido para hacer por la mañana y regresar a comer",
        "relevant": ["city-tour-cusco", "valle-sur", "maras-moray"],
    },
    # --- FAMILIA / ADULTOS MAYORES ---
    {
        "query": "Tour para toda la familia con niños pequeños",
        "relevant": ["city-tour-cusco", "valle-sagrado", "valle-sur", "maras-moray"],
    },
    {
        "query": "Algo tranquilo para personas mayores",
        "relevant": ["city-tour-cusco", "valle-sagrado", "valle-sur", "maras-moray"],
    },
    # --- CUATRIMOTOS ---
    {
        "query": "Tienen tours con cuatrimotos?",
        "relevant": ["maras-moray-cuatrimoto"],
    },
    {
        "query": "Quiero recorrer Maras y Moray en cuatrimoto",
        "relevant": ["maras-moray-cuatrimoto", "maras-moray"],
    },
    # --- EXPERIENCIAS CERCANAS ---
    {
        "query": "Algo cerca de la ciudad que no tome todo el día",
        "relevant": ["city-tour-cusco", "valle-sur", "maras-moray"],
    },
    {
        "query": "Qué puedo hacer si solo tengo un día libre en Cusco?",
        "relevant": ["city-tour-cusco", "valle-sagrado", "valle-sur"],
    },
]

# ============================================================
# EVALUATION FUNCTIONS
# ============================================================

def hit_at_k(retrieved_ids, relevant, k):
    """1 si al menos uno de los top-k retrieved está en relevant."""
    return 1 if any(r in relevant for r in retrieved_ids[:k]) else 0


def precision_at_k(retrieved_ids, relevant, k):
    """Proporción de top-k que está en relevant."""
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for r in top_k if r in relevant)
    return hits / k


def mrr(retrieved_ids, relevant):
    """Reciprocal rank del primer hit."""
    for i, r in enumerate(retrieved_ids):
        if r in relevant:
            return 1.0 / (i + 1)
    return 0.0


def extract_tour_id(doc):
    """Extrae tour_id de un documento recuperado."""
    return doc.metadata.get("tour_id", "unknown")


def run_evaluation():
    print("=" * 70)
    print("RETRIEVAL EVALUATION - v4-evidencias BASELINE")
    print("=" * 70)

    # --- Build retrievers ---
    print("\n[1] Building retrievers...")
    docs = documents()
    print(f"    Documents: {len(docs)}")

    embeddings = HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2')

    # Vector retriever
    chroma_dir = 'chroma_v4_evidencias_db'
    vectordb = Chroma(persist_directory=chroma_dir, embedding_function=embeddings)
    vector_retriever = vectordb.as_retriever(search_kwargs={'k': 20})

    # BM25 retriever
    lc_docs = [Document(page_content=d['page_content'], metadata=d['metadata']) for d in docs]
    bm25_retriever = BM25Retriever.from_documents(lc_docs, k=20)

    # Hybrid (RRF) retriever
    class SimpleHybridRetriever:
        def __init__(self, bm25, vector, rrf_k=60, k=20):
            self.bm25 = bm25
            self.vector = vector
            self.rrf_k = rrf_k
            self.k = k

        def invoke(self, query):
            bm25_docs = self.bm25.invoke(query)
            vector_docs = self.vector.invoke(query)

            doc_scores = {}
            for rank, doc in enumerate(bm25_docs):
                tid = extract_tour_id(doc)
                rrf_score = 1.0 / (self.rrf_k + rank + 1)
                doc_scores[tid] = {
                    "doc": doc, "score": rrf_score,
                    "bm25_rank": rank + 1, "vector_rank": None
                }

            for rank, doc in enumerate(vector_docs):
                tid = extract_tour_id(doc)
                rrf_score = 1.0 / (self.rrf_k + rank + 1)
                if tid in doc_scores:
                    doc_scores[tid]["score"] += rrf_score
                    doc_scores[tid]["vector_rank"] = rank + 1
                else:
                    doc_scores[tid] = {
                        "doc": doc, "score": rrf_score,
                        "bm25_rank": None, "vector_rank": rank + 1
                    }

            ranked = sorted(doc_scores.values(), key=lambda x: x["score"], reverse=True)
            return ranked[:self.k]

    hybrid = SimpleHybridRetriever(bm25_retriever, vector_retriever)

    # --- Evaluate each query ---
    print(f"\n[2] Evaluating {len(GROUND_TRUTH)} queries...\n")

    results = []
    total_hit3_bm25 = 0
    total_hit5_bm25 = 0
    total_p3_bm25 = 0.0
    total_p5_bm25 = 0.0
    total_mrr_bm25 = 0.0

    total_hit3_vec = 0
    total_hit5_vec = 0
    total_p3_vec = 0.0
    total_p5_vec = 0.0
    total_mrr_vec = 0.0

    total_hit3_rrf = 0
    total_hit5_rrf = 0
    total_p3_rrf = 0.0
    total_p5_rrf = 0.0
    total_mrr_rrf = 0.0

    for i, entry in enumerate(GROUND_TRUTH):
        query = entry["query"]
        relevant = set(entry["relevant"])

        # BM25
        bm25_docs = bm25_retriever.invoke(query)
        bm25_ids = [extract_tour_id(d) for d in bm25_docs]

        # Vector
        vec_docs = vector_retriever.invoke(query)
        vec_ids = [extract_tour_id(d) for d in vec_docs]

        # RRF
        rrf_results = hybrid.invoke(query)
        rrf_ids = [extract_tour_id(r["doc"]) for r in rrf_results]

        # Metrics
        h3_bm25 = hit_at_k(bm25_ids, relevant, 3)
        h5_bm25 = hit_at_k(bm25_ids, relevant, 5)
        p3_bm25 = precision_at_k(bm25_ids, relevant, 3)
        p5_bm25 = precision_at_k(bm25_ids, relevant, 5)
        mrr_bm25 = mrr(bm25_ids, relevant)

        h3_vec = hit_at_k(vec_ids, relevant, 3)
        h5_vec = hit_at_k(vec_ids, relevant, 5)
        p3_vec = precision_at_k(vec_ids, relevant, 3)
        p5_vec = precision_at_k(vec_ids, relevant, 5)
        mrr_vec = mrr(vec_ids, relevant)

        h3_rrf = hit_at_k(rrf_ids, relevant, 3)
        h5_rrf = hit_at_k(rrf_ids, relevant, 5)
        p3_rrf = precision_at_k(rrf_ids, relevant, 3)
        p5_rrf = precision_at_k(rrf_ids, relevant, 5)
        mrr_rrf = mrr(rrf_ids, relevant)

        total_hit3_bm25 += h3_bm25
        total_hit5_bm25 += h5_bm25
        total_p3_bm25 += p3_bm25
        total_p5_bm25 += p5_bm25
        total_mrr_bm25 += mrr_bm25

        total_hit3_vec += h3_vec
        total_hit5_vec += h5_vec
        total_p3_vec += p3_vec
        total_p5_vec += p5_vec
        total_mrr_vec += mrr_vec

        total_hit3_rrf += h3_rrf
        total_hit5_rrf += h5_rrf
        total_p3_rrf += p3_rrf
        total_p5_rrf += p5_rrf
        total_mrr_rrf += mrr_rrf

        results.append({
            "query": query,
            "relevant": list(relevant),
            "bm25_top5": bm25_ids[:5],
            "vector_top5": vec_ids[:5],
            "rrf_top5": rrf_ids[:5],
            "rrf_scores": [{"tour_id": r["doc"].metadata.get("tour_id"), "score": round(r["score"], 6),
                            "bm25_rank": r["bm25_rank"], "vector_rank": r["vector_rank"]}
                           for r in rrf_results[:5]],
            "hit3_bm25": h3_bm25, "hit5_bm25": h5_bm25,
            "p3_bm25": round(p3_bm25, 3), "p5_bm25": round(p5_bm25, 3), "mrr_bm25": round(mrr_bm25, 3),
            "hit3_vec": h3_vec, "hit5_vec": h5_vec,
            "p3_vec": round(p3_vec, 3), "p5_vec": round(p5_vec, 3), "mrr_vec": round(mrr_vec, 3),
            "hit3_rrf": h3_rrf, "hit5_rrf": h5_rrf,
            "p3_rrf": round(p3_rrf, 3), "p5_rrf": round(p5_rrf, 3), "mrr_rrf": round(mrr_rrf, 3),
        })

    n = len(GROUND_TRUTH)

    # --- Print results table ---
    print("=" * 70)
    print("RESULTS PER QUERY")
    print("=" * 70)
    print(f"{'#':>2} {'Q':<50} {'BM25_H3':>7} {'Vec_H3':>7} {'RRF_H3':>7} {'BM25_P3':>7} {'Vec_P3':>7} {'RRF_P3':>7}")
    print("-" * 100)
    for i, r in enumerate(results):
        q_short = r["query"][:48]
        print(f"{i+1:2d} {q_short:<50} {r['hit3_bm25']:>7} {r['hit3_vec']:>7} {r['hit3_rrf']:>7} "
              f"{r['p3_bm25']:>7.3f} {r['p3_vec']:>7.3f} {r['p3_rrf']:>7.3f}")

    # --- Global metrics ---
    print("\n" + "=" * 70)
    print("GLOBAL METRICS")
    print("=" * 70)
    print(f"{'Metric':<25} {'BM25':>10} {'Vector':>10} {'RRF':>10}")
    print("-" * 55)
    print(f"{'Hit@3':<25} {total_hit3_bm25/n:>10.3f} {total_hit3_vec/n:>10.3f} {total_hit3_rrf/n:>10.3f}")
    print(f"{'Hit@5':<25} {total_hit5_bm25/n:>10.3f} {total_hit5_vec/n:>10.3f} {total_hit5_rrf/n:>10.3f}")
    print(f"{'Precision@3':<25} {total_p3_bm25/n:>10.3f} {total_p3_vec/n:>10.3f} {total_p3_rrf/n:>10.3f}")
    print(f"{'Precision@5':<25} {total_p5_bm25/n:>10.3f} {total_p5_vec/n:>10.3f} {total_p5_rrf/n:>10.3f}")
    print(f"{'MRR':<25} {total_mrr_bm25/n:>10.3f} {total_mrr_vec/n:>10.3f} {total_mrr_rrf/n:>10.3f}")

    # --- Worst 5 queries ---
    print("\n" + "=" * 70)
    print("WORST 5 QUERIES (by RRF Hit@3)")
    print("=" * 70)
    sorted_results = sorted(results, key=lambda x: x["hit3_rrf"])
    for i, r in enumerate(sorted_results[:5]):
        print(f"\n  {i+1}. {r['query'][:60]}")
        print(f"     Relevant: {r['relevant']}")
        print(f"     RRF top5: {r['rrf_top5']}")
        print(f"     Hit@3={r['hit3_rrf']} P@3={r['p3_rrf']} MRR={r['mrr_rrf']}")

    # --- Detailed analysis of cultural query ---
    print("\n" + "=" * 70)
    print("DETAILED ANALYSIS: 'cultural en Cusco' query")
    print("=" * 70)
    cultural_idx = None
    for i, entry in enumerate(GROUND_TRUTH):
        if "cultural en Cusco" in entry["query"]:
            cultural_idx = i
            break

    if cultural_idx is not None:
        r = results[cultural_idx]
        print(f"\nQuery: {r['query']}")
        print(f"Relevant: {r['relevant']}")
        print(f"\nBM25 Top 5: {r['bm25_top5']}")
        print(f"Vector Top 5: {r['vector_top5']}")
        print(f"RRF Top 5: {r['rrf_top5']}")
        print(f"\nRRF Scores:")
        for s in r['rrf_scores']:
            print(f"  {s['tour_id']:<25} score={s['score']:.6f}  bm25_rank={s['bm25_rank']}  vec_rank={s['vector_rank']}")

        # Show which chunks are responsible
        print(f"\nChunk analysis (RRF top 5):")
        for item in hybrid.invoke(r["query"])[:5]:
            tid = extract_tour_id(item["doc"])
            content_preview = item["doc"].page_content[:120].replace("\n", " ")
            print(f"  {tid:<25} | {content_preview}...")

    # --- Save results ---
    output_path = os.path.join(os.path.dirname(__file__), "retrieval_eval_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_queries": n,
            "global_metrics": {
                "bm25": {"hit3": round(total_hit3_bm25/n, 3), "hit5": round(total_hit5_bm25/n, 3),
                          "p3": round(total_p3_bm25/n, 3), "p5": round(total_p5_bm25/n, 3),
                          "mrr": round(total_mrr_bm25/n, 3)},
                "vector": {"hit3": round(total_hit3_vec/n, 3), "hit5": round(total_hit5_vec/n, 3),
                           "p3": round(total_p3_vec/n, 3), "p5": round(total_p5_vec/n, 3),
                           "mrr": round(total_mrr_vec/n, 3)},
                "rrf": {"hit3": round(total_hit3_rrf/n, 3), "hit5": round(total_hit5_rrf/n, 3),
                        "p3": round(total_p3_rrf/n, 3), "p5": round(total_p5_rrf/n, 3),
                        "mrr": round(total_mrr_rrf/n, 3)},
            },
            "queries": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to: {output_path}")

    print("\n" + "=" * 70)
    print("EVALUATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    run_evaluation()
