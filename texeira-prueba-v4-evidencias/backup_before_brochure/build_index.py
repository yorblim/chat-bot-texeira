"""Crear exclusivamente el índice de prueba, sin borrar ni reutilizar índices anteriores."""
import hashlib
import json
import os
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['ANONYMIZED_TELEMETRY'] = 'False'
from trial_support import INDEX, ROOT, documents

if __name__ == '__main__':
    if INDEX.exists():
        raise SystemExit('El índice ya existe. No se sobrescribe; revisar antes de reindexar.')
    from src.retriever import build_vector_retriever
    docs = documents()
    _, db = build_vector_retriever(docs, persist_directory=str(INDEX))
    assert db._collection.count() == len(docs)
    (INDEX / 'READY.json').write_text(json.dumps({'documents':len(docs),'catalog_sha256':hashlib.sha256((ROOT/'data/provisional.json').read_bytes()).hexdigest()}),encoding='utf-8')
    print('Indice provisional verificado:',len(docs),'documentos')
