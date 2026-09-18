import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
"""Banco de aceptación ES/EN. No usa LLM ni mide precisión poblacional."""
import asyncio,json,sys,hashlib
from pathlib import Path
import app

CASES=[
 ('es_bus','es','¿Qué incluye Machu Picchu en tren?','evidence_includes',False,'Bus de subida y bajada','F1/F3: inclusiones'),
 ('en_bus','en','What does Machu Picchu by train include?','evidence_includes',False,'Bus up and down','F1/F3: inclusiones'),
 ('es_duration','es','¿Cuánto dura Salkantay?','evidence_duration',False,'4 días','F2: mapa de cuatro días; no inferir noches'),
 ('en_duration','en','How long is Salkantay?','evidence_duration',False,'4 days','F2: mapa de cuatro días; no inferir noches'),
 ('es_schedule','es','¿Qué horario tiene Valle Sagrado?','evidence_schedule',False,'07:30-18:30','F1: horario oficial confirmado'),
 ('en_schedule','en','What time is the Sacred Valley tour?','evidence_schedule',False,'07:30-18:30','F1: official confirmed schedule'),
 ('es_price','es','¿Cuánto cuesta Machu Picchu?','evidence_unknown',True,'agencia','Sin precio oficial en las fuentes'),
 ('en_price','en','How much does Machu Picchu cost?','evidence_unknown',True,'agency','Sin precio oficial en las fuentes'),
 ('es_availability','es','¿Tienen Valle Sagrado disponible mañana?','evidence_unknown',True,'agencia','Sin inventario por fecha'),
 ('en_availability','en','Is Sacred Valley available tomorrow?','evidence_unknown',True,'agency','Sin inventario por fecha'),
 ('es_cancel','es','¿Puedo cancelar mi reserva?','evidence_unknown',True,'agencia','Política no documentada'),
 ('en_cancel','en','Can I cancel my booking?','evidence_unknown',True,'agency','Política no documentada'),
 ('en_humantay','en','What does Humantay include?','evidence_includes',False,'Breakfast','F1: desayuno documentado'),
 ('en_atv','en','What does the ATV tour include?','evidence_includes',False,'Helmet and protective equipment','Catálogo/evidencia: equipo de protección'),
 ('en_ticket','en','Is the tourist ticket included in Sacred Valley?','evidence_includes',False,'Does not include: Tourist ticket','F3: boleto excluido'),
 ('en_missing','en','Is insurance included in Humantay?','evidence_unknown',True,'agency','Seguro no documentado'),
]

async def main():
    app.database.log_interaction=lambda **kw:None
    app.get_llm=lambda: (_ for _ in ()).throw(AssertionError('Proveedor externo bloqueado'))
    rows=[]
    for uid,lang,q,route,pending,term,basis in CASES:
        r=await app.test_chat(app.TestChatRequest(user_id='language-'+uid,message=q))
        d=json.loads(r.body);answer=d.get('response','')
        checks={'route':d.get('response_route')==route,'pending':d.get('needs_agency_confirmation')==pending,
                'resolution_flag':d.get('resolved_autonomously')==(not pending),
                'expected_content':term.casefold() in answer.casefold(),
                'english_without_spanish_templates':lang!='en' or not any(t in answer.lower() for t in ['incluye:','requiere confirmacion','escribe:','las fuentes','dias','días'])}
        rows.append(dict(id=uid,language=lang,question=q,expected_route=route,expected_pending=pending,basis=basis,
                         answer=answer,actual_route=d.get('response_route'),checks=checks,passed=all(checks.values())))
    result={'mode':'deterministic_local_no_llm','cases':rows,'passed':sum(r['passed'] for r in rows),'total':len(rows),
            'limits':'Regresión de casos conocidos; no precisión estadística, no evaluación de generación real ni validación humana.',
            'code_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ['app.py','verified_routes.py','handoff_support.py']}}
    dest=Path(sys.argv[1] if len(sys.argv)>1 else 'EVALUACION_IDIOMAS_LOCAL.json')
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':result['passed'],'total':len(rows),'failed_ids':[r['id'] for r in rows if not r['passed']]},ensure_ascii=False))
asyncio.run(main())
