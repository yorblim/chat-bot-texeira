"""
ingest_hybrid.py — Ingesta del catálogo consolidado a chroma_hybrid_db.

Crea un vector store INDEPENDIENTE de ./chroma_db (producción).
Usa EXCLUSIVAMENTE data/tours_catalog.json → catalog_to_documents().
NO toca documentos_tours/*.txt ni ./chroma_db.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.preprocessing import load_catalog, catalog_to_documents
from src.retriever import build_vector_retriever

HYBRID_DIR = "./chroma_hybrid_db"

def main():
    # 0. Eliminar chroma_hybrid_db si existe (limpieza previa)
    import shutil
    if os.path.exists(HYBRID_DIR):
        shutil.rmtree(HYBRID_DIR)
        print(f"[INGEST] Directorio previo {HYBRID_DIR} eliminado.")

    # 1. Cargar catálogo consolidado
    catalog = load_catalog()
    tours = catalog.get("tours", [])
    print(f"[INGEST] Catálogo cargado: {len(tours)} tours")

    # 2. Convertir a documentos chunked
    documents = catalog_to_documents(catalog)
    print(f"[INGEST] Documentos generados: {len(documents)} chunks")

    # 3b. ChromaDB solo acepta str/int/float/bool en metadata
    #     - list/dict → convertir a JSON string
    #     - None → eliminar el campo
    import json
    for doc in documents:
        meta = doc["metadata"]
        # Convertir images (list) a JSON string
        images = meta.pop("images", None)
        if images is not None:
            meta["images_json"] = json.dumps(images, ensure_ascii=False)
        # Eliminar keys con None
        doc["metadata"] = {k: v for k, v in meta.items() if v is not None}

    # 3. Indexar en chroma_hybrid_db
    retriever, vectordb = build_vector_retriever(
        documents=documents,
        persist_directory=HYBRID_DIR,
        k=10,
    )
    print(f"[INGEST] Vector store creado en {HYBRID_DIR}")

    # 4. Verificar colección
    count = vectordb._collection.count()
    print(f"\n[VERIFICACION] Chunks en colección: {count}")

    # 5. Listar tour_ids únicos y chunk counts
    all_data = vectordb._collection.get(include=["metadatas"])
    tour_ids = set()
    tour_chunks = {}
    for meta in all_data["metadatas"]:
        tid = meta.get("tour_id", "unknown")
        tour_ids.add(tid)
        tour_chunks[tid] = tour_chunks.get(tid, 0) + 1

    print(f"[VERIFICACION] Tours únicos: {len(tour_ids)}")
    print(f"\n[VERIFICACION] Distribución por tour:")
    for tid in sorted(tour_chunks.keys()):
        print(f"  {tid}: {tour_chunks[tid]} chunks")

    # 6. Verificar Salkantay
    has_salkantay = "salkantay-trek" in tour_ids
    print(f"\n[VERIFICACION] Salkantay presente: {'SI' if has_salkantay else 'NO'}")

    # 7. Verificar metadata de un chunk de ejemplo
    sample = all_data["metadatas"][0]
    print(f"\n[VERIFICACION] Metadata de ejemplo (chunk 0):")
    for k, v in sample.items():
        print(f"  {k}: {v}")

    # 8. Prueba de recuperación
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from src.retriever import EMBEDDING_MODEL
    print(f"\n[TEST] Query: 'cuánto cuesta Machu Picchu'")
    results = retriever.invoke("cuánto cuesta Machu Picchu")
    print(f"[TEST] Resultados: {len(results)} chunks")
    for i, doc in enumerate(results[:3]):
        tid = doc.metadata.get("tour_id", "?")
        tn = doc.metadata.get("tour_name", "?")
        print(f"  [{i+1}] {tid} ({tn}) — {doc.page_content[:80]}...")

    print(f"\n[OK] Ingesta completada. {count} chunks en {HYBRID_DIR}")

if __name__ == "__main__":
    main()
