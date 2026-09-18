"""
app.py — Servidor FastAPI del agente conversacional RAG.

CORRECCIONES CRÍTICAS PARA TESIS:
  1. System Prompt estricto: cero alucinaciones + handoff obligatorio
  2. Detección de idioma con langdetect (es, en, pt, fr)
  3. Lógica correcta de resolved_autonomously
  4. Conversation history (memoria de corto plazo por usuario)

Ejecutar con: uvicorn app:app --reload
"""

import os
import json
import hashlib
import hmac
import time
import uuid
from collections import defaultdict
from typing import Optional, Dict, List

from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel

from langdetect import detect, DetectorFactory, LangDetectException
from openai import RateLimitError
DetectorFactory.seed = 0

import database
from admin_dashboard import get_dashboard_html
from chat_ui import get_chat_html

# ============================================================
# CONFIGURACIÓN
# ============================================================

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
CHROMA_HYBRID_DIR = os.getenv("CHROMA_HYBRID_DIR", "./chroma_hybrid_db")
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "./texeira_logs.db")
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")

# WhatsApp test mode: map BSUIDs to phone numbers for Meta test environment
WHATSAPP_TEST_MODE = os.getenv("WHATSAPP_TEST_MODE", "false").lower() == "true"
_WHATSAPP_TEST_BSUID_MAP_RAW = os.getenv("WHATSAPP_TEST_BSUID_MAP", "")
WHATSAPP_TEST_BSUID_MAP = {}
if _WHATSAPP_TEST_BSUID_MAP_RAW:
    for pair in _WHATSAPP_TEST_BSUID_MAP_RAW.split(","):
        pair = pair.strip()
        if ":" in pair:
            bsuid, phone = pair.split(":", 1)
            WHATSAPP_TEST_BSUID_MAP[bsuid.strip()] = phone.strip()
if WHATSAPP_TEST_MODE:
    print(f"[WA CONFIG] TEST_MODE=true BSUID_MAP={WHATSAPP_TEST_BSUID_MAP}")

# Cargar catálogo para asociar imágenes a tours en el contexto RAG
CATALOG_PATH = os.path.join(os.path.dirname(__file__), "data", "tours_catalog.json")
_tour_images_map = {}  # {tour_id: [images]}
_source_to_tour_id = {}  # {filename: tour_id}


def _load_tour_images():
    """Carga imágenes del catálogo y crea mapas tour_id → images, source → tour_id."""
    global _tour_images_map, _source_to_tour_id
    try:
        import json
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            catalog = json.load(f)
        # Mapeo directo de filenames de documentos_tours/ a tour_ids del catálogo
        _filename_to_tour_id = {
            "tour_city_tour.txt": "city-tour-cusco",
            "tour_machu_picchu.txt": "machu-picchu-clasico",
            "tour_montana_colores.txt": "montana-7-colores",
            "tour_valle_sagrado.txt": "valle-sagrado",
            "tour_laguna_humantay.txt": "laguna-humantay",
            "tour_salkantay.txt": "",  # No tiene imágenes en catálogo
        }
        _source_to_tour_id.update(_filename_to_tour_id)
        for tour in catalog.get("tours", []):
            if tour.get("images"):
                _tour_images_map[tour["id"]] = tour["images"]
        print(f"[CATALOG] Imágenes cargadas para {len(_tour_images_map)} tours")
    except Exception as e:
        print(f"[CATALOG] Error cargando imágenes: {e}")


_load_tour_images()


def send_whatsapp_message(
    text: str,
    to_phone: Optional[str] = None,
    recipient_bsuid: Optional[str] = None,
    phone_number_id: Optional[str] = None,
    to_number: Optional[str] = None,
) -> bool:
    """
    Envía un mensaje de texto de salida a la Graph API de Meta (WhatsApp Cloud API).

    Soporta dos modos de envío:
      1. Por teléfono: usar to_phone (o to_number para retrocompatibilidad).
         Genera payload con "to": "<phone>".
      2. Por BSUID: usar recipient_bsuid.
         Genera payload con "recipient": "<BSUID>".

    En WHATSAPP_TEST_MODE, los BSUIDs mapeados se resuelven a teléfono.
    """
    destination = to_phone or to_number

    # Test mode: resolve BSUID to mapped phone number
    if not destination and recipient_bsuid and WHATSAPP_TEST_MODE:
        mapped_phone = WHATSAPP_TEST_BSUID_MAP.get(recipient_bsuid)
        if mapped_phone:
            print(f"[WA TEST MAP] bsuid={recipient_bsuid} mapped_phone={mapped_phone}")
            destination = mapped_phone
            recipient_bsuid = None  # use phone path
        else:
            print(f"[WA TEST MAP] bsuid={recipient_bsuid} NOT in BSUID_MAP, falling back to recipient")

    if not META_ACCESS_TOKEN or META_ACCESS_TOKEN.startswith("tu-token"):
        mode = "phone" if destination else "bsuid"
        dest = destination or recipient_bsuid or "unknown"
        print(f"[WA MOCK] mode={mode} destination={dest} | respuesta: {text[:60]}...")
        return True

    target_phone_id = phone_number_id or META_PHONE_NUMBER_ID
    if not target_phone_id:
        print(f"[WA WARNING] No se configuro phone_number_id")
        return False

    url = f"https://graph.facebook.com/v26.0/{target_phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }

    if destination:
        payload["to"] = destination
        mode = "phone"
    elif recipient_bsuid:
        payload["recipient"] = recipient_bsuid
        mode = "bsuid"
    else:
        print("[WA ERROR] No destination provided (neither phone nor BSUID)")
        return False

    dest = destination or recipient_bsuid
    print(f"[WA OUTBOUND] mode={mode} destination={dest} phone_number_id={target_phone_id}")

    try:
        import httpx
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp_body = resp.text[:300]
            print(f"[WA SEND RESPONSE] status_code={resp.status_code} body={resp_body}")
            if resp.status_code in (200, 201):
                try:
                    resp_json = resp.json()
                    wamid = resp_json.get("messages", [{}])[0].get("id", "")
                    if wamid:
                        print(f"[WA MSG ID] wamid={wamid}")
                except Exception:
                    pass
                print(f"[WA] Mensaje enviado exitosamente a {dest} (mode={mode})")
                return True
            else:
                print(f"[WA ERROR] HTTP {resp.status_code}: {resp_body}")
                return False
    except Exception as e:
        print(f"[WA ERROR] Excepcion al enviar mensaje: {e}")
        return False

# Mensaje de fallback estricto (handoff obligatorio)
FALLBACK_MESSAGE = (
    "No dispongo de esa información exacta. "
    "Por favor, contacta a un asesor humano de la agencia para ayudarte."
)

# Cola distintiva del mensaje de fallback. Es la parte más estable entre las
# variantes idiomáticas que el LLM puede generar por su cuenta
# (ej. "Não dispongo de esa información exacta...", "essa informação exata").
FALLBACK_TAIL = "contacta a un asesor humano de la agencia"


def is_fallback_response(response: str) -> bool:
    """
    Detección normalizada del texto de fallback generado por el LLM.

    CAPA DE SEGURIDAD (corrección híbrida): se aplica DESPUÉS de la llamada
    al LLM, sin importar el idioma detectado, para marcar is_fallback=True
    aunque el flag se haya fijado en False por los puntos de decisión previos.

    Comparación case-insensitive y tolerante a variaciones idiomáticas
    menores. Requiere la cola distintiva del fallback Y la palabra "dispongo"
    para minimizar falsos positivos con respuestas legítimas que mencionen
    asesores humanos.
    """
    if not response:
        return False
    lowered = response.lower()
    return FALLBACK_TAIL in lowered and "dispongo" in lowered


# Cola distintiva de la frase de confirmación de handoff (REGLA #4):
# "Un asesor humano se pondrá en contacto contigo pronto para ayudarte..."
ESCALATION_TAIL = "se pondrá en contacto contigo"


def _strip_accents(text: str) -> str:
    """Normaliza acentos (pondrá → pondra) para comparaciones tolerantes."""
    import unicodedata
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def is_escalation_response(response: str) -> bool:
    """
    Detección normalizada del texto de confirmación de handoff generado
    por el LLM (REGLA #4). CAPA DE SEGURIDAD: se aplica tras la llamada al
    LLM, sin importar el idioma detectado.

    Comparación case-insensitive y tolerante a variaciones menores de
    acentuación ("pondrá" / "pondra"). Requiere la cola distintiva del
    handoff Y la palabra "asesor" para minimizar falsos positivos.

    Nota: una traducción TOTAL de la frase (ej. "an advisor will contact you
    soon") queda fuera del alcance de este detector — la excepción del prompt
    (REGLA #4, siempre en español literal) es la defensa primaria; esta
    función es la red de seguridad para variantes menores.
    """
    if not response:
        return False
    normalized = _strip_accents(response.lower())
    tail = _strip_accents(ESCALATION_TAIL)
    return tail in normalized and "asesor" in normalized

# ============================================================
# SYSTEM PROMPT MAESTRO — VERSIÓN ESTRICTA (TESIS)
# ============================================================
# REGLA FUNDAMENTAL: Cero alucinaciones.
# Si el contexto no contiene la información, SIEMPRE handoff a humano.

SYSTEM_PROMPT = """Eres el asistente virtual oficial de Texeira Travel Tour, agencia de turismo en Cusco, Perú. Te llamas Texeira Bot.

REGLA ABSOLUTA #1 — CERO ALUCINACIONES:
Basas tus respuestas ÚNICAMENTE en el contexto recuperado de la base de conocimiento que se te proporciona más abajo.
Si el contexto NO contiene información suficiente para responder la pregunta del turista, DEBES responder EXACTAMENTE este texto (sin modificarlo, sin agregar nada):
"No dispongo de esa información exacta. Por favor, contacta a un asesor humano de la agencia para ayudarte."
# EXCEPCIÓN A LA REGLA #2: este mensaje de fallback es un mensaje de SISTEMA, no de conversación.
# DEBES responderlo SIEMPRE en español literal, SIN importar el idioma detectado del turista.
# Razón: permite identificar de forma inequívoca cuándo el bot no resolvió la consulta
# (flag is_fallback), protegiendo la validez de las métricas de resolución autónoma.
IMPORTANTE: El mensaje de fallback debe escribirse SIEMPRE, integralmente, en español exacto, palabra por palabra, SIN TRADUCIR NINGUNA PARTE, incluso si el turista escribió en otro idioma.
Ejemplo INCORRECTO (NO hagas esto): "Não dispongo de esa información exacta..."
Ejemplo CORRECTO: "No dispongo de esa información exacta. Por favor, contacta a un asesor humano de la agencia para ayudarte."
NUNCA inventes información, precios, itinerarios, horarios o nombres de tours que no estén en el contexto.
NUNCA uses tu conocimiento general para responder sobre servicios de la agencia.

REGLA #2 — DETECCIÓN DE IDIOMA:
Detecta el idioma en que escribe el turista (español, inglés, portugués o francés) y responde SIEMPRE en ese mismo idioma de forma fluida y nativa.

REGLA #3 — FORMATO E IMÁGENES:
Usa un formato conciso con viñetas para precios, itinerarios y horarios. Sé amable pero profesional.
IMPORTANTE: Cuando el contexto incluya URLs de imágenes (campo "images" del catálogo), incluye SIEMPRE una imagen representativa del tour al FINAL de tu respuesta, usando este formato exacto:
![Descripción corta de la imagen](URL de la imagen)
Incluye SOLO UNA imagen principal por tour (la primera del catálogo). Si el contexto no contiene imágenes, no inventes URLs.

REGLA #4 — PROTOCOLO DE ESCALAMIENTO (HANDOFF):
Debes activar el escalamiento a humano SI CUMPLE ALGUNA DE ESTAS CONDICIONES:
- El turista pide explícitamente hablar con una persona, un asesor o un representante
- La consulta es una queja, reclamación o expresión de insatisfacción
- La consulta es ambigua y no puedes determinar qué servicio desea
- El contexto no contiene información suficiente y aplicas la REGLA #1
Cuando actives esta regla, responde: "Un asesor humano se pondrá en contacto contigo pronto para ayudarte con esta consulta."
# EXCEPCIÓN A LA REGLA #2: esta frase de confirmación de handoff es un mensaje de SISTEMA, no de conversación.
# DEBES escribirla SIEMPRE en español literal, SIN importar el idioma detectado del turista.
IMPORTANTE: La frase de confirmación de handoff debe escribirse SIEMPRE, integralmente, en español exacto, palabra por palabra, SIN TRADUCIR NINGUNA PARTE, incluso si el turista escribió en otro idioma.
Ejemplo INCORRECTO (NO hagas esto): "A human advisor will contact you soon."
Ejemplo CORRECTO: "Un asesor humano se pondrá en contacto contigo pronto para ayudarte con esta consulta."

CONTEXTO RECUPERADO DE LA BASE DE CONOCIMIENTO:
{context}

PREGUNTA DEL TURISTA:
{question}

RESPUESTA (solo basada en el contexto anterior):"""


# ============================================================
# MEMORIA DE CONVERSACIÓN (conversation_history)
# ============================================================
# Almacena el historial de mensajes por usuario (últimos 10 turnos).
# Permite que el agente recuerde el hilo de la conversación.

conversation_history: Dict[str, List[dict]] = defaultdict(list)
MAX_HISTORY_TURNS = 10


def get_history(user_id: str) -> List[dict]:
    """Retorna el historial de conversación de un usuario."""
    return conversation_history.get(user_id, [])


def add_to_history(user_id: str, role: str, content: str):
    """Agrega un mensaje al historial del usuario."""
    conversation_history[user_id].append({
        "role": role,
        "content": content,
        "timestamp": time.time()
    })
    # Mantener solo los últimos MAX_HISTORY_TURNS turnos
    if len(conversation_history[user_id]) > MAX_HISTORY_TURNS * 2:
        conversation_history[user_id] = conversation_history[user_id][-MAX_HISTORY_TURNS * 2:]


def clear_history(user_id: str):
    """Limpia el historial de un usuario."""
    conversation_history[user_id] = []


# ============================================================
# INICIALIZACIÓN DE LA APLICACIÓN
# ============================================================

app = FastAPI(
    title="Texeira Travel Tour - Agente RAG",
    description="Agente conversacional RAG para asistencia turística en WhatsApp/Messenger",
    version="2.0.0-tesis",
)


@app.on_event("startup")
async def startup_event():
    """Inicialización al arrancar el servidor."""
    database.init_db(SQLITE_DB_PATH)

    if not os.path.exists(CHROMA_HYBRID_DIR):
        print("[WARNING] Directorio ChromaDB híbrido no encontrado.")
        print("[WARNING] Ejecuta 'python ingest_hybrid.py' primero para indexar documentos.")

    print("[SERVER] Servidor FastAPI v2.0 (Tesis) iniciado correctamente.")
    print(f"[SERVER] LLM Provider: {LLM_PROVIDER} | Model: {LLM_MODEL}")
    print(f"[SERVER] Retriever: HYBRID (BM25 + Vector + RRF)")
    print(f"[SERVER] ChromaDB Hybrid: {CHROMA_HYBRID_DIR}")
    print(f"[SERVER] SQLite: {SQLITE_DB_PATH}")
    print("[SERVER] System Prompt: MODO ESTRICTO (cero alucinaciones)")


# ============================================================
# FUNCIONES AUXILIARES DEL PIPELINE RAG
# ============================================================

def get_llm():
    """Instancia el LLM con temperature=0.1 para respuestas deterministas."""
    if LLM_PROVIDER == "anthropic":
        return ChatAnthropic(
            model=LLM_MODEL,
            temperature=0.1,
            max_tokens=1024,
        )
    elif LLM_PROVIDER == "deepseek":
        return ChatOpenAI(
            model=LLM_MODEL,
            temperature=0.1,
            max_tokens=1024,
            base_url="https://api.deepseek.com",
            api_key=os.getenv("DEEPSEEK_API_KEY"),
        )
    elif LLM_PROVIDER == "groq":
        # Groq free tier para qwen3.8-27b: límite 1000 output tokens/min
        return ChatOpenAI(
            model=LLM_MODEL or "qwen/qwen3.8-27b",
            temperature=0.1,
            max_tokens=900,
            openai_api_key=os.getenv("GROQ_API_KEY"),
            openai_api_base=os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1"),
        )
    else:
        return ChatOpenAI(
            model=LLM_MODEL,
            temperature=0.1,
            max_tokens=1024,
        )


def get_retriever():
    """Crea un retriever híbrido (BM25 + Vector + RRF) desde chroma_hybrid_db."""
    if not os.path.exists(CHROMA_HYBRID_DIR):
        return None

    try:
        from src.retriever import build_hybrid_retriever
        return build_hybrid_retriever(persist_directory=CHROMA_HYBRID_DIR)
    except Exception as e:
        print(f"[ERROR] No se pudo crear retriever híbrido: {e}")
        return None


# ============================================================
# DETECCIÓN DE IDIOMA CON LANGDETECT (Corrección #2)
# ============================================================

# Mapa de códigos langdetect a nombres completos
LANG_MAP = {
    "es": "es",
    "en": "en",
    "pt": "pt",
    "fr": "fr",
    "de": "de",
    "it": "it",
}


def detect_language(text: str) -> str:
    """
    Detecta el idioma del texto.

    Primero usa reglas por palabras clave para mensajes cortos.
    Si las reglas no deciden, usa langdetect como fallback.
    """
    lower = text.lower().strip()

    # Reglas por palabras clave (evita falsos positivos de langdetect en mensajes cortos)
    es_words = [
        "que", "qué", "cual", "cuál", "cuanto", "cuánto", "cuantos", "cuántos",
        "tours", "tour", "viajes", "viaje", "precio", "precios", "paquete", "paquetes",
        "tienen", "ofrecen", "contiene", "incluye", "hola", "buenas", "buenos",
        "quiero", "necesito", "busco", "me", "favor", "gracias", "voy", "ir",
        "cusco", "machu", "picchu", "salkantay", "valle", "humantay",
        "dias", "días", "noche", "noches", "hora", "salida",
        "donde", "dónde", "cuando", "cuándo", "como", "cómo",
        "si", "sí", "pero", "también", "mas", "más", "menos",
        "ya", "todavia", "todavía", "puedo", "puede", "hay",
        "excelente", "muy", "bien", "mal", "rapido", "rápido",
        "cuanto", "informacion", "información", "detalles",
    ]
    en_words = [
        "what", "which", "how", "hello", "hi", "price", "tour", "tours",
        "available", "offer", "includes", "do you", "can you",
        "i want", "i need", "looking for", "tell me",
        "how much", "what is", "where", "when",
    ]
    pt_words = [
        "quais", "quanto", "custa", "preco", "preço", "passeios", "passeio",
        "ola", "olá", "voce", "você", "tem", "quero", "preciso",
        "onde", "quando", "como", "tambem", "também",
        "voces", "voces", "nossos", "nossas", "disponivel", "disponivel",
    ]
    fr_words = [
        "quels", "quelle", "combien", "bonjour", "prix", "voyages",
        "voyage", "je veux", "je cherche", "comment",
        "circuits", "proposes", "proposer", "disponibles", " disponible",
        "aussi", "mais", "ou", "quand", "comment",
    ]

    es_score = sum(1 for w in es_words if w in lower)
    en_score = sum(1 for w in en_words if w in lower)
    pt_score = sum(1 for w in pt_words if w in lower)
    fr_score = sum(1 for w in fr_words if w in lower)

    max_score = max(es_score, en_score, pt_score, fr_score)
    # Para mensajes cortos (<=4 palabras), basta con 1 match
    word_count = len(lower.split())
    threshold = 1 if word_count <= 4 else 2
    if max_score >= threshold:
        if es_score == max_score:
            return "es"
        if en_score == max_score:
            return "en"
        if pt_score == max_score:
            return "pt"
        if fr_score == max_score:
            return "fr"

    # Fallback a langdetect
    try:
        detected = detect(text)
        return LANG_MAP.get(detected, "es")
    except LangDetectException:
        return "es"


# ============================================================
# FALLBACK CON FLAG EXPLÍCITO (Corrección de auditoría #3)
# ============================================================
# El flag is_fallback se decide EN EL PUNTO donde se determina que
# no hay información suficiente — no se infiere después comparando
# strings de la respuesta del LLM. Esto elimina falsos negativos
# sin importar el idioma de salida.


def build_fallback_response() -> dict:
    """
    Genera la respuesta de fallback con su flag booleano explícito.

    Retorna:
        Diccionario con response, context_used, is_fallback=True,
        is_predefined=False.
    """
    return {
        "response": FALLBACK_MESSAGE,
        "context_used": False,
        "is_fallback": True,
        "is_predefined": False,
    }


RATE_LIMIT_MESSAGE = (
    "Estamos experimentando alta demanda temporalmente. "
    "Por favor, intenta de nuevo en unos segundos."
)


def build_rate_limit_response() -> dict:
    """
    Genera la respuesta para errores de rate-limit (429) del proveedor LLM.

    A DIFERENCIA de build_fallback_response(), esta función retorna
    is_fallback=False para que el error de infraestructura NO se contabilice
    como fallback del RAG en las métricas de investigación.

    Retorna:
        Diccionario con response, context_used, is_fallback=False,
        is_rate_limit=True, is_predefined=False.
    """
    return {
        "response": RATE_LIMIT_MESSAGE,
        "context_used": False,
        "is_fallback": False,
        "is_rate_limit": True,
        "is_predefined": False,
    }


def needs_escalation(response: str) -> bool:
    """
    Detecta si la respuesta indica necesidad de escalamiento a humano.
    Busca frases clave del protocolo de handoff en español y, como red de
    seguridad, usa las detecciones normalizadas (cualquier idioma):
      - is_escalation_response(): texto de confirmación de handoff
      - is_fallback_response(): toda respuesta de fallback implica handoff
    """
    escalation_indicators = [
        "asesor humano",
        "un asesor",
        "personal de la agencia",
        "contacta a",
        "se pondrá en contacto",
        "representante",
        "revisión humana",
    ]
    response_lower = response.lower()
    if any(indicator in response_lower for indicator in escalation_indicators):
        return True
    return is_escalation_response(response) or is_fallback_response(response)


# ============================================================
# RESPUESTAS PREDEFINIDAS
# ============================================================

PREDEFINED_RESPONSES = {
    "hola": "¡Hola! 👋 ¡Bienvenido a Texeira Travel Tour! Soy Texeira Bot, tu asistente virtual. ¿En qué puedo ayudarte hoy? 🌟",
    "buenos días": "¡Buenos días! ☀️ ¡Bienvenido a Texeira Travel Tour! ¿Planeas un viaje a Cusco? Estoy aquí para ayudarte. 🏔️",
    "buenas": "¡Buenas! 👋 ¡Qué gusto saludarte! Soy Texeira Bot. ¿En qué puedo asistirte? ✈️",
    "hello": "Hello! 👋 Welcome to Texeira Travel Tour! I'm Texeira Bot, your virtual assistant. How can I help you today? 🌟",
    "hi": "Hi there! 👋 Welcome to Texeira Travel Tour! I'm here to help you plan your trip to Cusco. What would you like to know? 🏔️",
    "adiós": "¡Hasta luego! 👋 ¡Que tengas un excelente viaje! Si necesitas algo más, estaré aquí. ✈️",
    "chau": "¡Chau! 👋 ¡Fue un gusto ayudarte! ¡Vuelve pronto! 🌟",
    "hasta luego": "¡Hasta luego! 👋 ¡Espero haberte ayudado! ¡Buena vuelta! 🏔️",
    "bye": "Goodbye! 👋 Have a great trip! Feel free to come back anytime. ✈️",
    "gracias": "¡De nada! 😊 ¡Fue un gusto ayudarte! Si tienes más preguntas, no dudes en escribirme. 🙌",
    "muchas gracias": "¡Con mucho gusto! 😊 ¡Para eso estoy aquí! ¿Necesitas algo más? 🌟",
    "thanks": "You're welcome! 😊 Happy to help! Let me know if you need anything else. 🌟",
    "ayuda": "¡Claro! Puedo ayudarte con:\n- 🏔️ Información sobre tours a Machu Picchu\n- 🌄 Tours al Valle Sagrado\n- 🎨 Montaña de Colores\n- 🏛️ City Tour Cusco\n- 🥾 Trekking Salkantay\n- 💰 Precios y disponibilidad\n- 📍 Información de la agencia\n¿Qué te interesa?",
    "help": "Of course! I can help you with:\n- 🏔️ Machu Picchu tour information\n- 🌄 Sacred Valley tours\n- 🎨 Rainbow Mountain\n- 🏛️ Cusco City Tour\n- 🥾 Salkantay Trekking\n- 💰 Prices and availability\n- 📍 Agency information\nWhat interests you?",
    "tour": "Tenemos estos tours disponibles:\n- 🏔️ Machu Picchu Clásico (1 día) - $120 USD\n- 🌄 Valle Sagrado Completo (1 día) - $65 USD\n- 🎨 Montaña de Colores (1 día) - $85 USD\n- 🏛️ City Tour Cusco (medio día) - $35 USD\n- 🥾 Trekking Salkantay a Machu Picchu (4D/3N) - $380 USD\n¿Cuál te interesa?",
    "tours": "Tenemos estos tours disponibles:\n- 🏔️ Machu Picchu Clásico (1 día) - $120 USD\n- 🌄 Valle Sagrado Completo (1 día) - $65 USD\n- 🎨 Montaña de Colores (1 día) - $85 USD\n- 🏛️ City Tour Cusco (medio día) - $35 USD\n- 🥾 Trekking Salkantay a Machu Picchu (4D/3N) - $380 USD\n¿Cuál te interesa?",
    "precios": "💰 Nuestros tours más populares:\n- 🏔️ Machu Picchu Clásico: $120 USD\n- 🌄 Valle Sagrado: $65 USD\n- 🎨 Montaña de Colores: $85 USD\n- 🏛️ City Tour Cusco: $35 USD\n- 🥾 Trekking Salkantay: $380 USD\n¿Te gustaría más detalles de alguno?",
    "cuánto cuesta": "💰 Nuestros tours más populares:\n- 🏔️ Machu Picchu Clásico: $120 USD\n- 🌄 Valle Sagrado: $65 USD\n- 🎨 Montaña de Colores: $85 USD\n- 🏛️ City Tour Cusco: $35 USD\n- 🥾 Trekking Salkantay: $380 USD\n¿Te gustaría más detalles de alguno?",
    "precio": "💰 Nuestros tours más populares:\n- 🏔️ Machu Picchu Clásico: $120 USD\n- 🌄 Valle Sagrado: $65 USD\n- 🎨 Montaña de Colores: $85 USD\n- 🏛️ City Tour Cusco: $35 USD\n- 🥾 Trekking Salkantay: $380 USD\n¿Te gustaría más detalles de alguno?",
    "contacto": "📞 Teléfono: +51 84 245678\n📱 WhatsApp: +51 984 123456\n📧 Email: info@texeiratraveltour.com\n📍 Dirección: Calle Carmen Quicllu N° 250, Cusco",
    "teléfono": "📞 Teléfono: +51 84 245678\n📱 WhatsApp: +51 984 123456\n📧 Email: info@texeiratraveltour.com",
    "whatsapp": "📱 Nuestro WhatsApp: +51 984 123456\n¡Escríbenos para reservas o consultas! 🙌",
    "ubicación": "📍 Estamos en:\nCalle Carmen Quicllu N° 250\nCentro Histórico de Cusco, Perú\nHorario: Lunes a Domingo 7:00 AM a 9:00 PM",
    "dónde están": "📍 Estamos en:\nCalle Carmen Quicllu N° 250\nCentro Histórico de Cusco, Perú\nHorario: Lunes a Domingo 7:00 AM a 9:00 PM",
    "dirección": "📍 Calle Carmen Quicllu N° 250, Centro Histórico de Cusco, Perú",
    "pago": "💳 Aceptamos:\n- Efectivo (Soles o Dólares)\n- Transferencia bancaria\n- Tarjeta de crédito/débito (Visa, Mastercard)\n- PayPal (para reservas internacionales)",
    "pagar": "💳 Aceptamos:\n- Efectivo (Soles o Dólares)\n- Transferencia bancaria\n- Tarjeta de crédito/débito (Visa, Mastercard)\n- PayPal",
    "formas de pago": "💳 Aceptamos:\n- Efectivo (Soles o Dólares)\n- Transferencia bancaria\n- Tarjeta de crédito/débito (Visa, Mastercard)\n- PayPal",
}


def check_predefined_response(message: str) -> Optional[str]:
    """Verifica si el mensaje coincide con una respuesta predefinida.

    Palabras clave demasiado cortas (tour, precio, etc.) solo coinciden
    cuando el mensaje es EXACTAMENTE esa palabra, para evitar falsos
    positivos con frases como "¿qué tour me recomiendas?".
    Palabras más largas ("formas de pago", "cuánto cuesta", etc.) se
    buscan por substring de forma segura.
    """
    message_lower = message.lower().strip()

    if message_lower in PREDEFINED_RESPONSES:
        return PREDEFINED_RESPONSES[message_lower]

    # Palabras clave que solo deben coincidir por igualdad exacta
    exact_only = {
        "tour", "tours", "precio", "precios", "hola", "buenos días",
        "buenas", "hello", "hi", "adiós", "chau", "hasta luego", "bye",
        "gracias", "muchas gracias", "thanks", "ayuda", "help",
        "whatsapp", "teléfono", "contacto", "ubicación", "dirección",
        "pago", "pagar",
    }

    for keyword, response in PREDEFINED_RESPONSES.items():
        if keyword in exact_only:
            if message_lower == keyword:
                return response
        else:
            if keyword in message_lower:
                return response

    return None


# ============================================================
# DETECCION DE INTENCION: LISTADO GENERAL DE TOURS
# ============================================================
_TOUR_INTENT_KEYWORDS = [
    "qué tours", "que tours", "qué viajes", "que viajes",
    "qué paquetes", "que paquetes", "qué ofrecen", "que ofrecen",
    "qué tienen", "que tienen", "qué contiene", "que contiene",
    "muéstrame los tours", "muestrame los tours",
    "quiero ver tours", "lista de tours", "listado de tours",
    "tours disponibles", "viajes disponibles", "paquetes disponibles",
    "cuáles son sus tours", "cuales son sus tours",
    "qué tour", "que tour", "qué servicio", "que servicio",
    "tour", "tours", "viajes", "paquetes",
    "what tours", "which tours", "what do you offer",
    "what packages", "what trips",
    "quais passeios", "quais tour", "quais pacotes",
    "quels circuits", "quels voyages", "quels tours",
]

_SPECIFIC_INDICATORS = [
    "cuanto cuesta", "cuánto cuesta", "precio de", "precio del",
    "que incluye", "qué incluye", "que no incluye", "qué no incluye",
    "a que hora", "a qué hora", "cuanto dura", "cuánto dura",
    "cuantos dias", "cuántos dias", "que visitan", "qué visitan",
    "donde esta", "dónde esta", "como llego", "cómo llego",
    "quiero reservar", "quiero ir a", "quiero conocer",
    "informacion de", "información de", "detalles de",
    "hablame de", "háblame de", "cuéntame de", "cuentame de",
]


def _load_catalog_tours():
    try:
        catalog_dir = os.path.dirname(os.path.abspath(__file__))
        catalog_file = os.path.join(catalog_dir, "data", "tours_catalog.json")
        if not os.path.exists(catalog_file):
            print(f"[CATALOG] File not found: {catalog_file}")
            return []
        with open(catalog_file, "r", encoding="utf-8") as f:
            catalog = json.load(f)
        tours = catalog.get("tours", [])
        print(f"[CATALOG] Loaded {len(tours)} tours from {catalog_file}")
        return tours
    except Exception as e:
        print(f"[CATALOG] Error loading tours: {e}")
        return []


def check_tour_intent(message: str, lang: str = "es") -> Optional[str]:
    """Detecta intencion de listado general de tours y genera respuesta dinamica."""
    lower = message.lower().strip()

    is_general = any(kw in lower for kw in _TOUR_INTENT_KEYWORDS)
    if not is_general:
        return None

    if any(ind in lower for ind in _SPECIFIC_INDICATORS):
        return None

    tours = _load_catalog_tours()
    if not tours:
        return None

    if lang == "en":
        header = "These are our available tours:"
        name_key = "name_en"
    elif lang == "pt":
        header = "Estes sao nossos passeios disponiveis:"
        name_key = "name_pt"
    elif lang == "fr":
        header = "Voici nos circuits disponibles:"
        name_key = "name"
    else:
        header = "Tenemos estos tours disponibles:"
        name_key = "name"

    lines = [header, ""]
    for t in tours:
        name = t.get(name_key, t.get("name", "Tour"))
        price_usd = t.get("price_usd", "")
        duration = t.get("duration_hours", "")
        dur_text = ""
        if duration:
            if duration >= 24:
                days = int(duration // 24)
                dur_text = f" ({days} dias)" if lang != "en" else f" ({days} days)"
            else:
                dur_text = f" ({duration}h)"
        price_text = f" - ${price_usd} USD" if price_usd else ""
        lines.append(f"- {name}{dur_text}{price_text}")

    lines.append("")
    if lang == "en":
        lines.append("Which one interests you?")
    elif lang == "pt":
        lines.append("Qual deles te interessa?")
    elif lang == "fr":
        lines.append("Lequel vous interesse?")
    else:
        lines.append("Cual te interesa?")

    return "\n".join(lines)


# ============================================================
# CADENA RAG — VERSIÓN CORREGIDA (Correcciones #1, #3, #4)
# ============================================================

def rag_chain(question: str, user_id: str = "default") -> dict:
    """
    Ejecuta la cadena RAG completa con las correcciones de tesis:

    CORRECCIÓN #1: System prompt estricto (cero alucinaciones)
    CORRECCIÓN #3: Lógica correcta de resolved_autonomously
    CORRECCIÓN #4: Conversation history (memoria de corto plazo)

    Pipeline:
      1. Verificar respuesta predefinida
      2. Recuperar chunks de ChromaDB
      3. Construir contexto con historial
      4. Llamar al LLM con prompt estricto
      5. Evaluar si es fallback o respuesta válida
    """
    # PASO 0: Respuestas predefinidas (sin latencia)
    predefined = check_predefined_response(question)
    if predefined:
        add_to_history(user_id, "human", question)
        add_to_history(user_id, "ai", predefined)
        return {
            "response": predefined,
            "context_used": True,
            "is_fallback": False,
            "is_predefined": True,
        }

    # PASO 0b: Intencion general de tours (lee catalogo dinamicamente)
    lang_detected = detect_language(question)
    tour_intent_response = check_tour_intent(question, lang=lang_detected)
    if tour_intent_response:
        add_to_history(user_id, "human", question)
        add_to_history(user_id, "ai", tour_intent_response)
        return {
            "response": tour_intent_response,
            "context_used": True,
            "is_fallback": False,
            "is_predefined": False,
        }

    # PASO 1: Obtener historial del usuario (CORRECCIÓN #4)
    history = get_history(user_id)

    # PASO 2: Recuperar documentos relevantes
    retriever = get_retriever()
    if retriever is None:
        # Flag explícito: sin base vectorial no hay posibilidad de resolver
        result = build_fallback_response()
        add_to_history(user_id, "human", question)
        add_to_history(user_id, "ai", result["response"])
        return result

    try:
        docs = retriever.invoke(question)

        # Formatear contexto con metadata + imágenes incluidas
        context_parts = []
        for doc in docs:
            meta = doc.metadata
            # Encabezado de metadata estructurada
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
            # Contenido del chunk
            context_parts.append(doc.page_content)
            # Incluir URLs de imágenes del catálogo (lookup por source filename)
            source = meta.get("source", "")
            filename = os.path.basename(source) if source else ""
            tour_id = _source_to_tour_id.get(filename, meta.get("tour_id", ""))
            images = _tour_images_map.get(tour_id, [])
            if images:
                context_parts.append("Imágenes disponibles:")
                for img in images:
                    context_parts.append(f"  - ![img]({img['url']}): {img.get('caption', img.get('alt', ''))}")
        context = "\n\n".join(context_parts)

        # PASO 3: PUNTO DE DECISIÓN EXPLÍCITO DEL FALLBACK
        # Si el retriever no devolvió contexto relevante, se aplica el fallback
        # directamente SIN llamar al LLM. El flag is_fallback=True se decide
        # aquí, en el punto donde se determina que no hay información.
        if not context.strip():
            result = build_fallback_response()
            add_to_history(user_id, "human", question)
            add_to_history(user_id, "ai", result["response"])
            return result

        # PASO 4: Construir el LLM (solo se llama cuando SÍ hay contexto)
        llm = get_llm()

        # PASO 5: Construir prompt con historial (CORRECCIÓN #4)
        system_msg = SYSTEM_PROMPT.format(
            context=context,
            question=question
        )

        # Agregar historial al contexto de la conversación
        messages = [("system", system_msg)]

        # Agregar últimos turnos del historial (máximo 6 mensajes)
        for msg in history[-6:]:
            messages.append((msg["role"], msg["content"]))

        # Agregar la pregunta actual
        messages.append(("human", question))

        # PASO 6: Invocar al LLM
        result_llm = llm.invoke(messages)
        response_text = result_llm.content

        # PASO 6b: Reubicar imagen markdown antes de la pregunta final
        # El LLM tiende a poner la imagen al final; la movemos antes del
        # cierre para mejor UX visual.
        import re as _re_img
        _img_pattern = _re_img.compile(r'\n*!\[([^\]]*)\]\(([^)]+)\)\s*$')
        _img_match = _img_pattern.search(response_text)
        if _img_match:
            img_tag = _img_match.group(0).strip()
            response_text = _img_pattern.sub('', response_text).rstrip()
            # Buscar la última línea que contenga pregunta o offer
            lines = response_text.split('\n')
            insert_idx = len(lines)  # default: al final
            for i in range(len(lines) - 1, -1, -1):
                line = lines[i].strip()
                if line and ('?' in line or 'gustaría' in line or 'reservar' in line or 'consulta' in line):
                    insert_idx = i
                    break
            # Insertar imagen antes de la línea de pregunta/offer
            lines.insert(insert_idx, '')
            lines.insert(insert_idx + 1, img_tag)
            response_text = '\n'.join(lines)

        # CAPA FINAL DE DETECCIÓN DE FALLBACK (corrección híbrida):
        # si el LLM generó el texto del fallback por su cuenta —con posibles
        # variaciones idiomáticas (ej. "Não dispongo...")— se fuerza
        # is_fallback=True aunque los puntos de decisión previos hayan
        # permitido la llamada al LLM con contexto. Se aplica SIEMPRE,
        # en cualquier idioma, antes de loggear la interacción.
        is_fb = is_fallback_response(response_text)

        # CAPA FINAL DE DETECCIÓN DE ESCALAMIENTO (misma estrategia):
        # detecta la frase de confirmación de handoff aunque el LLM la
        # varíe mínimamente (ej. acentos). Se aplica tras la llamada al LLM.
        is_esc = is_escalation_response(response_text)

        # PRIORIDAD ENTRE DETECCIONES: si el LLM emitiera por error AMBAS
        # frases (fallback + handoff) en una misma respuesta, el FALLBACK
        # tiene prioridad conceptual (sin información → handoff implícito).
        # Ambos flags quedan en True: is_fallback decide resolved_autonomously
        # y is_escalation decide escalated_to_human, sin conflicto entre sí.

        # Guardar en historial
        add_to_history(user_id, "human", question)
        add_to_history(user_id, "ai", response_text)

        return {
            "response": response_text,
            "context_used": True,
            "is_fallback": is_fb,
            "is_escalation": is_esc or is_fb,
            "is_predefined": False,
        }

    except RateLimitError as e:
        # RATE-LIMIT LOG: registro separado para contar ocurrencias en sustentación
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        rate_limit_msg = f"[{ts}] Rate limit (429) en {LLM_PROVIDER}: {e}\n"
        print(f"[RATE-LIMIT] {rate_limit_msg.strip()}")
        try:
            os.makedirs("logs", exist_ok=True)
            with open("logs/rate_limits.log", "a", encoding="utf-8") as f:
                f.write(rate_limit_msg)
        except Exception:
            pass
        result = build_rate_limit_response()
        add_to_history(user_id, "human", question)
        add_to_history(user_id, "ai", result["response"])
        return result

    except Exception as e:
        import traceback
        print(f"[ERROR] Fallo en la cadena RAG: {e}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        result = build_fallback_response()
        result["response"] = "Lo siento, hubo un error técnico. Por favor, intenta nuevamente o contacta a un asesor."
        add_to_history(user_id, "human", question)
        add_to_history(user_id, "ai", result["response"])
        return result


# ============================================================
# MODELOS DE DATOS (Pydantic)
# ============================================================

class TestChatRequest(BaseModel):
    """Modelo para el endpoint /test-chat"""
    user_id: str
    message: str
    action: Optional[str] = None
    context: Optional[List[str]] = None
    client_message_id: Optional[str] = None


# Respuestas de navegación UI por idioma (no pasan por el RAG)
SHOW_MORE_INTRO = {
    "es": "Estas son las opciones restantes:",
    "en": "Here are the remaining options:",
    "pt": "Aqui estão as opções restantes:",
    "fr": "Voici les options restantes :",
}


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/webhook")
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    """Verificación del webhook de Meta (WhatsApp/Messenger)."""
    if META_VERIFY_TOKEN and hub_mode == "subscribe" and hub_verify_token == META_VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge or "")
    return JSONResponse(status_code=403, content={"error": "Token de verificación inválido"})


@app.post("/webhook")
async def receive_message(request: Request):
    """Recepción de mensajes de Meta (WhatsApp/Messenger)."""
    start_time = time.time()

    if not META_APP_SECRET:
        return JSONResponse(status_code=503, content={"error": "Webhook no configurado"})
    raw_body = await request.body()
    expected_signature = "sha256=" + hmac.new(
        META_APP_SECRET.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    supplied_signature = request.headers.get("X-Hub-Signature-256", "")
    if not hmac.compare_digest(expected_signature, supplied_signature):
        return JSONResponse(status_code=403, content={"error": "Firma inválida"})

    try:
        body = await request.json()

        try:
            entry = body.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            messages = value.get("messages", [])
            statuses = value.get("statuses", [])

            # ── STATUS WEBHOOK (delivery reports) ──────────────────────
            if statuses and not messages:
                for st in statuses:
                    print(f"[WA DELIVERY STATUS] "
                          f"status={st.get('status')} "
                          f"message_id={st.get('id')} "
                          f"recipient_id={st.get('recipient_id')} "
                          f"recipient_user_id={st.get('recipient_user_id', 'N/A')} "
                          f"recipient_parent_user_id={st.get('recipient_parent_user_id', 'N/A')} "
                          f"errors={st.get('errors', [])} "
                          f"error_code={st.get('errors', [{}])[0].get('code', 'N/A') if st.get('errors') else 'N/A'} "
                          f"error_title={st.get('errors', [{}])[0].get('title', 'N/A') if st.get('errors') else 'N/A'}")
                return JSONResponse(status_code=200, content={"status": "ok"})

            # ── INBOUND MESSAGE ────────────────────────────────────────
            if messages:
                msg = messages[0]
                contacts = value.get("contacts", [])
                contact = contacts[0] if contacts else {}

                user_message = msg.get("text", {}).get("body", "")
                phone_number_id = value.get("metadata", {}).get("phone_number_id")

                # Extract identifiers from contacts (most reliable source)
                contact_wa_id = contact.get("wa_id", "")
                contact_user_id = contact.get("user_id", "")
                contact_parent_user_id = contact.get("parent_user_id", "")

                # Extract identifiers from message
                msg_from = msg.get("from", "")
                msg_from_user_id = msg.get("from_user_id", "")
                msg_from_parent_user_id = msg.get("from_parent_user_id", "")

                # Determine phone_number: prefer contacts[].wa_id, fallback to message.from
                phone_number = contact_wa_id or (msg_from if msg_from and msg_from.isdigit() else "")

                # Determine BSUID: prefer contacts[].user_id, fallback to message.from_user_id
                bsuid = contact_user_id or msg_from_user_id or ""

                # Determine parent BSUID
                parent_bsuid = contact_parent_user_id or msg_from_parent_user_id or ""

                # Determine user_id for internal use: prefer phone, then BSUID
                user_id = phone_number or bsuid or msg_from or "unknown"

                print(f"[WA INBOUND] "
                      f"from={msg_from} "
                      f"from_user_id={msg_from_user_id} "
                      f"from_parent_user_id={msg_from_parent_user_id} "
                      f"contact.wa_id={contact_wa_id} "
                      f"contact.user_id={contact_user_id} "
                      f"contact.parent_user_id={contact_parent_user_id} "
                      f"selected_phone={phone_number} "
                      f"selected_bsuid={bsuid} "
                      f"selected_parent_bsuid={parent_bsuid} "
                      f"user_id={user_id}")

                channel = "whatsapp"
            else:
                user_id = body.get("user_id", "test_user")
                user_message = body.get("message", "")
                channel = body.get("channel", "test")
                phone_number_id = None
                phone_number = ""
                bsuid = ""
                parent_bsuid = ""
        except (IndexError, KeyError):
            user_id = body.get("user_id", "test_user")
            user_message = body.get("message", "")
            channel = body.get("channel", "test")
            phone_number_id = None
            phone_number = ""
            bsuid = ""
            parent_bsuid = ""

        if not user_message:
            return JSONResponse(status_code=400, content={"error": "No se proporcionó un mensaje válido"})

        detected_lang = detect_language(user_message)
        rag_result = rag_chain(user_message, user_id=user_id)
        bot_response = rag_result["response"]

        # CORRECCIÓN #3: resolved_autonomously = True SOLO si no es fallback
        resolved_autonomously = not rag_result["is_fallback"]
        # Red de seguridad: el flag de escalamiento de la cadena (si existe)
        # tiene prioridad; needs_escalation() cubre el resto.
        escalated_to_human = rag_result.get("is_escalation", False) or needs_escalation(bot_response)
        # CORRECCIÓN #4: flag para separar respuestas predefinidas en métricas
        is_predefined = rag_result.get("is_predefined", False)
        interaction_type = "predefined" if is_predefined else "llm"
        is_rate_limit = rag_result.get("is_rate_limit", False)
        latency_ms = (time.time() - start_time) * 1000

        database.log_interaction(
            user_id=user_id,
            channel=channel,
            detected_language=detected_lang,
            user_message=user_message,
            bot_response=bot_response,
            resolved_autonomously=resolved_autonomously,
            latency_ms=latency_ms,
            escalated_to_human=escalated_to_human,
            is_predefined_response=is_predefined,
            interaction_type=interaction_type,
            is_rate_limit=is_rate_limit,
            db_path=SQLITE_DB_PATH,
        )

        # Enviar respuesta saliente a WhatsApp Cloud API si el canal es WhatsApp
        if channel == "whatsapp" and user_id != "unknown":
            send_whatsapp_message(
                text=bot_response,
                to_phone=phone_number if phone_number else None,
                recipient_bsuid=bsuid if bsuid else None,
                phone_number_id=phone_number_id,
            )

        return JSONResponse(status_code=200, content={
            "status": "ok",
            "response": bot_response,
            "resolved_autonomously": resolved_autonomously,
            "escalated_to_human": escalated_to_human,
            "latency_ms": round(latency_ms, 2),
        })

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return JSONResponse(status_code=500, content={"error": f"Error interno: {str(e)}"})


@app.get("/metrics")
async def get_metrics():
    """Resumen de métricas para evaluación de la investigación."""
    try:
        summary = database.get_metrics_summary(SQLITE_DB_PATH)
        return JSONResponse(status_code=200, content=summary)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Error al obtener métricas: {str(e)}"})


@app.post("/test-chat")
async def test_chat(request: TestChatRequest):
    """
    Prueba manual del bot sin depender de Meta.
    Incluye conversation_history por usuario.

    Auditoría #2: si action == "show_more_options", la respuesta se genera
    directamente con las opciones restantes SIN pasar por la cadena RAG y se
    registra con interaction_type="ui_navigation" — no cuenta como éxito ni
    como fallo del RAG en las métricas.

    Auditoría #3: client_message_id permite idempotencia en reintentos.
    """
    start_time = time.time()

    try:
        # ---- ACCIÓN DE NAVEGACIÓN UI (Ver más opciones) ----
        if request.action == "show_more_options":
            items = [str(x).strip() for x in (request.context or []) if str(x).strip()]
            lang = detect_language(" ".join(items)) if items else "es"
            intro = SHOW_MORE_INTRO.get(lang, SHOW_MORE_INTRO["es"])
            if items:
                bot_response = intro + "\n" + "\n".join(f"- {x}" for x in items)
            else:
                bot_response = intro
            latency_ms = (time.time() - start_time) * 1000

            database.log_interaction(
                user_id=request.user_id,
                channel="test",
                detected_language=lang,
                user_message=request.message,
                bot_response=bot_response,
                resolved_autonomously=False,
                latency_ms=latency_ms,
                escalated_to_human=False,
                is_predefined_response=False,
                interaction_type="ui_navigation",
                client_message_id=request.client_message_id,
                db_path=SQLITE_DB_PATH,
            )

            return JSONResponse(status_code=200, content={
                "status": "ok",
                "response": bot_response,
                "resolved_autonomously": False,
                "escalated_to_human": False,
                "detected_language": lang,
                "latency_ms": round(latency_ms, 2),
            })

        # ---- FLUJO NORMAL (RAG) ----
        detected_lang = detect_language(request.message)
        rag_result = rag_chain(request.message, user_id=request.user_id)
        bot_response = rag_result["response"]

        # CORRECCIÓN #3: resolved_autonomously correcto
        resolved_autonomously = not rag_result["is_fallback"]
        # Red de seguridad: el flag de escalamiento de la cadena (si existe)
        # tiene prioridad; needs_escalation() cubre el resto.
        escalated_to_human = rag_result.get("is_escalation", False) or needs_escalation(bot_response)
        # CORRECCIÓN #4: flag para separar respuestas predefinidas en métricas
        is_predefined = rag_result.get("is_predefined", False)
        interaction_type = "predefined" if is_predefined else "llm"
        is_rate_limit = rag_result.get("is_rate_limit", False)
        latency_ms = (time.time() - start_time) * 1000

        database.log_interaction(
            user_id=request.user_id,
            channel="test",
            detected_language=detected_lang,
            user_message=request.message,
            bot_response=bot_response,
            resolved_autonomously=resolved_autonomously,
            latency_ms=latency_ms,
            escalated_to_human=escalated_to_human,
            is_predefined_response=is_predefined,
            interaction_type=interaction_type,
            is_rate_limit=is_rate_limit,
            client_message_id=request.client_message_id,
            db_path=SQLITE_DB_PATH,
        )

        return JSONResponse(status_code=200, content={
            "status": "ok",
            "response": bot_response,
            "resolved_autonomously": resolved_autonomously,
            "escalated_to_human": escalated_to_human,
            "detected_language": detected_lang,
            "latency_ms": round(latency_ms, 2),
        })

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return JSONResponse(status_code=500, content={"error": f"Error en test-chat: {str(e)}"})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Panel de administración para el staff."""
    try:
        metrics = database.get_metrics_summary(SQLITE_DB_PATH)
        interactions = database.get_recent_interactions(limit=20, db_path=SQLITE_DB_PATH)
        html = get_dashboard_html(metrics, interactions)
        return HTMLResponse(content=html)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error al cargar dashboard: {e}</h1>", status_code=500)


@app.get("/chat", response_class=HTMLResponse)
async def chat():
    """Interfaz de chat moderna estilo WhatsApp."""
    html = get_chat_html()
    return HTMLResponse(content=html)


@app.get("/chat-test", response_class=HTMLResponse)
async def chat_test():
    """
    Endpoint GET /chat-test — Interfaz de chat moderna (capa de presentación).

    Sirve el mismo HTML que /chat. Consume el endpoint /test-chat existente;
    no agrega lógica de backend ni afecta el registro de métricas.
    """
    html = get_chat_html()
    return HTMLResponse(content=html)


@app.get("/history/{user_id}")
async def get_user_history(user_id: str):
    """Endpoint para consultar el historial de conversación de un usuario."""
    history = get_history(user_id)
    return JSONResponse(status_code=200, content={
        "user_id": user_id,
        "turns": len(history),
        "history": history,
    })


@app.delete("/history/{user_id}")
async def clear_user_history(user_id: str):
    """Endpoint para limpiar el historial de un usuario."""
    clear_history(user_id)
    return JSONResponse(status_code=200, content={"status": "ok", "message": f"Historial de {user_id} limpiado"})


IMAGES_DIR = os.path.join(os.path.dirname(__file__), "data", "images")


@app.get("/images/{filename}")
async def serve_image(filename: str):
    """
    Endpoint estático para servir imágenes de tours locales.

    Permite que el chat UI muestre imágenes almacenadas en data/images/.
    Las imágenes deben estar en formato JPG/PNG/WebP.

    Uso: GET /images/cusco-city-tour.jpg
    """
    import re as _re
    # Seguridad: solo permitir nombres de archivo seguros
    if not _re.match(r'^[\w\-\.]+\.(jpg|jpeg|png|webp|gif)$', filename, _re.IGNORECASE):
        return JSONResponse(status_code=400, content={"error": "Nombre de archivo inválido"})

    file_path = os.path.join(IMAGES_DIR, filename)
    if not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"error": "Imagen no encontrada"})

    from fastapi.responses import FileResponse
    return FileResponse(file_path, media_type="image/jpeg")


@app.get("/")
async def root():
    """Endpoint raíz — Información del servicio"""
    return {
        "service": "Texeira Travel Tour - Agente RAG",
        "version": "2.0.0-tesis",
        "status": "running",
        "features": [
            "Cero alucinaciones (prompt estricto)",
            "Detección de idioma con langdetect",
            "Conversation history por usuario",
            "Métricas de investigación",
        ],
        "endpoints": {
            "GET /chat": "Interfaz de chat moderna",
            "POST /test-chat": "Prueba manual del bot",
            "GET /metrics": "Métricas de investigación",
            "GET /dashboard": "Panel de administración",
            "GET /history/{user_id}": "Historial de conversación",
            "DELETE /history/{user_id}": "Limpiar historial",
        },
    }
