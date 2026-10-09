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

REGLA #1b — RESPUESTAS PARCIALES EN PREGUNTAS COMPUESTAS:
Si la consulta del turista incluye varios puntos y el contexto contiene información para responder uno de ellos (por ejemplo, la altitud documentada de Humantay o Abra Málaga) pero carece de datos para otro (por ejemplo, la duración o nivel de dificultad de la subida a pie, o actividades adicionales no registradas):
- Responde con precisión el dato documentado que sí figura en el contexto.
- Aclara amablemente que el aspecto no documentado requiere confirmación con un asesor de la agencia.
- NUNCA rechaces toda la consulta con el mensaje de fallback si puedes responder válidamente una parte con el contexto oficial.

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


def add_history_turn(user_id: str, question: str, response: str, metadata=None):
    conversation_history.add_turn(user_id, question, response, metadata=metadata)


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
        "arqueologico", "arqueológico", "waqrapukara", "waqra", "pukara",
        "choquequirao", "vinicunca", "wayna", "huayna", "colca", "visita", "caminata",
    ]
    en_words = [
        "what", "which", "how", "hello", "hi", "price", "tour", "tours",
        "available", "offer", "includes", "included", "do you", "can you",
        "i want", "i need", "looking for", "tell me", "tickets", "ticket", "book",
        "how much", "what is", "where", "when", "does",
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
# NORMALIZACIÓN DE CONSULTAS PARA EL RETRIEVER
# ============================================================

def normalize_query(text: str, lang: Optional[str] = None) -> str:
    """
    Normaliza la consulta antes de pasarla al retriever:
    1. Corrige tildes faltantes y errores en palabras clave de tours
       (machu pichu -> machu picchu, montaña colores -> montaña de colores).
    2. Normaliza variantes comunes:
       (wayna picchu, waynapicchu -> wayna picchu; salkantay, salkantai -> salkantay).
    3. Elimina caracteres especiales innecesarios.
    4. NO modifica preguntas en inglés (las retorna intactas).
    """
    if not text:
        return ""

    if lang is None:
        try:
            lang = detect_language(text)
        except Exception:
            lang = "es"

    # Regla 4: NO modificar preguntas en inglés
    if lang == "en":
        return text

    # Regla 3: Eliminar caracteres especiales innecesarios (conservando letras con acentos, ñ, números y espacios)
    cleaned = re.sub(r"[¿?¡!*~_#$%^&@+=<>[\]{}|\\/\"`()]+", " ", text)
    cleaned = re.sub(r"[,;.:]+(?=\s|$)", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Reglas 1 y 2: Corrección de tildes faltantes y variantes comunes de tours
    replacements = [
        # Montaña de Colores / 7 Colores / Vinicunca
        (r"\bmonta[nñ]a\s+de\s+(?:7|siete)\s+colores\b", "montaña de 7 colores"),
        (r"\bmonta[nñ]a\s+(?:7|siete)\s+colores\b", "montaña de 7 colores"),
        (r"\bmonta[nñ]a\s+colores\b", "montaña de colores"),
        (r"\bmontana\s+de\s+colores\b", "montaña de colores"),
        (r"\bmontana\b", "montaña"),

        # Wayna Picchu / Huayna Picchu
        (r"\b(?:wayna|huayna)\s*picchu\b", "wayna picchu"),
        (r"\b(?:wayna|huayna)\s*pichu\b", "wayna picchu"),
        (r"\b(?:waynapicchu|huaynapicchu|waynapichu|huaynapichu)\b", "wayna picchu"),

        # Machu Picchu
        (r"\bmachupicchu\b", "machu picchu"),
        (r"\bmachupichu\b", "machu picchu"),
        (r"\bmachu\s+pichu\b", "machu picchu"),
        (r"\bmacchu\s+picchu\b", "machu picchu"),
        (r"\bmacchu\s+pichu\b", "machu picchu"),

        # Salkantay
        (r"\bsalkantai\b", "salkantay"),
        (r"\bsalcantai\b", "salkantay"),
        (r"\bsalcantay\b", "salkantay"),

        # Valle Sagrado
        (r"\bvalle\s+sagrao\b", "valle sagrado"),

        # Humantay
        (r"\blaguna\s+umantay\b", "laguna humantay"),
        (r"\bumantay\b", "humantay"),

        # Vinicunca
        (r"\bwinicunca\b", "vinicunca"),
        (r"\bwinikunka\b", "vinicunca"),
        (r"\bvinikunka\b", "vinicunca"),

        # Waqra Pukara
        (r"\bhuaccra\s*pukara\b", "waqra pukara"),
        (r"\bhuaccrapukara\b", "waqra pukara"),
        (r"\bwaqrapukara\b", "waqra pukara"),
        (r"\bwaqra\s*pucara\b", "waqra pukara"),

        # Choquequirao
        (r"\bchoquekirao\b", "choquequirao"),
        (r"\bchoquequiraw\b", "choquequirao"),

        # Cañón del Colca
        (r"\bcanon\s+del\s+colca\b", "cañón del colca"),
        (r"\bcanon\s+colca\b", "cañón del colca"),

        # Tour Místico
        (r"\btour\s+mistico\b", "tour místico"),

        # Q'eswachaca
        (r"\bqueswachaca\b", "q'eswachaca"),
        (r"\bqeswachaca\b", "q'eswachaca"),
    ]

    result = cleaned
    for pattern, repl in replacements:
        result = re.sub(pattern, repl, result, flags=re.IGNORECASE)

    return re.sub(r"\s+", " ", result).strip()


# ============================================================
# FALLBACK CON FLAG EXPLÍCITO (Corrección de auditoría #3)
# ============================================================
# El flag is_fallback se decide EN EL PUNTO donde se determina que
# no hay información suficiente — no se infiere después comparando
# strings de la respuesta del LLM. Esto elimina falsos negativos
# sin importar el idioma de salida.


def build_fallback_response(lang: str = "es") -> dict:
    """
    Genera la respuesta de fallback con su flag booleano explícito.

    Retorna:
        Diccionario con response, context_used, is_fallback=True,
        is_predefined=False.
    """
    messages = {
        "es": FALLBACK_MESSAGE,
        "en": "I don't have that exact documented information. Please consult an agency advisor to confirm the details.",
        "pt": "Não tenho essa informação exata documentada. Consulte um assessor da agência para confirmar os detalhes.",
    }
    return {
        "response": messages.get(lang, FALLBACK_MESSAGE),
        "context_used": False,
        "is_fallback": True,
        "is_predefined": False,
        "resolved_autonomously": False,
    }


RATE_LIMIT_MESSAGE = (
    "Estamos experimentando alta demanda temporalmente. "
    "Por favor, intenta de nuevo en unos segundos."
)


def build_rate_limit_response(lang: str = "es") -> dict:
    """
    Genera la respuesta para errores de rate-limit (429) del proveedor LLM.

    A DIFERENCIA de build_fallback_response(), esta función retorna
    is_fallback=False para que el error de infraestructura NO se contabilice
    como fallback del RAG en las métricas de investigación.

    Retorna:
        Diccionario con response, context_used, is_fallback=False,
        is_rate_limit=True, is_predefined=False.
    """
    messages = {
        "es": RATE_LIMIT_MESSAGE,
        "en": "We are experiencing high demand temporarily. Please try again in a few seconds.",
        "pt": "Estamos recebendo muitas consultas neste momento. Tente novamente em alguns segundos.",
    }
    return {
        "response": messages.get(lang, RATE_LIMIT_MESSAGE),
        "context_used": False,
        "is_fallback": False,
        "is_rate_limit": True,
        "is_predefined": False,
        "resolved_autonomously": False,
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
    "hola": "¡Hola! 👋 Soy el asistente virtual de Texeira Travel. Puedo ayudarte a explorar tours y consultar información, o comunicarte con un asesor.",
    "buenos días": "¡Hola! 👋 Soy el asistente virtual de Texeira Travel. Puedo ayudarte a explorar tours y consultar información, o comunicarte con un asesor.",
    "buenas tardes": "¡Hola! 👋 Soy el asistente virtual de Texeira Travel. Puedo ayudarte a explorar tours y consultar información, o comunicarte con un asesor.",
    "buenas noches": "¡Hola! 👋 Soy el asistente virtual de Texeira Travel. Puedo ayudarte a explorar tours y consultar información, o comunicarte con un asesor.",
    "buenas": "¡Hola! 👋 Soy el asistente virtual de Texeira Travel. Puedo ayudarte a explorar tours y consultar información, o comunicarte con un asesor.",
    "hello": "Hello! 👋 I am Texeira Travel's virtual assistant. I can help you explore tours and check information, or connect you with an advisor.",
    "hi": "Hello! 👋 I am Texeira Travel's virtual assistant. I can help you explore tours and check information, or connect you with an advisor.",
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
    "recomiend", "recomen", "sugier", "suger", "recommend", "suggest",
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
# RESOLUCIÓN CONTEXTUAL DEL RETRIEVER Y ENTIDADES (Memoria RAG)
# ============================================================

def resolve_contextual_retriever_query(question: str, history: list) -> tuple:
    """
    Analiza la consulta actual y el historial para contextualizar la búsqueda RAG.
    Retorna: (retriever_query, explicit_entities, contextual_entity_id, is_ambiguous, clarif_msg)
    - Si la consulta tiene una o más entidades explícitas:
        Usa la consulta normalizada original. No contamina con tours pasados del historial.
    - Si la consulta no tiene entidad explícita (pregunta de seguimiento):
        Examina el historial reciente en busca de tours activos.
        - Si hay 1 tour inequívoco en el contexto inmediato:
            Retorna ese tour y una query contextual enriquecida para el retriever,
            manteniendo la pregunta original intacta para el modelo.
        - Si hay 2 o más tours en conflicto/competencia sin referencia clara:
            Marca is_ambiguous = True para solicitar aclaración en lugar de inventar.
    """
    import re
    from trial_support import normalize
    try:
        from catalog_service import get_active_entity_keywords, get_tour_by_id
        kw_map = get_active_entity_keywords()
    except Exception:
        kw_map = None

    norm_q = normalize(question)
    normalized_query_text = normalize_query(question)

    # 1. Detectar todas las entidades nombradas explícitamente en la pregunta actual
    explicit_in_q = []
    if kw_map:
        for eid, kws in kw_map.items():
            for kw in kws:
                if kw and normalize(kw) in norm_q:
                    if eid not in explicit_in_q:
                        explicit_in_q.append(eid)
                    break
    else:
        from trial_support import detect_entity_from_question
        single = detect_entity_from_question(question)
        if single:
            explicit_in_q.append(single)

    if explicit_in_q:
        # Caso A: Pregunta con tour explícito o comparación directa (ej. "¿Y qué incluye City Tour?")
        # No se contamina con tours del historial
        return normalized_query_text, explicit_in_q, explicit_in_q[0], False, None

    # Caso B: Pregunta sin tour explícito -> Evaluar historial conversacional
    try:
        from verified_routes import is_recommendation_query, is_rejection_query, is_other_options_query
        is_rec_or_reject = is_recommendation_query(norm_q) or is_rejection_query(norm_q) or is_other_options_query(norm_q)
    except Exception:
        is_rec_or_reject = bool(re.search(r'\b(recomie\w*|recomen\w*|sugier\w*|suger\w*|ning[uú]n\w*|neither|none|otra\s+opci\w*|otro\s+tour\w*)\b', norm_q))

    if is_rec_or_reject:
        # Peticiones de recomendación, rechazo ("ninguno") u opciones alternativas NUNCA deben solicitar aclaración de tour
        return normalized_query_text, [], None, False, None

    is_ambiguous_ref = bool(re.search(
        r'\b((?:d?el|de la)\s+otr[oa]s?|el demas|los demas|the other( one)?|the second( one)?)\b',
        norm_q
    ))

    # Recolectar entidades mencionadas en los turnos recientes del historial (últimos 6 mensajes)
    # REGLA: SOLO turnos humanos representan selecciones o consultas del cliente (un listado del bot no es selección)
    recent_eids_by_turn = []
    for h in reversed(history[-6:]):
        if h.get("role") != "human":
            continue
        h_text = normalize(h.get("content", ""))
        turn_eids = []
        if kw_map:
            for eid, kws in kw_map.items():
                for kw in kws:
                    if kw and normalize(kw) in h_text:
                        if eid not in turn_eids:
                            turn_eids.append(eid)
                        break
        else:
            from trial_support import detect_entity_from_question
            e = detect_entity_from_question(h.get("content", ""))
            if e:
                turn_eids.append(e)
        if turn_eids:
            recent_eids_by_turn.append(turn_eids)

    # Entidades únicas en el historial reciente ordenadas por recencia
    candidate_eids = []
    for turn in recent_eids_by_turn:
        for eid in turn:
            if eid not in candidate_eids:
                candidate_eids.append(eid)

    # Detección de ambigüedad:
    # 1) Si dice explícitamente "el otro" / "the other" y hay >= 2 candidatos del historial humano
    # 2) O si el último turno previo HUMANO mencionó >= 2 candidatos a la vez y la pregunta actual es una consulta específica de atributo
    is_attribute_query = bool(re.search(
        r'\b(precio|tarifa|cuesta|cuanto cuesta|costo|foto|fotos|imagen|imagenes|que incluye|incluye|no incluye|horario|hora|salida|recorrido|reservar|reserva|price|rate|cost|how much|photo|photos|picture|pictures|include|schedule|departure|book|reservation)\b',
        norm_q
    ))
    last_turn_had_multiple = bool(recent_eids_by_turn and len(recent_eids_by_turn[0]) >= 2)
    should_clarify = (
        (is_ambiguous_ref and len(candidate_eids) >= 2) or
        (last_turn_had_multiple and len(candidate_eids) >= 2 and is_attribute_query)
    )
    if should_clarify:
        t1, t2 = candidate_eids[0], candidate_eids[1]
        try:
            from catalog_service import get_tour_by_id
            t1_obj = get_tour_by_id(t1)
            t2_obj = get_tour_by_id(t2)
            t1_name = t1_obj.get("name", t1) if t1_obj else t1
            t2_name = t2_obj.get("name", t2) if t2_obj else t2
        except Exception:
            t1_name, t2_name = t1, t2
        is_en = detect_language(question) == "en"
        clarif = (
            f"Which tour are you referring to? We discussed *{t1_name}* and *{t2_name}*. Please let me know which one you'd like to check or type its name 😊"
            if is_en else
            f"¿A cuál de los tours te refieres? Conversamos sobre *{t1_name}* y *{t2_name}*. Por favor indícame cuál deseas consultar o escribe su nombre 😊"
        )
        return normalized_query_text, [], None, True, clarif

    # Caso C: Tour inequívoco en el historial reciente
    if len(candidate_eids) == 1:
        contextual_eid = candidate_eids[0]
        contextual_tour_name = None
        try:
            from catalog_service import get_tour_by_id
            t_info = get_tour_by_id(contextual_eid)
            contextual_tour_name = t_info.get("name") if t_info else contextual_eid
        except Exception:
            contextual_tour_name = contextual_eid

        retriever_query = f"{contextual_tour_name} {normalized_query_text}" if contextual_tour_name else normalized_query_text
        return retriever_query, [contextual_eid], contextual_eid, False, None

    if len(candidate_eids) > 1 and not is_ambiguous_ref:
        # Foco activo más reciente
        contextual_eid = candidate_eids[0]
        try:
            from catalog_service import get_tour_by_id
            t_info = get_tour_by_id(contextual_eid)
            contextual_tour_name = t_info.get("name") if t_info else contextual_eid
        except Exception:
            contextual_tour_name = contextual_eid
        retriever_query = f"{contextual_tour_name} {normalized_query_text}" if contextual_tour_name else normalized_query_text
        return retriever_query, [contextual_eid], contextual_eid, False, None

    # Caso D: Sin tour en consulta ni en historial
    return normalized_query_text, [], None, False, None


# ============================================================
# CADENA RAG — VERSIÓN CORREGIDA (Correcciones #1, #3, #4)
# ============================================================

def rag_chain(question: str, user_id: str = "default") -> dict:
    """
    Ejecuta la cadena RAG completa con las correcciones de tesis:

    CORRECCIÓN #1: System prompt estricto (cero alucinaciones)
    CORRECCIÓN #3: Lógica correcta de resolved_autonomously
    CORRECCIÓN #4: Conversation history (memoria de corto plazo y recuperación contextual)

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
        result = build_fallback_response(lang_detected)
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
        retriever_query, explicit_eids, entity_detected, is_ambiguous, clarif_msg = (
            resolve_contextual_retriever_query(question, history)
        )

        if is_ambiguous and clarif_msg:
            add_to_history(user_id, "human", question)
            add_to_history(user_id, "ai", clarif_msg)
            return {
                "response": clarif_msg,
                "context_used": False,
                "is_fallback": False,
                "is_predefined": True,
                "response_route": "evidence_ambiguous",
                "evidence_status": "ambiguous",
                "needs_confirmation": True,
                "conflict_detected": False,
                "sources_used": [],
                "entity_id": ",".join(explicit_eids) if explicit_eids else "ambiguous",
            }

        docs = retriever.invoke(retriever_query)

        # Si es comparación multi-entidad, asegurar que documentos de ambas entidades estén en docs
        if len(explicit_eids) >= 2:
            docs_eids = {d.metadata.get("tour_id") for d in docs}
            for comp_eid in explicit_eids:
                if comp_eid not in docs_eids:
                    extra_docs = retriever.invoke(comp_eid)
                    for ed in extra_docs:
                        if ed.metadata.get("tour_id") == comp_eid and ed not in docs:
                            docs.append(ed)
                            break

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
            result = build_fallback_response(lang_detected)
            add_to_history(user_id, "human", question)
            add_to_history(user_id, "ai", result["response"])
            return result

        # PASO 4: Construir el LLM (solo se llama cuando SÍ hay contexto)
        llm = get_llm()

        # v4-evidencias: filtrar facts conflictivos del contexto antes del LLM y agregar datos vigentes
        eids_to_enrich = explicit_eids if len(explicit_eids) >= 2 else ([entity_detected] if entity_detected else [])
        if eids_to_enrich:
            for cur_eid in eids_to_enrich:
                context = _filter_conflicting_facts_from_context(context, cur_eid)
            try:
                from catalog_service import get_tour_by_id
                dyn_blocks = []
                for cur_eid in eids_to_enrich:
                    dyn_tour = get_tour_by_id(cur_eid)
                    if dyn_tour and dyn_tour.get("is_active", 1):
                        dyn_lines = [
                            f"[DATOS OFICIALES Y TARIFAS VIGENTES DE LA AGENCIA PARA {dyn_tour.get('name', cur_eid).upper()}]",
                            f"Tour: {dyn_tour.get('name')}",
                        ]
                        if dyn_tour.get("official_price"):
                            dyn_lines.append(f"Tarifa Oficial: {dyn_tour.get('official_price')} {dyn_tour.get('currency', 'USD')} por persona")
                        if dyn_tour.get("schedule"):
                            dyn_lines.append(f"Horario Oficial: {dyn_tour.get('schedule')}")
                        if dyn_tour.get("duration"):
                            dyn_lines.append(f"Duración: {dyn_tour.get('duration')}")
                        if dyn_tour.get("includes"):
                            dyn_lines.append(f"Incluye: {dyn_tour.get('includes')}")
                        if dyn_tour.get("excludes"):
                            dyn_lines.append(f"No incluye: {dyn_tour.get('excludes')}")
                        if dyn_tour.get("altitude"):
                            dyn_lines.append(f"Altitud: {dyn_tour.get('altitude')}")
                        if dyn_tour.get("route"):
                            dyn_lines.append(f"Ruta: {dyn_tour.get('route')}")
                        dyn_blocks.append("\n".join(dyn_lines))
                if dyn_blocks:
                    context = "\n\n".join(dyn_blocks) + "\n\n" + context
            except Exception:
                pass

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
        result = build_rate_limit_response(lang_detected)
        add_to_history(user_id, "human", question)
        add_to_history(user_id, "ai", result["response"])
        return result

    except Exception as e:
        import traceback
        print(f"[ERROR] Fallo en la cadena RAG: {e}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        result = build_fallback_response(lang_detected)
        result["response"] = {
            "es": "Lo siento, hubo un error técnico. Por favor, intenta nuevamente o contacta a un asesor.",
            "en": "Sorry, there was a technical error. Please try again or consult an advisor.",
            "pt": "Desculpe, ocorreu um erro técnico. Tente novamente ou consulte um assessor.",
        }.get(lang_detected, "Lo siento, hubo un error técnico. Por favor, intenta nuevamente o contacta a un asesor.")
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

TOUR_BUTTON_NAMES = {
    "camino-inka": {"es": "🥾 Camino Inca", "en": "🥾 Inca Trail"},
    "machu-picchu-tren": {"es": "🏔️ Machu Picchu", "en": "🏔️ Machu Picchu"},
    "montana-7-colores": {"es": "🌈 7 Colores", "en": "🌈 Rainbow Mtn"},
    "laguna-humantay": {"es": "💎 Humantay", "en": "💎 Humantay"},
    "city-tour-cusco": {"es": "🏛️ City Tour", "en": "🏛️ City Tour"},
    "valle-sagrado": {"es": "🌾 Valle Sagrado", "en": "🌾 Sacred Valley"},
    "salkantay-trek": {"es": "🥾 Salkantay", "en": "🥾 Salkantay"},
    "maras-moray": {"es": "🧂 Maras-Moray", "en": "🧂 Maras-Moray"},
    "maras-moray-cuatrimoto": {"es": "🏎️ Cuatrimotos", "en": "🏎️ ATVs"},
    "inka-jungle": {"es": "🚵 Inka Jungle", "en": "🚵 Inka Jungle"},
    "choquequirao": {"es": "🏕️ Choquequirao", "en": "🏕️ Choquequirao"},
    "valle-sur": {"es": "🌄 Valle Sur", "en": "🌄 South Valley"},
    "puente-qeswachaca": {"es": "🌉 Q'eswachaca", "en": "🌉 Q'eswachaca"},
    "tour-mistico": {"es": "🔮 Tour Místico", "en": "🔮 Mystic Tour"},
    "islas-titicaca": {"es": "⛵ Titicaca", "en": "⛵ Titicaca"},
    "canon-colca": {"es": "🦅 Cañón Colca", "en": "🦅 Colca Canyon"},
    "ruta-del-sol": {"es": "☀️ Ruta del Sol", "en": "☀️ Sun Route"},
    "waqra-pukara": {"es": "🏰 Waqra Pukara", "en": "🏰 Waqra Pukara"},
    "machu-picchu-car": {"es": "🚗 MP by Car", "en": "🚗 MP by Car"},
}


def _get_tour_display_name(eid: str, is_en: bool = False) -> str:
    """Retorna el nombre para visualización del tour, priorizando el catálogo dinámico o traducción."""
    if not eid or eid == "__AMBIGUOUS__":
        return ""
    names_es = {
        "camino-inka": "Camino Inca",
        "machu-picchu-tren": "Machu Picchu en tren",
        "machu-picchu-car": "Machu Picchu en auto",
        "montana-7-colores": "Montaña de 7 Colores",
        "laguna-humantay": "Laguna Humantay",
        "city-tour-cusco": "City Tour Cusco",
        "valle-sagrado": "Valle Sagrado",
        "salkantay-trek": "Salkantay Trek",
        "maras-moray": "Maras - Moray",
        "maras-moray-cuatrimoto": "Cuatrimotos Maras-Moray",
        "inka-jungle": "Inka Jungle",
        "choquequirao": "Choquequirao",
        "valle-sur": "Valle Sur",
        "puente-qeswachaca": "Puente Q'eswachaca",
        "tour-mistico": "Tour Místico",
        "islas-titicaca": "Islas del Titicaca",
        "canon-colca": "Cañón del Colca",
        "ruta-del-sol": "Ruta del Sol",
        "waqra-pukara": "Waqra Pukara",
    }
    names_en = {
        "camino-inka": "Inca Trail",
        "machu-picchu-tren": "Machu Picchu by Train",
        "machu-picchu-car": "Machu Picchu by Car",
        "montana-7-colores": "Rainbow Mountain",
        "laguna-humantay": "Humantay Lake",
        "city-tour-cusco": "City Tour Cusco",
        "valle-sagrado": "Sacred Valley",
        "salkantay-trek": "Salkantay Trek",
        "maras-moray": "Maras - Moray",
        "maras-moray-cuatrimoto": "ATVs Maras-Moray",
        "inka-jungle": "Inka Jungle",
        "choquequirao": "Choquequirao",
        "valle-sur": "South Valley",
        "puente-qeswachaca": "Q'eswachaca Bridge",
        "tour-mistico": "Mystic Tour",
        "islas-titicaca": "Lake Titicaca",
        "canon-colca": "Colca Canyon",
        "ruta-del-sol": "Sun Route",
        "waqra-pukara": "Waqra Pukara",
    }
    if is_en and eid in names_en:
        return names_en[eid]
    try:
        from catalog_service import get_tour_by_id
        t = get_tour_by_id(eid)
        if t and t.get("name"):
            return t["name"]
    except Exception:
        pass
    mapping = names_en if is_en else names_es
    return mapping.get(eid, eid)


def _get_tour_button_title(eid: str, is_en: bool = False) -> str:
    """Retorna un título corto <= 20 caracteres para botones de tour."""
    if not eid or eid == "__AMBIGUOUS__":
        return ""
    if eid in TOUR_BUTTON_NAMES:
        return TOUR_BUTTON_NAMES[eid]["en" if is_en else "es"]
    name = _get_tour_display_name(eid, is_en=is_en)
    return name[:20]


def _get_active_catalog_tour_buttons(lang: str = "es") -> List[dict]:
    """Genera botones de tours verificando que estén activos en el catálogo dinámico."""
    is_en = (lang == "en")
    active_eids = []
    try:
        from catalog_service import get_all_tours
        dynamic_all = get_all_tours(active_only=True)
        active_eids = [t['entity_id'] for t in dynamic_all if t.get('is_active')]
    except Exception:
        pass


    priority_order = [
        'camino-inka', 'machu-picchu-tren', 'montana-7-colores',
        'laguna-humantay', 'city-tour-cusco', 'valle-sagrado',
        'salkantay-trek', 'maras-moray', 'maras-moray-cuatrimoto'
    ]
    selected_eids = [eid for eid in priority_order if eid in active_eids]
    if not selected_eids:
        selected_eids = [eid for eid in active_eids if eid]

    buttons = []
    for eid in selected_eids[:2]:
        title = _get_tour_button_title(eid, is_en=is_en)
        buttons.append({"id": f"btn_tour:{eid}:{lang}", "title": title[:20]})

    buttons.append({
        "id": f"btn_advisor:{lang}",
        "title": "🙋‍♂️ Advisor" if is_en else "🙋‍♂️ Asesor"
    })
    return _localize_button_titles(buttons, lang)


def _localize_button_titles(buttons: List[dict], lang: str) -> List[dict]:
    """Keep action/entity IDs intact while localizing the Portuguese controls."""
    if lang != "pt":
        return buttons
    labels = {
        "Ver otros tours": "Ver outros passeios",
        "Consultar asesor": "Consultar assessor",
        "Reintentar": "Tentar novamente",
        "⬅️ Categorías": "⬅️ Categorias",
        "🗺️ Ver Tours": "🗺️ Ver passeios",
        "📄 Qué incluye": "📄 O que inclui",
        "📸 Reintentar foto": "📸 Repetir foto",
        "Solicitar reserva": "Solicitar reserva",
        "💰 Tarifas": "💰 Preços",
        "📸 Ver Fotos": "📸 Ver fotos",
        "🙋‍♂️ Asesor": "🙋‍♂️ Assessor",
        "🌄 Clásicos Cusco": "🌄 Clássicos Cusco",
        "🚌 Rutas Regionales": "🚌 Rotas Regionais",
        "➡️ Más tours": "➡️ Mais passeios",
    }
    return [dict(button, title=labels.get(button["title"], button["title"])[:20])
            for button in buttons]


def get_quick_buttons(
    route: str = "",
    user_message: str = "",
    detected_eid: str = "",
    lang: str = "es",
    photo_send_failed: bool = False,
) -> List[dict]:
    buttons = _build_quick_buttons(route, user_message, detected_eid, lang, photo_send_failed)
    return _localize_button_titles(buttons, lang)


def _build_quick_buttons(
    route: str = "",
    user_message: str = "",
    detected_eid: str = "",
    lang: str = "es",
    photo_send_failed: bool = False,
) -> List[dict]:
    """Genera hasta 3 botones contextuales según la intención y tour detectado.

    Todos los títulos están estrictamente acotados a <= 20 caracteres según la API de Meta.
    Los IDs transportan el identificador del tour y el idioma para preservar el contexto.
    """
    is_en = (lang == "en")
    u_lower = (user_message or "").lower()
    eid_suffix = f":{detected_eid}" if detected_eid else ""

    from catalog_service import is_deactivated_tour

    # 1. Tour desactivado: NUNCA ofrecer acciones comerciales (fotos, tarifas, reserva)
    if route == "evidence_inactive_tour" or (detected_eid and is_deactivated_tour(detected_eid)):
        if is_en:
            return [
                {"id": f"btn_tours:{lang}", "title": "View other tours"},
                {"id": f"btn_advisor:{lang}", "title": "Consult advisor"},
            ]
        else:
            return [
                {"id": f"btn_tours:{lang}", "title": "Ver otros tours"},
                {"id": f"btn_advisor:{lang}", "title": "Consultar asesor"},
            ]

    # 2. Error técnico al cargar catálogo (base de datos inaccesible)
    if route == "evidence_catalog_error":
        if is_en:
            return [
                {"id": f"btn_advisor:{lang}", "title": "Consult advisor"},
                {"id": f"btn_tours:{lang}", "title": "Retry"},
            ]
        else:
            return [
                {"id": f"btn_advisor:{lang}", "title": "Consultar asesor"},
                {"id": f"btn_tours:{lang}", "title": "Reintentar"},
            ]

    # 3. Catálogo vacío
    if route in ("evidence_catalog_empty", "catalog_unavailable"):
        return [{"id": f"btn_advisor:{lang}", "title": "Consult advisor" if is_en else "Consultar asesor"}]

    # 4. Categoría vacía
    if route == "evidence_category_empty":
        return [
            {"id": f"btn_cats:{lang}", "title": "⬅️ Categories" if is_en else "⬅️ Categorías"},
            {"id": f"btn_advisor:{lang}", "title": "Consult advisor" if is_en else "Consultar asesor"},
        ]

    # 5. Consulta ambigua ("el otro", aclaración entre 2 tours)
    if route == "evidence_ambiguous":
        buttons = []
        if detected_eid and "," in detected_eid:
            cands = [c.strip() for c in detected_eid.split(",") if c.strip()]
            for c in cands[:2]:
                title = _get_tour_button_title(c, is_en=is_en)
                buttons.append({"id": f"btn_tour:{c}:{lang}", "title": title[:20]})
        buttons.append({"id": f"btn_tours:{lang}", "title": "🗺️ View Tours" if is_en else "🗺️ Ver Tours"})
        return buttons[:3]

    # 5b. Recomendaciones de tours
    if route == "evidence_recommendation":
        return [
            {"id": f"btn_tours:{lang}", "title": "🗺️ View Tours" if is_en else "🗺️ Ver Tours"},
            {"id": f"btn_advisor:{lang}", "title": "Consult advisor" if is_en else "Consultar asesor"},
        ]

    # 6. Solicitud de atención o reserva registrada (handoff)
    if route == "human_request":
        buttons = [{"id": f"btn_tours:{lang}", "title": "View other tours" if is_en else "Ver otros tours"}]
        if detected_eid and not is_deactivated_tour(detected_eid):
            buttons.append({"id": f"btn_inc:{detected_eid}:{lang}", "title": "📄 What's included" if is_en else "📄 Qué incluye"})
        else:
            buttons.append({"id": f"btn_advisor:{lang}", "title": "Consult advisor" if is_en else "Consultar asesor"})
        return buttons[:2]

    # 7. Listado de tours o categorías
    if route == "evidence_listing" or _is_listing_question(u_lower):
        from verified_routes import get_dynamic_cat_specs
        try:
            from catalog_service import get_all_tours
            all_active = {t['entity_id']: t for t in get_all_tours(active_only=True) if t.get('is_active')}
        except Exception:
            all_active = {}
        cat_specs = get_dynamic_cat_specs(all_active)
        cat_buttons = []
        for spec in cat_specs.values():
            if len(spec.get('tours', [])) > 0:
                title = spec['btn_title_en'] if is_en else spec['btn_title_es']
                cat_buttons.append({"id": f"{spec['btn_id']}:{lang}", "title": title[:20]})
        if cat_buttons:
            return cat_buttons[:3]
        return [{"id": f"btn_advisor:{lang}", "title": "Consult advisor" if is_en else "Consultar asesor"}]

    # 8. Tours de una categoría con paginación
    if route == "evidence_category_tours":
        cat_key = ""
        for ck in ('treks', 'cusco', 'reg'):
            if ck in u_lower:
                cat_key = ck
                break
        page = 0
        import re
        m_page = re.search(r'(?:pagina|page)\s+(\d+)', u_lower)
        if m_page:
            try:
                page = int(m_page.group(1))
            except Exception:
                page = 0

        from verified_routes import get_dynamic_cat_specs, paginate_category_tours
        try:
            from catalog_service import get_all_tours, is_deactivated_tour
            all_active = {t['entity_id']: t for t in get_all_tours(active_only=True) if t.get('is_active') and not is_deactivated_tour(t['entity_id'])}
        except Exception:
            all_active = {}
        cat_specs = get_dynamic_cat_specs(all_active)
        spec = cat_specs.get(cat_key)
        if spec:
            active_tours_cat = [t for t in spec.get('tours', []) if t[0] in all_active]
            pages = paginate_category_tours(active_tours_cat)
            if not pages:
                return [{"id": f"btn_cats:{lang}", "title": "⬅️ Categories" if is_en else "⬅️ Categorías"}]
            if page >= len(pages):
                page = 0
            page_slice = pages[page]
            buttons = []
            for t in page_slice:
                eid = t[0]
                title = _get_tour_button_title(eid, is_en=is_en)
                buttons.append({"id": f"btn_tour:{eid}:{lang}", "title": title[:20]})
            if page + 1 < len(pages):
                buttons.append({"id": f"btn_cat_page:{cat_key}:{page+1}:{lang}", "title": "➡️ More tours" if is_en else "➡️ Más tours"})
            if page > 0 or len(pages) == 1:
                buttons.append({"id": f"btn_cats:{lang}", "title": "⬅️ Categories" if is_en else "⬅️ Categorías"})
            return buttons[:3]
        else:
            return [{"id": f"btn_cats:{lang}", "title": "⬅️ Categories" if is_en else "⬅️ Categorías"}]

    # 9. Fallo de envío de foto en Meta API
    if photo_send_failed and detected_eid:
        if is_en:
            return [
                {"id": f"btn_photo{eid_suffix}:{lang}", "title": "📸 Retry photo"},
                {"id": f"btn_inc{eid_suffix}:{lang}", "title": "📄 What's included"},
                {"id": f"btn_book{eid_suffix}:{lang}", "title": "Request reservation"},
            ]
        else:
            return [
                {"id": f"btn_photo{eid_suffix}:{lang}", "title": "📸 Reintentar foto"},
                {"id": f"btn_inc{eid_suffix}:{lang}", "title": "📄 Qué incluye"},
                {"id": f"btn_book{eid_suffix}:{lang}", "title": "Solicitar reserva"},
            ]

    # 10. Foto inexistente en línea
    if route == "evidence_photo_unavailable" and detected_eid:
        if is_en:
            return [
                {"id": f"btn_inc{eid_suffix}:{lang}", "title": "📄 What's included"},
                {"id": f"btn_rates{eid_suffix}:{lang}", "title": "💰 Rates"},
                {"id": f"btn_book{eid_suffix}:{lang}", "title": "Request reservation"},
            ]
        else:
            return [
                {"id": f"btn_inc{eid_suffix}:{lang}", "title": "📄 Qué incluye"},
                {"id": f"btn_rates{eid_suffix}:{lang}", "title": "💰 Tarifas"},
                {"id": f"btn_book{eid_suffix}:{lang}", "title": "Solicitar reserva"},
            ]

    # 11. Foto enviada exitosamente
    if route == "evidence_photo" or is_photo_requested(user_message):
        if is_en:
            return [
                {"id": f"btn_rates{eid_suffix}:{lang}", "title": "💰 Rates"},
                {"id": f"btn_inc{eid_suffix}:{lang}", "title": "📄 What's included"},
                {"id": f"btn_book{eid_suffix}:{lang}", "title": "Request reservation"},
            ]
        else:
            return [
                {"id": f"btn_rates{eid_suffix}:{lang}", "title": "💰 Tarifas"},
                {"id": f"btn_inc{eid_suffix}:{lang}", "title": "📄 Qué incluye"},
                {"id": f"btn_book{eid_suffix}:{lang}", "title": "Solicitar reserva"},
            ]

    # 12. Precios / tarifas
    if route in ("evidence_confirmed_price", "evidence_special_rate") or _is_price_question(u_lower):
        if is_en:
            return [
                {"id": f"btn_photo{eid_suffix}:{lang}", "title": "📸 View Photos"},
                {"id": f"btn_inc{eid_suffix}:{lang}", "title": "📄 What's included"},
                {"id": f"btn_book{eid_suffix}:{lang}", "title": "Request reservation"},
            ]
        else:
            return [
                {"id": f"btn_photo{eid_suffix}:{lang}", "title": "📸 Ver Fotos"},
                {"id": f"btn_inc{eid_suffix}:{lang}", "title": "📄 Qué incluye"},
                {"id": f"btn_book{eid_suffix}:{lang}", "title": "Solicitar reserva"},
            ]

    # 13. Qué incluye
    if route in ("evidence_confirmed_includes", "evidence_includes") or _is_includes_question(u_lower):
        if is_en:
            return [
                {"id": f"btn_rates{eid_suffix}:{lang}", "title": "💰 Rates"},
                {"id": f"btn_photo{eid_suffix}:{lang}", "title": "📸 View Photos"},
                {"id": f"btn_book{eid_suffix}:{lang}", "title": "Request reservation"},
            ]
        else:
            return [
                {"id": f"btn_rates{eid_suffix}:{lang}", "title": "💰 Tarifas"},
                {"id": f"btn_photo{eid_suffix}:{lang}", "title": "📸 Ver Fotos"},
                {"id": f"btn_book{eid_suffix}:{lang}", "title": "Solicitar reserva"},
            ]

    # 14. Horario publicado o precio sin confirmar
    if route == "evidence_schedule" and detected_eid:
        if is_en:
            return [
                {"id": f"btn_inc{eid_suffix}:{lang}", "title": "📄 What's included"},
                {"id": f"btn_photo{eid_suffix}:{lang}", "title": "📸 View Photos"},
                {"id": f"btn_advisor:{lang}", "title": "Consult advisor"},
            ]
        else:
            return [
                {"id": f"btn_inc{eid_suffix}:{lang}", "title": "📄 Qué incluye"},
                {"id": f"btn_photo{eid_suffix}:{lang}", "title": "📸 Ver Fotos"},
                {"id": f"btn_advisor:{lang}", "title": "Consultar asesor"},
            ]

    # 15. Ficha de tour (overview) o tour detectado activo
    if detected_eid:
        if is_en:
            return [
                {"id": f"btn_inc:{detected_eid}:{lang}", "title": "📄 What's included"},
                {"id": f"btn_photo:{detected_eid}:{lang}", "title": "📸 View Photos"},
                {"id": f"btn_book:{detected_eid}:{lang}", "title": "Request reservation"},
            ]
        else:
            return [
                {"id": f"btn_inc:{detected_eid}:{lang}", "title": "📄 Qué incluye"},
                {"id": f"btn_photo:{detected_eid}:{lang}", "title": "📸 Ver Fotos"},
                {"id": f"btn_book:{detected_eid}:{lang}", "title": "Solicitar reserva"},
            ]

    # 16. Saludo / ayuda / bienvenida
    if is_en:
        return [
            {"id": f"btn_tours:{lang}", "title": "🗺️ View Tours"},
            {"id": f"btn_advisor:{lang}", "title": "🙋‍♂️ Advisor"},
        ]
    else:
        return [
            {"id": f"btn_tours:{lang}", "title": "🗺️ Ver Tours"},
            {"id": f"btn_advisor:{lang}", "title": "🙋‍♂️ Asesor"},
        ]

    # 8. Si es escalamiento / contacto / handoff
    if route in ("evidence_contact", "evidence_human_escalation"):
        return [
            {"id": f"btn_tours:{lang}", "title": "🗺️ View Tours" if is_en else "🗺️ Ver Tours"},
        ]

    # 9. Por defecto
    if is_en:
        return [
            {"id": f"btn_tours:{lang}", "title": "🗺️ View Tours"},
            {"id": f"btn_advisor:{lang}", "title": "🙋‍♂️ Advisor"},
        ]
    else:
        return [
            {"id": f"btn_tours:{lang}", "title": "🗺️ Ver Tours"},
            {"id": f"btn_advisor:{lang}", "title": "🙋‍♂️ Asesor"},
        ]


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
        items_to_process = []
        has_busy = False
        all_dedup = False
        all_system = False
        seen_unsupported = False
        last_mid = ""

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
            last_mid = message_id
            print(f"[FB INBOUND] psid={psid} user_id={user_id} "
                  f"message_id={message_id} text=\"{user_message[:50]}\"")

            owner = None
            if message_id:
                state, owner = database.claim_webhook(message_id, user_id, SQLITE_DB_PATH)
                if state == 'completed':
                    return JSONResponse(status_code=200, content={"status": "ok", "dedup": True})
                if state == 'uncertain':
                    print(f"[FB UNCERTAIN] Mensaje previo con entrega incierta retenido: id={message_id}")
                    return JSONResponse(status_code=200, content={"status": "ok", "dedup": True, "uncertain": True})
                if state == 'busy':
                    return JSONResponse(status_code=503, content={"status": "processing"}, headers={"Retry-After": "10"})

            items_to_process.append({
                "user_message": user_message,
                "message_id": message_id,
                "owner": owner,
                "user_id": user_id,
                "channel": channel,
                "phone_number": "",
                "bsuid": psid,
                "phone_number_id": None,
                "is_interactive_ambiguous": False,
                "ambiguous_clarif_buttons": [],
                "interaction_lang": None,
            })

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

            entries = body.get("entry", [])
            all_statuses = []
            raw_messages = []

            if isinstance(entries, list):
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    for change in entry.get("changes", []):
                        if not isinstance(change, dict):
                            continue
                        val = change.get("value", {})
                        if not isinstance(val, dict):
                            continue
                        phone_id = val.get("metadata", {}).get("phone_number_id")

                        # Extraer contactos dentro de ESTE change/value únicamente (evitar fugas entre cambios)
                        change_contacts = val.get("contacts", [])
                        contacts_by_wa = {}
                        contacts_by_uid = {}
                        if isinstance(change_contacts, list):
                            for c in change_contacts:
                                if isinstance(c, dict):
                                    c_wa = str(c.get("wa_id", "")).strip()
                                    c_uid = str(c.get("user_id", "")).strip()
                                    if c_wa:
                                        contacts_by_wa[c_wa] = c
                                    if c_uid:
                                        contacts_by_uid[c_uid] = c

                        for st in val.get("statuses", []):
                            all_statuses.append(st)

                        for msg in val.get("messages", []):
                            if not isinstance(msg, dict):
                                continue
                            msg_from = str(msg.get("from", "")).strip()
                            msg_from_uid = str(msg.get("from_user_id", "")).strip()

                            matched_contact = {}
                            if msg_from and msg_from in contacts_by_wa:
                                matched_contact = contacts_by_wa[msg_from]
                            elif msg_from_uid and msg_from_uid in contacts_by_uid:
                                matched_contact = contacts_by_uid[msg_from_uid]
                            elif len(change_contacts) == 1 and isinstance(change_contacts[0], dict):
                                single_c = change_contacts[0]
                                c_wa = str(single_c.get("wa_id", "")).strip()
                                c_uid = str(single_c.get("user_id", "")).strip()
                                if (c_wa and c_wa == msg_from) or (c_uid and c_uid == msg_from_uid) or (not c_wa and not c_uid):
                                    matched_contact = single_c

                            raw_messages.append((msg, matched_contact, phone_id))

            # --- STATUS NOTIFICATIONS (delivery reports) ---
            if all_statuses:
                for st in all_statuses:
                    print(f"[WA DELIVERY STATUS] "
                          f"status={st.get('status')} "
                          f"message_id={st.get('id')} "
                          f"recipient_id={st.get('recipient_id')} "
                          f"recipient_user_id={st.get('recipient_user_id', 'N/A')} "
                          f"recipient_parent_user_id={st.get('recipient_parent_user_id', 'N/A')} "
                          f"errors={st.get('errors', [])} "
                          f"error_code={st.get('errors', [{}])[0].get('code', 'N/A') if st.get('errors') else 'N/A'} "
                          f"error_title={st.get('errors', [{}])[0].get('title', 'N/A') if st.get('errors') else 'N/A'}")
                if not raw_messages:
                    return JSONResponse(status_code=200, content={"status": "ok"})

            if not raw_messages:
                test_uid = body.get("user_id")
                test_msg = body.get("message")
                if test_uid or test_msg:
                    user_id = test_uid or "test_user"
                    user_message = test_msg or ""
                    if not user_message:
                        return JSONResponse(status_code=400, content={"error": "No se proporciono un mensaje valido"})
                    items_to_process.append({
                        "user_message": user_message,
                        "message_id": "",
                        "owner": None,
                        "user_id": user_id,
                        "channel": body.get("channel", "test"),
                        "phone_number": "",
                        "bsuid": "",
                        "phone_number_id": None,
                        "is_interactive_ambiguous": False,
                        "ambiguous_clarif_buttons": [],
                        "interaction_lang": None,
                    })
                else:
                    return JSONResponse(status_code=200, content={"status": "ok", "ignored": "no_messages"})
            else:
                all_system = True
                all_dedup = True
                has_busy = False
                has_uncertain = False
                seen_unsupported = False

                for msg, contact, phone_number_id in raw_messages:
                    msg_id = msg.get("id", "")
                    if msg_id:
                        last_mid = msg_id
                    msg_type = msg.get("type", "")

                    # 1. Filtro from_me (eco saliente oficial de Meta)
                    if msg.get("from_me") is True:
                        print(f"[WA IGNORED] Mensaje saliente from_me=True descartado: {msg_id}")
                        continue

                    # 2. Filtro eventos de sistema de Meta
                    if msg_type == "system":
                        print(f"[WA IGNORED] Mensaje de tipo 'system' descartado: {msg_id}")
                        continue

                    all_system = False
                    user_message = msg.get("text", {}).get("body", "")

                    # 3. Filtro tipos multimedia no soportados sin texto
                    if msg_type not in ("text", "interactive", "button") and not user_message:
                        print(f"[WA IGNORED] Tipo de mensaje no soportado descartado: type={msg_type} id={msg_id}")
                        seen_unsupported = True
                        continue

                    # Extraer identificadores del remitente respetando el mensaje propio
                    contact_wa_id = str(contact.get("wa_id", "")).strip() if contact else ""
                    contact_user_id = str(contact.get("user_id", "")).strip() if contact else ""
                    contact_parent_user_id = str(contact.get("parent_user_id", "")).strip() if contact else ""
                    msg_from = str(msg.get("from", "")).strip()
                    msg_from_user_id = str(msg.get("from_user_id", "")).strip()
                    msg_from_parent_user_id = str(msg.get("from_parent_user_id", "")).strip()
                    msg_timestamp = msg.get("timestamp", "")

                    # Priorizar el remitente del mensaje; recurrir al contacto solo si concuerda o no hay remitente
                    phone_number = (msg_from if msg_from and msg_from.isdigit() else "") or (contact_wa_id if contact_wa_id.isdigit() else "")
                    bsuid = msg_from_user_id or contact_user_id or ""
                    parent_bsuid = msg_from_parent_user_id or contact_parent_user_id or ""
                    user_id = phone_number or bsuid or msg_from or "unknown"

                    is_interactive_ambiguous = False
                    ambiguous_clarif_buttons = []
                    interaction_lang = None

                    # Soporte para respuestas interactivas de WhatsApp
                    if msg_type == "interactive":
                        interactive_obj = msg.get("interactive", {})
                        itype = interactive_obj.get("type", "")
                        btn_id = ""
                        btn_title = ""
                        if itype == "button_reply":
                            reply_data = interactive_obj.get("button_reply", {})
                            btn_id = reply_data.get("id", "")
                            btn_title = reply_data.get("title", "")
                        elif itype == "list_reply":
                            reply_data = interactive_obj.get("list_reply", {})
                            btn_id = reply_data.get("id", "")
                            btn_title = reply_data.get("title", "")

                        btn_parts = btn_id.split(":")
                        action = btn_parts[0]
                        explicit_eid = None
                        explicit_lang = None
                        cat_page_num = 0
                        if action == "btn_cat_page":
                            if len(btn_parts) >= 4:
                                explicit_eid = btn_parts[1]
                                cat_page_num = int(btn_parts[2]) if btn_parts[2].isdigit() else 0
                                explicit_lang = btn_parts[3]
                            elif len(btn_parts) >= 3:
                                explicit_eid = btn_parts[1]
                                cat_page_num = int(btn_parts[2]) if btn_parts[2].isdigit() else 0
                        elif len(btn_parts) >= 3:
                            explicit_eid = btn_parts[1]
                            explicit_lang = btn_parts[2]
                        elif len(btn_parts) == 2:
                            if btn_parts[1] in ("es", "en", "pt"):
                                explicit_lang = btn_parts[1]
                            else:
                                explicit_eid = btn_parts[1]

                        # Detectar idioma de la interacción
                        hist = get_history(user_id) if user_id else []
                        last_user_turn = ""
                        for h in reversed(hist):
                            if h.get("role") == "human":
                                last_user_turn = h.get("content", "")
                                break

                        if explicit_lang in ("es", "en", "pt"):
                            interaction_lang = explicit_lang
                        elif any(w in btn_title.lower() for w in ["passeios", "assessor", "o que inclui", "preços", "rotas regionais", "clássicos cusco"]):
                            interaction_lang = "pt"
                        elif any(w in btn_title.lower() for w in ["rates", "photo", "what's included", "what is included", "advisor", "view tours", "book now", "request reservation", "inca trail", "rainbow mtn", "categories"]):
                            interaction_lang = "en"
                        elif any(w in btn_title.lower() for w in ["qué incluye", "que incluye", "asesor", "ver tours", "más tours"]):
                            interaction_lang = "es"
                        else:
                            history_lang = detect_language(last_user_turn) if last_user_turn else "es"
                            interaction_lang = history_lang if history_lang in ("es", "en", "pt") else "es"

                        is_en = interaction_lang == "en"
                        is_pt = interaction_lang == "pt"

                        def interaction_text(es_text, en_text, pt_text):
                            return pt_text if is_pt else en_text if is_en else es_text

                        target_eid = explicit_eid
                        tours_in_hist = []
                        if not target_eid:
                            from trial_support import normalize
                            try:
                                from catalog_service import get_active_entity_keywords
                                active_kw = get_active_entity_keywords()
                                for h in hist:
                                    if h.get("role") == "human":
                                        norm_c = normalize(h.get("content", ""))
                                        for teid, kws in active_kw.items():
                                            if any(normalize(kw) in norm_c for kw in kws):
                                                if teid not in tours_in_hist:
                                                    tours_in_hist.append(teid)
                            except Exception:
                                pass

                            if len(tours_in_hist) == 1:
                                target_eid = tours_in_hist[0]
                            elif len(tours_in_hist) > 1:
                                target_eid = "__AMBIGUOUS__"

                        tour_name = _get_tour_display_name(target_eid, is_en=is_en) if (target_eid and target_eid != "__AMBIGUOUS__") else ""

                        from catalog_service import is_deactivated_tour
                        # Mapeo semántico de botones interactivos preservando entidad e idioma
                        if target_eid and target_eid != "__AMBIGUOUS__" and is_deactivated_tour(target_eid):
                            user_message = interaction_text(
                                f"informacion de {tour_name or target_eid}",
                                f"information about {tour_name or target_eid}",
                                f"informações sobre {tour_name or target_eid}")
                        elif target_eid == "__AMBIGUOUS__" and action in ("btn_inc", "btn_rates", "btn_price", "btn_photo", "btn_book"):
                            is_interactive_ambiguous = True
                            if is_pt:
                                user_message = "Qual passeio você deseja consultar? Escreva o nome do passeio ou escolha uma opção abaixo."
                                ambiguous_clarif_buttons = [
                                    {"id": f"btn_tour:{t}:pt", "title": _get_tour_button_title(t)}
                                    for t in tours_in_hist[:2]
                                ]
                                ambiguous_clarif_buttons.append({"id": "btn_advisor:pt", "title": "🙋‍♂️ Assessor"})
                            elif is_en:
                                user_message = "Which tour would you like to check? Please specify the tour name (e.g., *Inca Trail* or *City Tour*) 😊"
                                ambiguous_clarif_buttons = [
                                    {"id": f"btn_tour:{t}:en", "title": _get_tour_button_title(t, is_en=True)}
                                    for t in tours_in_hist[:2]
                                ]
                                ambiguous_clarif_buttons.append({"id": "btn_advisor:en", "title": "🙋‍♂️ Advisor"})
                            else:
                                user_message = "¿De cuál de nuestros tours deseas consultar? Por favor escribe el nombre del tour (por ejemplo: *Camino Inca* o *City Tour*) 😊"
                                ambiguous_clarif_buttons = [
                                    {"id": f"btn_tour:{t}:es", "title": _get_tour_button_title(t, is_en=False)}
                                    for t in tours_in_hist[:2]
                                ]
                                ambiguous_clarif_buttons.append({"id": "btn_advisor:es", "title": "🙋‍♂️ Asesor"})
                        elif action == "btn_photo":
                            user_message = interaction_text(
                                f"fotos de {tour_name}" if tour_name else "fotos",
                                f"photos of {tour_name}" if tour_name else "photos",
                                f"fotos do passeio {tour_name}" if tour_name else "fotos do passeio")
                        elif action in ("btn_rates", "btn_price"):
                            user_message = interaction_text(
                                f"tarifas y precios de {tour_name}" if tour_name else "tarifas y precios",
                                f"official rates for {tour_name}" if tour_name else "rates and prices",
                                f"preços oficiais de {tour_name}" if tour_name else "preços oficiais")
                        elif action == "btn_inc":
                            user_message = interaction_text(
                                f"que incluye {tour_name}" if tour_name else "que incluye",
                                f"what does {tour_name} include" if tour_name else "what does it include",
                                f"o que está incluído em {tour_name}" if tour_name else "o que está incluído no passeio")
                        elif action == "btn_book":
                            user_message = interaction_text(
                                f"solicitar reserva de {tour_name}" if tour_name else "solicitar reserva",
                                f"request reservation for {tour_name}" if tour_name else "request reservation",
                                f"solicitar reserva do passeio {tour_name}" if tour_name else "solicitar reserva do passeio")
                        elif action == "btn_advisor":
                            user_message = interaction_text("asesor", "advisor", "consultar assessor")
                        elif action == "btn_cat":
                            cat_key = explicit_eid or ""
                            user_message = interaction_text(f"categoria {cat_key}", f"category {cat_key}", f"categoria {cat_key} de passeios")
                        elif action == "btn_cat_page":
                            cat_key = explicit_eid or ""
                            user_message = interaction_text(
                                f"categoria {cat_key} pagina {cat_page_num}",
                                f"category {cat_key} page {cat_page_num}",
                                f"categoria {cat_key} pagina {cat_page_num} de passeios")
                        elif action in ("btn_cats", "btn_categories", "btn_tours"):
                            user_message = interaction_text("ver categorias de tours", "view tour categories", "ver categorias de passeios")
                        elif action == "btn_tour":
                            user_message = interaction_text(f"informacion de {tour_name}", f"information about {tour_name}", f"informações sobre {tour_name}")
                        elif action == "btn_ci":
                            user_message = interaction_text("informacion de Camino Inca", "information about Inca Trail", "informações sobre Camino Inca")
                        elif action == "btn_mp":
                            user_message = interaction_text("informacion de Machu Picchu en tren", "information about Machu Picchu", "informações sobre Machu Picchu en tren")
                        else:
                            user_message = btn_title or btn_id

                    if not user_message:
                        continue

                    # Deduplicación por mensaje individual
                    owner = None
                    if msg_id:
                        state, owner = database.claim_webhook(msg_id, user_id, SQLITE_DB_PATH)
                        if state == 'completed':
                            print(f"[WA DEDUP] Mensaje ya procesado anteriormente: id={msg_id}")
                            continue
                        if state == 'uncertain':
                            print(f"[WA UNCERTAIN] Mensaje previo con entrega incierta retenido para conciliacion: id={msg_id}")
                            has_uncertain = True
                            continue
                        if state == 'busy':
                            print(f"[WA BUSY] Mensaje en proceso concurrente: id={msg_id}")
                            has_busy = True
                            all_dedup = False
                            continue

                    all_dedup = False
                    print(f"[WA INBOUND] message_id={msg_id} from={msg_from} from_user_id={msg_from_user_id} "
                          f"type={msg_type} timestamp={msg_timestamp} text=\"{user_message[:50]}\" "
                          f"selected_phone={phone_number} user_id={user_id}")

                    items_to_process.append({
                        "user_message": user_message,
                        "message_id": msg_id,
                        "owner": owner,
                        "user_id": user_id,
                        "channel": "whatsapp",
                        "phone_number": phone_number,
                        "bsuid": bsuid,
                        "phone_number_id": phone_number_id,
                        "is_interactive_ambiguous": is_interactive_ambiguous,
                        "ambiguous_clarif_buttons": ambiguous_clarif_buttons,
                        "interaction_lang": interaction_lang,
                    })

        # Función de procesamiento síncrono por mensaje individual
        def _process_one_inbound(item: dict) -> bool:
            import operational_metrics as operational
            event_id = None
            generation_ms = None
            rag_result = {}
            accepted = False
            item_start = time.time()
            item_metric_start = time.perf_counter()

            u_msg = item["user_message"]
            u_id = item["user_id"]
            u_chan = item["channel"]
            m_id = item.get("message_id") or ""
            u_owner = item.get("owner")
            p_num = item.get("phone_number") or ""
            p_bsuid = item.get("bsuid") or ""
            p_id = item.get("phone_number_id")
            is_ambig = item.get("is_interactive_ambiguous", False)
            ambig_btns = item.get("ambiguous_clarif_buttons") or []
            i_lang = item.get("interaction_lang")

            send_status = "rejected"
            is_accepted = False
            receipt_finished = False

            try:
                if u_chan == 'whatsapp':
                    event_id = operational.start()
                if is_ambig:
                    bot_response = u_msg
                    route = "help"
                    quick_buttons = ambig_btns
                    rag_result = {
                        "response": bot_response,
                        "route": "help",
                        "response_route": "help",
                        "resolved_autonomously": False,
                        "is_fallback": False,
                        "is_predefined": True,
                    }
                else:
                    rag_result = rag_chain(u_msg, user_id=u_id)
                    from handoff_support import apply_request
                    rag_result = apply_request(globals(), rag_result, u_id, u_chan, u_msg)
                    bot_response = rag_result["response"]

                resolved_autonomously = rag_result.get("resolved_autonomously", not rag_result.get("is_fallback", False))
                escalated_to_human = rag_result.get('handoff_registered', False)
                is_predefined = rag_result.get("is_predefined", False)
                interaction_type = "predefined" if is_predefined else "llm"
                is_rate_limit = rag_result.get("is_rate_limit", False)
                latency_ms = (time.time() - item_start) * 1000

                database.log_interaction(
                    user_id=u_id,
                    channel=u_chan,
                    detected_language=i_lang or rag_result.get("language") or detect_language(u_msg),
                    user_message=u_msg,
                    bot_response=bot_response,
                    resolved_autonomously=resolved_autonomously,
                    latency_ms=latency_ms,
                    escalated_to_human=escalated_to_human,
                    is_predefined_response=is_predefined,
                    interaction_type=interaction_type,
                    is_rate_limit=is_rate_limit,
                    client_message_id=m_id or None,
                    db_path=SQLITE_DB_PATH,
                )

                generation_ms = (time.perf_counter() - item_metric_start) * 1000
                if u_owner:
                    database.renew_webhook(m_id, u_owner, SQLITE_DB_PATH)

                accepted = u_chan not in {'whatsapp', 'messenger'}
                if u_chan == "whatsapp":
                    bot_response_clean = format_whatsapp_text(bot_response)

                    # Evaluar solicitud de folleto previo al envío de texto para incorporar nota si no existe PDF
                    route = rag_result.get('response_route') or rag_result.get('route') or ''
                    no_multimedia_routes = {'social', 'help', 'evidence_unknown', 'evidence_conflict', 'evidence_contact', 'evidence_listing', 'evidence_inactive_tour'}
                    detected_eid = rag_result.get('entity_id') or ''

                    tour_doc_info = None
                    if is_brochure_requested(u_msg) and route not in no_multimedia_routes:
                        tour_doc_info = get_tour_brochure_data(u_msg + " " + bot_response, user_msg=u_msg, entity_id=detected_eid)
                        if not tour_doc_info:
                            bot_response_clean += "\n\n📄 _Nota: Actualmente este tour no cuenta con folleto en PDF en línea, pero nuestro asesor te facilitará el itinerario completo._"

                    # 1. Despacho seguro de Fotografía SOLO si fue solicitada y existe en catálogo
                    photo_api_accepted = None
                    if route == "evidence_photo" and is_photo_requested(u_msg):
                        tour_img_info = get_tour_image_data(u_msg + " " + bot_response, user_msg=u_msg, entity_id=detected_eid)
                        if tour_img_info:
                            img_url, img_caption = tour_img_info
                            photo_api_accepted = send_whatsapp_image(
                                image_url=img_url,
                                caption=img_caption,
                                to_phone=p_num if p_num else None,
                                recipient_bsuid=p_bsuid if p_bsuid else None,
                                phone_number_id=p_id,
                            )
                            if photo_api_accepted:
                                print(f"[WA MULTIMEDIA PHOTO API ACCEPTED] to={p_num or p_bsuid} url={img_url}")
                            else:
                                print(f"[WA MULTIMEDIA PHOTO SEND FAILED] to={p_num or p_bsuid} url={img_url}")
                                is_en_user = (detect_language(u_msg) == "en")
                                is_pt_user = (detect_language(u_msg) == "pt")
                                tour_name_disp = _get_tour_display_name(detected_eid, is_en=is_en_user) if detected_eid else ""
                                bot_response_clean = (
                                    f"Não conseguimos carregar a fotografia oficial de *{tour_name_disp or 'este passeio'}*. Nosso assessor poderá compartilhar a galeria diretamente."
                                    if is_pt_user else
                                    f"Tuvimos un inconveniente al cargar la fotografía oficial de *{tour_name_disp or 'este tour'}*. Nuestro asesor te compartirá la galería completa directamente."
                                    if not is_en_user else
                                    f"We encountered an issue loading the official photo for *{tour_name_disp or 'this tour'}*. Our advisor will share the full gallery directly with you."
                                )

                    # Botones de respuesta rápida interactivos (Meta WhatsApp Cloud API)
                    if not is_ambig:
                        eff_lang = i_lang or rag_result.get("language") or detect_language(u_msg)
                        if eff_lang not in ("es", "en", "pt"):
                            eff_lang = "es"
                        quick_buttons = get_quick_buttons(
                            route=route,
                            user_message=u_msg,
                            detected_eid=detected_eid,
                            lang=eff_lang,
                            photo_send_failed=(photo_api_accepted is False),
                        )

                    accepted = u_id != 'unknown' and send_whatsapp_message(
                        text=bot_response_clean,
                        to_phone=p_num if p_num else None,
                        recipient_bsuid=p_bsuid if p_bsuid else None,
                        phone_number_id=p_id,
                        buttons=quick_buttons,
                    )

                    # Determinar el estado formal de salida: accepted, rejected o uncertain
                    send_status = "rejected"
                    is_accepted = False
                    if hasattr(accepted, "status"):
                        send_status = accepted.status
                        is_accepted = accepted.is_accepted
                    elif accepted is True:
                        send_status = "accepted"
                        is_accepted = True
                    elif accepted is False:
                        send_status = "rejected"
                        is_accepted = False

                    # Finalizar el recibo inmediatamente tras el intento de envío para asegurar
                    # que cualquier fallo posterior no sobreescriba su resultado legítimo.
                    if u_owner and not receipt_finished:
                        try:
                            database.finish_webhook(m_id, u_owner, send_status, SQLITE_DB_PATH)
                            receipt_finished = True
                        except Exception as db_err:
                            print(f"[DB ERROR] Error finalizando recibo temprano: {db_err}")

                    # 2. Despacho de Folleto PDF si fue solicitado y está cargado en el catálogo
                    try:
                        if is_accepted and tour_doc_info and route not in no_multimedia_routes:
                            doc_url, doc_filename, doc_caption = tour_doc_info
                            send_whatsapp_document(
                                document_url=doc_url,
                                filename=doc_filename,
                                caption=doc_caption,
                                to_phone=p_num if p_num else None,
                                recipient_bsuid=p_bsuid if p_bsuid else None,
                                phone_number_id=p_id,
                            )
                            print(f"[WA MULTIMEDIA BROCHURE SENT] to={p_num or p_bsuid} filename={doc_filename}")
                    except Exception as media_err:
                        print(f"[WA MULTIMEDIA DISPATCH ERROR] {media_err}")

                    op_status = "api_accepted" if is_accepted else ("send_uncertain" if send_status == "uncertain" else "send_failed")
                    try:
                        operational.finish(event_id, op_status,
                                           generation_ms, (time.perf_counter()-item_metric_start)*1000, rag_result)
                    except Exception as op_err:
                        print(f"[OPERATIONAL METRICS ERROR] {op_err}")
                elif u_chan == "messenger":
                    accepted = send_messenger_message(text=bot_response, psid=p_bsuid)
                    send_status = "accepted" if accepted else "rejected"
                    is_accepted = bool(accepted)
                    print(f"[FB OUTBOUND RESULT] psid={p_bsuid} accepted={accepted}")
                    if u_owner and not receipt_finished:
                        try:
                            database.finish_webhook(m_id, u_owner, send_status, SQLITE_DB_PATH)
                            receipt_finished = True
                        except Exception as db_err:
                            print(f"[DB ERROR] Error finalizando recibo messenger: {db_err}")
                elif u_chan == "test":
                    send_status = "accepted"
                    is_accepted = True
                    if u_owner and not receipt_finished:
                        try:
                            database.finish_webhook(m_id, u_owner, send_status, SQLITE_DB_PATH)
                            receipt_finished = True
                        except Exception as db_err:
                            print(f"[DB ERROR] Error finalizando recibo test: {db_err}")

                if u_owner and not receipt_finished:
                    database.finish_webhook(m_id, u_owner, send_status, SQLITE_DB_PATH)
                    receipt_finished = True
                elapsed = (time.time() - item_start) * 1000
                channel_tag = "FB" if u_chan == "messenger" else ("TEST" if u_chan == "test" else "WA")
                print(f"[{channel_tag} PROCESSED] user_id={u_id} latency={elapsed:.0f}ms route={rag_result.get('response_route', 'unknown')}")
                return send_status
            except Exception as e:
                elapsed = (time.time() - item_start) * 1000
                if u_owner and not receipt_finished:
                    final_receipt_status = send_status if send_status in ("accepted", "uncertain") else "failed"
                    try:
                        database.finish_webhook(m_id, u_owner, final_receipt_status, SQLITE_DB_PATH)
                        receipt_finished = True
                    except Exception as db_err:
                        print(f"[DB ERROR] Error finalizando recibo en excepción: {db_err}")
                if event_id:
                    try:
                        operational.finish(event_id, 'processing_failed', generation_ms,
                                           (time.perf_counter()-item_metric_start)*1000, rag_result)
                    except Exception:
                        pass
                channel_tag = "FB" if u_chan == "messenger" else ("TEST" if u_chan == "test" else "WA")
                print(f"[{channel_tag} ERROR] user_id={u_id} error={e} latency={elapsed:.0f}ms")
                return send_status if send_status in ("accepted", "uncertain") else "failed"

        if not items_to_process:
            if has_busy:
                return JSONResponse(status_code=503, content={"status": "processing"}, headers={"Retry-After": "10"})
            if all_system:
                return JSONResponse(status_code=200, content={"status": "ok", "ignored": "system_message"})
            if all_dedup or has_uncertain:
                return JSONResponse(status_code=200, content={"status": "ok", "dedup": True, "uncertain": has_uncertain})
            if seen_unsupported:
                return JSONResponse(status_code=200, content={"status": "ok", "ignored": "unsupported_type"})
            return JSONResponse(status_code=200, content={"status": "ok"})

        has_failure = False
        has_uncertain_send = False
        for item in items_to_process:
            outcome = await asyncio.to_thread(_process_one_inbound, item)
            if outcome == "uncertain":
                has_uncertain_send = True
            elif outcome in ("rejected", "failed", False):
                has_failure = True

        if has_failure or has_uncertain_send:
            return JSONResponse(status_code=503, content={"error": "Procesamiento temporalmente no disponible"}, headers={"Retry-After": "10"})

        if has_busy:
            return JSONResponse(status_code=503, content={"status": "processing"}, headers={"Retry-After": "10"})

        return JSONResponse(status_code=200, content={
            "status": "ok",
            "message_id": last_mid,
        })

    except Exception as e:
        print(f"[WEBHOOK INTERNAL ERROR] {e}")
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
        detected_lang = rag_result.get("language") or detected_lang
        bot_response = rag_result["response"]

        # Enriquecer respuesta en /test-chat para que fotos y folletos se muestren en la UI web
        from src.visual.visual_engine import is_photo_requested, is_brochure_requested, get_tour_image_data, get_tour_brochure_data
        detected_eid = rag_result.get('entity_id') or ''
        route = rag_result.get('response_route') or rag_result.get('route') or ''
        no_multimedia_routes = {'social', 'help', 'evidence_unknown', 'evidence_conflict', 'evidence_contact', 'evidence_listing', 'evidence_inactive_tour'}

        if is_photo_requested(request.message) and route not in no_multimedia_routes:
            tour_img_info = get_tour_image_data(request.message + " " + bot_response, user_msg=request.message, entity_id=detected_eid)
            if tour_img_info:
                img_url, img_caption = tour_img_info
                bot_response += f"\n\n![{img_caption}]({img_url})"

        if is_brochure_requested(request.message) and route not in no_multimedia_routes:
            tour_doc_info = get_tour_brochure_data(request.message + " " + bot_response, user_msg=request.message, entity_id=detected_eid)
            if tour_doc_info:
                doc_url, doc_filename, doc_caption = tour_doc_info
                bot_response += f"\n\n[📄 Descargar Folleto PDF: {doc_filename}]({doc_url})"

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

        quick_buttons = get_quick_buttons(
            route=route,
            user_message=request.message,
            detected_eid=detected_eid,
            lang=detected_lang,
        )

        return JSONResponse(status_code=200, content={
            "status": "ok",
            "response": bot_response,
            "quick_buttons": quick_buttons,
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
                            'Consulta el <a href="/operational-metrics">registro operativo de WhatsApp</a> y <a href="/handoffs">Atención al cliente</a>.'
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
