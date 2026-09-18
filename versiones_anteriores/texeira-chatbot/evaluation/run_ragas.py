"""
Evaluación RAGAS — Tesis: Agente Conversacional RAG
Texeira Travel Tour

Este script usa la LIBRERÍA RAGAS (métricas oficiales) sobre la cadena RAG
REAL de producción (app.rag_chain), sin reconstruir un pipeline paralelo.

Métricas RAGAS calculadas:
  - faithfulness: ¿La respuesta es fiel al contexto recuperado? (anti-alucinación)
  - context_precision: ¿Los contextos recuperados son relevantes para la pregunta?

LLM evaluador: DeepSeek (el mismo proveedor del proyecto, vía LangchainLLMWrapper).
Embeddings del evaluador: mismo modelo local de producción
(paraphrase-multilingual-MiniLM-L12-v2), sin costo adicional.

Uso standalone (1 corrida):
  python evaluation/run_ragas.py

Uso programático (múltiples corridas):
  from run_ragas import run_single_evaluation
  results = run_single_evaluation(verbose=True)

No modifica app.py, el system prompt ni la base de datos de producción.
"""

import asyncio
import csv
import inspect
import io
import json
import math
import os
import re
import sys
import time
from pathlib import Path

# Forzar UTF-8 en stdout para Windows (una sola vez)
if not (hasattr(sys.stdout, "encoding") and str(sys.stdout.encoding).lower() == "utf-8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app
from app import rag_chain, FALLBACK_MESSAGE

DATASET_PATH = Path(__file__).resolve().parent / "test_dataset.json"
CSV_PATH = Path(__file__).resolve().parent / "resultados_ragas.csv"

# Pausa entre llamadas al LLM durante la evaluación.
# Si LLM_PROVIDER=groq, se recomienda al menos 2-3 segundos entre llamadas
# para no exceder el límite de 30 req/min del tier gratuito.
EVAL_DELAY_SECONDS = float(os.getenv("EVAL_DELAY_SECONDS", "0"))

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Precios aproximados por proveedor (por millón de tokens, USD).
# Si se usa un proveedor diferente, se estiman con los precios de DeepSeek
# como referencia conservadora (son de los más baratos).
PROVIDER_PRICING = {
    "deepseek": {"input": 0.27, "output": 1.10},
    "openai":   {"input": 0.15, "output": 0.60},   # gpt-4o-mini
    "anthropic": {"input": 0.25, "output": 1.25},   # claude-3-haiku
    "groq":     {"input": 0.05, "output": 0.10},    # qwen/qwen3.8-27b (estimado)
}
_active_provider = os.getenv("LLM_PROVIDER", "deepseek").lower()
_ACTIVE_INPUT_USD = PROVIDER_PRICING.get(_active_provider, PROVIDER_PRICING["deepseek"])["input"]
_ACTIVE_OUTPUT_USD = PROVIDER_PRICING.get(_active_provider, PROVIDER_PRICING["deepseek"])["output"]
# Alias para compatibilidad con run_ragas_multi.py
DEEPSEEK_INPUT_USD_PER_M = _ACTIVE_INPUT_USD
DEEPSEEK_OUTPUT_USD_PER_M = _ACTIVE_OUTPUT_USD

# Contador global de llamadas y tokens (modo: 'rag' o 'judge')
tracker = {
    "rag_calls": 0,
    "judge_calls": 0,
    "input_tokens": 0,
    "output_tokens": 0,
    "mode": "rag",
}


class CountingLLM:
    """Envuelve un LLM de LangChain para contar llamadas y tokens.

    Se usa de dos formas:
      1. Se instala como app.get_llm para que las llamadas INTERNAS de
         rag_chain() queden contadas (modo 'rag').
      2. Se pasa a RAGAS como LLM evaluador (modo 'judge').
    """

    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, item):
        return getattr(self._inner, item)

    def _count_calls(self):
        if tracker["mode"] == "judge":
            tracker["judge_calls"] += 1
        else:
            tracker["rag_calls"] += 1

    def _count_llm_result(self, result, prompts):
        llm_output = getattr(result, "llm_output", None) or {}
        usage = llm_output.get("token_usage") or {}
        if usage.get("prompt_tokens"):
            tracker["input_tokens"] += int(usage["prompt_tokens"])
            tracker["output_tokens"] += int(usage.get("completion_tokens") or 0)
        else:
            est_in = sum(len(str(p.to_string())) for p in prompts) // 4
            est_out = 0
            try:
                for gen_list in result.generations:
                    for g in gen_list:
                        est_out += len(getattr(g, "text", "") or "") // 4
            except Exception:
                pass
            tracker["input_tokens"] += est_in
            tracker["output_tokens"] += est_out
        self._count_calls()

    def _count(self, result, messages):
        usage = getattr(result, "usage_metadata", None)
        if usage and usage.get("input_tokens"):
            tracker["input_tokens"] += int(usage["input_tokens"])
            tracker["output_tokens"] += int(usage.get("output_tokens") or 0)
        else:
            # Estimación de respaldo: ~4 caracteres por token
            try:
                est_in = sum(len(getattr(m, "content", "") or str(m)) for m in messages) // 4
            except TypeError:
                est_in = len(str(messages)) // 4
            est_out = len(getattr(result, "content", "") or "") // 4
            tracker["input_tokens"] += est_in
            tracker["output_tokens"] += est_out
        self._count_calls()

    def invoke(self, messages, *args, **kwargs):
        result = self._inner.invoke(messages, *args, **kwargs)
        self._count(result, messages)
        return result

    async def ainvoke(self, messages, *args, **kwargs):
        result = await self._inner.ainvoke(messages, *args, **kwargs)
        self._count(result, messages)
        return result

    def generate_prompt(self, prompts, *args, **kwargs):
        result = self._inner.generate_prompt(prompts, *args, **kwargs)
        self._count_llm_result(result, prompts)
        return result

    async def agenerate_prompt(self, prompts, *args, **kwargs):
        # RAGAS usa agenerate_prompt() para el juez (vía LangchainLLMWrapper)
        result = await self._inner.agenerate_prompt(prompts, *args, **kwargs)
        self._count_llm_result(result, prompts)
        return result


class BulletAwareSegmenter:
    """Segmentador de oraciones para respuestas con viñetas.

    El segmentador por defecto de RAGAS (pysbd) descarta las oraciones que
    no terminan en punto — y las respuestas de este bot usan viñetas sin
    puntuación final. Este segmentador divide por saltos de línea y
    puntuación, limpia marcadores de viñeta y normaliza el punto final para
    que RAGAS pueda extraer los statements correctamente.
    """

    def segment(self, text):
        parts = re.split(r"\n+|(?<=[.!?])\s+", str(text))
        out = []
        for p in parts:
            s = re.sub(r"^[-*\u2022]\s*", "", p.strip())
            if not s:
                continue
            if not s.endswith((".", "。", "!", "！")):
                s += "."
            out.append(s)
        return out


# ============================================================
# CONEXIÓN CON LA CADENA DE PRODUCCIÓN (monkeypatch controlado)
# ============================================================

_chain_originals = {}


def setup_production_chain():
    """Instala una sola vez los monkeypatches para medir la cadena REAL.

    Retorna (shared_retriever, original_get_llm).
    """
    if "get_retriever" not in _chain_originals:
        _chain_originals["get_retriever"] = app.get_retriever
        _chain_originals["get_llm"] = app.get_llm
        _chain_originals["check_predefined_response"] = app.check_predefined_response

        shared_retriever = app.get_retriever()
        if shared_retriever is None:
            raise RuntimeError("No se pudo cargar el retriever. ¿Está indexada la base vectorial?")

        app.get_retriever = lambda: shared_retriever
        app.get_llm = lambda: CountingLLM(_chain_originals["get_llm"]())
        # Se desactivan las respuestas predefinidas SOLO para la evaluación:
        # así medimos la cadena RAG pura (recuperación + LLM + fallback).
        app.check_predefined_response = lambda *args, **kwargs: None

        _chain_originals["shared_retriever"] = shared_retriever

    return _chain_originals["shared_retriever"], _chain_originals["get_llm"]


def load_dataset(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_expected(item: dict) -> str:
    expected = item.get("expected")
    if expected:
        return expected
    return "fallback" if item.get("scope") == "out_of_scope" else "answer"


# ============================================================
# EVALUACIÓN ÚNICA (reutilizable)
# ============================================================

def run_single_evaluation(verbose: bool = True, dataset_filter: str = None) -> dict:
    """
    Ejecuta UNA evaluación completa del dataset.

    Parámetros:
        verbose: imprime progreso por pregunta.
        dataset_filter: si se indica ('in_scope' / 'out_of_scope'), solo se
            evalúan las preguntas con ese scope.

    Retorna un dict con:
      - rows: resultados por pregunta (question, language, scope, expected,
              answer, contexts, fallback_detected, fallback_correct,
              latency_s, faithfulness, context_precision)
      - summary: promedios agregados
      - cost: {rag_calls, judge_calls, input_tokens, output_tokens} de ESTA corrida
    """
    start_snapshot = dict(tracker)

    if verbose:
        print("\n" + "=" * 72)
        print("CORRIDA DE EVALUACIÓN RAGAS")
        print("Texeira Travel Tour | Cadena real: app.rag_chain()")
        print("=" * 72)

    # 1. Cargar dataset (con filtro opcional por scope)
    dataset = load_dataset(DATASET_PATH)
    if dataset_filter:
        dataset = [d for d in dataset if d.get("scope") == dataset_filter]
    if verbose:
        filtro = f" (filtro: {dataset_filter})" if dataset_filter else ""
        print(f"  Dataset: {len(dataset)} preguntas cargadas{filtro}")

    # 2. Conectar la cadena REAL de producción
    shared_retriever, original_get_llm = setup_production_chain()
    if verbose:
        print("  → Retriever compartido con la cadena real")
        print("  → LLM contador de tokens activo (modo 'rag')")
        print("  → Respuestas predefinidas desactivadas SOLO en la evaluación")

    # 3. Ejecutar rag_chain() real por cada pregunta
    if verbose:
        print("\n  Ejecutando la cadena RAG real para cada pregunta...")
    rows = []
    for i, item in enumerate(dataset):
        q = item["question"]
        expected = _resolve_expected(item)
        tracker["mode"] = "rag"

        if verbose:
            print(f"  [{i+1:02d}/{len(dataset)}] {q[:55]}...", end=" ", flush=True)
        try:
            start = time.time()
            rag_result = rag_chain(q, user_id=f"ragas_eval_{i}")
            latency = time.time() - start

            answer = rag_result["response"]
            contexts = [doc.page_content for doc in shared_retriever.invoke(q)]
            fallback_detected = FALLBACK_MESSAGE in answer
            fallback_correct = (expected == "fallback") == fallback_detected

            rows.append({
                "question": q,
                "language": item.get("language") or "es",
                "scope": item.get("scope") or ("out_of_scope" if expected == "fallback" else "in_scope"),
                "expected": expected,
                "answer": answer,
                "ground_truth": item["ground_truth"],
                "contexts": contexts,
                "fallback_detected": fallback_detected,
                "fallback_correct": fallback_correct,
                "latency_s": round(latency, 2),
                "faithfulness": None,
                "context_precision": None,
            })
            if verbose:
                status = "FALLBACK" if fallback_detected else "OK"
                print(f"→ {status} ({latency:.1f}s)")
        except Exception as e:
            if verbose:
                print(f"→ ERROR: {e}")
            rows.append({
                "question": q,
                "language": item.get("language") or "es",
                "scope": item.get("scope") or ("out_of_scope" if expected == "fallback" else "in_scope"),
                "expected": expected,
                "answer": "ERROR AL EJECUTAR LA CADENA",
                "ground_truth": item["ground_truth"],
                "contexts": [],
                "fallback_detected": False,
                "fallback_correct": False,
                "latency_s": 0.0,
                "faithfulness": None,
                "context_precision": None,
            })

        # Pausa configurable entre llamadas al LLM (crítico para Groq: 30 req/min)
        if EVAL_DELAY_SECONDS > 0:
            time.sleep(EVAL_DELAY_SECONDS)

    # 4. Métricas RAGAS (solo sobre preguntas dentro del alcance)
    in_scope = [r for r in rows if r["expected"] == "answer"]
    if verbose:
        print(f"\n  Calculando métricas RAGAS sobre {len(in_scope)} preguntas en alcance...")

    if in_scope:
        try:
            from datasets import Dataset
            from ragas import evaluate
            from ragas.metrics import context_precision
            from ragas.metrics._faithfulness import Faithfulness
            from ragas.llms import LangchainLLMWrapper
            from ragas.embeddings import LangchainEmbeddingsWrapper
            from langchain_community.embeddings import HuggingFaceEmbeddings

            tracker["mode"] = "judge"
            judge_llm = CountingLLM(original_get_llm())
            judge_embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

            faithfulness_metric = Faithfulness(sentence_segmenter=BulletAwareSegmenter())

            eval_dataset = Dataset.from_dict({
                "question": [r["question"] for r in in_scope],
                "answer": [r["answer"] for r in in_scope],
                "contexts": [r["contexts"] for r in in_scope],
                "ground_truth": [r["ground_truth"] for r in in_scope],
            })

            result = evaluate(
                eval_dataset,
                metrics=[faithfulness_metric, context_precision],
                llm=LangchainLLMWrapper(judge_llm),
                embeddings=LangchainEmbeddingsWrapper(judge_embeddings),
            )
            if inspect.isawaitable(result):
                result = asyncio.run(result)

            df = result.to_pandas()
            for idx, r in enumerate(in_scope):
                f_val = float(df["faithfulness"].iloc[idx])
                cp_val = float(df["context_precision"].iloc[idx])
                r["faithfulness"] = round(f_val, 4) if not math.isnan(f_val) else None
                r["context_precision"] = round(cp_val, 4) if not math.isnan(cp_val) else None
            if verbose:
                print("  → Métricas RAGAS calculadas")
        except Exception as e:
            if verbose:
                print(f"  ✗ Error en RAGAS: {e}")
                print("  (las métricas quedarán vacías)")

    end_snapshot = dict(tracker)
    cost = {k: end_snapshot[k] - start_snapshot[k] for k in start_snapshot if isinstance(start_snapshot[k], int)}

    # Resumen agregado
    def avg(values):
        return sum(values) / len(values) if values else 0.0

    f_values = [r["faithfulness"] for r in in_scope if r["faithfulness"] is not None]
    cp_values = [r["context_precision"] for r in in_scope if r["context_precision"] is not None]
    out_of_scope = [r for r in rows if r["expected"] == "fallback"]
    fb_correct = sum(1 for r in out_of_scope if r["fallback_correct"])

    summary = {
        "total_questions": len(rows),
        "in_scope": len(in_scope),
        "out_of_scope": len(out_of_scope),
        "faithfulness_avg": round(avg(f_values), 4),
        "context_precision_avg": round(avg(cp_values), 4),
        "fallback_accuracy": (fb_correct, len(out_of_scope)),
    }

    return {"rows": rows, "summary": summary, "cost": cost}


# ============================================================
# REPORTE DE UNA CORRIDA (consola + CSV)
# ============================================================

def print_single_report(results: dict):
    rows = results["rows"]
    summary = results["summary"]
    cost = results["cost"]

    # ---- CSV ----
    csv_fields = [
        "pregunta", "idioma", "tipo_esperado", "fallback_detectado",
        "fallback_correcto", "faithfulness", "context_precision",
        "latencia_s", "respuesta_generada", "ground_truth",
    ]
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "pregunta": r["question"],
                "idioma": r["language"],
                "tipo_esperado": r["expected"],
                "fallback_detectado": "Sí" if r["fallback_detected"] else "No",
                "fallback_correcto": "Sí" if r["fallback_correct"] else "No",
                "faithfulness": r["faithfulness"] if r["faithfulness"] is not None else "",
                "context_precision": r["context_precision"] if r["context_precision"] is not None else "",
                "latencia_s": r["latency_s"],
                "respuesta_generada": r["answer"],
                "ground_truth": r["ground_truth"],
            })
    print(f"\n  → CSV guardado en: {CSV_PATH}")

    # ---- Tabla por pregunta ----
    in_scope = [r for r in rows if r["expected"] == "answer"]
    print("\n" + "=" * 72)
    print("TABLA POR PREGUNTA")
    print("=" * 72)
    print(f"{'Pregunta':<46} {'Idioma':<6} {'Faith.':<7} {'CtxPrec':<8} {'FB OK':<6}")
    print("-" * 72)
    for r in rows:
        fb_ok = "—"
        if r["expected"] == "fallback":
            fb_ok = "✓" if r["fallback_correct"] else "✗"
        q_short = r["question"][:45] + ("…" if len(r["question"]) > 45 else "")
        f_val = f"{r['faithfulness']:.2f}" if r["faithfulness"] is not None else "—"
        cp_val = f"{r['context_precision']:.2f}" if r["context_precision"] is not None else "—"
        print(f"{q_short:<46} {r['language']:<6} {f_val:<7} {cp_val:<8} {fb_ok:<6}")

    # ---- Resumen ----
    print("\n" + "=" * 72)
    print("RESUMEN DE MÉTRICAS")
    print("=" * 72)
    print(f"  Preguntas totales:                {summary['total_questions']}")
    print(f"  Dentro del alcance:               {summary['in_scope']}")
    print(f"  Fuera del alcance (fallback):     {summary['out_of_scope']}")
    print()
    print(f"  Faithfulness promedio:            {summary['faithfulness_avg']:.4f}")
    print(f"  Context Precision promedio:       {summary['context_precision_avg']:.4f}")
    fb_c, fb_t = summary["fallback_accuracy"]
    print(f"  Accuracy de fallback:             {fb_c}/{fb_t} "
          f"({(fb_c / fb_t * 100 if fb_t else 0):.1f}%)")

    # Desglose multilingüe
    print("\n  DESGLOSE MULTILINGÜE (faithfulness por idioma):")
    for lang in sorted({r["language"] for r in in_scope}):
        lang_f = [r["faithfulness"] for r in in_scope
                  if r["language"] == lang and r["faithfulness"] is not None]
        if lang_f:
            print(f"    {lang:<4} → {sum(lang_f) / len(lang_f):.4f}  (n={len(lang_f)})")

    # ---- Costo ----
    total_calls = cost.get("rag_calls", 0) + cost.get("judge_calls", 0)
    cost_usd = (
        cost.get("input_tokens", 0) / 1_000_000 * DEEPSEEK_INPUT_USD_PER_M
        + cost.get("output_tokens", 0) / 1_000_000 * DEEPSEEK_OUTPUT_USD_PER_M
    )
    print("\n" + "=" * 72)
    print("CONSUMO DE LLM Y COSTO ESTIMADO (ESTA CORRIDA)")
    print("=" * 72)
    print(f"  Llamadas al LLM (respuestas RAG):  {cost.get('rag_calls', 0)}")
    print(f"  Llamadas al LLM (juez RAGAS):      {cost.get('judge_calls', 0)}")
    print(f"  Total de llamadas:                 {total_calls}")
    print(f"  Tokens de entrada (aprox.):        {cost.get('input_tokens', 0):,}")
    print(f"  Tokens de salida (aprox.):         {cost.get('output_tokens', 0):,}")
    print(f"  Costo estimado ({_active_provider}):          ${cost_usd:.4f} USD")
    print(f"  Resultados por pregunta: {CSV_PATH}")
    print("=" * 72)


def main():
    # Filtro opcional por scope: python run_ragas.py --filter out_of_scope
    dataset_filter = None
    if "--filter" in sys.argv:
        idx = sys.argv.index("--filter")
        if idx + 1 < len(sys.argv):
            dataset_filter = sys.argv[idx + 1]

    results = run_single_evaluation(verbose=True, dataset_filter=dataset_filter)
    print_single_report(results)


if __name__ == "__main__":
    main()
