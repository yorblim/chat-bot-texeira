"""
preprocessing.py — Tokenización y normalización léxica multilingüe.

Módulo central del pipeline de recuperación híbrido. Resuelve el problema
crítico de la recuperación inexacta de información turística andina:
toponimias en quechua con variaciones ortográficas y fonéticas.

Problema que resuelve:
  Turistas escriben "Sacsayhuaman", "Saqsaywaman", "Sacsahuaman" o
  "Sacsaywaman" — todos refieren al mismo sitio arqueológico. Un retriever
  BM25 tradicional falla porque trata cada variante como un término distinto.

Solución:
  Diccionario de normalización que mapea variantes fonéticas y ortográficas
  de 40+ términos quechuas/andinos a su forma canónica, combinado con
  normalización estándar del español (tildes, minúsculas, stop words).

Uso:
  from src.preprocessing import normalize_query, tokenize_for_bm25
  canonical = normalize_query("Sacsayhuaman es gratis?")
  tokens = tokenize_for_bm25("¿Cuánto cuesta el tour de Sacsayhuaman?")
"""

import json
import re
import unicodedata
from pathlib import Path
from typing import List, Set

# ============================================================
# DICCIONARIO DE NORMALIZACIÓN QUECHUA/ANDINO
# ============================================================
# Mapea variantes fonéticas y ortográficas a la forma canónica.
# Fuente: consultas a lugareños, guías turísticos de Cusco y
# documentación del Ministerio de Cultura del Perú.

QUECHUA_NORMALIZATION: dict[str, str] = {
    # === Sacsayhuamán ===
    "sacsayhuaman": "sacsayhuaman",
    "sacsahuaman": "sacsayhuaman",
    "sacsaywaman": "sacsayhuaman",
    "saqsaywaman": "sacsayhuaman",
    "sacsayhuamán": "sacsayhuaman",
    "sacsahuamán": "sacsayhuaman",
    "sacsaywamán": "sacsayhuaman",
    "sacsaywaman": "sacsayhuaman",
    "sacsahuaman": "sacsayhuaman",
    "sacsayhuamam": "sacsayhuaman",
    "sacsayhuaman": "sacsayhuaman",

    # === Qorikancha ===
    "qorikancha": "qorikancha",
    "qorikanka": "qorikancha",
    "korikancha": "qorikancha",
    "korikanka": "qorikancha",
    "qoricancha": "qorikancha",
    "coricancha": "qorikancha",
    "qorikanchá": "qorikancha",
    "korikanchá": "qorikancha",

    # === Ollantaytambo ===
    "ollantaytambo": "ollantaytambo",
    "ollantay tampo": "ollantaytambo",
    "ollantaytampho": "ollantaytambo",
    "ollantaytampu": "ollantaytambo",
    "uyantay tambo": "ollantaytambo",
    "ollantaytambo": "ollantaytambo",
    "ollantaytambo": "ollantaytambo",

    # === Machu Picchu ===
    "machu picchu": "machupicchu",
    "machupicchu": "machupicchu",
    "machu pikchu": "machupicchu",
    "machu piccho": "machupicchu",
    "machu pichu": "machupicchu",
    "maqchu pikchu": "machupicchu",
    "old peak": "machupicchu",
    "machu picchu": "machupicchu",

    # === Huayna Picchu ===
    "huayna picchu": "huaynapicchu",
    "huaynapicchu": "huaynapicchu",
    "wayna picchu": "huaynapicchu",
    "huayna pikchu": "huaynapicchu",
    "huayna picchu": "huaynapicchu",

    # === Intihuatana ===
    "intihuatana": "intihuatana",
    "inti watana": "intihuatana",
    "intihuatana": "intihuatana",
    "inti wáhtana": "intihuatana",

    # === Pisac ===
    "pisac": "pisac",
    "pisraq": "pisac",
    "pisarac": "pisac",
    "pisac": "pisac",

    # === Chinchero ===
    "chinchero": "chinchero",
    "chincheru": "chinchero",
    "chinchéu": "chinchero",

    # === Humantay ===
    "humantay": "humantay",
    "humant'a": "humantay",
    "uman tay": "humantay",
    "humantay": "humantay",

    # === Vinicunca ===
    "vinicunca": "vinicunca",
    "wiñi cunca": "vinicunca",
    "vinicunca": "vinicunca",
    "vinicunca": "vinicunca",

    # === Ausangate ===
    "ausangate": "ausangate",
    "awsangate": "ausangate",
    "ausangate": "ausangate",

    # === Moray ===
    "moray": "moray",
    "moray": "moray",

    # === Maras ===
    "maras": "maras",
    "salinas de maras": "maras",

    # === Otros términos andinos ===
    "pachamama": "pachamama",
    "apu": "apu",
    "ayllu": "ayllu",
    "khipu": "khipu",
    "quipu": "khipu",
    "tambo": "tambo",
    "chaski": "chaski",
    "misqchi": "misqchi",
    "allin punchau": "allinpunchau",
    "saylla": "saylla",
    "urubamba": "urubamba",
    "vilcanota": "vilcanota",
    "vilcabamba": "vilcabamba",
    "tambopata": "tambopata",
    "manu": "manu",
}

# ============================================================
# STOP WORDS MULTILINGÜES
# ============================================================

STOP_WORDS_ES: Set[str] = {
    "de", "la", "el", "en", "y", "a", "los", "del", "las", "un", "una",
    "por", "con", "no", "se", "que", "es", "al", "lo", "como", "más",
    "pero", "sus", "le", "ya", "o", "este", "sí", "porque", "esta",
    "entre", "cuando", "muy", "sin", "sobre", "también", "me", "hasta",
    "hay", "donde", "quien", "desde", "todo", "nos", "durante", "todos",
    "uno", "les", "ni", "contra", "otros", "ese", "eso", "ante", "ellos",
    "e", "esto", "mí", "antes", "algunos", "qué", "unos", "yo", "otro",
    "otras", "otra", "él", "tanto", "esa", "estos", "mucho", "quienes",
    "nada", "muchos", "cual", "poco", "ella", "estar", "estas", "algunas",
    "algo", "nosotros", "tiene", "ser", "tan", "puede", "había", "era",
    "cada", "fue", "ese", "eso", "haber", "esas", "estaba", "estoy",
    "había", "hubo", "sería", "tengo", "tendría", "tendría", "será",
    "tiene", "tendría", "habría", "sería", "sería", "sería", "sería",
}

STOP_WORDS_EN: Set[str] = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "just", "because", "but", "and", "or", "if", "while", "about", "up",
    "it", "its", "i", "me", "my", "we", "our", "you", "your", "he", "him",
    "his", "she", "her", "they", "them", "their", "what", "which", "who",
    "whom", "this", "that", "these", "those", "am", "im",
}

STOP_WORDS_PT: Set[str] = {
    "de", "a", "o", "que", "e", "do", "da", "em", "um", "para", "é",
    "com", "não", "uma", "os", "no", "se", "na", "por", "mais", "dos",
    "como", "mas", "foi", "ao", "ele", "das", "tem", "seu", "sua", "ou",
    "ser", "quando", "muito", "há", "nos", "já", "está", "eu", "também",
    "só", "pelo", "pela", "até", "isso", "ela", "entre", "era", "depois",
    "sem", "mesmo", "aos", "ter", "seus", "quem", "nas", "me", "esse",
    "eles", "estão", "você", "tinha", "foram", "essa", "num", "nem",
    "suas", "meu", "às", "minha", "têm", "numa", "pelos", "elas",
    "havia", "seja", "qual", "será", "nós", "tenho", "lhe", "deles",
    "essas", "esses", "pelas", "este", "fosse", "dele", "tu", "te",
    "vocês", "vos", "lhes", "meus", "minhas", "teu", "tua", "teus",
    "tuas", "nosso", "nossa", "nossos", "nossas", "dela", "delas",
    "esta", "estes", "estas", "aquele", "aquela", "aqueles", "aquelas",
    "isto", "aquilo", "estou", "está", "estamos", "estão", "estive",
    "estivemos", "estiveram", "estava", "estávamos", "estavam", "estivera",
}

# ============================================================
# FUNCIONES DE NORMALIZACIÓN
# ============================================================

# Compilar regex una sola vez para reutilización
_RE_NON_ALPHA = re.compile(r"[^\w\s]", re.UNICODE)
_RE_MULTI_SPACE = re.compile(r"\s+", re.UNICODE)


def strip_accents(text: str) -> str:
    """Elimina acentos/diacríticos: á→a, ñ→n, ü→u."""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def normalize_quechua(term: str) -> str:
    """
    Normaliza un término quechua/andino a su forma canónica.

    Resuelve variaciones ortográficas y fonéticas:
      - "Sacsayhuaman" → "sacsayhuaman"
      - "Saqsaywaman"  → "sacsayhuaman"
      - "Korikancha"   → "qorikancha"

    Args:
        term: Término en minúsculas ya normalizado.

    Returns:
        Forma canónica del término, o el término original si no está en
        el diccionario.
    """
    return QUECHUA_NORMALIZATION.get(term, term)


def tokenize_for_bm25(text: str, lang: str = "es") -> List[str]:
    """
    Tokeniza y normaliza texto para BM25.

    Pipeline:
      1. Minúsculas
      2. Eliminación de acentos
      3. Eliminación de puntuación
      4. Tokenización por espacio
      5. Eliminación de stop words
      6. Normalización quechua para cada token

    Args:
        text: Texto de entrada (query o documento).
        lang: Idioma del texto ('es', 'en', 'pt').

    Returns:
        Lista de tokens normalizados.
    """
    if not text:
        return []

    # Seleccionar stop words según idioma
    if lang == "en":
        stop_words = STOP_WORDS_EN
    elif lang == "pt":
        stop_words = STOP_WORDS_PT
    else:
        stop_words = STOP_WORDS_ES

    # Pipeline de normalización
    text = text.lower()
    text = strip_accents(text)
    text = _RE_NON_ALPHA.sub(" ", text)
    text = _RE_MULTI_SPACE.sub(" ", text).strip()

    tokens = text.split()

    # Filtrar stop words y aplicar normalización quechua
    result = []
    for token in tokens:
        if token in stop_words or len(token) < 2:
            continue
        canonical = normalize_quechua(token)
        result.append(canonical)

    return result


def normalize_query(text: str, lang: str = "es") -> str:
    """
    Normaliza una query completa (para embedding y para BM25).

    Aplica normalización quechua a los términos compuestos y individuales.
    Retorna el texto normalizado como string (no como tokens).

    Args:
        text: Query del usuario.
        lang: Idioma detectado.

    Returns:
        Texto normalizado con formas canónicas de términos quechuas.
    """
    if not text:
        return ""

    # Normalizar variantes de términos compuestos primero
    normalized = text.lower()
    for variant, canonical in sorted(QUECHUA_NORMALIZATION.items(),
                                     key=lambda x: -len(x[0])):
        if variant in normalized:
            normalized = normalized.replace(variant, canonical)

    # Limpiar puntuación y normalizar espacios
    normalized = strip_accents(normalized)
    normalized = _RE_NON_ALPHA.sub(" ", normalized)
    normalized = _RE_MULTI_SPACE.sub(" ", normalized).strip()

    return normalized


def detect_language(text: str) -> str:
    """
    Detecta el idioma del texto de forma ligera (sin dependencias externas).

    Usa heurísticas de caracteres frecuentes para español, inglés y portugués.
    Para detección precisa en producción, usar langdetect (ya integrado en
    app.py).

    Args:
        text: Texto de entrada.

    Returns:
        Código de idioma ('es', 'en', 'pt').
    """
    text_lower = text.lower()

    # Señales fuertes de español
    es_signals = ["¿", "¡", "cuánto", "cuántos", "tienen", "tour", "precio",
                  "disponibilidad", "quiero", "necesito", "puedo", "gracias",
                  "buenos", "buenas", "señor", "señora"]
    es_count = sum(1 for s in es_signals if s in text_lower)

    # Señales fuertes de portugués
    pt_signals = ["você", "obrigado", "obrigada", "quanto", "quais",
                  "gostaria", "poderia", "tenho", "preciso", "bom", "boa",
                  "senhor", "senhora", "noite", "dia"]
    pt_count = sum(1 for s in pt_signals if s in text_lower)

    # Señales fuertes de inglés
    en_signals = ["how much", "what", "where", "when", "which", "i want",
                  "i need", "can i", "do you", "is there", "thank you",
                  "hello", "good morning", "good afternoon"]
    en_count = sum(1 for s in en_signals if s in text_lower)

    if es_count >= pt_count and es_count >= en_count:
        return "es"
    elif pt_count >= en_count:
        return "pt"
    else:
        return "en"


def load_catalog(data_path: str = None) -> dict:
    """
    Carga el catálogo de tours desde JSON.

    Args:
        data_path: Ruta al archivo tours_catalog.json.
                   Si es None, busca en data/tours_catalog.json relativo
                   al directorio del proyecto.

    Returns:
        Diccionario con el catálogo completo.
    """
    if data_path is None:
        data_path = Path(__file__).resolve().parent.parent / "data" / "tours_catalog.json"
    else:
        data_path = Path(data_path)

    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


def catalog_to_documents(
    catalog: dict,
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> List[dict]:
    """
    Convierte el catálogo JSON a documentos chunked para indexación.

    Aplica chunking semántico (RecursiveCharacterTextSplitter) para que cada
    chunk quepa en el contexto del LLM. La metadata estructurada (tour_id,
    price_usd, images, etc.) se propaga a CADA chunk resultante.

    Args:
        catalog: Diccionario del catálogo (load_catalog()).
        chunk_size: Tamaño máximo de chunk en caracteres (default: 800).
        chunk_overlap: Superposición entre chunks (default: 150).

    Returns:
        Lista de documentos chunked, cada uno con 'page_content' y 'metadata'.
    """
    from langchain.text_splitter import RecursiveCharacterTextSplitter

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    documents = []

    for tour in catalog.get("tours", []):
        # Construir texto plano para indexing
        sections = []

        sections.append(f"Tour: {tour['name']}")
        sections.append(f"Descripción: {tour['description']}")
        sections.append(f"Categoría: {tour['category']}")

        duration_val = tour.get('duration_hours', tour.get('duration_days', 'N/A'))
        duration_unit = 'horas' if 'duration_hours' in tour else 'días'
        sections.append(f"Duración: {duration_val} {duration_unit}")

        price_pen = tour.get('price_pen')
        if price_pen:
            sections.append(f"Precio: ${tour['price_usd']} USD / S/{price_pen} PEN por persona")
        else:
            sections.append(f"Precio: ${tour['price_usd']} USD por persona")

        if tour.get("highlights"):
            sections.append("Puntos de interés: " + ", ".join(tour["highlights"]))

        if tour.get("itinerary"):
            sections.append("Itinerario:")
            for step in tour["itinerary"]:
                sections.append(f"  - {step}")

        if tour.get("includes"):
            sections.append("Incluye: " + ", ".join(tour["includes"]))

        if tour.get("not_includes"):
            sections.append("No incluye: " + ", ".join(tour["not_includes"]))

        if tour.get("schedule"):
            sched = tour["schedule"]
            sections.append(f"Horario: Salida {sched.get('departure', 'N/A')}, "
                          f"Retorno {sched.get('return', 'N/A')}, "
                          f"Frecuencia: {sched.get('frequency', 'N/A')}")
            if sched.get("advance_booking"):
                sections.append(f"Reserva anticipada: {sched['advance_booking']}")

        if tour.get("physical_requirements"):
            sections.append(f"Requisitos físicos: {tour['physical_requirements']}")

        if tour.get("cancellation_policy"):
            sections.append(f"Política de cancelación: {tour['cancellation_policy']}")

        # Keywords para boosting en BM25
        all_keywords = tour.get("keywords", []) + tour.get("keywords_en", [])
        if all_keywords:
            sections.append("Palabras clave: " + ", ".join(all_keywords))

        # Aliases quechuas para normalización
        aliases = tour.get("aliases_quechua", [])
        if aliases:
            sections.append("Nombres alternativos: " + ", ".join(aliases))

        full_text = "\n".join(sections)

        # Metadata base que se propaga a todos los chunks del tour
        base_metadata = {
            "tour_id": tour["id"],
            "tour_name": tour["name"],
            "tour_name_en": tour.get("name_en", ""),
            "category": tour["category"],
            "price_usd": tour["price_usd"],
            "price_pen": tour.get("price_pen"),
            "source": "tours_catalog",
        }
        if tour.get("images"):
            base_metadata["images"] = tour["images"]

        # Chunking: dividir el texto y propagar metadata a cada chunk
        chunks = text_splitter.split_text(full_text)
        for i, chunk in enumerate(chunks):
            chunk_metadata = {
                **base_metadata,
                "chunk_index": i,
                "chunk_total": len(chunks),
            }
            documents.append({
                "page_content": chunk,
                "metadata": chunk_metadata,
            })

    # Agregar documento de políticas generales (sin chunking — texto corto)
    policies = catalog.get("policies", {})
    if policies:
        policy_sections = ["POLÍTICAS GENERALES DE LA AGENCIA"]
        policy_sections.append(f"Métodos de pago: {', '.join(policies.get('payment_methods', []))}")
        policy_sections.append(f"Anticipo requerido: {policies.get('deposit_required', 'N/A')}")
        policy_sections.append(f"Descuento niños: {policies.get('children_discount', 'N/A')}")
        policy_sections.append(f"Descuento grupos: {policies.get('group_discount', 'N/A')}")

        for note in policies.get("safety_notes", []):
            policy_sections.append(f"Seguridad: {note}")

        for note in policies.get("weather_considerations", []):
            policy_sections.append(f"Clima: {note}")

        policy_text = "\n".join(policy_sections)
        policy_chunks = text_splitter.split_text(policy_text)
        for i, chunk in enumerate(policy_chunks):
            documents.append({
                "page_content": chunk,
                "metadata": {
                    "tour_id": "policies",
                    "tour_name": "Políticas Generales",
                    "category": "policies",
                    "source": "tours_catalog",
                    "chunk_index": i,
                    "chunk_total": len(policy_chunks),
                },
            })

    return documents
