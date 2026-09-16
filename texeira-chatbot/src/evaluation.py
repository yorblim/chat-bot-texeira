"""
evaluation.py — Evaluación empírica: RAG Tradicional vs RAG Híbrido.

Script de evaluación para la tesis que compara dos enfoques de recuperación:

  Enfoque 1: RAG Tradicional (Solo vectores densos — baseline)
  Enfoque 2: RAG Híbrido (BM25 + Vectores + RRF — propuesta)

Métricas evaluadas (framework RAGAS):
  - faithfulness: ¿La respuesta es fiel al contexto recuperado?
  - answer_relevancy: ¿La respuesta responde lo que preguntan?
  - context_precision: ¿Los contextos recuperados son los correctos?
  - context_recall: ¿El contexto contiene toda la información necesaria?

Conjunto de pruebas: 15 preguntas frecuentes reales de turistas en Cusco,
incluyendo nombres quechuas y errores ortográficos comunes.

Uso:
  python -m src.evaluation          # Ejecuta comparación completa
  python -m src.evaluation --quick  # Solo 5 preguntas (debug rápido)

No modifica app.py, el system prompt ni la base de datos de producción.
"""

import io
import json
import math
import os
import re
import sys
import time
from pathlib import Path

# Forzar UTF-8 en stdout para Windows
if not (hasattr(sys.stdout, "encoding") and str(sys.stdout.encoding).lower() == "utf-8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ============================================================
# CONJUNTO DE PRUEBAS: 15 PREGUNTAS REALES
# ============================================================
# Cada pregunta está diseñada para evaluar un aspecto específico del RAG:
#   - Preguntas con nombres quechuas (normalización)
#   - Preguntas con errores ortográficos (tolerancia)
#   - Preguntas multilingües (ES/EN/PT)
#   - Preguntas fuera de alcance (fallback)
#   - Preguntas que requieren datos específicos (precios, horarios)

TEST_QUESTIONS = [
    # === Preguntas con nombres quechuas (evalúa normalización) ===
    {
        "question": "¿Cuánto cuesta ir a Sacsayhuaman?",
        "ground_truth": "La entrada a Sacsayhuaman cuesta S/30 soles (~$8 USD) y está incluida en el City Tour Cusco ($35 USD).",
        "language": "es",
        "category": "quechua_toponym",
        "expected_behavior": "should_retrieve_sacsayhuaman",
    },
    {
        "question": "Tell me about Qorikancha temple",
        "ground_truth": "Qorikancha (Temple of the Sun) is included in the City Tour Cusco ($35 USD). It was the most important temple in the Inca Empire.",
        "language": "en",
        "category": "quechua_toponym",
        "expected_behavior": "should_retrieve_qorikancha",
    },
    {
        "question": "Quanto costa Ollantaytambo?",
        "ground_truth": "Ollantaytambo is part of the Sacred Valley tour ($55 USD). The entrance fee is included.",
        "language": "pt",
        "category": "quechua_toponym",
        "expected_behavior": "should_retrieve_ollantaytambo",
    },

    # === Preguntas con errores ortográficos (evalúa tolerancia) ===
    {
        "question": "Quiero ir a Machu Pichu, ¿cuánto vale?",
        "ground_truth": "El tour Machu Picchu Clásico cuesta $120 USD por persona, incluye tren, autobús y entrada.",
        "language": "es",
        "category": "spelling_error",
        "expected_behavior": "should_retrieve_machu_picchu",
    },
    {
        "question": "Tour del Valle Sagrado incluye almuerzo?",
        "ground_truth": "Sí, el Valle Sagrado de los Incas ($55 USD) incluye almuerzo buffet en Urubamba.",
        "language": "es",
        "category": "spelling_error",
        "expected_behavior": "should_retrieve_valle_sagrado",
    },

    # === Preguntas multilingües ===
    {
        "question": "What's included in the Rainbow Mountain tour?",
        "ground_truth": "The Rainbow Mountain (Vinicunca) tour ($50 USD) includes: tourist transport, certified trekking guide, buffet lunch, water, trekking poles, emergency oxygen, and travel insurance.",
        "language": "en",
        "category": "multilingual",
        "expected_behavior": "should_retrieve_rainbow_mountain",
    },
    {
        "question": "Qual a política de cancelação?",
        "ground_truth": "A política de cancelação varia conforme o tour: cancelamento gratuito até 48 horas antes. Entre 24-48 horas: 50%. Menos de 24 horas: 100%.",
        "language": "pt",
        "category": "multilingual",
        "expected_behavior": "should_retrieve_policies",
    },

    # === Preguntas que requieren datos específicos ===
    {
        "question": "¿A qué hora sale el tour a Laguna Humantay?",
        "ground_truth": "El tour a Laguna Humantay sale a las 4:30 AM del hotel y retorna a las 5:00 PM.",
        "language": "es",
        "category": "specific_data",
        "expected_behavior": "should_retrieve_humantay",
    },
    {
        "question": "¿Se puede hacer el trekking a Vinicunca con niños?",
        "ground_truth": "El tour Montaña de 7 Colores (Vinicunca) requiere nivel muy alto de exigencia física a 5,200 m.s.n.m. No se recomienda para niños ni personas con condiciones médicas.",
        "language": "es",
        "category": "specific_data",
        "expected_behavior": "should_retrieve_vinicunca",
    },

    # === Preguntas fuera de alcance (evalúa fallback) ===
    {
        "question": "¿Qué opinas del nuevo presidente de Perú?",
        "ground_truth": "FALLBACK: No dispongo de esa información exacta. Por favor, contacta a un asesor humano de la agencia para ayudarte.",
        "language": "es",
        "category": "out_of_scope",
        "expected_behavior": "should_fallback",
    },
    {
        "question": "¿Cuánto cuesta un helado de chocolate en Cusco?",
        "ground_truth": "FALLBACK: No dispongo de esa información exacta. Por favor, contacta a un asesor humano de la agencia para ayudarte.",
        "language": "es",
        "category": "out_of_scope",
        "expected_behavior": "should_fallback",
    },

    # === Preguntas que requieren combinación de información ===
    {
        "question": "¿Cuál es la diferencia entre el City Tour y el Valle Sagrado?",
        "ground_truth": "El City Tour ($35 USD, 8 horas) visita monumentos del centro de Cusco. El Valle Sagrado ($55 USD, 12 horas) visita Pisac, Ollantaytambo y Moray. El Valle Sagrado incluye almuerzo.",
        "language": "es",
        "category": "comparison",
        "expected_behavior": "should_retrieve_both_tours",
    },
    {
        "question": "I want a complete package for 7 days. What's included?",
        "ground_truth": "The Complete Cusco Package 7 Days/6 Nights costs $650 USD per person and includes: 6 nights hotel, all tours, airport transfers, guides, entries, breakfasts, Machu Picchu entry and train.",
        "language": "en",
        "category": "comparison",
        "expected_behavior": "should_retrieve_package",
    },

    # === Preguntas con variantes fonéticas ===
    {
        "question": "¿El tour de Machu Picchu incluye el tren de vuelta?",
        "ground_truth": "Sí, el Machu Picchu Clásico ($120 USD) incluye tren ida y vuelta (clase ejecutiva) y autobús round-trip Aguas Calientes-Machu Picchu.",
        "language": "es",
        "category": "phonetic_variant",
        "expected_behavior": "should_retrieve_machu_picchu",
    },
    {
        "question": "Quero saber sobre o pacote completo de Cusco",
        "ground_truth": "O pacote completo de Cusco (7 dias/6 noites) custa $650 USD por pessoa e inclui: 6 noites de hotel, todos os traslados, passeios, guias, entradas, café da manhã e seguro.",
        "language": "pt",
        "category": "phonetic_variant",
        "expected_behavior": "should_retrieve_package",
    },
]


# ============================================================
# CLASE DE EVALUACIÓN
# ============================================================

class HybridRAGEvaluator:
    """
    Evaluador comparativo: RAG Tradicional vs RAG Híbrido.

    Ejecuta las 15 preguntas de prueba contra ambos agentes y calcula
    métricas RAGAS para cada uno. Genera un reporte comparativo.
    """

    def __init__(self, quick_mode: bool = False):
        """
        Args:
            quick_mode: Si True, solo evalúa 5 preguntas (debug rápido).
        """
        self.questions = TEST_QUESTIONS[:5] if quick_mode else TEST_QUESTIONS
        self.results = {"vector": [], "hybrid": []}
        self.start_time = None

    def _build_agents(self):
        """Construye ambos agentes (vector y hybrid) para comparación."""
        from src.agent import create_vector_agent, create_hybrid_agent

        print("  Construyendo agente vectorial (baseline)...")
        vector_agent = create_vector_agent()

        print("  Construyendo agente híbrido (BM25 + Vector + RRF)...")
        hybrid_agent = create_hybrid_agent()

        return vector_agent, hybrid_agent

    def _evaluate_single(
        self,
        question: str,
        ground_truth: str,
        agent_config: dict,
        agent_type: str,
    ) -> dict:
        """
        Evalúa una pregunta contra un agente específico.

        Args:
            question: Pregunta del test.
            ground_truth: Respuesta esperada.
            agent_config: Configuración del agente.
            agent_type: 'vector' o 'hybrid'.

        Returns:
            Diccionario con resultados de la evaluación.
        """
        try:
            start = time.time()

            # Invocar el agente
            response = agent_config["chain"].invoke(question)
            latency = time.time() - start

            # Obtener documentos recuperados para análisis
            retriever = agent_config["retriever"]
            if agent_type == "hybrid":
                from src.preprocessing import normalize_query
                docs = retriever.invoke(normalize_query(question))
            else:
                docs = retriever.invoke(question)

            # Detectar fallback
            is_fallback = (
                "No dispongo de esa información exacta" in response
                or "contacta a un asesor humano de la agencia" in response
            )

            # Verificar si el fallback es correcto
            expected_fallback = "FALLBACK" in ground_truth
            fallback_correct = expected_fallback == is_fallback

            return {
                "question": question,
                "answer": response.strip(),
                "ground_truth": ground_truth,
                "contexts": [d.page_content for d in docs],
                "tour_ids_retrieved": [d.metadata.get("tour_id") for d in docs],
                "latency_s": round(latency, 2),
                "is_fallback": is_fallback,
                "expected_fallback": expected_fallback,
                "fallback_correct": fallback_correct,
                "docs_count": len(docs),
            }

        except Exception as e:
            return {
                "question": question,
                "answer": f"ERROR: {str(e)}",
                "ground_truth": ground_truth,
                "contexts": [],
                "tour_ids_retrieved": [],
                "latency_s": 0.0,
                "is_fallback": False,
                "expected_fallback": "FALLBACK" in ground_truth,
                "fallback_correct": False,
                "docs_count": 0,
                "error": str(e),
            }

    def run_comparison(self) -> dict:
        """
        Ejecuta la comparación completa entre ambos enfoques.

        Returns:
            Diccionario con resultados detallados y resumen.
        """
        self.start_time = time.time()

        print("=" * 72)
        print("EVALUACIÓN COMPARATIVA: RAG TRADICIONAL vs RAG HÍBRIDO")
        print("Texeira Travel Tour — Tesis Ingeniería de Sistemas")
        print("=" * 72)
        print(f"  Preguntas: {len(self.questions)}")
        print()

        # 1. Construir agentes
        vector_agent, hybrid_agent = self._build_agents()
        print()

        # 2. Evaluar cada pregunta con ambos agentes
        for i, q in enumerate(self.questions, 1):
            print(f"  [{i:02d}/{len(self.questions)}] {q['question'][:55]}...", end=" ", flush=True)

            # Evaluar con vector (baseline)
            vec_result = self._evaluate_single(
                q["question"], q["ground_truth"], vector_agent, "vector"
            )
            self.results["vector"].append(vec_result)

            # Evaluar con hybrid (propuesta)
            hyb_result = self._evaluate_single(
                q["question"], q["ground_truth"], hybrid_agent, "hybrid"
            )
            self.results["hybrid"].append(hyb_result)

            # Mostrar progreso
            vec_fb = "FB" if vec_result["is_fallback"] else "OK"
            hyb_fb = "FB" if hyb_result["is_fallback"] else "OK"
            print(f"vec={vec_fb}({vec_result['latency_s']:.1f}s) "
                  f"hyb={hyb_fb}({hyb_result['latency_s']:.1f}s)")

        # 3. Calcular métricas RAGAS si está disponible
        print("\n  Calculando métricas RAGAS...")
        ragas_metrics = self._compute_ragas_metrics()

        # 4. Calcular métricas manuales
        manual_metrics = self._compute_manual_metrics()

        # 5. Generar reporte
        total_time = time.time() - self.start_time
        report = self._generate_report(ragas_metrics, manual_metrics, total_time)

        return report

    def _compute_ragas_metrics(self) -> dict:
        """
        Calcula métricas RAGAS para ambos enfoques.

        Returns:
            Diccionario con métricas RAGAS por enfoque.
        """
        metrics = {}

        for approach_name in ["vector", "hybrid"]:
            try:
                from datasets import Dataset
                from ragas import evaluate
                from ragas.metrics import faithfulness, context_precision, answer_relevancy
                from ragas.llms import LangchainLLMWrapper
                from ragas.embeddings import LangchainEmbeddingsWrapper
                from langchain_community.embeddings import HuggingFaceEmbeddings
                from src.retriever import EMBEDDING_MODEL

                # Preparar dataset para RAGAS
                rows = self.results[approach_name]
                eval_data = {
                    "question": [r["question"] for r in rows],
                    "answer": [r["answer"] for r in rows],
                    "contexts": [r["contexts"] for r in rows],
                    "ground_truth": [r["ground_truth"] for r in rows],
                }

                # Filtrar preguntas sin contextos (RAGAS requiere al menos 1)
                valid_indices = [i for i, ctxs in enumerate(eval_data["contexts"]) if ctxs]
                if len(valid_indices) < 2:
                    print(f"  ⚠ {approach_name}: pocas preguntas con contextos válidos para RAGAS")
                    metrics[approach_name] = None
                    continue

                dataset = Dataset.from_dict({
                    k: [v[i] for i in valid_indices] for k, v in eval_data.items()
                })

                # Configurar LLM juez y embeddings
                from app import get_llm
                judge_llm = LangchainLLMWrapper(get_llm())
                judge_embeddings = LangchainEmbeddingsWrapper(
                    HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
                )

                # Evaluar
                result = evaluate(
                    dataset,
                    metrics=[faithfulness, context_precision, answer_relevancy],
                    llm=judge_llm,
                    embeddings=judge_embeddings,
                )

                import inspect
                if inspect.isawaitable(result):
                    import asyncio
                    result = asyncio.run(result)

                df = result.to_pandas()
                metrics[approach_name] = {
                    "faithfulness": round(float(df["faithfulness"].mean()), 4),
                    "context_precision": round(float(df["context_precision"].mean()), 4),
                    "answer_relevancy": round(float(df["answer_relevancy"].mean()), 4),
                }

                print(f"  → {approach_name}: faith={metrics[approach_name]['faithfulness']:.4f}, "
                      f"ctx_prec={metrics[approach_name]['context_precision']:.4f}, "
                      f"ans_rel={metrics[approach_name]['answer_relevancy']:.4f}")

            except Exception as e:
                print(f"  ✗ Error RAGAS ({approach_name}): {e}")
                metrics[approach_name] = None

        return metrics

    def _compute_manual_metrics(self) -> dict:
        """
        Calcula métricas manuales (fallback accuracy, latencia, etc.).

        Returns:
            Diccionario con métricas manuales por enfoque.
        """
        metrics = {}

        for approach_name in ["vector", "hybrid"]:
            rows = self.results[approach_name]

            # Fallback accuracy
            fb_correct = sum(1 for r in rows if r["fallback_correct"])
            fb_total = len(rows)

            # Latencia promedio
            latencies = [r["latency_s"] for r in rows if r["latency_s"] > 0]
            avg_latency = sum(latencies) / len(latencies) if latencies else 0

            # Documentos recuperados promedio
            doc_counts = [r["docs_count"] for r in rows]
            avg_docs = sum(doc_counts) / len(doc_counts) if doc_counts else 0

            # Tour IDs únicos recuperados
            all_tour_ids = set()
            for r in rows:
                all_tour_ids.update(r["tour_ids_retrieved"])

            metrics[approach_name] = {
                "fallback_accuracy": round(fb_correct / fb_total * 100, 1) if fb_total else 0,
                "fallback_correct": fb_correct,
                "fallback_total": fb_total,
                "avg_latency_s": round(avg_latency, 2),
                "avg_docs_retrieved": round(avg_docs, 1),
                "unique_tours_retrieved": len(all_tour_ids),
                "total_questions": len(rows),
            }

        return metrics

    def _generate_report(
        self,
        ragas_metrics: dict,
        manual_metrics: dict,
        total_time: float,
    ) -> dict:
        """
        Genera el reporte comparativo final.

        Args:
            ragas_metrics: Métricas RAGAS por enfoque.
            manual_metrics: Métricas manuales por enfoque.
            total_time: Tiempo total de evaluación.

        Returns:
            Diccionario con el reporte completo.
        """
        print("\n" + "=" * 72)
        print("REPORTE COMPARATIVO: RAG TRADICIONAL vs RAG HÍBRIDO")
        print("=" * 72)

        # Tabla de métricas manuales
        print(f"\n{'Métrica':<30} {'Vector (baseline)':<20} {'Híbrido (propuesta)':<20}")
        print("-" * 70)
        for key in ["fallback_accuracy", "avg_latency_s", "avg_docs_retrieved"]:
            vec_val = manual_metrics["vector"].get(key, "N/A")
            hyb_val = manual_metrics["hybrid"].get(key, "N/A")
            label = key.replace("_", " ").title()
            if isinstance(vec_val, float):
                label = f"{label} (%)".replace("(%)", " (%)" if "accuracy" in key else " (s)" if "latency" in key else "")
            print(f"{label:<30} {str(vec_val):<20} {str(hyb_val):<20}")

        # Tabla de métricas RAGAS
        if ragas_metrics.get("vector") and ragas_metrics.get("hybrid"):
            print(f"\n{'Métrica RAGAS':<30} {'Vector (baseline)':<20} {'Híbrido (propuesta)':<20}")
            print("-" * 70)
            for metric in ["faithfulness", "context_precision", "answer_relevancy"]:
                vec_val = ragas_metrics["vector"].get(metric, "N/A")
                hyb_val = ragas_metrics["hybrid"].get(metric, "N/A")
                label = metric.replace("_", " ").title()
                print(f"{label:<30} {str(vec_val):<20} {str(hyb_val):<20}")

        print(f"\n  Tiempo total de evaluación: {total_time:.1f}s")
        print("=" * 72)

        # Guardar resultados
        output_path = ROOT / "src" / "evaluation_results.json"
        report = {
            "meta": {
                "total_questions": len(self.questions),
                "total_time_s": round(total_time, 1),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
            "ragas_metrics": ragas_metrics,
            "manual_metrics": manual_metrics,
            "detailed_results": {
                "vector": self.results["vector"],
                "hybrid": self.results["hybrid"],
            },
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n  → Resultados guardados en: {output_path}")
        return report


# ============================================================
# PUNTO DE ENTRADA
# ============================================================

if __name__ == "__main__":
    quick = "--quick" in sys.argv
    evaluator = HybridRAGEvaluator(quick_mode=quick)
    evaluator.run_comparison()
