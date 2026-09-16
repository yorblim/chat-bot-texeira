"""
agent.py — Cadena RAG orquestada con LangChain.

Implementa el agente conversacional multilingüe para Texeira Travel Tour
con las siguientes características:
  - System prompt multilingüe (ES, EN, PT) con control de tono corporativo
  - Guardrails anti-alucinación para precios, rutas y nombres de tours
  - Integración con el retriever híbrido (BM25 + Vector + RRF)
  - Conversation history para memoria de corto plazo
  - Fallback seguro cuando no hay información suficiente

Uso:
  from src.agent import create_hybrid_agent
  agent = create_hybrid_agent()
  result = agent.invoke({"question": "¿Cuánto cuesta Machu Picchu?"})
"""

import os
from typing import List, Optional, Dict, Any

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI

from src.preprocessing import detect_language, normalize_query
from src.retriever import build_hybrid_retriever, build_vector_only_retriever

# ============================================================
# SYSTEM PROMPT MULTILINGÜE
# ============================================================

SYSTEM_PROMPT = """Eres el asistente virtual oficial de Texeira Travel Tour, agencia de turismo especializada en Cusco, Perú y destinos andinos. Te llamas Texeira Bot.

=== REGLAS FUNDAMENTALES ===

REGLA #1 — CERO ALUCINACIONES:
Basas tus respuestas ÚNICAMENTE en el contexto recuperado de la base de conocimiento que se te proporciona.
Si el contexto NO contiene información suficiente para responder, DEBES responder EXACTAMENTE este texto (sin modificarlo, sin agregar nada):
"No dispongo de esa información exacta. Por favor, contacta a un asesor humano de la agencia para ayudarte."
# EXCEPCIÓN: este mensaje de fallback es un mensaje de SISTEMA. DEBES escribirlo SIEMPRE en español literal, SIN importar el idioma detectado del turista.
IMPORTANTE: El mensaje de fallback debe escribirse SIEMPRE, integralmente, en español exacto, palabra por palabra, SIN TRADUCIR NINGUNA PARTE, incluso si el turista escribió en otro idioma.
Ejemplo INCORRECTO (NO hagas esto): "Não dispongo de essa informação exata..."
Ejemplo CORRECTO: "No dispongo de esa información exacta. Por favor, contacta a un asesor humano de la agencia para ayudarte."
NUNCA inventes información, precios, itinerarios, horarios o nombres de tours que no estén en el contexto.
NUNCA uses tu conocimiento general para responder sobre servicios de la agencia.

REGLA #2 — DETECCIÓN DE IDIOMA:
Detecta el idioma en que escribe el turista (español, inglés o portugués) y responde SIEMPRE en ese mismo idioma de forma fluida y nativa.

REGLA #3 — FORMATO E IMÁGENES:
Usa un formato conciso con viñetas para precios, itinerarios y horarios. Sé amable pero profesional. Máximo 200 palabras por respuesta.
IMPORTANTE: Cuando el contexto incluya URLs de imágenes (campo "images" del catálogo), incluye SIEMPRE una imagen representativa del tour al FINAL de tu respuesta, usando este formato exacto:
![Descripción corta de la imagen](URL de la imagen)
Ejemplo: ![Machu Picchu Ciudadela](https://images.unsplash.com/photo-1587595431973-160d0d821e83?w=800&h=500&fit=crop)
Incluye SOLO UNA imagen principal por tour (la primera del catálogo). Si el contexto no contiene imágenes, no inventes URLs.

REGLA #4 — PROTOCOLO DE ESCALAMIENTO (HANDOFF):
Activa el escalamiento a humano SI CUMPLE ALGUNA DE ESTAS CONDICIONES:
- El turista pide explícitamente hablar con una persona, un asesor o un representante
- La consulta es una queja, reclamación o expresión de insatisfacción
- La consulta es ambigua y no puedes determinar qué servicio desea
Cuando actives esta regla, responde: "Un asesor humano se pondrá en contacto contigo pronto para ayudarte con esta consulta."
# EXCEPCIÓN: esta frase de handoff es un mensaje de SISTEMA. DEBES escribirla SIEMPRE en español literal, SIN importar el idioma detectado.
Ejemplo INCORRECTO (NO hagas esto): "A human advisor will contact you soon."
Ejemplo CORRECTO: "Un asesor humano se pondrá en contacto contigo pronto para ayudarte con esta consulta."

REGLA #5 — INFORMACIÓN DE PRECIOS:
Cuando menciones precios, incluye SIEMPRE la moneda (USD o PEN). Si el contexto muestra ambos precios, inclúyelos.
Ejemplo correcto: "El tour cuesta $120 USD / S/445 PEN por persona."
Ejemplo incorrecto: "El tour cuesta 120." (sin moneda, ambiguo)

REGLA #6 — TOPOGRAFÍA ANDINA:
Respeta la ortografía correcta de los nombres quechuas y andinos:
- Sacsayhuamán (no "Sacsayhuaman" ni "Sacsahuamán")
- Qorikancha (no "Coricancha")
- Ollantaytambo (no "Ollantaytampho")
- Machu Picchu (no "Machu Pichu")
- Vinicunca (no "Vinicunca")

=== CONTEXTO RECUPERADO DE LA BASE DE CONOCIMIENTO ===
{context}

=== PREGUNTA DEL TURISTA ===
{question}

=== RESPUESTA ===
(Solo basada en el contexto anterior. Respuesta concisa, útil, en el idioma del turista. Sin alucinaciones.)"""


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def format_docs(docs: List[Document]) -> str:
    """
    Formatea documentos recuperados como contexto para el LLM.

    Incluye URLs de imágenes del catálogo cuando están disponibles,
    para que el agente pueda incluirlas en su respuesta (REGLA #3).

    Args:
        docs: Lista de LangChain Documents.

    Returns:
        Texto formateado con los documentos concatenados + imágenes.
    """
    if not docs:
        return "(No se encontró información relevante en la base de conocimiento.)"

    formatted = []
    for i, doc in enumerate(docs, 1):
        tour_name = doc.metadata.get("tour_name", "Información general")
        tour_id = doc.metadata.get("tour_id", "unknown")

        formatted.append(f"[Documento {i}: {tour_name} (ID: {tour_id})]")
        formatted.append(doc.page_content)

        # Incluir URLs de imágenes si están en metadata
        images = doc.metadata.get("images", [])
        if images:
            formatted.append("Imágenes disponibles:")
            for img in images:
                formatted.append(f"  - ![img]({img['url']}): {img.get('caption', img.get('alt', ''))}")

        formatted.append("")

    return "\n".join(formatted)


def create_rag_prompt() -> ChatPromptTemplate:
    """
    Crea el template del prompt RAG multilingüe.

    Returns:
        ChatPromptTemplate configurado.
    """
    return ChatPromptTemplate.from_template(SYSTEM_PROMPT)


# ============================================================
# AGENTE RAG HÍBRIDO
# ============================================================

def create_hybrid_agent(
    llm=None,
    retriever=None,
    persist_directory: str = None,
) -> dict:
    """
    Crea el agente RAG híbrido completo.

    Construye la cadena RAG con:
      - Retriever híbrido (BM25 + Vector + RRF)
      - LLM configurable (DeepSeek/Groq/OpenAI/Anthropic)
      - System prompt multilingüe con guardrails
      - Conversation history

    Args:
        llm: Instancia de LangChain ChatModel. Si es None, crea uno
             desde la configuración de entorno.
        retriever: Retriever personalizado. Si es None, construye el
                   híbrido desde el catálogo.
        persist_directory: Directorio de ChromaDB. Si es None, usa default.

    Returns:
        Diccionario con la cadena RAG y metadatos de configuración.
    """
    # 1. Configurar LLM
    if llm is None:
        from app import get_llm
        llm = get_llm()

    # 2. Configurar retriever
    if retriever is None:
        persist_dir = persist_directory or os.getenv("CHROMA_HYBRID_DIR", "./chroma_hybrid_db")
        retriever = build_hybrid_retriever(persist_directory=persist_dir)

    # 3. Construir cadena RAG
    prompt = create_rag_prompt()

    chain = (
        {
            "context": retriever | format_docs,
            "question": RunnablePassthrough(),
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    return {
        "chain": chain,
        "retriever": retriever,
        "llm": llm,
        "prompt": prompt,
        "type": "hybrid_rrf",
    }


# ============================================================
# AGENTE RAG TRADICIONAL (Solo Vectores — baseline)
# ============================================================

def create_vector_agent(
    llm=None,
    retriever=None,
    persist_directory: str = None,
) -> dict:
    """
    Crea un agente RAG tradicional (solo búsqueda vectorial).

    Se usa como BASELINE para la evaluación comparativa en la tesis.
    La diferencia con create_hybrid_agent() es que NO usa BM25 ni RRF.

    Args:
        llm: Instancia de LangChain ChatModel.
        retriever: Retriever vectorial personalizado.
        persist_directory: Directorio de ChromaDB.

    Returns:
        Diccionario con la cadena RAG y metadatos de configuración.
    """
    if llm is None:
        from app import get_llm
        llm = get_llm()

    if retriever is None:
        persist_dir = persist_directory or os.getenv("CHROMA_HYBRID_DIR", "./chroma_hybrid_db")
        retriever = build_vector_only_retriever(persist_directory=persist_dir)

    prompt = create_rag_prompt()

    chain = (
        {
            "context": retriever | format_docs,
            "question": RunnablePassthrough(),
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    return {
        "chain": chain,
        "retriever": retriever,
        "llm": llm,
        "prompt": prompt,
        "type": "vector_only",
    }


# ============================================================
# FUNCIONES DE CONVENIENCIA
# ============================================================

def ask_hybrid(question: str, agent_config: dict = None) -> dict:
    """
    Función de conveniencia para hacer preguntas al agente híbrido.

    Args:
        question: Pregunta del usuario.
        agent_config: Configuración del agente (create_hybrid_agent()).

    Returns:
        Diccionario con response, context_used, is_fallback.
    """
    if agent_config is None:
        agent_config = create_hybrid_agent()

    try:
        response = agent_config["chain"].invoke(question)

        # Detectar fallback
        is_fallback = (
            "No dispongo de esa información exacta" in response
            or "contacta a un asesor humano de la agencia" in response
        )

        # Obtener documentos recuperados para inspección
        docs = agent_config["retriever"].invoke(normalize_query(question))

        return {
            "response": response.strip(),
            "context_used": len(docs) > 0,
            "is_fallback": is_fallback,
            "docs_retrieved": len(docs),
            "tour_ids": [d.metadata.get("tour_id") for d in docs],
        }
    except Exception as e:
        return {
            "response": "Lo siento, hubo un error técnico. Por favor, intenta de nuevo o contacta a un asesor.",
            "context_used": False,
            "is_fallback": True,
            "error": str(e),
        }


def ask_vector(question: str, agent_config: dict = None) -> dict:
    """
    Función de conveniencia para hacer preguntas al agente vectorial.

    Args:
        question: Pregunta del usuario.
        agent_config: Configuración del agente (create_vector_agent()).

    Returns:
        Diccionario con response, context_used, is_fallback.
    """
    if agent_config is None:
        agent_config = create_vector_agent()

    try:
        response = agent_config["chain"].invoke(question)

        is_fallback = (
            "No dispongo de esa información exacta" in response
            or "contacta a un asesor humano de la agencia" in response
        )

        docs = agent_config["retriever"].invoke(question)

        return {
            "response": response.strip(),
            "context_used": len(docs) > 0,
            "is_fallback": is_fallback,
            "docs_retrieved": len(docs),
            "tour_ids": [d.metadata.get("tour_id") for d in docs],
        }
    except Exception as e:
        return {
            "response": "Lo siento, hubo un error técnico. Por favor, intenta de nuevo o contacta a un asesor.",
            "context_used": False,
            "is_fallback": True,
            "error": str(e),
        }
