"""
ingest.py — Script de ingesta de documentos al almacén vectorial (ChromaDB).

Este script implementa la fase de INGESTA del pipeline RAG:
  1. Lee todos los archivos .txt y .pdf del directorio DOCS_DIR
  2. Aplica chunking semántico (RecursiveCharacterTextSplitter)
  3. Genera embeddings con sentence-transformers
  4. Indexa los chunks en ChromaDB con métrica de similitud coseno

Es IDEMPOTENTE: usa hash SHA-256 del contenido de cada chunk como ID,
por lo que ejecutarlo múltiples veces NO genera duplicados.

Uso:
    python ingest.py

El directorio documentos_tours/ debe contener los PDFs y TXTs de tours.
"""

import hashlib
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

# Importar loaders de forma compatible con distintas versiones de LangChain
try:
    from langchain_community.document_loaders import PyPDFLoader as PDFLoader, TextLoader
except ImportError:
    try:
        from langchain_community.document_loaders import PDFLoader, TextLoader
    except ImportError:
        from langchain_community.document_loaders import TextLoader
        PDFLoader = None

# Cargar variables de entorno desde .env
load_dotenv()

# Configuración desde .env
DOCS_DIR = os.getenv("DOCS_DIR", "./documentos_tours")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")

# Parámetros de chunking — ajustables según la naturaleza de los documentos
CHUNK_SIZE = 800       # Tamaño máximo de cada chunk en caracteres
CHUNK_OVERLAP = 150    # Superposición entre chunks para mantener contexto


def compute_hash(text: str) -> str:
    """
    Calcula el hash SHA-256 de un texto.
    Se usa como ID único del chunk para evitar duplicados en re-indexación.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_documents(docs_dir: str) -> list:
    """
    Carga todos los archivos .txt y .pdf del directorio especificado.

    Cada tipo de archivo usa su loader correspondiente:
      - TextLoader para .txt
      - PDFLoader para .pdf

    Retorna:
        Lista de documentos LangChain cargados
    """
    docs_path = Path(docs_dir)
    if not docs_path.exists():
        print(f"[INGEST] El directorio {docs_dir} no existe. Creándolo...")
        docs_path.mkdir(parents=True, exist_ok=True)
        return []

    documents = []

    # Cargar archivos de texto
    txt_files = list(docs_path.glob("*.txt"))
    for txt_file in txt_files:
        try:
            loader = TextLoader(str(txt_file), encoding="utf-8")
            documents.extend(loader.load())
            print(f"[INGEST] Cargado: {txt_file.name} ({len(documents)} docs acumulados)")
        except Exception as e:
            print(f"[INGEST] Error cargando {txt_file.name}: {e}")

    # Cargar archivos PDF
    pdf_files = list(docs_path.glob("*.pdf"))
    for pdf_file in pdf_files:
        try:
            loader = PDFLoader(str(pdf_file))
            documents.extend(loader.load())
            print(f"[INGEST] Cargado: {pdf_file.name} ({len(documents)} docs acumulados)")
        except Exception as e:
            print(f"[INGEST] Error cargando {pdf_file.name}: {e}")

    print(f"[INGEST] Total de documentos cargados: {len(documents)}")
    return documents


def split_documents(documents: list) -> list:
    """
    Aplica chunking semántico a los documentos usando RecursiveCharacterTextSplitter.

    Este split es fundamental para el RAG:divide textos largos en chunks
    que los embeddings pueden representar de forma significativa, manteniendo
    suficiente contexto entre chunks gracias al overlap.

    Retorna:
        Lista de chunks (documentos fragmentados)
    """
    if not documents:
        return []

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = text_splitter.split_documents(documents)
    print(f"[INGEST] Chunks generados: {len(chunks)} (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    return chunks


def ingest_to_chromadb(chunks: list) -> None:
    """
    Indexa los chunks en ChromaDB con embeddings y métrica de similitud coseno.

    ChromaDB es la base de vectores local que almacena los embeddings.
    La métrica cosine permite calcular la similitud semántica entre
    la consulta del turista y los chunks de la base de conocimiento.

    Cada chunk se identifica con su hash SHA-256 para ser idempotente.
    """
    if not chunks:
        print("[INGEST] No hay chunks para indexar.")
        return

    # Inicializar embeddings locales con sentence-transformers (sin costo, sin API key)
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )

    # Limpiar colección previa para eliminar chunks obsoletos (evita chunks huérfanos con datos desactualizados)
    try:
        old_db = Chroma(
            persist_directory=CHROMA_PERSIST_DIR,
            embedding_function=embeddings,
        )
        old_db.delete_collection()
        print("[INGEST] Colección previa depurada con éxito.")
    except Exception as e:
        print(f"[INGEST] Colección limpia o inicial: {e}")

    # Calcular IDs únicos basados en hash del contenido
    chunk_ids = [compute_hash(chunk.page_content) for chunk in chunks]

    # Crear la colección limpia y actualizada en ChromaDB
    # collection_metadata={"hnsw:space": "cosine"} establece métrica coseno
    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        ids=chunk_ids,
        collection_metadata={"hnsw:space": "cosine"},
        persist_directory=CHROMA_PERSIST_DIR,
    )

    print(f"[INGEST] [OK] {len(chunks)} chunks indexados en ChromaDB")
    print(f"[INGEST] Directorio de persistencia: {CHROMA_PERSIST_DIR}")


def main():
    """
    Función principal del script de ingesta.
    Ejecuta el pipeline completo: carga → chunking → indexación.
    """
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    print("=" * 60)
    print("  INGESTA DE DOCUMENTOS — TEXEIRA TRAVEL TOUR RAG")
    print("=" * 60)
    print(f"  Directorio de documentos: {DOCS_DIR}")
    print(f"  Directorio ChromaDB:       {CHROMA_PERSIST_DIR}")
    print(f"  Chunk size:                {CHUNK_SIZE}")
    print(f"  Chunk overlap:             {CHUNK_OVERLAP}")
    print("=" * 60)

    # Paso 1: Cargar documentos
    documents = load_documents(DOCS_DIR)
    if not documents:
        print("[INGEST] [AVISO] No se encontraron documentos. Coloca archivos .txt o .pdf en documentos_tours/")
        return

    # Paso 2: Fragmentar documentos en chunks
    chunks = split_documents(documents)

    # Paso 3: Indexar en ChromaDB
    ingest_to_chromadb(chunks)

    print("=" * 60)
    print("  INGESTA COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":
    main()
