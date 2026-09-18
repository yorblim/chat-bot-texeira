import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
"""Ejercita webhook con envío simulado: aceptación, rechazo y fallo interno."""
import asyncio,hashlib,hmac,json,tempfile,time
from pathlib import Path
import httpx
import app
import operational_metrics as op
import handoff_support as h
import whatsapp_entry

async def run():
    with tempfile.TemporaryDirectory() as folder:
        op.DB=Path(folder)/'events.db';h.DB=Path(folder)/'requests.db'
        app.META_APP_SECRET='test-secret'
        app.database.log_interaction=lambda **kw:1
        app.database.is_duplicate_webhook=lambda *args:False
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app),base_url='http://test') as c:
            for i in range(3):
                def answer(*args,**kwargs):
                    if i==2:raise RuntimeError('simulated processing failure')
                    return dict(response='test response',resolved_autonomously=True,is_fallback=False,is_rate_limit=i==1,response_route='test')
                def send(**kwargs):
                    time.sleep(.02)
                    return i==0
                app.rag_chain=answer;app.send_whatsapp_message=send
                body=json.dumps({'entry':[{'changes':[{'value':{'metadata':{'phone_number_id':'test-id'},'messages':[{'id':f'test-{i}','from':'51900000000','type':'text','text':{'body':'test'}}]}}]}]}).encode()
                sig='sha256='+hmac.new(b'test-secret',body,hashlib.sha256).hexdigest()
                r=await c.post('/webhook',content=body,headers={'X-Hub-Signature-256':sig})
                assert r.status_code==200,r.text
            s=op.summary()
            assert s['received']==3 and s['api_accepted']==1 and s['send_failed']==1 and s['processing_failed']==1,s
            assert s['api_acceptance_pct']==33.33 and s['provider_rate_limits']==1,s
            assert s['resolution_validated'] is None and s['delivery_confirmed'] is None
            with op.connection() as conn:
                rows=conn.execute('SELECT * FROM operational_events').fetchall()
            assert rows[0]['response_attempt_ms']>=rows[0]['generation_ms']+15
            assert rows[1]['model_claims_resolved']==1 and rows[1]['status']=='send_failed'
            assert s['human_requests']=={}
            ticket,_=h.create_request('test','whatsapp','asesor',[])
            h.create_request('test','whatsapp','asesor',[])
            h.create_request('other','test','asesor',[])
            assert op.summary()['human_requests']=={'pending':1}
            assert (await c.get('/operational-metrics/data')).status_code==200
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=whatsapp_entry.app),base_url='http://test') as c:
            assert (await c.get('/operational-metrics/data')).status_code==404
    Path('RESULTADO_METRICAS_OPERATIVAS.json').write_text(json.dumps({'passed':True,'external_messages':0,'external_llm_calls':0,'checks':['webhook_accepted','send_failure_not_success','processing_failure_counted','rate_limit_in_denominator','send_latency_included','unique_human_requests','unmeasured_not_zero','public_metrics_unavailable']}),encoding='utf-8')
    print('PASS: webhook y métricas operativas; sin mensajes externos ni LLM.')

asyncio.run(run())
