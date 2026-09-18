import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
"""Reproduce respuestas guardadas, sin red, LLM real ni escritura de logs."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import app

root = Path(__file__).parent
saved = json.loads((root/'evaluation-ten-live-20260911-111304.json').read_text(encoding='utf-8'))['rows']
app.get_retriever = lambda: SimpleNamespace(invoke=lambda q: [SimpleNamespace(page_content='Contexto de prueba local.', metadata={})])
app.database.log_interaction = lambda **kwargs: None
rows = []
async def check(case_id, question, response):
    app.get_llm = lambda: SimpleNamespace(invoke=lambda messages: SimpleNamespace(content=response))
    user = 'review-opencode-' + case_id
    result = await app.test_chat(app.TestChatRequest(user_id=user, message=question))
    body = json.loads(result.body)
    history = app.get_history(user)
    rows.append({'id':case_id, 'result':body, 'history_matches_response': bool(history) and history[-1]['content'] in body.get('response','')})

async def main():
    for r in saved:
        if r['id'] in {'C06','C07','C08','C09'}:
            await check(r['id'], r['question'], r['result']['response'])
    await check('handoff_false_positive', 'Necesito ayuda con mi viaje', 'Contacta a un asesor para consultar los detalles.')
    await check('contact_paraphrase', '¿Hay cupos mañana?', 'Puedes contactar a Texeira mediante estas fuentes de precios: https://www.mptc.com.pe/tour.php?id=3')
    await check('pen_bypass', '¿Cuál es el precio en soles de Salkantay?', 'Sin cotización confirmada.')
    (root/'REVISION_OPENCODE.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    for r in rows:
        b = r['result']
        print(r['id'], json.dumps({k:b.get(k) for k in ['resolved_autonomously','escalated_to_human','needs_agency_confirmation'] }), 'history_matches', r['history_matches_response'])
asyncio.run(main())
