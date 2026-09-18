"""
inspect_case.py — Diagnóstico puntual de un caso de la evaluación RAGAS.

Uso: python evaluation/inspect_case.py

Toma UNA pregunta del test_dataset.json (filtro configurable en QUERY_FILTER),
ejecuta la cadena RAG real (app.rag_chain) exactamente como run_ragas.py e
imprime, sin truncar:
  1. Pregunta exacta y ground_truth
  2. Contexto completo recuperado por el retriever (con scan de palabras
     relacionadas a mascotas/animales para detectar contexto contaminante)
  3. PROMPT COMPLETO enviado al LLM (capturado en la frontera del LLM,
     tal cual lo recibió — no una reconstrucción)
  4. Respuesta completa generada
  5. La misma pregunta ejecutada N_REPEATS veces adicionales (respuestas
     completas) para confirmar si el comportamiento es estable
  6. Preguntas de control equivalentes en español e inglés (CONTROL_QUESTIONS)
  7. Métrica faithfulness de RAGAS con desglose de claims (si ragas lo expone)

No modifica app.py, el system prompt ni la base de datos de producción.
"""

import asyncio
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app
from app import rag_chain, FALLBACK_MESSAGE

# Reutiliza la configuración de run_ragas.py (LLM contador y segmentador)
from run_ragas import CountingLLM, BulletAwareSegmenter, tracker

DATASET_PATH = Path(__file__).resolve().parent / "test_dataset.json"
QUERY_FILTER = "animal de estimação"

# Preguntas de control equivalentes en otros idiomas (mismo tema)
CONTROL_QUESTIONS = [
    ("es", "¿Puedo llevar a mi mascota en el tour?"),
    ("en", "Can I bring my pet on the tour?"),
]

# Repeticiones adicionales de la pregunta principal
N_REPEATS = 3

# Palabras clave para detectar contexto relacionado a mascotas/animales
PET_KEYWORDS = ["mascot", "pet", "animal", "perro", "gato", "can", "dog", "cat"]


# Captura el prompt EXACTO que la cadena le pasa al LLM
captured_prompts = []


class PromptCaptureLLM:
    """Envuelve el LLM y registra los mensajes exactos que recibe invoke()."""

    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, item):
        return getattr(self._inner, item)

    def invoke(self, messages, *args, **kwargs):
        captured_prompts.append(list(messages))
        return self._inner.invoke(messages, *args, **kwargs)


def load_dataset(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def sep(title: str):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def run_case(question: str, tag: str) -> tuple[str, list[str], bool]:
    """Ejecuta rag_chain() y retorna (respuesta, contexts, es_fallback)."""
    captured_prompts.clear()
    tracker["mode"] = "rag"
    rag_result = rag_chain(question, user_id=f"inspect_{tag}_{len(captured_prompts)}_{id(question)}")
    contexts = [doc.page_content for doc in _shared_retriever.invoke(question)]
    answer = rag_result["response"]
    return answer, contexts, FALLBACK_MESSAGE in answer


async def faithfulness_breakdown(metric, wrapped_llm, question, answer, contexts):
    """Ejecuta faithfulness sobre un caso e imprime el desglose interno."""
    if hasattr(metric, "set_llm"):
        metric.set_llm(wrapped_llm)
    else:
        metric.llm = wrapped_llm

    row = {
        "user_input": question,
        "response": answer,
        "retrieved_contexts": contexts,
    }

    statements_simplified = await metric._create_statements(row, None)
    all_statements = []
    for comp in statements_simplified.sentences:
        for stmt in comp.simpler_statements:
            all_statements.append(stmt)

    sep("CLAIMS EXTRAÍDOS DE LA RESPUESTA (statements)")
    if not all_statements:
        print("  ⚠ RAGAS no extrajo ningún claim de esta respuesta.")
    for i, s in enumerate(all_statements, 1):
        print(f"  [{i:02d}] {s}")

    verdicts = await metric._create_verdicts(row, all_statements, None)

    sep("VEREDICTO DE CADA CLAIM CONTRA EL CONTEXTO RECUPERADO")
    for v in verdicts.statements:
        mark = "FIEL ✓" if v.verdict == 1 else "INFIEL ✗"
        print(f"  {mark} | {v.statement}")
        print(f"         Razón: {v.reason}")
        print()

    score = metric._compute_score(verdicts)
    sep("SCORE FAITHFULNESS (RAGAS) PARA ESTE CASO")
    print(f"  {score}")
    return score


_shared_retriever = None


def main():
    global _shared_retriever

    dataset = load_dataset(DATASET_PATH)
    case = next((c for c in dataset if QUERY_FILTER.lower() in c["question"].lower()), None)
    if case is None:
        print(f"  ✗ No se encontró ninguna pregunta con '{QUERY_FILTER}' en {DATASET_PATH.name}")
        sys.exit(1)

    question = case["question"]
    ground_truth = case["ground_truth"]

    sep("DATASET")
    print(f"  scope del dataset: {case.get('scope')} | expected: {case.get('expected')}")
    sep("1) PREGUNTA EXACTA (del test_dataset.json)")
    print(f"  {question}")

    sep("2) GROUND_TRUTH (del test_dataset.json)")
    print(f"  {ground_truth}")

    # ---- Conectar la cadena REAL (igual que run_ragas.py) + captura de prompt ----
    original_get_retriever = app.get_retriever
    original_get_llm = app.get_llm

    _shared_retriever = original_get_retriever()
    app.get_retriever = lambda: _shared_retriever
    app.get_llm = lambda: PromptCaptureLLM(original_get_llm())
    # Igual que run_ragas.py: sin atajos predefinidos, se mide la cadena RAG pura
    app.check_predefined_response = lambda *args, **kwargs: None

    # ---- Ejecución principal ----
    answer, contexts, is_fallback = run_case(question, "principal")

    sep("3) CONTEXTO COMPLETO RECUPERADO POR EL RETRIEVER")
    print(f"  (chunks entregados a la cadena: {len(contexts)})")
    for i, ctx in enumerate(contexts, 1):
        print(f"\n  --- CHUNK {i} ---")
        print(ctx)

    # Scan de palabras relacionadas a mascotas en el contexto recuperado
    print("\n  --- SCAN DE PALABRAS RELACIONADAS A MASCOTAS/ANIMALES ---")
    found_any = False
    for i, ctx in enumerate(contexts, 1):
        lower = ctx.lower()
        hits = [kw for kw in PET_KEYWORDS if kw in lower]
        if hits:
            found_any = True
            print(f"    Chunk {i}: CONTIENE {hits}")
    if not found_any:
        print("    NINGÚN chunk contiene palabras de mascotas/animales.")
        print("    → El retriever NO trajo contexto relacionado: si el LLM")
        print("      responde algo distinto al fallback, está violando la")
        print("      REGLA ABSOLUTA #1 del system prompt.")

    sep("4) PROMPT COMPLETO ENVIADO AL LLM (capturado en la frontera del LLM)")
    if not captured_prompts:
        print("  ⚠ No se capturó ningún prompt (¿la cadena no llamó al LLM?)")
    for messages in captured_prompts:
        for m in messages:
            role, content = m[0], m[1]
            print(f"\n  ---- [ROL: {role}] ----")
            print(content)

    sep("5) RESPUESTA COMPLETA GENERADA (ejecución principal)")
    print(answer)
    print()
    print(f"  → ¿Es el fallback literal? {'SÍ ✓' if is_fallback else 'NO ✗ (no disparó el fallback)'}")

    # ---- Repeticiones manuales de la misma pregunta ----
    sep(f"6) {N_REPEATS} EJECUCIONES ADICIONALES DE LA MISMA PREGUNTA")
    for k in range(1, N_REPEATS + 1):
        ans_k, _, fb_k = run_case(question, f"rep{k}")
        print(f"\n  --- EJECUCIÓN ADICIONAL {k}/{N_REPEATS} ---")
        print(ans_k)
        print(f"  → ¿Fallback? {'SÍ ✓' if fb_k else 'NO ✗'}")

    # ---- Controles en español e inglés ----
    sep("7) PREGUNTAS DE CONTROL EQUIVALENTES (es / en)")
    for lang, ctrl_q in CONTROL_QUESTIONS:
        ctrl_ans, ctrl_ctx, ctrl_fb = run_case(ctrl_q, f"ctrl_{lang}")
        print(f"\n  --- CONTROL [{lang}] {ctrl_q} ---")
        print(ctrl_ans)
        print(f"  → ¿Fallback? {'SÍ ✓' if ctrl_fb else 'NO ✗'}")
        # mini-scan de contexto del control
        ctrl_hits = False
        for ctx in ctrl_ctx:
            if any(kw in ctx.lower() for kw in PET_KEYWORDS):
                ctrl_hits = True
        print(f"  → ¿El retriever trajo contexto con palabras mascota/animal? {'SÍ' if ctrl_hits else 'No'}")

    # ---- Faithfulness puntual con desglose (sobre la ejecución principal) ----
    tracker["mode"] = "judge"
    judge_llm = CountingLLM(original_get_llm())

    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics._faithfulness import Faithfulness

    metric = Faithfulness(sentence_segmenter=BulletAwareSegmenter())
    wrapped_llm = LangchainLLMWrapper(judge_llm)

    try:
        score = asyncio.run(
            faithfulness_breakdown(metric, wrapped_llm, question, answer, contexts)
        )
    except Exception as e:
        print(f"\n  ✗ No se pudo acceder al desglose interno de ragas: {type(e).__name__}: {e}")
        from datasets import Dataset
        from ragas import evaluate

        single = Dataset.from_dict({
            "question": [question],
            "answer": [answer],
            "contexts": [contexts],
        })
        result = evaluate(single, metrics=[metric], llm=wrapped_llm)
        if asyncio.iscoroutine(result):
            result = asyncio.run(result)
        score = result.to_pandas()["faithfulness"].iloc[0]
        sep("SCORE FAITHFULNESS (RAGAS) — SIN DESGLOSE")
        print(f"  {score}")

    sep("RESUMEN DEL DIAGNÓSTICO")
    print(f"  Pregunta: {question}")
    print(f"  ¿Fallback en ejecución principal? {'SÍ' if is_fallback else 'NO'}")
    print(f"  Faithfulness (RAGAS): {score}")
    print("  Evidencia arriba: contexto (sec. 3 + scan), prompt exacto (sec. 4),")
    print("  estabilidad (sec. 6) y controles es/en (sec. 7).")


if __name__ == "__main__":
    main()
