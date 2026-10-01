"""Reconstruye el índice oficial reproduciendo los documentos exactos de evidence_facts.json y tours_catalog.json."""
import os
import sys
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', ANONYMIZED_TELEMETRY='False')

import trial_support as support
from src.retriever import build_vector_retriever

target = support.INDEX
print(f"Reconstruyendo índice en {target.name}...")

# Respaldar de forma atómica si existe
backup = ROOT / f"{target.name}_prev_bak"
if backup.exists():
    shutil.rmtree(backup)
if target.exists():
    shutil.copytree(target, backup)
    shutil.rmtree(target)

try:
    documents = support.documents(include_dynamic=False)
    print(f"Total documentos generados: {len(documents)}")
    _, db = build_vector_retriever(documents, persist_directory=str(target))
    stored = db._collection.get(include=['documents', 'metadatas'])
    actual = [{'page_content': text, 'metadata': metadata}
              for text, metadata in zip(stored['documents'], stored['metadatas'])]
    canonical = lambda rows: sorted(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
    assert canonical(actual) == canonical(documents), "Discrepancia entre documentos generados y almacenados"
    
    hashes = support.input_hashes()
    marker = dict(
        version='catalogo-20260926',
        documents=len(documents),
        inputs=hashes
    )
    (target / 'READY.json').write_text(json.dumps(marker, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"PASS: {len(documents)} documentos exactos en {target.name}.")
    # Si todo salió bien, limpiar backup
    if backup.exists():
        shutil.rmtree(backup)
except Exception as e:
    print(f"ERROR: {e}")
    if backup.exists():
        if target.exists():
            shutil.rmtree(target)
        shutil.move(backup, target)
        print("Restaurado backup anterior debido al error.")
    sys.exit(1)
