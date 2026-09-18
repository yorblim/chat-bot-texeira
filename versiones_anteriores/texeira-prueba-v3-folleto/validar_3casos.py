"""Validacion real con LLM - 3 consultas criticas"""
import os, json, time
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['ANONYMIZED_TELEMETRY'] = 'False'
import sys
sys.path.insert(0, '.')
import app
from fastapi.testclient import TestClient
client = TestClient(app.app)

queries = [
    ('valid-1', 'ES', 'Disponibilidad navidena', u'\u00bfQu\u00e9 tours tienen para hacer el 25 de diciembre?'),
    ('valid-2', 'EN', 'Cancelacion ingles', 'Can I cancel my booking for Valle Sagrado?'),
    ('valid-3', 'ES', 'Pago PayPal + total', u'\u00bfPuedo pagar con PayPal y cu\u00e1nto es el total?'),
]

results = []
for uid, lang, desc, msg in queries:
    start = time.time()
    resp = client.post('/test-chat', json={'message': msg, 'user_id': uid})
    elapsed = (time.time() - start) * 1000
    data = resp.json()
    results.append({
        'uid': uid, 'lang': lang, 'desc': desc, 'msg': msg,
        'response': data.get('response', ''),
        'resolved': data.get('resolved_autonomously'),
        'escalated': data.get('escalated_to_human'),
        'needs_agency': data.get('needs_agency_confirmation'),
        'route': data.get('route'),
        'latency_ms': data.get('latency_ms'),
        'is_rate_limit': data.get('is_rate_limit', False),
    })
    rl = data.get('is_rate_limit', False)
    resolved = data.get('resolved_autonomously')
    needs = data.get('needs_agency_confirmation')
    route = data.get('route')
    latency = data.get('latency_ms')
    print('[%s] %s: resolved=%s needs=%s route=%s latency=%sms rate_limit=%s' % (uid, desc, resolved, needs, route, latency, rl))
    print('  RESPUESTA (300 chars): %s' % data.get('response', '')[:300])
    print()

with open('validacion_real_3casos.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print('Resultados guardados en validacion_real_3casos.json')
