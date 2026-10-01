"""
test_live_llm_evaluation.py — Evaluación sintética real y controlada del LLM (Groq / Qwen 3.8-27B).

Protocolo de ejecución:
1. Máximo cuatro llamadas reales al LLM Groq (qwen/qwen3.8-27b), más el turno preparatorio determinista.
2. Sin servicios de pago alternativos ni cambios de proveedor.
3. Instrumentación completa: captura respuestas íntegras, documentos efectivos de ChromaDB,
   prompt estructurado, latencia en segundos, consumo reportado (token_usage) y posibles errores.
4. Evaluación semántica rigurosa contra las fuentes oficiales de Texeira Travel (F1/F2/F3/catálogo).
5. Detención inmediata ante cualquier error de cuota o rate limit (HTTP 429).
6. Sin mensajes por WhatsApp, sin merge a main, sin despliegue a producción.
"""

import os
import sys
import time
import json
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Asegurar configuración de runtime antes de importar app
import runtime_settings
runtime_settings.configure()

os.environ["TEXEIRA_ENABLE_WHATSAPP"] = "false"
os.environ["TEXEIRA_ENABLE_MESSENGER"] = "false"

import app
import catalog_service


class RealLlmAuditor:
    """Wrapper espía sobre la instancia real del LLM para auditar latencia, uso y respuestas."""
    def __init__(self, real_llm):
        self.real_llm = real_llm
        self.call_count = 0
        self.records = []

    def invoke(self, messages, **kwargs):
        self.call_count += 1
        if self.call_count > 4:
            raise RuntimeError(f"Límite estricto excedido: máximo 4 llamadas reales al LLM (intento {self.call_count})")

        t0 = time.time()
        error_info = None
        resp = None
        try:
            resp = self.real_llm.invoke(messages, **kwargs)
        except Exception as e:
            latency = time.time() - t0
            error_info = {
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
            self.records.append({
                "call_index": self.call_count,
                "latency_seconds": round(latency, 3),
                "messages_count": len(messages),
                "last_human_message": messages[-1][1] if messages else "",
                "error": error_info,
                "success": False
            })
            raise e

        latency = time.time() - t0
        meta = getattr(resp, "response_metadata", {})
        token_usage = meta.get("token_usage") or getattr(resp, "usage_metadata", {}) or {}

        record = {
            "call_index": self.call_count,
            "latency_seconds": round(latency, 3),
            "messages_count": len(messages),
            "last_human_message": messages[-1][1] if messages else "",
            "raw_response": resp.content,
            "model_name": meta.get("model_name", os.getenv("LLM_MODEL", "qwen/qwen3.8-27b")),
            "finish_reason": meta.get("finish_reason", "stop"),
            "token_usage": token_usage,
            "prompt_tokens": token_usage.get("prompt_tokens"),
            "completion_tokens": token_usage.get("completion_tokens"),
            "total_tokens": token_usage.get("total_tokens"),
            "error": None,
            "success": True
        }
        self.records.append(record)
        return resp


class RealRetrieverAuditor:
    """Wrapper espía sobre el retriever híbrido real para auditar consultas y chunks."""
    def __init__(self, real_retriever):
        self.real_retriever = real_retriever
        self.invocations = []

    def invoke(self, query):
        docs = self.real_retriever.invoke(query) if self.real_retriever else []
        self.invocations.append({
            "query": query,
            "docs_count": len(docs),
            "docs": [
                {
                    "tour_id": d.metadata.get("tour_id", ""),
                    "tour_name": d.metadata.get("tour_name", ""),
                    "source": d.metadata.get("source", ""),
                    "content_snippet": d.page_content[:200].replace("\n", " ")
                }
                for d in docs
            ]
        })
        return docs


def safe_print(text):
    try:
        print(text)
    except Exception:
        try:
            print(str(text).encode("ascii", "backslashreplace").decode("ascii"))
        except Exception:
            pass


def run_live_llm_evaluation():
    safe_print("=" * 70)
    safe_print("  EVALUACIÓN REAL DEL LLM: GROQ (qwen/qwen3.8-27b)")
    safe_print("=" * 70)

    # 1. Verificar configuración efectiva
    provider = os.getenv("LLM_PROVIDER")
    model = os.getenv("LLM_MODEL")
    api_key = os.getenv("GROQ_API_KEY")

    safe_print(f"Proveedor configurado: {provider}")
    safe_print(f"Modelo configurado:    {model}")
    safe_print(f"GROQ_API_KEY presente: {'Sí' if api_key else 'NO'}")

    if not api_key:
        safe_print("[ERROR FATAL] GROQ_API_KEY no encontrada en las variables de entorno.")
        sys.exit(1)

    # Inicializar catálogo y retriever real
    catalog_service.init_catalog_db()
    real_retriever = app.get_retriever()
    if not real_retriever:
        safe_print("[ERROR FATAL] No se pudo inicializar el retriever híbrido.")
        sys.exit(1)

    real_llm = app.get_llm()
    llm_auditor = RealLlmAuditor(real_llm)
    retriever_auditor = RealRetrieverAuditor(real_retriever)

    # Reemplazar componentes con wrappers de auditoría (conservando la llamada real)
    app.get_llm = lambda: llm_auditor
    app.get_retriever = lambda: retriever_auditor

    eval_results = []

    try:
        # -------------------------------------------------------------
        # CASO 1: Inka Jungle — Pregunta abierta de aventura
        # -------------------------------------------------------------
        safe_print("\n--- [Llamada 1/4] Inka Jungle: Descenso en bicicleta y aventura ---")
        q1 = "¿Cómo es el descenso en bicicleta por el Abra Málaga y qué actividades de aventura se hacen en el Inka Jungle?"
        u1 = "eval_real_user_open"
        app.clear_history(u1)

        t_start = time.time()
        res1 = app.rag_chain(q1, user_id=u1)
        dur1 = time.time() - t_start

        last_llm_rec = llm_auditor.records[-1] if llm_auditor.records else {}
        last_ret_rec = retriever_auditor.invocations[-1] if retriever_auditor.invocations else {}

        eval_results.append({
            "case_id": "1_inka_jungle_open",
            "name": "Inka Jungle (Pregunta abierta de aventura)",
            "query": q1,
            "route": res1.get("response_route"),
            "llm_response": res1.get("response"),
            "latency_seconds": last_llm_rec.get("latency_seconds", round(dur1, 3)),
            "token_usage": last_llm_rec.get("token_usage", {}),
            "retriever_query": last_ret_rec.get("query"),
            "retrieved_docs": last_ret_rec.get("docs", []),
            "evaluation_criteria": {
                "cites_abra_malaga": "abra málaga" in res1.get("response", "").lower() or "abra malaga" in res1.get("response", "").lower() or "4350" in res1.get("response", "") or "4,350" in res1.get("response", ""),
                "cites_bici_cycling": "bicicleta" in res1.get("response", "").lower() or "bici" in res1.get("response", "").lower(),
                "avoids_undocumented_activities": "canotaje" not in res1.get("response", "").lower() and "tirolina" not in res1.get("response", "").lower() and "rafting" not in res1.get("response", "").lower(),
                "mentions_confirmation_needed": any(term in res1.get("response", "").lower() for term in ["asesor", "confirmar", "confirmación", "equipo", "consultar"]),
                "avoids_hallucinations": "vuelo" not in res1.get("response", "").lower() and "helicóptero" not in res1.get("response", "").lower(),
            }
        })
        safe_print(f"Ruta: {res1.get('response_route')} | Latencia: {last_llm_rec.get('latency_seconds')}s")
        safe_print(f"Tokens: {last_llm_rec.get('token_usage')}")
        safe_print(f"Respuesta (primeros 180 chars): {res1.get('response', '')[:180]}...")

        # -------------------------------------------------------------
        # PREPARACIÓN CASO 2: Turno 0 determinista (Humantay)
        # -------------------------------------------------------------
        safe_print("\n--- [Preparación Determinista] Turno 0: Consulta inicial de Humantay ---")
        u_conv = "eval_real_user_context"
        app.clear_history(u_conv)
        q0 = "¿Tienen información de la Laguna Humantay?"
        res0 = app.rag_chain(q0, user_id=u_conv)
        safe_print(f"Ruta determinista: {res0.get('response_route')} (LLM calls hasta ahora: {llm_auditor.call_count})")

        # -------------------------------------------------------------
        # CASO 2: Laguna Humantay — Seguimiento elíptico contextual
        # -------------------------------------------------------------
        safe_print("\n--- [Llamada 2/4] Laguna Humantay: Seguimiento elíptico (altitud y subida) ---")
        q2 = "¿A qué altura máxima sobre el nivel del mar se encuentra y qué tan exigente es la subida a pie?"
        
        t_start = time.time()
        res2 = app.rag_chain(q2, user_id=u_conv)
        dur2 = time.time() - t_start

        last_llm_rec2 = llm_auditor.records[-1] if llm_auditor.records else {}
        last_ret_rec2 = retriever_auditor.invocations[-1] if retriever_auditor.invocations else {}

        eval_results.append({
            "case_id": "2_humantay_contextual_followup",
            "name": "Laguna Humantay (Seguimiento elíptico contextual)",
            "query": q2,
            "route": res2.get("response_route"),
            "llm_response": res2.get("response"),
            "latency_seconds": last_llm_rec2.get("latency_seconds", round(dur2, 3)),
            "token_usage": last_llm_rec2.get("token_usage", {}),
            "retriever_query": last_ret_rec2.get("query"),
            "retrieved_docs": last_ret_rec2.get("docs", []),
            "evaluation_criteria": {
                "retains_original_question": last_llm_rec2.get("last_human_message") == q2,
                "retrieved_humantay_doc": any(d.get("tour_id") == "laguna-humantay" for d in last_ret_rec2.get("docs", [])),
                "cites_altitude_4200": "4200" in res2.get("response", "") or "4,200" in res2.get("response", "") or "4.200" in res2.get("response", ""),
                "clarifies_hike_confirmation": any(term in res2.get("response", "").lower() for term in ["confirmar", "confirmación", "asesor", "consultar", "equipo"]),
                "avoids_full_refusal": "no dispongo de esa información exacta" not in res2.get("response", "").lower(),
                "identifies_humantay": "humantay" in res2.get("response", "").lower(),
            }
        })
        safe_print(f"Ruta: {res2.get('response_route')} | Latencia: {last_llm_rec2.get('latency_seconds')}s")
        safe_print(f"Retriever Query: '{last_ret_rec2.get('query')}'")
        safe_print(f"Respuesta (primeros 180 chars): {res2.get('response', '')[:180]}...")

        # -------------------------------------------------------------
        # CASO 3: Cambio de tour (Switch Tour hacia City Tour Cusco)
        # -------------------------------------------------------------
        safe_print("\n--- [Llamada 3/4] Cambio de Tour: City Tour Cusco (mismo usuario de Humantay) ---")
        q3 = "¿Cómo es el recorrido y qué lugares se visitan en el City Tour Cusco?"

        t_start = time.time()
        res3 = app.rag_chain(q3, user_id=u_conv)
        dur3 = time.time() - t_start

        last_llm_rec3 = llm_auditor.records[-1] if llm_auditor.records else {}
        last_ret_rec3 = retriever_auditor.invocations[-1] if retriever_auditor.invocations else {}

        eval_results.append({
            "case_id": "3_switch_to_city_tour",
            "name": "Cambio de tour tras Humantay (City Tour Cusco)",
            "query": q3,
            "route": res3.get("response_route"),
            "llm_response": res3.get("response"),
            "latency_seconds": last_llm_rec3.get("latency_seconds", round(dur3, 3)),
            "token_usage": last_llm_rec3.get("token_usage", {}),
            "retriever_query": last_ret_rec3.get("query"),
            "retrieved_docs": last_ret_rec3.get("docs", []),
            "evaluation_criteria": {
                "retains_original_question": last_llm_rec3.get("last_human_message") == q3,
                "retrieved_city_tour_doc": any(d.get("tour_id") == "city-tour-cusco" for d in last_ret_rec3.get("docs", [])),
                "retriever_query_without_humantay": "humantay" not in last_ret_rec3.get("query", "").lower(),
                "cites_key_sites": any(site in res3.get("response", "").lower() for site in ["qorikancha", "coricancha", "catedral", "sacsayhuamán", "sacsayhuaman"]),
                "avoids_humantay_contamination": "humantay" not in res3.get("response", "").lower(),
            }
        })
        safe_print(f"Ruta: {res3.get('response_route')} | Latencia: {last_llm_rec3.get('latency_seconds')}s")
        safe_print(f"Retriever Query: '{last_ret_rec3.get('query')}'")
        safe_print(f"Respuesta (primeros 180 chars): {res3.get('response', '')[:180]}...")

        # -------------------------------------------------------------
        # CASO 4: Comparación entre Camino Inca Clásico y Salkantay Trek
        # -------------------------------------------------------------
        safe_print("\n--- [Llamada 4/4] Comparación: Camino Inca Clásico vs Salkantay Trek ---")
        q4 = "¿Qué diferencias hay entre el Camino Inca Clásico y el Salkantay Trek en duración y precio?"
        u4 = "eval_real_user_comp"
        app.clear_history(u4)

        t_start = time.time()
        res4 = app.rag_chain(q4, user_id=u4)
        dur4 = time.time() - t_start

        last_llm_rec4 = llm_auditor.records[-1] if llm_auditor.records else {}
        last_ret_rec4 = retriever_auditor.invocations[-1] if retriever_auditor.invocations else {}

        eval_results.append({
            "case_id": "4_comparison_camino_vs_salkantay",
            "name": "Comparación entre dos tours (Camino Inca vs Salkantay)",
            "query": q4,
            "route": res4.get("response_route"),
            "llm_response": res4.get("response"),
            "latency_seconds": last_llm_rec4.get("latency_seconds", round(dur4, 3)),
            "token_usage": last_llm_rec4.get("token_usage", {}),
            "retriever_query": last_ret_rec4.get("query"),
            "retrieved_docs": last_ret_rec4.get("docs", []),
            "evaluation_criteria": {
                "retains_original_question": last_llm_rec4.get("last_human_message") == q4,
                "retrieved_camino_doc": any(d.get("tour_id") == "camino-inka" for d in last_ret_rec4.get("docs", [])),
                "retrieved_salkantay_doc": any(d.get("tour_id") == "salkantay-trek" for d in last_ret_rec4.get("docs", [])),
                "cites_camino_official_price": "790" in res4.get("response", ""),
                "cites_duration_comparison": "4 d" in res4.get("response", "").lower() or "4 días" in res4.get("response", "").lower() or "4 dias" in res4.get("response", "").lower(),
                "avoids_inventing_salkantay_price": "790 usd" not in res4.get("response", "").lower() or "asesor" in res4.get("response", "").lower() or "consultar" in res4.get("response", "").lower() or "confirmar" in res4.get("response", "").lower(),
            }
        })
        safe_print(f"Ruta: {res4.get('response_route')} | Latencia: {last_llm_rec4.get('latency_seconds')}s")
        safe_print(f"Respuesta (primeros 180 chars): {res4.get('response', '')[:180]}...")

    except Exception as exc:
        safe_print(f"\n[ERROR EN EVALUACIÓN REAL] {type(exc).__name__}: {exc}")
        # Registrar fallo y detener
        out_error = {
            "status": "FAILED_DUE_TO_ERROR",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "completed_calls": llm_auditor.call_count,
            "partial_results": eval_results
        }
        err_path = app._trial_root / "docs" / "EVIDENCIA_EVALUACION_REAL_LLM_20260930.json"
        with open(err_path, "w", encoding="utf-8") as f:
            json.dump(out_error, f, indent=2, ensure_ascii=False)
        safe_print(f"Detención inmediata. Reporte parcial guardado en: {err_path}")
        sys.exit(1)

    safe_print("\n" + "=" * 70)
    safe_print(f"  EVALUACIÓN REAL COMPLETADA EXITOSAMENTE: {llm_auditor.call_count}/4 LLAMADAS")
    safe_print("=" * 70)

    # Guardar reporte JSON completo
    report_data = {
        "metadata": {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "llm_provider": provider,
            "llm_model": model,
            "total_real_llm_calls": llm_auditor.call_count,
            "total_prompt_tokens": sum(r.get("prompt_tokens") or 0 for r in llm_auditor.records),
            "total_completion_tokens": sum(r.get("completion_tokens") or 0 for r in llm_auditor.records),
            "total_tokens": sum(r.get("total_tokens") or 0 for r in llm_auditor.records),
            "average_latency_seconds": round(sum(r.get("latency_seconds", 0) for r in llm_auditor.records) / len(llm_auditor.records), 3) if llm_auditor.records else 0,
        },
        "cases": eval_results
    }

    out_json = app._trial_root / "docs" / "EVIDENCIA_EVALUACION_REAL_LLM_20260930.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    safe_print(f"[REPORTE JSON] Evidencia guardada en: {out_json}")


if __name__ == "__main__":
    run_live_llm_evaluation()
