"""
test_calidad_whatsapp.py — Evaluación de calidad conversacional WhatsApp.

Simula preguntas reales de turistas bajo 5 escenarios operativos:
  1. Preguntas con errores ortográficos típicos (sin tilde, sin 'h', 'q', 'kiero', etc.)
  2. Preguntas ambiguas (sin tour especificado, fechas abiertas)
  3. Preguntas en inglés con errores de digitación
  4. Preguntas fuera del catálogo oficial de Texeira Travel
  5. Solicitudes explícitas de derivación a asesor humano (handoff)

Para cada caso registra:
  - pregunta_enviada
  - respuesta_recibida
  - hubo_fallback
  - latencia_ms

Los resultados se guardan en docs/evaluaciones/test_calidad_whatsapp_FECHA.json
REGLA: NO consume tokens reales de APIs externas; utiliza mocks del LLM.
"""

import os
import sys
import time
import json
from datetime import datetime
from pathlib import Path

# Configuración de codificación de salida para Windows
sys.stdout.reconfigure(encoding='utf-8')

# Configuración de entorno local y seguro (cero llamadas de red)
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

os.environ['TEXEIRA_ENABLE_WHATSAPP'] = 'false'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

import app
from handoff_support import apply_request


# ============================================================
# MOCK DEL LLM (CERO CONSUMO DE TOKENS REALES)
# ============================================================

class MockLLMResponse:
    def __init__(self, content: str):
        self.content = content


class MockTourLLM:
    """
    Mock inteligente del LLM que emula las respuestas del agente RAG
    según el prompt de sistema y las reglas de negocio de Texeira Travel.
    """
    def invoke(self, messages):
        question = ""
        for role, text in messages:
            if role == "human":
                question = text

        q_low = question.lower().strip()

        # 1. Preguntas fuera del catálogo (Lima, Titicaca)
        if any(kw in q_low for kw in ["lima", "titicaca", "lago titicaca"]):
            return MockLLMResponse(
                "No dispongo de información sobre tours a ese destino en los materiales oficiales de Texeira Travel. "
                "Por favor, contacta a un asesor humano de la agencia para verificar si disponen de opciones personalizadas."
            )

        # 2. Consultas en inglés con errores
        if "machu pichu" in q_low and any(k in q_low for k in ["how much", "price", "cost"]):
            return MockLLMResponse(
                "The classic Machu Picchu tour starts at $120 USD per person. "
                "It includes round-trip tourist train, bus tickets up and down to the citadel, entrance fee, and a certified bilingual guide."
            )
        if any(k in q_low for k in ["wat time", "what time", "schedule", "start"]):
            return MockLLMResponse(
                "Our tours have different departure times in Cusco: City Tour departs at 10:00 AM or 1:30 PM, Sacred Valley at 7:00 AM, "
                "and Machu Picchu depends on your selected train schedule. Which tour would you like to check?"
            )

        # 3. Preguntas con errores ortográficos típicos
        if "machu pichu" in q_low:
            return MockLLMResponse(
                "El tour a Machu Picchu Clásico tiene un precio referencial de $120 USD por persona. "
                "Incluye transporte en tren turístico, bus de subida y bajada a la ciudadela, boleto de ingreso y guiado profesional."
            )
        if "valle sagrao" in q_low or "valle sagrado" in q_low:
            return MockLLMResponse(
                "El tour al Valle Sagrado de los Incas incluye transporte turístico y guía profesional bilingüe. "
                "Visita los sitios arqueológicos de Pisac y Ollantaytambo. No incluye el Boleto Turístico del Cusco (BTC)."
            )
        if "montaña de colores" in q_low or "montana de colores" in q_low or "colores" in q_low:
            return MockLLMResponse(
                "El tour a la Montaña de 7 Colores (Vinicunca) tiene un precio de $85 USD por persona. "
                "Incluye transporte turístico ida y vuelta, guía profesional, desayuno buffet, almuerzo y equipo de primeros auxilios."
            )

        # 4. Preguntas ambiguas (sin tour especificado)
        if "cuanto cuesta" in q_low or "cuánto cuesta" in q_low:
            return MockLLMResponse(
                "En Texeira Travel ofrecemos diversos tours en Cusco: Machu Picchu ($120 USD), Valle Sagrado ($65 USD), "
                "Montaña de 7 Colores ($85 USD) y City Tour ($35 USD). ¿Sobre cuál de ellos te gustaría recibir información detallada?"
            )
        if "que incluye" in q_low or "qué incluye" in q_low:
            return MockLLMResponse(
                "Nuestros tours incluyen diferentes servicios según el itinerario (transporte, guía oficial, entradas o alimentación). "
                "¿Qué tour en específico deseas consultar?"
            )
        if "quiero ir mañana" in q_low:
            return MockLLMResponse(
                "Para coordinar salidas de última hora como para mañana, te recomendamos verificar cupos disponibles "
                "directamente con nuestro equipo de asesores en la agencia."
            )

        return MockLLMResponse(
            "Texeira Travel ofrece tours en Cusco como Machu Picchu, Valle Sagrado, City Tour y Montaña de 7 Colores. "
            "¿En qué tour estás interesado?"
        )


# Inyectar el Mock del LLM para evitar consumo de tokens de API
app.get_llm = lambda: MockTourLLM()


# ============================================================
# DEFINICIÓN DE ESCENARIOS DE PRUEBA
# ============================================================

ESCENARIOS = [
    {
        "escenario_id": 1,
        "categoria": "Preguntas con errores ortográficos típicos",
        "descripcion": "Turistas que escriben sin acentos, sin 'h', con abreviaturas o jerga coloquial",
        "preguntas": [
            "cuanto cuesta machu pichu",
            "q incluye el tour del valle sagrao",
            "a ke hora sale el city tour",
            "kiero ir a la montaña de colores cuanto es",
        ]
    },
    {
        "escenario_id": 2,
        "categoria": "Preguntas ambiguas",
        "descripcion": "Consultas incompletas que omiten el tour o solicitan fechas inmediatas",
        "preguntas": [
            "cuanto cuesta",
            "que incluye",
            "quiero ir mañana",
        ]
    },
    {
        "escenario_id": 3,
        "categoria": "Preguntas en inglés con errores",
        "descripcion": "Turistas internacionales con errores tipográficos comunes en inglés",
        "preguntas": [
            "how much is machu pichu tour",
            "wat time does the tour start",
        ]
    },
    {
        "escenario_id": 4,
        "categoria": "Preguntas fuera del catálogo",
        "descripcion": "Destinos no ofrecidos por la agencia (Lima, Titicaca desde Lima)",
        "preguntas": [
            "tienen tours a Lima",
            "hacen tours al lago titicaca desde Lima",
        ]
    },
    {
        "escenario_id": 5,
        "categoria": "Solicitudes de asesor",
        "descripcion": "Peticiones directas para hablar con una persona o agente de soporte",
        "preguntas": [
            "quiero hablar con alguien",
            "necesito un asesor",
        ]
    },
]


def run_evaluation() -> dict:
    """
    Ejecuta la evaluación completa simulando mensajes de WhatsApp,
    registrando pregunta, respuesta, fallback y latencia.
    """
    print("\n" + "=" * 70)
    print("EVALUACIÓN DE CALIDAD CONVERSACIONAL WHATSAPP — TEXEIRA TRAVEL")
    print("=" * 70)

    eval_start_time = datetime.now()
    fecha_tag = eval_start_time.strftime("%Y%m%d_%H%M%S")
    fecha_dia = eval_start_time.strftime("%Y%m%d")

    registros = []
    fallbacks_count = 0
    handoffs_count = 0
    latencias = []

    for esc in ESCENARIOS:
        sc_id = esc["escenario_id"]
        cat = esc["categoria"]
        print(f"\n--- Escenario {sc_id}: {cat} ---")

        for q in esc["preguntas"]:
            user_id = f"sim_wa_user_{sc_id}_{len(registros)+1}"
            channel = "whatsapp"

            t0 = time.perf_counter()
            # 1. Ejecución del pipeline RAG
            rag_result = app.rag_chain(q, user_id=user_id)
            # 2. Aplicación de handoff support si hubo solicitud de asesor
            final_result = apply_request(app.__dict__, rag_result, user_id, channel, q)
            t1 = time.perf_counter()

            latencia_ms = round((t1 - t0) * 1000, 2)
            latencias.append(latencia_ms)

            bot_response = final_result.get("response", "")
            if hasattr(app, "format_whatsapp_text"):
                bot_response = app.format_whatsapp_text(bot_response)

            hubo_fallback = final_result.get("is_fallback", False) or app.is_fallback_response(bot_response)
            if hubo_fallback:
                fallbacks_count += 1

            es_handoff = final_result.get("handoff_registered", False) or final_result.get("handoff_requested", False)
            if es_handoff:
                handoffs_count += 1

            ruta = final_result.get("response_route") or final_result.get("route") or "general"

            registro = {
                "escenario_id": sc_id,
                "categoria": cat,
                "pregunta_enviada": q,
                "respuesta_recibida": bot_response,
                "hubo_fallback": hubo_fallback,
                "latencia_ms": latencia_ms,
                "ruta_asignada": ruta,
                "solicitud_asesor": es_handoff,
                "resuelto_autonomamente": not hubo_fallback and not es_handoff,
            }
            registros.append(registro)

            indicador = "🚨 FALLBACK" if hubo_fallback else ("🛎️ ASESOR" if es_handoff else "✅ OK")
            preview = bot_response[:65].replace("\n", " ") + "..."
            print(f"  {indicador} | '{q}' [{latencia_ms}ms] -> {preview}")

    # Cálculo de métricas agregadas
    total_preguntas = len(registros)
    avg_latency = round(sum(latencias) / total_preguntas, 2) if total_preguntas else 0.0

    reporte = {
        "metadata": {
            "fecha_ejecucion": eval_start_time.isoformat(),
            "ambiente": "simulacion_local_sin_tokens_api",
            "canal": "whatsapp",
            "modelo_mock": "MockTourLLM (cero costo)",
            "archivo_salida": f"test_calidad_whatsapp_{fecha_dia}.json",
        },
        "resumen_ejecutivo": {
            "total_preguntas_evaluadas": total_preguntas,
            "total_escenarios": len(ESCENARIOS),
            "latencia_promedio_ms": avg_latency,
            "tasa_fallback_pct": round((fallbacks_count / total_preguntas) * 100, 2),
            "solicitudes_asesor_detectadas": handoffs_count,
            "respuestas_autonomas": total_preguntas - fallbacks_count - handoffs_count,
        },
        "resultados_detallados": registros,
    }

    # Guardar reporte en docs/evaluaciones/
    eval_dir = ROOT_DIR / "docs" / "evaluaciones"
    eval_dir.mkdir(parents=True, exist_ok=True)

    # 1. Archivo por fecha del día (test_calidad_whatsapp_FECHA.json)
    dest_file_day = eval_dir / f"test_calidad_whatsapp_{fecha_dia}.json"
    with open(dest_file_day, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)

    # 2. Archivo específico con timestamp para trazabilidad
    dest_file_ts = eval_dir / f"test_calidad_whatsapp_{fecha_tag}.json"
    with open(dest_file_ts, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print(f"REPORTE GUARDADO CON ÉXITO:")
    print(f"  - {dest_file_day}")
    print(f"  - {dest_file_ts}")
    print(f"Total casos: {total_preguntas} | Fallbacks: {fallbacks_count} | Asesor: {handoffs_count} | Latencia media: {avg_latency} ms")
    print("=" * 70 + "\n")

    return reporte


def test_calidad_whatsapp():
    """Valida los resultados de la simulación mediante aserciones clave."""
    reporte = run_evaluation()
    detalles = reporte["resultados_detallados"]

    assert len(detalles) == 13, f"Se esperaban 13 preguntas evaluadas, se obtuvieron {len(detalles)}"

    # Verificar que cada caso tiene los campos obligatorios
    for r in detalles:
        assert r["pregunta_enviada"], "Falta pregunta_enviada"
        assert r["respuesta_recibida"], f"Falta respuesta_recibida para '{r['pregunta_enviada']}'"
        assert isinstance(r["hubo_fallback"], bool), "hubo_fallback debe ser booleano"
        assert r["latencia_ms"] >= 0, "latencia_ms debe ser positiva"

    # Verificar que las solicitudes de asesor fueron derivadas correctamente
    asesor_cases = [r for r in detalles if r["escenario_id"] == 5]
    for ac in asesor_cases:
        assert ac["solicitud_asesor"] is True, f"Fallo al detectar handoff en '{ac['pregunta_enviada']}'"
        assert "registrada" in ac["respuesta_recibida"].lower() or "asesor" in ac["respuesta_recibida"].lower()

    # Verificar que las preguntas con errores ortográficos obtuvieron respuesta útil sin error
    orto_cases = [r for r in detalles if r["escenario_id"] == 1]
    for oc in orto_cases:
        assert len(oc["respuesta_recibida"]) > 15, f"Respuesta demasiado corta para '{oc['pregunta_enviada']}'"

    print("PASS: Todas las aserciones de calidad de WhatsApp fueron superadas exitosamente.")


if __name__ == "__main__":
    test_calidad_whatsapp()
