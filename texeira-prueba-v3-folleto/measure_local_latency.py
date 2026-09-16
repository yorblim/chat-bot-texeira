"""Medición local sin proveedor LLM ni descarga de modelos."""
import os
import json
import time
from pathlib import Path

os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['ANONYMIZED_TELEMETRY'] = 'False'
timings = {}
start = time.perf_counter()
from trial_support import retriever
timings['import_support_seconds'] = time.perf_counter() - start
start = time.perf_counter()
engine = retriever()
assert engine is not None
timings['initialize_seconds'] = time.perf_counter() - start
for name in ['first_query_seconds', 'second_query_seconds']:
    start = time.perf_counter()
    docs = engine.invoke('What does the Machu Picchu tour include?')
    timings[name] = time.perf_counter() - start
    assert docs and len(docs) <= 5
start = time.perf_counter()
assert retriever() is engine
timings['cached_access_seconds'] = time.perf_counter() - start
result = {'mode': 'local_offline_no_llm', 'seconds': timings, 'documents_returned': len(docs)}
Path(__file__).with_name('local_latency.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result), flush=True)
