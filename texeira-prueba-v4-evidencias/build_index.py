"""build_index.py v4-evidencias: Genera indice ChromaDB desde evidence_facts.json."""
import hashlib
import json
import os
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['ANONYMIZED_TELEMETRY'] = 'False'
from trial_support import INDEX, ROOT, documents, input_hashes

if __name__ == '__main__':
    if INDEX.exists():
        raise SystemExit('El indice ya existe. No se sobrescribe; revisar antes de reindexar.')
    from src.retriever import build_vector_retriever
    docs = documents()
    print(f'Generando indice con {len(docs)} documentos...')
    _, db = build_vector_retriever(docs, persist_directory=str(INDEX))
    assert db._collection.count() == len(docs)
    (INDEX / 'READY.json').write_text(
        json.dumps({
            'documents': len(docs),
            'inputs': input_hashes(),
            'catalog_sha256': hashlib.sha256((ROOT / 'data/tours_catalog.json').read_bytes()).hexdigest(),
            'version': 'v4-evidencias',
            'evidence_facts': hashlib.sha256((ROOT / 'data/evidence_facts.json').read_bytes()).hexdigest()
        }),
        encoding='utf-8'
    )
    print(f'Indice v4-evidencias verificado: {len(docs)} documentos')
