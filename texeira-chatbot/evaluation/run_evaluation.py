"""
Evaluación de Calidad RAG — Pipeline ALTERNATIVO (LLM-as-Judge)

NOTA: Este script es un pipeline alternativo de evaluación independiente de
RAGAS. NO es el método de validación principal citado en la tesis.

Para la evaluación oficial, ver:
  - evaluation/run_ragas.py        (1 corrida, métricas RAGAS oficiales)
  - evaluation/run_ragas_multi.py  (3 corridas + estadística + CSV + JSON)

Este script se conserva como referencia y comparación metodológica. Emplea
un enfoque LLM-as-Judge (el propio LLM evalúa calidad de sus respuestas)
con métricas complementarias:
  - faithfulness: ¿La respuesta es fiel al contexto? (anti-alucinación)
  - answer_relevancy: ¿Responde lo que preguntan?
  - context_precision: ¿Los contextos son los correctos?
  - completeness: ¿La respuesta cubre toda la información esperada?

Uso:
  python evaluation/run_evaluation.py
"""

import sys
import os
import json
import time
import io
from pathlib import Path

# Forzar UTF-8 en stdout para Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import get_retriever, get_llm, SYSTEM_PROMPT


def load_ground_truth(path: str = None) -> list[dict]:
    if path is None:
        path = str(Path(__file__).resolve().parent / "ground_truth.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_rag(question: str, retriever, llm) -> dict:
    docs = retriever.invoke(question)
    contexts = [doc.page_content for doc in docs]
    context_str = "\n\n".join(contexts)

    system_msg = SYSTEM_PROMPT.format(
        context=context_str,
        question=question
    )
    messages = [("system", system_msg), ("human", question)]

    result = llm.invoke(messages)
    answer = result.content

    return {
        "question": question,
        "answer": answer,
        "contexts": contexts,
        "context_str": context_str,
    }


def judge_metric(llm, question: str, answer: str, context: str,
                 ground_truth: str, metric: str) -> float:
    """Usa el LLM como juez para evaluar una métrica específica (0-1)."""

    prompts = {
        "faithfulness": """Eres un evaluador de sistemas RAG. Evalúa si la respuesta es FIEL al contexto proporcionado.

CONTEXTO RECUPERADO:
{context}

PREGUNTA: {question}

RESPUESTA GENERADA: {answer}

CRITERIOS:
- La respuesta NO debe inventar información que no esté en el contexto
- La respuesta NO debe contradecir el contexto
- La respuesta debe basarse exclusivamente en la información del contexto
- Si la respuesta dice "no tengo información" cuando SÍ hay información en el contexto, penalizar

Responde SOLO con un número del 0 al 1:
0 = completamente infiel (inventa o contradice)
1 = completamente fiel (todo está en el contexto)

Número:""",

        "answer_relevancy": """Eres un evaluador de sistemas RAG. Evalúa si la respuesta es RELEVANTE para la pregunta.

PREGUNTA: {question}

RESPUESTA GENERADA: {answer}

CRITERIOS:
- ¿La respuesta realmente responde lo que preguntó el usuario?
- ¿Es una respuesta directa o se desvía del tema?
- ¿Aporta información útil relacionada con la pregunta?

Responde SOLO con un número del 0 al 1:
0 = completamente irrelevante
1 = perfectamente relevante

Número:""",

        "context_precision": """Eres un evaluador de sistemas RAG. Evalúa si los contextos recuperados son PRECISOS.

PREGUNTA: {question}

CONTEXTO RECUPERADO:
{context}

RESPUESTA ESPERADA: {ground_truth}

CRITERIOS:
- ¿El contexto recuperado contiene la información necesaria para responder?
- ¿Hay información irrelevante en los contextos recuperados?
- ¿Los contextos son los correctos para esta pregunta?

Responde SOLO con un número del 0 al 1:
0 = contextos completamente incorrectos
1 = contextos perfectamente precisos

Número:""",

        "completeness": """Eres un evaluador de sistemas RAG. Evalúa si la respuesta es COMPLETA comparada con la respuesta esperada.

RESPUESTA GENERADA: {answer}

RESPUESTA ESPERADA: {ground_truth}

CRITERIOS:
- ¿La respuesta cubre todos los puntos importantes de la respuesta esperada?
- ¿Falta información relevante?
- ¿Es una respuesta completa o está truncada?

Responde SOLO con un número del 0 al 1:
0 = información muy incompleta
1 = información completamente completa

Número:""",
    }

    prompt = prompts[metric].format(
        question=question,
        answer=answer,
        context=context,
        ground_truth=ground_truth,
    )

    messages = [("system", "Eres un evaluador preciso. Responde SOLO con un número."), ("human", prompt)]

    try:
        result = llm.invoke(messages)
        text = result.content.strip()
        # Extraer número
        for line in text.split("\n"):
            line = line.strip()
            try:
                score = float(line)
                return max(0.0, min(1.0, score))
            except ValueError:
                continue
        # Intentar extraer de la respuesta completa
        import re
        match = re.search(r'(\d+\.?\d*)', text)
        if match:
            return max(0.0, min(1.0, float(match.group(1))))
        return 0.5  # Default si no se pudo parsear
    except Exception as e:
        print(f"    Error evaluando {metric}: {e}")
        return 0.5


def main():
    print("=" * 60)
    print("EVALUACIÓN DE CALIDAD RAG — LLM-as-Judge")
    print("Tesis: Agente Conversacional RAG")
    print("Texeira Travel Tour")
    print("=" * 60)

    # 1. Cargar ground truth
    print("\n[1/4] Cargando ground truth...")
    ground_truth = load_ground_truth()
    print(f"  → {len(ground_truth)} preguntas cargadas")

    # 2. Inicializar RAG
    print("\n[2/4] Inicializando pipeline RAG...")
    retriever = get_retriever()
    llm = get_llm()
    if retriever is None:
        print("  ✗ No se pudo cargar el retriever.")
        sys.exit(1)
    print("  → Retriever y LLM listos")

    # 3. Ejecutar y evaluar
    print("\n[3/4] Ejecutando evaluación...")
    all_results = []
    metric_sums = {"faithfulness": 0, "answer_relevancy": 0, "context_precision": 0, "completeness": 0}
    metric_counts = {"faithfulness": 0, "answer_relevancy": 0, "context_precision": 0, "completeness": 0}

    for i, item in enumerate(ground_truth):
        q = item["question"]
        gt = item["ground_truth"]
        print(f"\n  [{i+1}/{len(ground_truth)}] {q[:70]}...")

        try:
            start = time.time()
            rag_result = run_rag(q, retriever, llm)
            latency = time.time() - start

            # Detectar fallback
            fallback_msg = "no dispongo de esa información exacta"
            is_fallback = fallback_msg in rag_result["answer"].lower()

            if is_fallback:
                print(f"    → FALLBACK ({latency:.1f}s) — saltando evaluación de métricas")
                scores = {m: 0.0 for m in metric_sums}
            else:
                print(f"    → OK ({latency:.1f}s) — evaluando métricas...", end=" ")
                scores = {}
                for metric in metric_sums:
                    score = judge_metric(
                        llm, q, rag_result["answer"],
                        rag_result["context_str"], gt, metric
                    )
                    scores[metric] = score
                    metric_sums[metric] += score
                    metric_counts[metric] += 1
                    print(f"{metric[:4]}={score:.2f}", end=" ")
                print()

            all_results.append({
                "question": q,
                "answer": rag_result["answer"][:300],
                "ground_truth": gt[:300],
                "latency_s": round(latency, 2),
                "is_fallback": is_fallback,
                "num_contexts": len(rag_result["contexts"]),
                "scores": scores,
            })

        except Exception as e:
            print(f"    → ERROR: {e}")
            all_results.append({
                "question": q,
                "answer": "ERROR",
                "ground_truth": gt[:300],
                "latency_s": 0,
                "is_fallback": True,
                "num_contexts": 0,
                "scores": {m: 0.0 for m in metric_sums},
            })

    # 4. Calcular promedios
    print("\n[4/4] Calculando métricas finales...")
    avg_metrics = {}
    for metric in metric_sums:
        if metric_counts[metric] > 0:
            avg_metrics[metric] = round(metric_sums[metric] / metric_counts[metric], 4)
        else:
            avg_metrics[metric] = 0.0

    # Guardar resultados
    output = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_questions": len(ground_truth),
        "questions_with_llm_response": len(ground_truth) - sum(1 for r in all_results if r["is_fallback"]),
        "avg_metrics": avg_metrics,
        "avg_latency_s": round(sum(r["latency_s"] for r in all_results) / len(all_results), 2),
        "details": all_results,
    }

    output_path = str(Path(__file__).resolve().parent / "evaluation_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Resumen
    print("\n" + "=" * 60)
    print("RESULTADOS DE EVALUACIÓN")
    print("=" * 60)
    print(f"  Preguntas totales:           {len(ground_truth)}")
    print(f"  Respuestas con LLM:          {output['questions_with_llm_response']}")
    print(f"  Latencia promedio:           {output['avg_latency_s']}s")
    print()
    print("  MÉTRICAS DE CALIDAD:")
    print(f"    Faithfulness:    {avg_metrics['faithfulness']:.4f}  ", end="")
    if avg_metrics['faithfulness'] >= 0.7:
        print("✓ BUENO (anti-alucinación efectivo)")
    elif avg_metrics['faithfulness'] >= 0.5:
        print("⚠ MODERADO")
    else:
        print("✗ BAJO (revisar)")

    print(f"    Relevancy:       {avg_metrics['answer_relevancy']:.4f}  ", end="")
    if avg_metrics['answer_relevancy'] >= 0.7:
        print("✓ BUENO")
    else:
        print("⚠ MODERADO/BAJO")

    print(f"    Context Precision:{avg_metrics['context_precision']:.4f}  ", end="")
    if avg_metrics['context_precision'] >= 0.7:
        print("✓ BUENO")
    else:
        print("⚠ MODERADO/BAJO")

    print(f"    Completeness:    {avg_metrics['completeness']:.4f}  ", end="")
    if avg_metrics['completeness'] >= 0.7:
        print("✓ BUENO")
    else:
        print("⚠ MODERADO/BAJO")

    print(f"\n  Resultados guardados en: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
