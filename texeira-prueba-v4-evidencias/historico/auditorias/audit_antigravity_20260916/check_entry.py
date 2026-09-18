"""Diagnóstico aislado de entrada pública; sin app, modelo, red o datos reales."""
import asyncio, json, os, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import httpx
import whatsapp_entry as entry

async def main():
    entry._state.update(ready=False,local_app=None,error='synthetic-private-error')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=entry.app),base_url='http://test') as client:
        health=await client.get('/healthz')
        not_ready=await client.post('/webhook',json={'synthetic':True})
        # Caso sintético: clave de verificación configurada vacía.
        old=os.environ.get('META_VERIFY_TOKEN')
        os.environ['META_VERIFY_TOKEN']=''
        try:
            verify=await client.get('/webhook',params={'hub.mode':'subscribe','hub.verify_token':'','hub.challenge':'synthetic'})
        finally:
            if old is None: os.environ.pop('META_VERIFY_TOKEN',None)
            else: os.environ['META_VERIFY_TOKEN']=old
        completed=False
        async def fake(scope,receive,send):
            nonlocal completed
            await send({'type':'http.response.start','status':200,'headers':[]})
            await send({'type':'http.response.body','body':b'ok'})
            await asyncio.sleep(.02)
            completed=True
        entry._state.update(ready=True,local_app=fake,error=None)
        response=await client.post('/webhook',json={'synthetic':True})
        result={'health_on_error_status':health.status_code,
                'health_exposes_error_detail':'synthetic-private-error' in health.text,
                'not_ready_post_status':not_ready.status_code,
                'empty_verify_token_status':verify.status_code,
                'delegated_response_status':response.status_code,
                'background_finished_before_http_return':completed,
                'network_or_real_llm_calls':0}
        Path('audit_antigravity_20260916/entry_results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result))

asyncio.run(main())
