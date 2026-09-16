"""Entrada pública: fallos, ACK, firma delegada y superficie, sin red/modelo."""
import asyncio
import os
from unittest.mock import patch
import httpx
from fastapi import FastAPI
import whatsapp_entry as entry

async def run():
    with patch.object(entry,'_load_app',side_effect=RuntimeError('synthetic-secret')):
        try: await entry.startup()
        except RuntimeError: pass
        else: raise AssertionError('El arranque debe fallar')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=entry.app),base_url='http://test') as c:
        r=await c.get('/healthz')
        assert r.status_code==503 and 'synthetic-secret' not in r.text
        assert (await c.post('/webhook',json={})).status_code==503
        with patch.dict(os.environ,{'META_VERIFY_TOKEN':''}):
            assert (await c.get('/webhook',params={'hub.mode':'subscribe','hub.verify_token':'','hub.challenge':'x'})).status_code==403
        with patch.dict(os.environ,{'META_VERIFY_TOKEN':'synthetic'}):
            r=await c.get('/webhook',params={'hub.mode':'subscribe','hub.verify_token':'synthetic','hub.challenge':'x'})
            assert r.status_code==200 and r.text=='x'
        for path in ['/dashboard','/handoffs','/operational-metrics','/test-chat','/docs']:
            assert (await c.get(path)).status_code==404
    local=FastAPI(); lifecycle=[]
    async def start(): lifecycle.append('start')
    async def stop(): lifecycle.append('stop')
    local.add_event_handler('startup',start);local.add_event_handler('shutdown',stop)
    with patch.dict(os.environ,{},clear=True),patch.object(entry,'_load_app',return_value=local):
        await entry.startup()
        assert entry.health().status_code==200
        await entry.shutdown()
        assert lifecycle==['start','stop'] and entry.health().status_code==503
    with patch.dict(os.environ,{'K_SERVICE':'synthetic'}),patch.object(entry,'_load_app') as loader:
        try: await entry.startup()
        except RuntimeError: pass
        else: raise AssertionError('No habilitar Cloud Run sin persistencia/cola')
        loader.assert_not_called()
    order=[]
    async def fake(scope,receive,send):
        await send({'type':'http.response.start','status':403,'headers':[]})
        await send({'type':'http.response.body','body':b'rejected'})
        order.append('background')
    async def receive(): return {'type':'http.request','body':b'','more_body':False}
    async def send(message):
        order.append(message['type'])
        if message['type']=='http.response.start': assert message['status']==403
    entry._state.update(ready=True,local_app=fake,error=None)
    await entry.app({'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':'POST','scheme':'http','path':'/webhook','raw_path':b'/webhook','query_string':b'','headers':[],'server':('test',80),'client':('127.0.0.1',123),'root_path':''},receive,send)
    assert order==['http.response.start','http.response.body','background'],order
    print('PASS: arranque fallido, salud, token, rutas privadas, lifecycle, ACK inmediato y estado 403 preservado.')

asyncio.run(run())
