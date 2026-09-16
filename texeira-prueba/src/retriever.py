"""
retriever.py — Retrieval Híbrido: BM25 + Búsqueda Vectorial + Reciprocal Rank Fusion.

Implementa la arquitectura central de la tesis: un sistema de recuperación
híbrido que combina la búsqueda léxica (BM25) con la búsqueda semántica
densa (vectores) usando Reciprocal Rank Fusion (RRF) para fusionar los
resultados de ambos retrievers.

Arquitectura:
  ┌─────────────┐    ┌──────────────────┐
  │   BM25      │    │  Vector Store    │
  │ (léxico)    │    │  (semántico)     │
  └──────┬──────┘    └────────┬─────────┘
         │                    │
         └────────┬───────────┘
                  │
         ┌────────▼────────┐
         │  RRF Ensemble   │
         │  (fusionador)   │
         └────────┬────────┘
                  │
         ┌────────▼────────┐
         │  Top-K Results  │
         └─────────────────┘

Uso:
  from src.retriever import build_hybrid_retriever
  retriever = build_hybrid_retriever()
  docs = retriever.invoke("¿Cuánto cuesta Sacsayhuaman?")
"""

import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

from src.preprocessing import (
    tokenize_for_bm25,
    normalize_query,
    load_catalog,
    catalog_to_documents,
)

# ============================================================
# CONFIGURACIÓN
# ============================================================

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CHROMA_PERSIST_DIR = os.getenv("CHROMA_HYBRID_DIR", "./chroma_hybrid_db")
CATALOG_PATH = os.getenv("TOURS_CATALOG_PATH", None)
BM25_K = 10  # Documentos recuperados por BM25
VECTOR_K = 10  # Documentos recuperados por búsqueda vectorial
FINAL_K = 5  # Documentos finales después de RRF
RRF_K = 60  # Constante de suavizado RRF (paper original: k=60)


# ============================================================
# BM25 RETRIEVER (Búsqueda Léxica)
# ============================================================

class BM25RetrieverCustom(BaseRetriever):
    """
    Retriever BM25 personalizado usando rank_bm25.

    A diferencia del BM25Retriever de LangChain que requiere un corpus
    de LangChain Documents, esta implementación trabaja directamente con
    el corpus tokenizado y el diccionario de normalización quechua.

    Características:
      - Tokenización multilingüe (ES/EN/PT) con normalización quechua
      - Manejo de sinónimos y variantes ortográficas via preprocessing
      - Scoring BM25 estándar con parámetros ajustables
    """

    documents: List[dict]  # Documentos del catálogo (page_content + metadata)
    k: int = BM25_K
    lang: str = "es"

    class Config:
        arbitrary_types_allowed = True

    def _get_relevant_documents(self, query: str) -> List[Document]:
        """
        Recupera los k documentos más relevantes usando BM25.

        Args:
            query: Query del usuario.

        Returns:
            Lista de LangChain Documents con score BM25 en metadata.
        """
        from rank_bm25 import BM25Okapi

        # Tokenizar el corpus completo
        corpus_tokens = [
            tokenize_for_bm25(doc["page_content"], self.lang)
            for doc in self.documents
        ]

        # Filtrar documentos vacíos (tokens vacíos después de stop words)
        valid_indices = [i for i, tokens in enumerate(corpus_tokens) if tokens]
        valid_corpus = [corpus_tokens[i] for i in valid_indices]

        if not valid_corpus:
            return []

        # Crear índice BM25 y buscar
        bm25 = BM25Okapi(valid_corpus)
        query_tokens = tokenize_for_bm25(query, self.lang)

        if not query_tokens:
            return []

        scores = bm25.get_scores(query_tokens)

        # Obtener top-k índices
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:self.k]

        # Construir resultados
        results = []
        for idx in ranked_indices:
            original_idx = valid_indices[idx]
            doc = self.documents[original_idx]
            results.append(Document(
                page_content=doc["page_content"],
                metadata={
                    **doc["metadata"],
                    "retrieval_method": "bm25",
                    "bm25_score": float(scores[idx]),
                    "rank": len(results) + 1,
                },
            ))

        return results


# ============================================================
# VECTOR STORE RETRIEVER (Búsqueda Semántica)
# ============================================================

def build_vector_retriever(
    documents: List[dict],
    persist_directory: str = CHROMA_PERSIST_DIR,
    embedding_model: str = EMBEDDING_MODEL,
    k: int = VECTOR_K,
) -> Tuple[BaseRetriever, Chroma]:
    """
    Construye un Vector Store Retriever con ChromaDB.

    Indexa los documentos del catálogo en ChromaDB usando embeddings
    multilingües de HuggingFace y retorna un retriever de LangChain.

    Args:
        documents: Lista de documentos del catálogo.
        persist_directory: Directorio de persistencia de ChromaDB.
        embedding_model: Modelo de embeddings HuggingFace.
        k: Número de documentos a recuperar.

    Returns:
        Tupla (retriever, vectordb) — el vectordb se retorna para
        permitir inspección y reutilización.
    """
    # Cargar embeddings (local, sin costo de API)
    embeddings = HuggingFaceEmbeddings(model_name=embedding_model)

    # Convertir a LangChain Documents
    lc_documents = [
        Document(page_content=doc["page_content"], metadata=doc["metadata"])
        for doc in documents
    ]

    # Construir o cargar ChromaDB
    if os.path.exists(persist_directory) and os.listdir(persist_directory):
        vectordb = Chroma(
            persist_directory=persist_directory,
            embedding_function=embeddings,
        )
        # Verificar si los documentos ya están indexados
        existing_count = vectordb._collection.count()
        if existing_count < len(lc_documents):
            vectordb.add_documents(lc_documents)
            vectordb.persist()
    else:
        vectordb = Chroma.from_documents(
            documents=lc_documents,
            embedding=embeddings,
            persist_directory=persist_directory,
        )
        vectordb.persist()

    retriever = vectordb.as_retriever(search_kwargs={"k": k})
    return retriever, vectordb


# ============================================================
# ENSEMBLE RETRIEVER (Reciprocal Rank Fusion)
# ============================================================

class HybridRetriever(BaseRetriever):
    """
    Retriever híbrido que combina BM25 y búsqueda vectorial
    mediante Reciprocal Rank Fusion (RRF).

    RRF es una técnica de fusión de rankings que:
      1. Asigna un score a cada documento basado en su posición en
         cada ranking individual: score = 1 / (k + position)
      2. Suma los scores de ambos rankings
      3. Reordena por el score combinado

    Ventajas sobre ponderación lineal:
      - No requiere normalización de scores entre retrievers
      - Es robusto ante la distribución de scores muy diferentes
      - El parámetro k controla la suavización (mayor k = más suave)

    Paper de referencia: Cormack, Clarke, Butt (2009).
    "Reciprocal Rank Fusion outperforms Condorcet and individual Rank
    Learning Methods" - SIGIR.
    """

    bm25_retriever: BM25RetrieverCustom
    vector_retriever: BaseRetriever
    k: int = FINAL_K
    rrf_k: int = RRF_K
    max_chunks_per_tour: int = 2

    class Config:
        arbitrary_types_allowed = True

    def _get_relevant_documents(self, query: str) -> List[Document]:
        """
        Ejecuta ambos retrievers y fusiona con RRF.

        Args:
            query: Query del usuario.

        Returns:
            Lista de k documentos fusionados por RRF.
        """
        # Normalizar query para BM25 (normalización quechua)
        normalized_query = normalize_query(query)

        # Ejecutar ambos retrievers
        bm25_docs = self.bm25_retriever.invoke(normalized_query)
        vector_docs = self.vector_retriever.invoke(query)

        # Calcular scores RRF
        doc_scores = {}

        # BM25 ranking
        for rank, doc in enumerate(bm25_docs):
            chunk_idx = doc.metadata.get("chunk_index", 0)
            doc_id = f"{doc.metadata.get('tour_id', 'unknown')}__c{chunk_idx}"
            rrf_score = 1.0 / (self.rrf_k + rank + 1)
            doc_scores[doc_id] = {
                "doc": doc,
                "score": rrf_score,
                "bm25_rank": rank + 1,
                "vector_rank": None,
            }

        # Vector ranking
        for rank, doc in enumerate(vector_docs):
            chunk_idx = doc.metadata.get("chunk_index", 0)
            doc_id = f"{doc.metadata.get('tour_id', 'unknown')}__c{chunk_idx}"
            rrf_score = 1.0 / (self.rrf_k + rank + 1)
            if doc_id in doc_scores:
                doc_scores[doc_id]["score"] += rrf_score
                doc_scores[doc_id]["vector_rank"] = rank + 1
            else:
                doc_scores[doc_id] = {
                    "doc": doc,
                    "score": rrf_score,
                    "bm25_rank": None,
                    "vector_rank": rank + 1,
                }

        # Ordenar por score RRF combinado
        ranked = sorted(doc_scores.values(), key=lambda x: x["score"], reverse=True)

        # Cap de diversidad: máximo max_chunks_per_tour chunks por tour_id
        tour_chunk_count = {}
        diversified = []
        for item in ranked:
            tour_id = item["doc"].metadata.get("tour_id", "unknown")
            count = tour_chunk_count.get(tour_id, 0)
            if count < self.max_chunks_per_tour:
                diversified.append(item)
                tour_chunk_count[tour_id] = count + 1

        # Retornar top-k con metadata enriquecida
        results = []
        for item in diversified[:self.k]:
            doc = item["doc"]
            enriched_metadata = {
                **doc.metadata,
                "retrieval_method": "hybrid_rrf",
                "rrf_score": round(item["score"], 6),
                "bm25_rank": item["bm25_rank"],
                "vector_rank": item["vector_rank"],
            }
            results.append(Document(
                page_content=doc.page_content,
                metadata=enriched_metadata,
            ))

        return results


# ============================================================
# FUNCIONES DE CONSTRUCCIÓN
# ============================================================

def build_bm25_retriever(
    documents: List[dict] = None,
    lang: str = "es",
    k: int = BM25_K,
) -> BM25RetrieverCustom:
    """
    Construye un BM25 Retriever desde el catálogo de tours.

    Args:
        documents: Documentos del catálogo. Si es None, carga automáticamente.
        lang: Idioma principal para tokenización.
        k: Número de documentos a recuperar.

    Returns:
        BM25RetrieverCustom configurado.
    """
    if documents is None:
        catalog = load_catalog(CATALOG_PATH)
        documents = catalog_to_documents(catalog)

    return BM25RetrieverCustom(documents=documents, k=k, lang=lang)


def build_hybrid_retriever(
    documents: List[dict] = None,
    persist_directory: str = CHROMA_PERSIST_DIR,
    bm25_k: int = BM25_K,
    vector_k: int = VECTOR_K,
    final_k: int = FINAL_K,
    rrf_k: int = RRF_K,
    lang: str = "es",
) -> HybridRetriever:
    """
    Construye el retriever híbrido completo (BM25 + Vector + RRF).

    Esta es la función principal del módulo. Carga el catálogo, construye
    ambos retrievers y los fusiona con RRF.

    Args:
        documents: Documentos del catálogo. Si es None, carga automáticamente.
        persist_directory: Directorio de ChromaDB.
        bm25_k: Top-k para BM25.
        vector_k: Top-k para búsqueda vectorial.
        final_k: Top-k final después de RRF.
        rrf_k: Constante de suavizado RRF.
        lang: Idioma principal.

    Returns:
        HybridRetriever configurado y listo para usar.
    """
    if documents is None:
        catalog = load_catalog(CATALOG_PATH)
        documents = catalog_to_documents(catalog)

    # Construir BM25 retriever
    bm25_retriever = build_bm25_retriever(documents, lang=lang, k=bm25_k)

    # Construir Vector retriever
    vector_retriever, _ = build_vector_retriever(
        documents,
        persist_directory=persist_directory,
        k=vector_k,
    )

    # Fusionar con RRF
    hybrid = HybridRetriever(
        bm25_retriever=bm25_retriever,
        vector_retriever=vector_retriever,
        k=final_k,
        rrf_k=rrf_k,
    )

    return hybrid


def build_vector_only_retriever(
    documents: List[dict] = None,
    persist_directory: str = CHROMA_PERSIST_DIR,
    vector_k: int = VECTOR_K,
) -> BaseRetriever:
    """
    Construye un retriever solo vectorial (para comparación con RAGAS).

    Se usa como baseline en la evaluación: RAG tradicional sin BM25.

    Args:
        documents: Documentos del catálogo. Si es None, carga automáticamente.
        persist_directory: Directorio de ChromaDB.
        vector_k: Top-k para búsqueda vectorial.

    Returns:
        Retriever vectorial puro.
    """
    if documents is None:
        catalog = load_catalog(CATALOG_PATH)
        documents = catalog_to_documents(catalog)

    retriever, _ = build_vector_retriever(
        documents,
        persist_directory=persist_directory,
        k=vector_k,
    )
    return retriever


# ============================================================
# UTILIDADES DE DIAGNÓSTICO
# ============================================================

def compare_retrievers(
    query: str,
    bm25_retriever: BM25RetrieverCustom,
    vector_retriever: BaseRetriever,
    hybrid_retriever: HybridRetriever,
) -> dict:
    """
    Compara los 3 retrievers para una query dada (diagnóstico).

    Útil para visualizar cómo BM25, vectores y RRF difieren en sus
    resultados para la misma pregunta.

    Args:
        query: Pregunta del usuario.
        bm25_retriever: Retriever BM25.
        vector_retriever: Retriever vectorial.
        hybrid_retriever: Retriever híbrido.

    Returns:
        Diccionario con resultados de cada retriever.
    """
    normalized = normalize_query(query)

    bm25_results = bm25_retriever.invoke(normalized)
    vector_results = vector_retriever.invoke(query)
    hybrid_results = hybrid_retriever.invoke(query)

    def format_results(docs: List[Document]) -> list:
        return [
            {
                "tour_id": doc.metadata.get("tour_id", "N/A"),
                "tour_name": doc.metadata.get("tour_name", "N/A"),
                "retrieval_method": doc.metadata.get("retrieval_method", "N/A"),
                "score": doc.metadata.get("rrf_score") or doc.metadata.get("bm25_score", "N/A"),
                "bm25_rank": doc.metadata.get("bm25_rank"),
                "vector_rank": doc.metadata.get("vector_rank"),
            }
            for doc in docs
        ]

    return {
        "query": query,
        "normalized_query": normalized,
        "bm25_results": format_results(bm25_results),
        "vector_results": format_results(vector_results),
        "hybrid_results": format_results(hybrid_results),
        "bm25_count": len(bm25_results),
        "vector_count": len(vector_results),
        "hybrid_count": len(hybrid_results),
    }
