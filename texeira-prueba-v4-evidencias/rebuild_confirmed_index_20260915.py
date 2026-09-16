"""Construcción local versionada; conserva el índice anterior."""
import json
import os
from pathlib import Path
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
os.environ['ANONYMIZED_TELEMETRY']='False'
import trial_support as support
from src.retriever import build_vector_retriever

target=support.ROOT/'chroma_f1_confirmado_20260915_db'
if target.exists(): raise SystemExit('El destino ya existe; no se sobrescribe.')
docs=support.documents()
_, db=build_vector_retriever(docs,persist_directory=str(target))
stored=db._collection.get(include=['documents','metadatas'])
actual=[{'page_content':text,'metadata':meta} for text,meta in zip(stored['documents'],stored['metadatas'])]
canonical=lambda rows: sorted(json.dumps(row,ensure_ascii=False,sort_keys=True) for row in rows)
assert canonical(actual)==canonical(docs), 'Contenido/metadatos no coinciden'
assert not any('CONFLICTOS PENDIENTES' in row['page_content'] for row in actual)
marker={'documents':len(docs),'inputs':support.input_hashes(),'version':'f1-confirmado-20260915'}
(target/'READY.json').write_text(json.dumps(marker,indent=2),encoding='utf-8')
Path('VERIFICACION_INDICE_F1_20260915.json').write_text(json.dumps({
    'index':target.name,'documents':len(docs),'content_and_metadata_match':True,
    'old_conflict_texts':0,'inputs':marker['inputs'],
    'source_decision':'Usuario confirma en esta conversación que la agencia prioriza horarios F1.'},indent=2),encoding='utf-8')
print(f'PASS: {len(docs)} documentos y metadatos exactos; índice nuevo {target.name}')
