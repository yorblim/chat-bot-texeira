import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import os,json
from pathlib import Path
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
os.environ['ANONYMIZED_TELEMETRY']='False'
from trial_support import retriever,INDEX,input_hashes
r=retriever()
assert r is not None
assert r.k==5 and r.rrf_k==60 and r.max_chunks_per_tour==2
rows=[]
for q,target in [('bus subida bajada Machu Picchu en Tren','machu-picchu-tren'),('Salkantay Trek duración','salkantay-trek'),('Puente Q’eswachaca','puente-qeswachaca'),('Tour Cuatrimoto casco equipo','maras-moray-cuatrimoto')]:
    docs=r.invoke(q); ids=[d.metadata['tour_id'] for d in docs]
    assert target in ids,(q,ids)
    assert len(ids)<=5 and max(ids.count(x) for x in ids)<=2
    assert all('09:00-14:00' not in d.page_content and 'eugenio.tejeira@' not in d.page_content for d in docs)
    rows.append(dict(question=q,ids=ids))
assert json.loads((INDEX/'READY.json').read_text())['inputs']==input_hashes()
Path('AUDIT_RETRIEVAL_RESULTS.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS 4 búsquedas locales; RRF60/top5/cap2 e integridad de índice verificados; sin LLM.')
