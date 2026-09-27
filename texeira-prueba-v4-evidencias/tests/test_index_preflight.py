"""Impide desplegar fuentes y vectorstore incompatibles, sin LLM ni embeddings."""
import json
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import trial_support as support
import catalog_service

marker = json.loads((support.INDEX / 'READY.json').read_text(encoding='utf-8'))
with patch.object(catalog_service, 'get_tour_by_id', side_effect=AssertionError('Fingerprint must not read live DB')):
    assert support.input_hashes() == marker['inputs'], 'Fuentes/índice no coinciden'
    docs = support.documents(include_dynamic=False)
    assert len(docs) == marker['documents']
assert (support.INDEX / 'chroma.sqlite3').is_file(), 'Falta SQLite del índice'
print(f'PASS: manifiesto y {len(docs)} documentos; independiente de DB administrativa.')
