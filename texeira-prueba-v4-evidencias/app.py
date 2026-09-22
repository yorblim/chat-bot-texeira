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
import re
import json
import hashlib
import hmac
import time
import uuid
import asyncio
from typing import Optional, Dict, List

from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel

# --- v4-evidencias: evidence layer ---
from src.evidence import (
    detect_conflicts, build_context_for_entity,
    build_context_for_question, get_listing,
    get_includes, get_route, stats, FIELD_POLICIES,
    get_facts, is_product_confirmed,
)
from trial_support import (
    detect_entity_from_question, detect_field_from_question,
    ENTITY_IDS as _BASE_CONFIRMED_PRODUCTS, NAMES as _ENTITY_NAMES_LIST,
)

class DynamicEntityNameMap(dict):
    """Mapeo dinámico de entity_id a nombre legible, consultando el catálogo dinámico."""
    def get(self, key, default=None):
        if dict.__contains__(self, key):
            return dict.__getitem__(self, key)
        try:
            from catalog_service import get_tour_by_id
            tour = get_tour_by_id(key)
            if tour:
                return tour["name"]
        except Exception:
            pass
        return default if default is not None else key

    def __getitem__(self, key):
        val = self.get(key)
        if val is not None:
            return val
        raise KeyError(key)

class DynamicConfirmedProducts(list):
    """Colección dinámica de productos confirmados que incluye tours creados por la agencia."""
    def __contains__(self, key):
        if list.__contains__(self, key):
            return True
        try:
            from catalog_service import get_tour_by_id
            tour = get_tour_by_id(key)
            return bool(tour and tour.get("is_active", 1))
        except Exception:
            return False

CONFIRMED_PRODUCTS = DynamicConfirmedProducts(_BASE_CONFIRMED_PRODUCTS)
ENTITY_NAME_MAP = DynamicEntityNameMap(zip(_BASE_CONFIRMED_PRODUCTS, _ENTITY_NAMES_LIST))

from langdetect import detect, DetectorFactory, LangDetectException
from openai import RateLimitError
DetectorFactory.seed = 0

import database
from admin_dashboard import get_dashboard_html
from chat_ui import get_chat_html

# ============================================================
# CONFIGURACIÓN
# ============================================================

# Entorno aislado: cargar solo configuración LLM, nunca credenciales de Meta.
from pathlib import Path
_trial_root = Path(__file__).resolve().parent
from runtime_settings import configure
_whatsapp_enabled, _messenger_enabled = configure()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
CHROMA_HYBRID_DIR = os.getenv("CHROMA_HYBRID_DIR", "./chroma_hybrid_db")
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "./texeira_logs.db")
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")

# Facebook Messenger
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
FB_APP_SECRET = os.getenv("FB_APP_SECRET", "")
if _messenger_enabled:
    print('[FB CONFIG] Messenger habilitado.')

# Notificación a asesor humano vía WhatsApp
ADVISOR_WHATSAPP_PHONE = os.getenv("ADVISOR_WHATSAPP_PHONE", "")
ADVISOR_NOTIFICATIONS_ENABLED = os.getenv('TEXEIRA_ENABLE_ADVISOR_NOTIFICATIONS', 'false').lower() == 'true'
if ADVISOR_WHATSAPP_PHONE:
    print(f'[ADVISOR CONFIG] Teléfono de asesor configurado: {ADVISOR_WHATSAPP_PHONE[:4]}****')

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
    print('[WA CONFIG] Modo de prueba activo; identificadores no mostrados.')

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


# ============================================================
# SERVICIOS DE MENSAJERÍA Y MOTOR VISUAL (MODULARIZADOS)
# ============================================================
from src.services.whatsapp import send_whatsapp_message, send_whatsapp_image, send_whatsapp_document
from src.services.messenger import send_messenger_message
from src.visual.visual_engine import (
    format_whatsapp_text,
    get_tour_image_data,
    get_tour_brochure_data,
    is_photo_requested,
    is_brochure_requested,
)


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
    if tail not in normalized or "asesor" not in normalized:
        return False
    # Verificar si está en una negación (el LLM dice que NO puede contactar)
    import re as _re
    negation_patterns = [
        r'\bno puedo\b', r'\bno puede\b', r'\bno es posible\b',
        r'\bno dispongo\b', r'\bno tengo\b', r'\bno hay\b',
        r'\bno contactar\b', r'\bno prometer\b',
    ]
    # Buscar la frase "se pondra en contacto" y verificar si hay negación cerca
    tail_idx = normalized.find(tail)
    if tail_idx >= 0:
        # Obtener la oración que contiene la frase
        sentence_start = normalized.rfind('.', 0, tail_idx)
        sentence_start = max(0, sentence_start + 1 if sentence_start >= 0 else 0)
        sentence = normalized[sentence_start:tail_idx + len(tail) + 50].strip()
        if any(_re.search(pat, sentence) for pat in negation_patterns):
            return False
    return True

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

REGLA #3 — DISEÑO VISUAL Y ESTÉTICA PARA WHATSAPP:
Tus respuestas deben tener un diseño visual premium, estructurado y atractivo, ideal para WhatsApp:
- Usa encabezados amables y elegantes con emojis turísticos (✨, 🏔️, 🏛️, 🌈, 🚆, 🎒, 📍, 🕒).
- Resalta títulos de tours siempre en *Negrita*.
- Usa viñetas con emojis temáticos en vez de guiones o asteriscos feos:
  🕒 *Horarios:* ...
  📍 *Recorrido:* ...
  🎒 *Incluye:* ...
  🎟️ *Entradas:* ...
  💡 *Recomendación:* ...
  NUNCA uses asteriscos anidados como '* *Horarios:*'.
- Si el turista consulta sobre presupuesto ("no es mucho mi presupuesto", "económico", "barato", "descuentos"):
  Sé sumamente empático, cálido y orientador. Menciona que en Texeira Travel Tour contamos con opciones ideales y accesibles (como City Tour Cusco de medio día o Valle Sagrado), e invítalo cordialmente a coordinar con un asesor humano para consultar ofertas y promociones personalizadas a su presupuesto.
- Concluye con un mensaje cálido de invitación o pregunta de seguimiento (ejemplo: "¿Te gustaría consultar disponibilidad o cotizar alguno de estos destinos? ✨").

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

from conversation_memory import ConversationMemory, suspend_recording

MAX_HISTORY_TURNS = 10
conversation_history = ConversationMemory(lambda: SQLITE_DB_PATH, MAX_HISTORY_TURNS * 2)


def get_history(user_id: str) -> List[dict]:
    return conversation_history.get(user_id, [])


def add_to_history(user_id: str, role: str, content: str):
    conversation_history.append(user_id, role, content)


def add_history_turn(user_id: str, question: str, response: str):
    conversation_history.add_turn(user_id, question, response)


def clear_history(user_id: str):
    conversation_history.clear(user_id)


def update_last_history_response(user_id: str, content: str):
    conversation_history.update_last_response(user_id, content)


# ============================================================
# INICIALIZACIÓN DE LA APLICACIÓN
# ============================================================

app = FastAPI(
    title="Texeira Travel Tour - Agente RAG",
    description="Agente conversacional RAG para asistencia turística en WhatsApp/Messenger",
    version="2.0.0-tesis",
)


from auth_middleware import install_auth
install_auth(app)

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
            request_timeout=10,
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
    Detecta si la respuesta indica transferencia ejecutada a humano.
    No marcar orientación como "contacta a" como escalamiento.
    Solo incluye indicadores de handoff efectivo o fallback.
    """
    import re as _re
    # Solo indicadores de transferencia efectiva (no orientación)
    escalation_indicators = [
        "asesor humano",
        "personal de la agencia",
        "se pondrá en contacto",
        "representante",
        "revisión humana",
        "transferirte a",
        "te conecto con",
    ]
    response_lower = response.lower()
    
    for indicator in escalation_indicators:
        idx = response_lower.find(indicator)
        if idx >= 0:
            # Verificar si está en una negación
            sentence_start = response_lower.rfind('.', 0, idx)
            sentence_start = max(0, sentence_start + 1 if sentence_start >= 0 else 0)
            sentence = response_lower[sentence_start:idx+len(indicator)+50].strip()
            negation_patterns = [
                r'\bno\b', r'\bsin\b', r'\bevitar\b', r'\bevita\b', r'\bevite\b',
                r'\bno prometer\b', r'\bno contactar\b', r'\bno prometa\b', r'\bno contacte\b',
                r'\bno confirmar\b', r'\bno puede\b', r'\bno puedo\b', r'\bno es posible\b',
                r'\bno dispongo\b', r'\bno tengo\b', r'\bno hay\b'
            ]
            if any(_re.search(pat, sentence) for pat in negation_patterns):
                continue
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
    "contacto": "📞 *Contacto Oficial Texeira Travel Tour:*\n• Teléfonos / WhatsApp: +51 953 767 860 / +51 984 679 715\n• Email: texeiratraveltour@hotmail.com\n• Dirección: Calle Carmen Quicllu N° 250, Centro Histórico de Cusco, Perú 🇵🇪\n• Razón Social: Texeira Travel — Travel Agency E.I.R.L.",
    "teléfono": "📞 *Teléfonos de Atención:*\n• Principal: +51 953 767 860\n• Secundario: +51 984 679 715\n📧 Email: texeiratraveltour@hotmail.com",
    "whatsapp": "📱 *WhatsApp Oficial de Atención:* +51 953 767 860\n¡Escríbenos con total confianza para ayudarte con tus planes y reservas en Cusco! ✨",
    "ubicación": "📍 *Nuestra Oficina:*\nCalle Carmen Quicllu N° 250\nCentro Histórico de Cusco, Perú 🇵🇪\nHorario: Lunes a Domingo 7:00 AM a 9:00 PM",
    "dónde están": "📍 *Nuestra Oficina:*\nCalle Carmen Quicllu N° 250\nCentro Histórico de Cusco, Perú 🇵🇪\nHorario: Lunes a Domingo 7:00 AM a 9:00 PM",
    "dirección": "📍 *Dirección de Oficina:*\nCalle Carmen Quicllu N° 250, Centro Histórico de Cusco, Perú 🇵🇪",
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
        header = "✨ *Featured Tours — Texeira Travel Tour* 🇵🇪\n\nThese are our available tours and excursions in Cusco:"
        name_key = "name_en"
        closing = "💬 *Which one would you like to explore or book?* ✨\n_Send us the tour name and we will provide full details (schedule, itinerary, recommendations)._"
    elif lang == "pt":
        header = "✨ *Passeios em Destaque — Texeira Travel Tour* 🇵🇪\n\nEstes são nossos passeios disponíveis em Cusco:"
        name_key = "name_pt"
        closing = "💬 *Qual deles você gostaria de conhecer?* ✨\n_Envie-nos o nome do passeio para detalhes e itinerário._"
    elif lang == "fr":
        header = "✨ *Circuits — Texeira Travel Tour* 🇵🇪\n\nVoici nos circuits disponibles à Cusco:"
        name_key = "name"
        closing = "💬 *Lequel vous intéresse?* ✨\n_Écrivez-nous le nom du circuit pour plus de détails._"
    else:
        header = "✨ *Tours y Experiencias — Texeira Travel Tour* 🇵🇪\n\nTenemos estos tours disponibles para tu viaje a Cusco:"
        name_key = "name"
        closing = "💬 *¿Cuál te interesa conocer o cotizar?* ✨\n_Escríbeme el nombre del tour y con gusto te daré todos los detalles (itinerario, horarios y recomendaciones)._"

    lines = [header, ""]
    tour_emojis = {
        "city": "🏛️",
        "machu": "🏔️",
        "valle": "🌾",
        "colores": "🌈",
        "vinicunca": "🌈",
        "humantay": "💎",
        "maras": "🧂",
        "moray": "🧂",
        "salkantay": "🥾",
        "inka": "🥾",
        "inca": "🥾",
        "titicaca": "⛵",
        "colca": "🦅",
        "sol": "☀️",
        "waqra": "🏰",
        "choquequirao": "🏕️",
        "mistico": "🔮",
    }
    for t in tours:
        name = t.get(name_key, t.get("name", "Tour"))
        price_usd = t.get("price_usd", "")
        duration = t.get("duration_hours", "")
        dur_text = ""
        if duration:
            if duration >= 24:
                days = int(duration // 24)
                dur_text = f" ({days} días)" if lang != "en" else f" ({days} days)"
            else:
                dur_text = f" ({duration}h)"
        price_text = f" — *${price_usd} USD*" if price_usd else ""
        lower_name = name.lower()
        icon = "📍"
        for k, emoji in tour_emojis.items():
            if k in lower_name:
                icon = emoji
                break
        lines.append(f"• {icon} *{name}*{dur_text}{price_text}")

    lines.append("")
    lines.append(closing)

    return "\n".join(lines)


# ============================================================
# EVIDENCE LAYER — V4-EVIDENCIAS
# ============================================================

def _get_sources_from_conflicts(conflicts: list) -> list:
    """Extract source IDs from conflict list."""
    sources = set()
    for c in conflicts:
        src_a = c.get('source_a', {})
        src_b = c.get('source_b', {})
        if src_a.get('source_id'):
            sources.add(src_a['source_id'])
        if src_b.get('source_id'):
            sources.add(src_b['source_id'])
    return list(sources)


def _evaluate_evidence_layer(question: str, user_id: str) -> dict | None:
    """
    Evalúa si la pregunta puede resolverse SIN LLM usando el evidence layer.
    Retorna dict con respuesta si se resolvió, None si debe continuar a RAG.

    Casos resueltos sin LLM:
    A: Horarios con conflicto → respuesta determinista solicitando confirmación
    B: Datos confirmed/sin conflicto → respuesta directa
    C: Unknown que requiere confirmación de agencia → fallback
    D: Producto no confirmado → fallback
    E: No se detectó entity/field relevante → None (continuar a RAG)
    """
    q_lower = question.lower().strip()

    entity_detected = detect_entity_from_question(question)
    campo_detected = detect_field_from_question(question)
    is_listing = _is_listing_question(q_lower)
    is_price_q = _is_price_question(q_lower)
    is_schedule_q = _is_schedule_question(q_lower)
    is_includes_q = _is_includes_question(q_lower)
    is_route_q = _is_route_question(q_lower)

    # --- CASO A: Horarios con conflicto → determinista sin LLM ---
    if is_schedule_q and entity_detected:
        conflicts = detect_conflicts(entity_detected, 'schedule')
        if conflicts:
            add_to_history(user_id, "human", question)
            response = _build_conflict_response(entity_detected, 'schedule', conflicts)
            add_to_history(user_id, "ai", response)
            return {
                "response": response,
                "context_used": True,
                "is_fallback": False,
                "is_predefined": False,
                "response_route": "evidence_conflict",
                "evidence_status": "conflict",
                "needs_confirmation": True,
                "conflict_detected": True,
                "sources_used": _get_sources_from_conflicts(conflicts),
            }

    # --- CASO B: Listing de tours → respuesta directa ---
    if is_listing:
        add_to_history(user_id, "human", question)
        response = get_listing()
        add_to_history(user_id, "ai", response)
        return {
            "response": response,
            "context_used": True,
            "is_fallback": False,
            "is_predefined": False,
            "response_route": "evidence_listing",
            "evidence_status": "confirmed",
            "needs_confirmation": False,
            "conflict_detected": False,
            "sources_used": ["F1", "F2", "F3"],
        }

    # --- CASO C: Precio oficial unknown → no inventar ---
    if is_price_q and entity_detected:
        price_facts = get_facts(entity_detected, 'official_price')
        market_facts = get_facts(entity_detected, 'market_price')
        price_conflicts = detect_conflicts(entity_detected, 'official_price')
        if price_conflicts:
            add_to_history(user_id, "human", question)
            response = _build_conflict_response(entity_detected, 'official_price', price_conflicts)
            add_to_history(user_id, "ai", response)
            return {
                "response": response,
                "context_used": True,
                "is_fallback": False,
                "is_predefined": False,
                "response_route": "evidence_conflict",
                "evidence_status": "conflict",
                "needs_confirmation": True,
                "conflict_detected": True,
                "sources_used": _get_sources_from_conflicts(price_conflicts),
            }
        if price_facts:
            entity_name = ENTITY_NAME_MAP.get(entity_detected, entity_detected)
            price_val = price_facts[0].value
            add_to_history(user_id, "human", question)
            response = (
                f"El precio oficial de {entity_name} es de {price_val} por persona "
                "(servicio compartido). Para coordinar tu reserva o consultar disponibilidad, escribe: asesor."
            )
            add_to_history(user_id, "ai", response)
            return {
                "response": response,
                "context_used": True,
                "is_fallback": False,
                "is_predefined": False,
                "response_route": "evidence_confirmed_price",
                "evidence_status": "confirmed",
                "needs_confirmation": False,
                "conflict_detected": False,
                "sources_used": [f.source_id for f in price_facts],
            }
        if not price_facts and not market_facts:
            entity_name = ENTITY_NAME_MAP.get(entity_detected, entity_detected)
            add_to_history(user_id, "human", question)
            response = (
                f"No dispongo de precios oficiales para {entity_name}. "
                "Los precios que circulan son referencias de mercado. "
                "Te recomiendo contactar directamente a la agencia para obtener la tarifa vigente."
            )
            add_to_history(user_id, "ai", response)
            return {
                "response": response,
                "context_used": True,
                "is_fallback": False,
                "is_predefined": False,
                "response_route": "evidence_unknown_price",
                "evidence_status": "unknown",
                "needs_confirmation": True,
                "conflict_detected": False,
                "sources_used": [],
            }

    # --- CASO D: Inclusiones con conflicto o exclusión → determinista ---
    if is_includes_q and entity_detected:
        includes_conflicts = detect_conflicts(entity_detected, 'includes')
        if includes_conflicts:
            add_to_history(user_id, "human", question)
            response = _build_conflict_response(entity_detected, 'includes', includes_conflicts)
            add_to_history(user_id, "ai", response)
            return {
                "response": response,
                "context_used": True,
                "is_fallback": False,
                "is_predefined": False,
                "response_route": "evidence_conflict",
                "evidence_status": "conflict",
                "needs_confirmation": True,
                "conflict_detected": True,
                "sources_used": _get_sources_from_conflicts(includes_conflicts),
            }
        # Verificar si el item preguntado está EXCLUIDO
        q_words = question.lower().split()
        excludes = get_facts(entity_detected, 'excludes')
        for ex in excludes:
            ex_item = str(ex.item).lower().replace('_', ' ')
            if any(w in ex_item for w in q_words if len(w) > 3):
                entity_name = ENTITY_NAME_MAP.get(entity_detected, entity_detected)
                add_to_history(user_id, "human", question)
                response = (
                    f"{entity_name} no incluye {ex.item.replace('_', ' ')}. "
                    f"Esto está confirmado como excluido por la fuente {ex.source_id}."
                )
                add_to_history(user_id, "ai", response)
                return {
                    "response": response,
                    "context_used": True,
                    "is_fallback": False,
                    "is_predefined": False,
                    "response_route": "evidence_exclusion",
                    "evidence_status": "confirmed",
                    "needs_confirmation": False,
                    "conflict_detected": False,
                    "sources_used": [ex.source_id],
                }
        # Sin conflicto: construir contexto de inclusiones para el LLM
        includes_ctx = build_context_for_entity(entity_detected)
        if includes_ctx:
            add_to_history(user_id, "human", question)
            add_to_history(user_id, "ai", includes_ctx)
            return {
                "response": includes_ctx,
                "context_used": True,
                "is_fallback": False,
                "is_predefined": False,
                "response_route": "evidence_confirmed_includes",
                "evidence_status": "confirmed",
                "needs_confirmation": False,
                "conflict_detected": False,
                "sources_used": list(set(f.source_id for f in get_facts(entity_detected, 'includes'))),
            }

    # --- CASO E: Ruta/itinerario → contexto determinista ---
    if is_route_q and entity_detected:
        route_ctx = build_context_for_entity(entity_detected)
        if route_ctx:
            add_to_history(user_id, "human", question)
            add_to_history(user_id, "ai", route_ctx)
            return {
                "response": route_ctx,
                "context_used": True,
                "is_fallback": False,
                "is_predefined": False,
                "response_route": "evidence_route",
                "evidence_status": "confirmed",
                "needs_confirmation": False,
                "conflict_detected": False,
                "sources_used": list(set(f.source_id for f in get_facts(entity_detected, 'route'))),
            }

    # --- CASO F: Producto no confirmado → fallback ---
    if entity_detected and entity_detected not in CONFIRMED_PRODUCTS:
        entity_name = ENTITY_NAME_MAP.get(entity_detected, entity_detected)
        add_to_history(user_id, "human", question)
        response = (
            f"No dispongo de información confirmada sobre {entity_name}. "
            "Te recomiendo contactar directamente a la agencia para verificar disponibilidad."
        )
        add_to_history(user_id, "ai", response)
        return {
            "response": response,
            "context_used": True,
            "is_fallback": False,
            "is_predefined": False,
            "response_route": "evidence_unconfirmed_product",
            "evidence_status": "unknown",
            "needs_confirmation": True,
            "conflict_detected": False,
            "sources_used": [],
        }

    # --- CASO G: No se detectó entity/field relevante → None (continuar a RAG) ---
    return None


def _is_listing_question(q_lower: str) -> bool:
    """Detecta preguntas sobre listado de tours. Solo matches claros."""
    listing_phrases = [
        'qué tours', 'que tours', 'qué paquetes', 'que paquetes',
        'qué servicios', 'que servicios', 'qué ofrecen', 'que ofrecen',
        'qué tienen', 'que tienen', 'qué hay', 'que hay',
        'cuáles son', 'cuales son', 'what tours', 'which tours',
        'list of tours', 'what services',
    ]
    if any(phrase in q_lower for phrase in listing_phrases):
        return True
    # Preguntas muy cortas con solo "tour(s)" como palabra clave principal
    words = q_lower.split()
    if len(words) <= 5 and ('tours' in words or 'paquetes' in words or 'servicios' in words):
        return True
    return False


def _is_price_question(q_lower: str) -> bool:
    """Detecta preguntas sobre precios."""
    price_kws = ['precio', 'price', 'costo', 'cost', 'cuánto', 'cuanto', 'how much', 'valor', 'tarifa', 'fare']
    return any(kw in q_lower for kw in price_kws)


def _is_schedule_question(q_lower: str) -> bool:
    """Detecta preguntas sobre horarios."""
    schedule_kws = ['horario', 'schedule', 'hora', 'hour', 'a qué hora', 'at what time', 'sale', 'parte', 'sale a las', 'comienza']
    return any(kw in q_lower for kw in schedule_kws)


def _is_includes_question(q_lower: str) -> bool:
    """Detecta preguntas sobre inclusiones."""
    inc_kws = ['incluye', 'includes', 'incluido', 'included', 'qué incluye', 'que incluye', 'what includes', 'contiene', 'contiene']
    return any(kw in q_lower for kw in inc_kws)


def _is_route_question(q_lower: str) -> bool:
    """Detecta preguntas sobre rutas/itinerarios."""
    route_kws = ['ruta', 'route', 'itinerario', 'itinerary', 'recorrido', 'dónde va', 'where does it go', 'paradas', 'stops']
    return any(kw in q_lower for kw in route_kws)


def _build_conflict_response(entity_id: str, field: str, conflicts: list) -> str:
    """Construye respuesta determinista para conflictos SIN LLM."""
    entity_name = ENTITY_NAME_MAP.get(entity_id, entity_id)
    responses = {
        'schedule': {
            'city-tour-cusco': (
                "El horario del City Tour Cusco tiene información contradictoria en nuestras fuentes. "
                "Una fuente indica 10:00 AM - 2:00 PM / 1:30 PM - 6:30 PM, "
                "y otra indica 9:00 AM - 2:00 PM / 1:30 PM - 6:00 PM. "
                "Te recomiendo confirmar el horario vigente directamente con la agencia."
            ),
            'valle-sagrado': (
                "La hora de salida del Valle Sagrado tiene información contradictoria. "
                "Una fuente indica 7:30 AM y otra indica 7:00 AM. "
                "Te recomiendo confirmar con la agencia."
            ),
            'montana-7-colores': (
                "El horario de la Montaña de 7 Colores tiene información contradictoria. "
                "Una fuente indica salida a las 4:30 AM y otra a las 5:00 AM. "
                "Te recomiendo confirmar con la agencia."
            ),
        },
        'official_price': {
            '_default': (
                f"El precio oficial de {entity_name} tiene información contradictoria o no está confirmado. "
                "Te recomiendo contactar directamente a la agencia para obtener la tarifa vigente."
            ),
        },
        'includes': {
            '_default': (
                f"Las inclusiones de {entity_name} tienen información contradictoria entre fuentes. "
                "Te recomiendo confirmar con la agencia qué incluye actualmente."
            ),
        },
    }
    field_responses = responses.get(field, {})
    return field_responses.get(entity_id, field_responses.get('_default',
        f"La información sobre {field} de {entity_name} tiene fuentes contradictorias. "
        "Te recomiendo confirmar con la agencia."
    ))


def _filter_conflicting_facts_from_context(context: str, entity_id: str) -> str:
    """
    Filtra del contexto RAG las líneas que contienen datos conflictivos
    para el entity_id detectado, evitando que el LLM reciba datos
    contradictorios que pueda confundir como definitivos.
    """
    conflicts = detect_conflicts(entity_id, 'schedule')
    if not conflicts:
        return context

    # Recopilar todos los valores conflictivos
    conflict_values = set()
    for conflict in conflicts:
        src_a = conflict.get('source_a', {})
        src_b = conflict.get('source_b', {})
        if src_a.get('value'):
            conflict_values.add(src_a['value'].lower())
        if src_b.get('value'):
            conflict_values.add(src_b['value'].lower())

    if not conflict_values:
        return context

    # Filtrar líneas que contengan valores conflictivos
    lines = context.split('\n')
    filtered = []
    for line in lines:
        line_lower = line.lower()
        if any(cv in line_lower for cv in conflict_values):
            continue
        filtered.append(line)
    return '\n'.join(filtered)


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
            "response_route": "predefined",
            "evidence_status": "predefined",
            "needs_confirmation": False,
            "conflict_detected": False,
            "sources_used": [],
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
            "response_route": "tour_intent",
            "evidence_status": "tour_listing",
            "needs_confirmation": False,
            "conflict_detected": False,
            "sources_used": ["F1", "F2", "F3"],
        }

    # PASO 0c: EVIDENCE LAYER (v4-evidencias)
    # Determina respuesta SIN LLM cuando hay datos confirmados,
    # conflictos, o información unknown que requiere confirmación.
    evidence_result = _evaluate_evidence_layer(question, user_id)
    if evidence_result is not None:
        return evidence_result

    # PASO 1: Obtener historial del usuario (CORRECCIÓN #4)
    history = get_history(user_id)

    # PASO 2: Recuperar documentos relevantes
    retriever = get_retriever()
    if retriever is None:
        # Flag explícito: sin base vectorial no hay posibilidad de resolver
        result = build_fallback_response()
        add_to_history(user_id, "human", question)
        add_to_history(user_id, "ai", result["response"])
        result.update({
            "response_route": "no_retriever",
            "evidence_status": "unknown",
            "needs_confirmation": True,
            "conflict_detected": False,
            "sources_used": [],
        })
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

        # v4-evidencias: filtrar facts conflictivos del contexto antes del LLM
        entity_detected = detect_entity_from_question(question)
        if entity_detected:
            context = _filter_conflicting_facts_from_context(context, entity_detected)

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

# Detectar consultas sobre condiciones comerciales no confirmadas
        # C07: métodos de pago y adelanto | C08: disponibilidad/reserva | C09: precio exacto en PEN
        q_lower = question.lower()
        needs_agency_conf = False
        if any(kw in q_lower for kw in ["yape", "adelanto", "pago", "pagar", "forma de pago", "depósito", "deposito", "payment", "deposit"]):
            needs_agency_conf = True
        if any(kw in q_lower for kw in ["cupo", "cupos", "disponibilidad", "reserva", "reservar", "confirmar reserva", "availability", "reservation", "book", "booking", "spots", "open spots"]):
            needs_agency_conf = True
        if any(kw in q_lower for kw in ["exacto en soles", "en soles", "precio en pen", "tipo de cambio", "conversión", "conversion", "soles", "pen", "exchange rate"]):
            needs_agency_conf = True
        if any(kw in q_lower for kw in ["descuento", "discount", "dto", "oferta especial"]):
            needs_agency_conf = True

        # Post-procesamiento de la respuesta para correcciones específicas
        # Cargar datos de contacto de la agencia
        import json
        from pathlib import Path
        catalog_path = Path(__file__).parent / "data" / "tours_catalog.json"
        agency_contact = ""
        if catalog_path.exists():
            catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
            agency = catalog.get("agency", {})
            phone1 = agency.get("published_phone", "+51 953 767 860")
            phone2 = agency.get("published_secondary_phone", "+51 984 679 715")
            address = agency.get("published_address", "Calle Carmen Quicllu N.º 250, Cusco")
            agency_contact = f"\n\nPara contactar a la agencia:\n- Teléfonos: {phone1} / {phone2}\n- Dirección: {address}"

        # C08: corregir "fuentes de precios" por contacto de la agencia
        if "fuentes de precios" in response_text.lower() or "enlaces de las fuentes" in response_text.lower():
            import re as _re_contact
            response_text = _re_contact.sub(r'¿Te gustaría que te proporcione los enlaces de las fuentes de precios para que puedas contactar a la agencia\?', '', response_text)
            response_text = _re_contact.sub(r'te recomiendo contactar directamente a la agencia publicada en las fuentes de referencia\.?', f'te recomiendo contactar directamente a la agencia:{agency_contact}', response_text)
            response_text = _re_contact.sub(r'Consultar las políticas de reserva, cancelación y pagos directamente con ellos, ya que esta información no está confirmada en el contexto actual\.?', f'Consultar las políticas de reserva, cancelación y pagos directamente con la agencia:{agency_contact}', response_text)

        # Agregar contacto si la respuesta sugiere contactar la agencia pero no incluye teléfonos
        if agency_contact and ('contactar' in response_text.lower() or 'contacta' in response_text.lower() or 'canales oficiales' in response_text.lower() or 'contact the agency' in response_text.lower() or 'contact the agency directly' in response_text.lower()) and '+51' not in response_text:
            response_text = response_text.rstrip() + agency_contact

        # C09: evitar "Prohibición de conversiones" - reemplazar por explicación clara
        if "prohibición de conversiones" in response_text.lower():
            response_text = response_text.replace(
                "Prohibición de conversiones",
                "Tipo de cambio no confirmado"
            )
            import re as _re_conversions
            response_text = _re_conversions.sub(
                r'(no puedo|No puedo|no puede|No puede) realizar conversiones de divisas ni inventar importes en soles\.',
                'No dispongo de un tipo de cambio oficial confirmado para convertir a soles (PEN).',
                response_text
            )

        # Guardar en historial DESPUÉS del post-procesamiento
        add_to_history(user_id, "human", question)
        add_to_history(user_id, "ai", response_text)

        # resolved_autonomously = False si necesita confirmación de la agencia O si es fallback
        resolved_auto = not is_fb and not needs_agency_conf

        return {
            "response": response_text,
            "context_used": True,
            "is_fallback": is_fb,
            "is_escalation": is_esc or is_fb,
            "is_predefined": False,
            "needs_agency_confirmation": needs_agency_conf,
            "resolved_autonomously": resolved_auto,
            "response_route": "rag_llm",
            "evidence_status": "rag_context",
            "needs_confirmation": needs_agency_conf,
            "conflict_detected": False,
            "sources_used": [],
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
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    """Recepcion de mensajes de Meta (WhatsApp Cloud API y Facebook Messenger)."""
    start_time = time.time()
    metric_start = time.perf_counter()
    raw_body = await request.body()

    try:
        body = json.loads(raw_body)
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Payload JSON invalido"})
    try:

        # ----------------------------------------------------------------
        # Detectar canal por el campo 'object' del payload de Meta
        # ----------------------------------------------------------------
        meta_object = body.get("object", "")

        # ================================================================
        # RAMA MESSENGER: object == "page"
        # ================================================================
        if meta_object == "page":
            # No aceptar tráfico sin una clave con la que autenticar a Meta.
            if not FB_APP_SECRET:
                return JSONResponse(status_code=503, content={"error": "Webhook Messenger no configurado"})
            if FB_APP_SECRET:
                expected_sig = "sha256=" + hmac.new(
                    FB_APP_SECRET.encode("utf-8"), raw_body, hashlib.sha256
                ).hexdigest()
                supplied_sig = request.headers.get("X-Hub-Signature-256", "")
                if not hmac.compare_digest(expected_sig, supplied_sig):
                    return JSONResponse(status_code=403, content={"error": "Firma Messenger invalida"})

            try:
                entry = body.get("entry", [{}])[0]
                messaging = entry.get("messaging", [{}])[0]
                psid = messaging.get("sender", {}).get("id", "")
                msg_obj = messaging.get("message", {})
                user_message = msg_obj.get("text", "")
                message_id = msg_obj.get("mid", "")

                # Ignorar eco (mensajes enviados por la propia página)
                if msg_obj.get('is_echo') or messaging.get("sender", {}).get("id") == messaging.get("recipient", {}).get("id"):
                    return JSONResponse(status_code=200, content={"status": "ok", "echo": True})

                # Ignorar eventos sin texto (postbacks, reacciones, etc.)
                if not user_message:
                    postback = messaging.get("postback", {})
                    if postback:
                        user_message = postback.get("payload") or postback.get("title", "")
                    if not user_message:
                        return JSONResponse(status_code=200, content={"status": "ok", "ignored": "no_text"})

            except (IndexError, KeyError, TypeError) as e:
                print(f"[FB PARSE ERROR] {e}")
                return JSONResponse(status_code=200, content={"status": "ok", "parse_error": str(e)})

            user_id = f"fb_{psid}" if psid else "fb_unknown"
            channel = "messenger"
            phone_number = ""
            bsuid = psid
            parent_bsuid = ""
            phone_number_id = None

            print(f"[FB INBOUND] psid={psid} user_id={user_id} "
                  f"message_id={message_id} text=\"{user_message[:50]}\"")

        # ================================================================
        # RAMA WHATSAPP: object == "whatsapp_business_account" o sin object
        # ================================================================
        else:
            if not META_APP_SECRET:
                return JSONResponse(status_code=503, content={"error": "Webhook WhatsApp no configurado"})

            expected_signature = "sha256=" + hmac.new(
                META_APP_SECRET.encode("utf-8"), raw_body, hashlib.sha256
            ).hexdigest()
            supplied_signature = request.headers.get("X-Hub-Signature-256", "")
            if not hmac.compare_digest(expected_signature, supplied_signature):
                return JSONResponse(status_code=403, content={"error": "Firma invalida"})

            try:
                entry = body.get("entry", [{}])[0]
                changes = entry.get("changes", [{}])[0]
                value = changes.get("value", {})
                messages = value.get("messages", [])
                statuses = value.get("statuses", [])

                # --- STATUS WEBHOOK (delivery reports) ---
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

                # --- INBOUND MESSAGE ---
                if messages:
                    msg = messages[0]
                    contacts = value.get("contacts", [])
                    contact = contacts[0] if contacts else {}

                    user_message = msg.get("text", {}).get("body", "")
                    message_id = msg.get("id", "")
                    msg_timestamp = msg.get("timestamp", "")
                    msg_type = msg.get("type", "")
                    phone_number_id = value.get("metadata", {}).get("phone_number_id")

                    # Extract identifiers from contacts
                    contact_wa_id = contact.get("wa_id", "")
                    contact_user_id = contact.get("user_id", "")
                    contact_parent_user_id = contact.get("parent_user_id", "")

                    # Extract identifiers from message
                    msg_from = msg.get("from", "")
                    msg_from_user_id = msg.get("from_user_id", "")
                    msg_from_parent_user_id = msg.get("from_parent_user_id", "")

                    # Determine identifiers
                    phone_number = contact_wa_id or (msg_from if msg_from and msg_from.isdigit() else "")
                    bsuid = contact_user_id or msg_from_user_id or ""
                    parent_bsuid = contact_parent_user_id or msg_from_parent_user_id or ""
                    user_id = phone_number or bsuid or msg_from or "unknown"

                    print(f"[WA INBOUND] "
                          f"message_id={message_id} "
                          f"from={msg_from} "
                          f"from_user_id={msg_from_user_id} "
                          f"type={msg_type} "
                          f"timestamp={msg_timestamp} "
                          f"text=\"{user_message[:50]}\" "
                          f"selected_phone={phone_number} "
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
                    message_id = ""
            except (IndexError, KeyError):
                user_id = body.get("user_id", "test_user")
                user_message = body.get("message", "")
                channel = body.get("channel", "test")
                phone_number_id = None
                phone_number = ""
                bsuid = ""
                parent_bsuid = ""
                message_id = ""

        if not user_message:
            return JSONResponse(status_code=400, content={"error": "No se proporciono un mensaje valido"})

        owner = None
        if message_id:
            state, owner = database.claim_webhook(message_id, user_id, SQLITE_DB_PATH)
            if state == 'completed':
                return JSONResponse(status_code=200, content={"status": "ok", "dedup": True})
            if state == 'busy':
                return JSONResponse(status_code=503, content={"status": "processing"}, headers={"Retry-After": "10"})

        # Completar el intento antes del ACK para conservar CPU durante la petición.
        def _process_message():
            import operational_metrics as operational
            event_id = None
            generation_ms = None
            rag_result = {}
            accepted = False
            try:
                if channel == 'whatsapp':
                    event_id = operational.start()
                rag_result = rag_chain(user_message, user_id=user_id)
                from handoff_support import apply_request
                rag_result = apply_request(globals(), rag_result, user_id, channel, user_message)
                bot_response = rag_result["response"]
                resolved_autonomously = rag_result.get("resolved_autonomously", not rag_result["is_fallback"])
                escalated_to_human = rag_result.get('handoff_registered', False)
                is_predefined = rag_result.get("is_predefined", False)
                interaction_type = "predefined" if is_predefined else "llm"
                is_rate_limit = rag_result.get("is_rate_limit", False)
                latency_ms = (time.time() - start_time) * 1000

                database.log_interaction(
                    user_id=user_id,
                    channel=channel,
                    detected_language=detect_language(user_message),
                    user_message=user_message,
                    bot_response=bot_response,
                    resolved_autonomously=resolved_autonomously,
                    latency_ms=latency_ms,
                    escalated_to_human=escalated_to_human,
                    is_predefined_response=is_predefined,
                    interaction_type=interaction_type,
                    is_rate_limit=is_rate_limit,
                    client_message_id=message_id or None,
                    db_path=SQLITE_DB_PATH,
                )

                generation_ms = (time.perf_counter() - metric_start) * 1000
                if owner:
                    database.renew_webhook(message_id, owner, SQLITE_DB_PATH)
                accepted = channel not in {'whatsapp', 'messenger'}
                if channel == "whatsapp":
                    bot_response_clean = format_whatsapp_text(bot_response)

                    # Evaluar solicitud de folleto previo al envío de texto para incorporar nota si no existe PDF
                    route = rag_result.get('response_route') or rag_result.get('route') or ''
                    no_multimedia_routes = {'social', 'help', 'evidence_unknown', 'evidence_conflict', 'evidence_contact', 'evidence_listing'}
                    detected_eid = rag_result.get('entity_id') or ''

                    tour_doc_info = None
                    if is_brochure_requested(user_message) and route not in no_multimedia_routes:
                        tour_doc_info = get_tour_brochure_data(user_message + " " + bot_response, user_msg=user_message, entity_id=detected_eid)
                        if not tour_doc_info:
                            bot_response_clean += "\n\n📄 _Nota: Actualmente este tour no cuenta con folleto en PDF en línea, pero nuestro asesor te facilitará el itinerario completo._"

                    accepted = user_id != 'unknown' and send_whatsapp_message(
                        text=bot_response_clean,
                        to_phone=phone_number if phone_number else None,
                        recipient_bsuid=bsuid if bsuid else None,
                        phone_number_id=phone_number_id,
                    )

                    # Despacho de Assets Multimedia (Fotos y Folletos PDF) SOLO bajo solicitud válida
                    try:
                        if accepted and route not in no_multimedia_routes:
                            # 1. Enviar Foto si fue solicitada expresamente
                            if is_photo_requested(user_message):
                                tour_img_info = get_tour_image_data(user_message + " " + bot_response, user_msg=user_message, entity_id=detected_eid)
                                if tour_img_info:
                                    img_url, img_caption = tour_img_info
                                    send_whatsapp_image(
                                        image_url=img_url,
                                        caption=img_caption,
                                        to_phone=phone_number if phone_number else None,
                                        recipient_bsuid=bsuid if bsuid else None,
                                        phone_number_id=phone_number_id,
                                    )
                                    print(f"[WA MULTIMEDIA PHOTO SENT] to={phone_number or bsuid} url={img_url}")

                            # 2. Enviar Folleto PDF si fue solicitado y está cargado en el catálogo
                            if tour_doc_info:
                                doc_url, doc_filename, doc_caption = tour_doc_info
                                send_whatsapp_document(
                                    document_url=doc_url,
                                    filename=doc_filename,
                                    caption=doc_caption,
                                    to_phone=phone_number if phone_number else None,
                                    recipient_bsuid=bsuid if bsuid else None,
                                    phone_number_id=phone_number_id,
                                )
                                print(f"[WA MULTIMEDIA BROCHURE SENT] to={phone_number or bsuid} filename={doc_filename}")
                    except Exception as media_err:
                        print(f"[WA MULTIMEDIA DISPATCH ERROR] {media_err}")

                    operational.finish(event_id, 'api_accepted' if accepted else 'send_failed',
                                       generation_ms, (time.perf_counter()-metric_start)*1000, rag_result)
                elif channel == "messenger":
                    accepted = send_messenger_message(text=bot_response, psid=bsuid)
                    print(f"[FB OUTBOUND RESULT] psid={bsuid} accepted={accepted}")

                if owner:
                    database.finish_webhook(message_id, owner, bool(accepted), SQLITE_DB_PATH)
                elapsed = (time.time() - start_time) * 1000
                channel_tag = "FB" if channel == "messenger" else "WA"
                print(f"[{channel_tag} PROCESSED] user_id={user_id} latency={elapsed:.0f}ms route={rag_result.get('response_route', 'unknown')}")
                return bool(accepted)
            except Exception as e:
                elapsed = (time.time() - start_time) * 1000
                if owner:
                    database.finish_webhook(message_id, owner, bool(accepted), SQLITE_DB_PATH)
                if event_id:
                    operational.finish(event_id, 'processing_failed', generation_ms,
                                       (time.perf_counter()-metric_start)*1000, rag_result)
                channel_tag = "FB" if channel == "messenger" else "WA"
                print(f"[{channel_tag} ERROR] user_id={user_id} error={e} latency={elapsed:.0f}ms")
                return bool(accepted)

        # Procesar con CPU al 100% activa mientras la conexión con Meta está abierta
        succeeded = await asyncio.to_thread(_process_message)
        if not succeeded:
            return JSONResponse(status_code=503, content={"error": "Procesamiento temporalmente no disponible"}, headers={"Retry-After": "10"})

        return JSONResponse(status_code=200, content={
            "status": "ok",
            "message_id": message_id,
        })

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return JSONResponse(status_code=500, content={"error": "Error interno; vuelve a intentar"})


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
        from handoff_support import apply_request
        rag_result = apply_request(globals(), rag_result, request.user_id, 'test', request.message)
        bot_response = rag_result["response"]

        # CORRECCIÓN #3: resolved_autonomously correcto
        resolved_autonomously = rag_result.get("resolved_autonomously", not rag_result["is_fallback"])
        # Red de seguridad: el flag de escalamiento de la cadena (si existe)
        # tiene prioridad; needs_escalation() cubre el resto.
        escalated_to_human = rag_result.get('handoff_registered', False)
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
            "needs_agency_confirmation": rag_result.get("needs_agency_confirmation", False),
            "route": rag_result.get("route", "predefined" if is_predefined else "rag"),
            "response_route": rag_result.get("response_route", rag_result.get("route", "unknown")),
            "handoff_id": rag_result.get('handoff_id'),
            "handoff_status": rag_result.get('handoff_status'),
            "evidence_status": rag_result.get("evidence_status", "unknown"),
            "needs_confirmation": rag_result.get("needs_confirmation", rag_result.get("needs_agency_confirmation", False)),
            "conflict_detected": rag_result.get("conflict_detected", False),
            "sources_used": rag_result.get("sources_used", []),
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
        html = html.replace('<body>', '<body><aside style="padding:16px;background:#fff3cd;color:#222">'
                            'Indicadores históricos: no acreditan entrega ni resolución validada. '
                            'El registro operativo está en el panel local de asesores (puerto 8023).'
                            '</aside>', 1)
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
    if os.path.exists(file_path):
        from fastapi.responses import FileResponse
        return FileResponse(file_path, media_type="image/jpeg")

    # Recuperación desde base de datos (PostgreSQL/SQLite)
    try:
        from catalog_service import get_asset_bytes
        asset = get_asset_bytes(filename, "photo")
        if asset:
            content_bytes, media_type = asset
            from fastapi.responses import Response
            return Response(content=content_bytes, media_type=media_type)
    except Exception:
        pass

    return JSONResponse(status_code=404, content={"error": "Imagen no encontrada"})


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
            "GET /catalogo": "Gestión de catálogo y tarifas",
            "GET /history/{user_id}": "Historial de conversación",
            "DELETE /history/{user_id}": "Limpiar historial",
        },
    }

# Activar la adaptación solo en esta copia de prueba.
from trial_support import install as _install_trial
_install_trial(globals())
from handoff_support import install as _install_handoff
_install_handoff(globals())
from operational_metrics import install as _install_operational
_install_operational(app)
from catalog_support import install as _install_catalog
_install_catalog(app)

