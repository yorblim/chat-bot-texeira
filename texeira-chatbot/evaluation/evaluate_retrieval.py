import json, sys, warnings, os
from collections import defaultdict
warnings.filterwarnings("ignore")
sys.path.insert(0, r"C:\Users\HP\Desktop\Chat bot\texeira-chatbot")
from src.retriever import build_hybrid_retriever

DATASET_PATH = r"C:\Users\HP\Desktop\Chat bot\texeira-chatbot\evaluation\eval_dataset.json"
OUTPUT_PATH = r"C:\Users\HP\Desktop\Chat bot\texeira-chatbot\evaluation\baseline_retrieval_results.json"

with open(DATASET_PATH, "r", encoding="utf-8") as f:
    dataset = json.load(f)

retriever = build_hybrid_retriever(persist_directory="./chroma_hybrid_db")

results = []
for item in dataset:
    qid = item["id"]
    query = item["query"]
    relevant = item.get("relevant_tour_ids", [])
    answerable = item.get("answerable", True)

    applicable = not (not answerable and len(relevant) == 0)

    docs = retriever.invoke(query)
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

    if applicable and relevant:
        relevant_set = set(relevant)
        retrieved_set = set(retrieved_tour_ids)

        # Hit: al menos un tour relevante en top 5
        intersection = relevant_set & retrieved_set
        hit = 1 if intersection else 0

        # Reciprocal Rank: posición del PRIMER documento relevante
        first_relevant_rank = None
        for r in retrieved:
            if r["tour_id"] in relevant_set:
                first_relevant_rank = r["rank"]
                break
        rr = 1.0 / first_relevant_rank if first_relevant_rank else 0.0

        # Recall: tours únicos relevantes recuperados / total relevantes
        recall = len(intersection) / len(relevant_set) if relevant_set else 0.0
    else:
        hit = None
        rr = None
        recall = None

    results.append({
        "id": qid,
        "category": item["category"],
        "language": item["language"],
        "query_style": item.get("query_style", "standard"),
        "query": query,
        "answerable": answerable,
        "relevant_tour_ids": relevant,
        "retrieval_metric_applicable": applicable,
        "retrieved": retrieved,
        "hit_at_5": hit,
        "reciprocal_rank": rr,
        "recall_at_5": recall,
    })

# Global metrics (applicable only)
applicable = [r for r in results if r["retrieval_metric_applicable"]]
n = len(applicable)
hit_sum = sum(r["hit_at_5"] for r in applicable)
mrr_sum = sum(r["reciprocal_rank"] for r in applicable)
recall_sum = sum(r["recall_at_5"] for r in applicable)

global_metrics = {
    "hit_rate_at_5": {"numerator": hit_sum, "denominator": n, "value": round(hit_sum / n, 4) if n else 0},
    "mrr": {"numerator": round(mrr_sum, 4), "denominator": n, "value": round(mrr_sum / n, 4) if n else 0},
    "mean_recall_at_5": {"numerator": round(recall_sum, 4), "denominator": n, "value": round(recall_sum / n, 4) if n else 0},
}

# By category
by_cat = defaultdict(list)
for r in applicable:
    by_cat[r["category"]].append(r)

cat_metrics = {}
for cat, items in sorted(by_cat.items()):
    nn = len(items)
    hh = sum(r["hit_at_5"] for r in items)
    mm = sum(r["reciprocal_rank"] for r in items)
    rr = sum(r["recall_at_5"] for r in items)
    cat_metrics[cat] = {
        "count": nn,
        "hit_rate_at_5": round(hh / nn, 4) if nn else 0,
        "mrr": round(mm / nn, 4) if nn else 0,
        "mean_recall_at_5": round(rr / nn, 4) if nn else 0,
    }

# By language
by_lang = defaultdict(list)
for r in applicable:
    by_lang[r["language"]].append(r)

lang_metrics = {}
for lang, items in sorted(by_lang.items()):
    nn = len(items)
    hh = sum(r["hit_at_5"] for r in items)
    mm = sum(r["reciprocal_rank"] for r in items)
    rr = sum(r["recall_at_5"] for r in items)
    lang_metrics[lang] = {
        "count": nn,
        "hit_rate_at_5": round(hh / nn, 4) if nn else 0,
        "mrr": round(mm / nn, 4) if nn else 0,
        "mean_recall_at_5": round(rr / nn, 4) if nn else 0,
    }

# By query_style
by_style = defaultdict(list)
for r in applicable:
    by_style[r["query_style"]].append(r)

style_metrics = {}
for style, items in sorted(by_style.items()):
    nn = len(items)
    hh = sum(r["hit_at_5"] for r in items)
    mm = sum(r["reciprocal_rank"] for r in items)
    rr = sum(r["recall_at_5"] for r in items)
    style_metrics[style] = {
        "count": nn,
        "hit_rate_at_5": round(hh / nn, 4) if nn else 0,
        "mrr": round(mm / nn, 4) if nn else 0,
        "mean_recall_at_5": round(rr / nn, 4) if nn else 0,
    }

# Errors: hit=0
misses = []
for r in applicable:
    if r["hit_at_5"] == 0:
        misses.append({
            "id": r["id"],
            "query": r["query"],
            "relevant_tour_ids": r["relevant_tour_ids"],
            "top5": [{"rank": x["rank"], "tour_id": x["tour_id"], "chunk_index": x["chunk_index"]} for x in r["retrieved"]],
        })

# Low rank: hit=1 but RR < 0.5 (first relevant at rank 3-5)
low_rank = []
for r in applicable:
    if r["hit_at_5"] == 1 and r["reciprocal_rank"] < 0.5:
        first_rel = None
        for x in r["retrieved"]:
            if x["tour_id"] in set(r["relevant_tour_ids"]):
                first_rel = x["rank"]
                break
        low_rank.append({
            "id": r["id"],
            "query": r["query"],
            "relevant_tour_ids": r["relevant_tour_ids"],
            "first_relevant_rank": first_rel,
            "reciprocal_rank": r["reciprocal_rank"],
        })

output = {
    "config": {
        "retriever": "HybridRetriever",
        "vector_store": "./chroma_hybrid_db",
        "final_k": 5,
        "max_chunks_per_tour": 2,
        "rrf_k": 60,
    },
    "summary": {
        "total_queries": len(dataset),
        "applicable_queries": n,
        "out_of_catalog": len(dataset) - n,
    },
    "global_metrics": global_metrics,
    "metrics_by_category": cat_metrics,
    "metrics_by_language": lang_metrics,
    "metrics_by_query_style": style_metrics,
    "errors_miss": misses,
    "errors_low_rank": low_rank,
    "results": results,
}

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

# Print summary
print(f"Queries ejecutadas: {len(dataset)}")
print(f"Applicable: {n}, Out-of-catalog: {len(dataset) - n}")
print(f"\nGLOBAL:")
print(f"  Hit Rate@5 = {hit_sum}/{n} = {global_metrics['hit_rate_at_5']['value']}")
print(f"  MRR        = {round(mrr_sum,4)}/{n} = {global_metrics['mrr']['value']}")
print(f"  Recall@5   = {round(recall_sum,4)}/{n} = {global_metrics['mean_recall_at_5']['value']}")
print(f"\nBY CATEGORY:")
for cat, m in cat_metrics.items():
    print(f"  {cat:15s} n={m['count']:2d}  Hit={m['hit_rate_at_5']:.4f}  MRR={m['mrr']:.4f}  Recall={m['mean_recall_at_5']:.4f}")
print(f"\nBY LANGUAGE:")
for lang, m in lang_metrics.items():
    print(f"  {lang:5s} n={m['count']:2d}  Hit={m['hit_rate_at_5']:.4f}  MRR={m['mrr']:.4f}  Recall={m['mean_recall_at_5']:.4f}")
print(f"\nBY QUERY_STYLE:")
for style, m in style_metrics.items():
    print(f"  {style:12s} n={m['count']:2d}  Hit={m['hit_rate_at_5']:.4f}  MRR={m['mrr']:.4f}  Recall={m['mean_recall_at_5']:.4f}")
print(f"\nMISS (hit=0): {len(misses)}")
for x in misses:
    print(f"  {x['id']}: {x['query'][:50]}...")
    print(f"    relevant={x['relevant_tour_ids']}")
    print(f"    top5={[t['tour_id'] for t in x['top5']]}")
print(f"\nLOW RANK (hit=1, RR<0.5): {len(low_rank)}")
for x in low_rank:
    print(f"  {x['id']}: rank={x['first_relevant_rank']} RR={x['reciprocal_rank']:.4f} | {x['query'][:50]}...")

# Audit multi-relevant queries
print(f"\nAUDITORÍA MULTI-RELEVANTES (len(relevant_tour_ids) > 1):")
for r in applicable:
    rel = r["relevant_tour_ids"]
    if len(rel) > 1:
        rel_set = set(rel)
        ret_set = set(x["tour_id"] for x in r["retrieved"])
        inter = rel_set & ret_set
        print(f"  {r['id']}: relevant={rel}")
        print(f"    retrieved={[x['tour_id'] for x in r['retrieved']]}")
        print(f"    intersection={sorted(inter)} | recall={len(inter)}/{len(rel_set)}={r['recall_at_5']:.4f}")
