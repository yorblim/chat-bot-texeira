"""Índice reproducible de fuentes oficiales; no lee DB dinámica ni llama al LLM."""
import os
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', ANONYMIZED_TELEMETRY='False')
import trial_support as support
from src.retriever import build_vector_retriever

target = support.INDEX
if target.exists():
    raise SystemExit('Destino ya existe; no sobrescribir índices.')
documents = support.documents(include_dynamic=False)
_, db = build_vector_retriever(documents, persist_directory=str(target))
stored = db._collection.get(include=['documents', 'metadatas'])
actual = [{'page_content': text, 'metadata': metadata}
          for text, metadata in zip(stored['documents'], stored['metadatas'])]
canonical = lambda rows: sorted(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
assert canonical(actual) == canonical(documents)
(target / 'READY.json').write_text(json.dumps(dict(version='catalogo-20260926',
    documents=len(documents), inputs=support.input_hashes()), indent=2), encoding='utf-8')
print(f'PASS: {len(documents)} documentos exactos en {target.name}; anterior conservado.')
