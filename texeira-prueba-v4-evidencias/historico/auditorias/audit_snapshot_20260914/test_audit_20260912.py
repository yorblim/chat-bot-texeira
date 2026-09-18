"""Regresión auditada: fuentes locales, endpoint y dobles sin proveedor externo."""
import asyncio,json
from pathlib import Path
from types import SimpleNamespace
import app
import trial_support as s
from src import evidence as e

records=[]
app.database.log_interaction=lambda **kw:records.append(kw)
def forbidden():raise AssertionError('Llamada externa no autorizada')
app.get_llm=forbidden
rows=[]
async def check(q,predicate,user=None):
    user=user or 'audit-'+str(len(rows))
    before=len(app.get_history(user))
    raw=await app.test_chat(app.TestChatRequest(user_id=user,message=q))
    result=json.loads(raw.body)
    assert raw.status_code==200,(q,result)
    assert predicate(result),(q,result)
    history=app.get_history(user)
    assert len(history)==min(before+2,20),(q,'duplicated history')
    assert history[-1]['content']==result['response'],q
    assert result['escalated_to_human'] is False,q
    rows.append({'question':q,'result':result,'passed':True})
async def main():
    for t in s.CATALOG['tours']:assert e.is_product_confirmed(t['entity_id']),t
    assert s.CATALOG['agency']['emails'][1]=='eugeniotejeira@hotmail.com'
    await check('¿Qué tours tienen?',lambda r:'Salkantay' in r['response'] and 'Q’eswachaca' in r['response'])
    for tour in ['City Tour','Valle Sagrado','7 colores']:
        await check('¿Qué horario tiene '+tour+'?',lambda r:r['conflict_detected'] and not r['resolved_autonomously'])
    await check('¿Qué horario tiene Valle Sur?',lambda r:'08:40-14:00' in r['response'])
    await check('¿Qué incluye Machu Picchu en tren?',lambda r:'bus subida bajada' in r['response'],'follow')
    await check('¿Y el horario?',lambda r:r['needs_agency_confirmation'],'follow')
    await check('What does Machu Picchu by car include?',lambda r:r['needs_agency_confirmation'] and 'round-trip train' not in r['response'])
    await check('¿Qué incluye el tour cuatrimoto Maras-Moray?',lambda r:'casco equipo proteccion' in r['response'])
    await check('¿El boleto turístico está incluido en Valle Sagrado?',lambda r:'No incluye: boleto turistico' in r['response'])
    await check('¿Qué no incluye Valle Sagrado?',lambda r:'No incluye: boleto turistico' in r['response'])
    await check('¿La entrada está incluida en Humantay?',lambda r:r['needs_agency_confirmation'])
    await check('¿Qué incluye Salkantay?',lambda r:r['needs_agency_confirmation'])
    await check('¿Cuánto dura Salkantay?',lambda r:'4 días' in r['response'] and '3 noches' not in r['response'])
    await check('¿Cuánto cuesta Machu Picchu?',lambda r:r['needs_agency_confirmation'])
    await check('¿Tienen Valle Sagrado disponible mañana?',lambda r:r['needs_agency_confirmation'] and not r['resolved_autonomously'])
    await check('Can I cancel my booking?',lambda r:r['needs_agency_confirmation'])
    await check('Can I pay with PayPal?',lambda r:r['needs_agency_confirmation'])
    await check('¿Cuál es el correo?',lambda r:'eugeniotejeira@hotmail.com' in r['response'] and 'eugenio.tejeira' not in r['response'])
    await check('¿Tienen paquete de 7 días?',lambda r:r['needs_agency_confirmation'])
    # Reproducción de conflicto de inclusión/exclusión, sin alterar los archivos.
    original=e._load_facts
    baseline=original()
    contradictory=e.Fact(dict(fact_id='test',entity_id='laguna-humantay',field='excludes',item='desayuno',value=True,source_id='TEST'))
    e._load_facts=lambda:baseline+[contradictory]
    try:
        assert e.detect_conflicts('laguna-humantay','includes')
        assert 'includes/desayuno: confirmado' not in e.build_context_for_entity('laguna-humantay')
    finally:e._load_facts=original
    # Ruta RAG: conserva historial final y no afirma derivación ejecutada.
    app.get_retriever=lambda:SimpleNamespace(invoke=lambda q:[SimpleNamespace(page_content='Contacto documentado; datos pendientes.',metadata={})])
    app.get_llm=lambda:SimpleNamespace(invoke=lambda messages:SimpleNamespace(content='Consulta con un asesor de la agencia.'))
    await check('Necesito orientación para mi viaje',lambda r:not r['escalated_to_human'])
    assert all(r['interaction_type']=='predefined' for r in records[:-1])
    Path('AUDIT_TEST_RESULTS.json').write_text(json.dumps({'mode':'local_no_external_llm','cases':rows,'additional_checks':['catalog-evidence consistency','includes-excludes conflict','history final','route metrics']},ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS',len(rows),'casos endpoint + integridad, conflicto y métricas; sin API.')
asyncio.run(main())
