"""Pruebas locales de cola persistente, transiciones y protección del panel."""
import asyncio
import json
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import httpx
import app
import handoff_support as h
import whatsapp_entry

async def run():
    with tempfile.TemporaryDirectory() as folder:
        h.DB=Path(folder)/'requests.db'
        records=[]
        app.database.log_interaction=lambda **kw: records.append(kw)
        app.get_llm=lambda: (_ for _ in ()).throw(AssertionError('No LLM'))
        assert not h.requested('No quiero hablar con un asesor')
        assert not h.requested('¿Qué incluye Machu Picchu en tren?')
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app),base_url='http://test') as c:
            app.add_to_history('handoff-test','human','Quiero consultar disponibilidad')
            app.add_to_history('handoff-test','ai','Pendiente de confirmar')
            r=await c.post('/test-chat',json={'user_id':'handoff-test','message':'Quiero hablar con un asesor'})
            assert r.status_code==200,r.text
            d=r.json();ticket=d['handoff_id']
            assert ticket and d['escalated_to_human'] and not d['resolved_autonomously']
            assert app.get_history('handoff-test')[-1]['content']==d['response']
            assert records[-1]['escalated_to_human'] and not records[-1]['resolved_autonomously']
            again=(await c.post('/test-chat',json={'user_id':'handoff-test','message':'asesor'})).json()
            assert again['handoff_id']==ticket
            rows=(await c.get('/handoffs/data')).json()
            assert len(rows)==1 and 'disponibilidad' in rows[0]['context']
            assert (await c.post('/handoffs/'+ticket,json={'status':'closed','advisor':'Ana','note':'x'})).status_code==403
            page=(await c.get('/handoffs')).text
            csrf=re.search(r"'X-Handoff-CSRF':'([^']+)'",page).group(1)
            headers={'X-Handoff-CSRF':csrf}
            assert (await c.post('/handoffs/'+ticket,headers=headers,json={'status':'closed','advisor':'Ana','note':'x'})).status_code==400
            assert (await c.post('/handoffs/'+ticket,headers=headers,json={'status':'in_progress','advisor':'Ana'})).status_code==200
            assert (await c.post('/handoffs/'+ticket,headers=headers,json={'status':'closed','advisor':'Ana'})).status_code==400
            assert (await c.post('/handoffs/'+ticket,headers=headers,json={'status':'closed','advisor':'Ana','note':'Atendida manualmente en prueba.'})).status_code==200
            assert (await c.get('/handoffs/data')).json()[0]['status']=='closed'
            english=(await c.post('/test-chat',json={'user_id':'english-user','message':'speak to an agent'})).json()
            assert 'Your request' in english['response'] and 'pending human attention' in english['response']
            assert not english['resolved_autonomously'] and english['handoff_id']
            assert app.get_history('english-user')[-1]['content']==english['response']
        # Reintentos simultáneos no duplican solicitudes abiertas; canales separados.
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids=list(pool.map(lambda _:h.create_request('same','whatsapp','asesor',[])[0]['id'],range(8)))
        assert len(set(ids))==1
        assert h.create_request('same','test','asesor',[])[0]['id']!=ids[0]
        # El servidor público nunca expone el panel ni sus datos.
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=whatsapp_entry.app),base_url='http://test') as c:
            assert (await c.get('/handoffs')).status_code==404
            assert (await c.get('/handoffs/data')).status_code==404
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app,client=('203.0.113.1',1)),base_url='http://test') as c:
            assert (await c.get('/handoffs/data')).status_code==403
    Path('RESULTADO_HANDOFF.json').write_text(json.dumps({'passed':True,'mode':'local_no_llm_no_messages','checks':['request_not_resolution','history_final','persistent_context','deduplication','transitions','csrf','concurrent_duplicates','channel_isolation','public_panel_unavailable']}),encoding='utf-8')
    print('PASS: solicitudes, persistencia, concurrencia, estados y protección; sin mensajes ni LLM.')

asyncio.run(run())
