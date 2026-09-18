import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
"""Cinco solicitudes reales al servidor local; sin reintentos automáticos."""
import json
import time
import uuid
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

questions = ['¿Cuánto cuesta Valle Sagrado?', '¿Y qué incluye?', '¿Las entradas están incluidas?', '¿Puedo cancelar gratis mañana?', 'What does the Machu Picchu tour include?']
run_id = 'live-five-' + datetime.now().strftime('%Y%m%d-%H%M%S')
output = Path(__file__).parent / (run_id + '.json')
rows = []
for question in questions:
    request = urllib.request.Request('http://127.0.0.1:8020/test-chat', data=json.dumps({'user_id':run_id, 'message':question, 'client_message_id':str(uuid.uuid4())}).encode(), headers={'Content-Type':'application/json'}, method='POST')
    start = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=150) as response:
            payload = json.load(response)
            row = {'question':question, 'http_status':response.status, 'elapsed_seconds':round(time.monotonic()-start,3), 'result':payload}
    except Exception as error:
        row = {'question':question, 'elapsed_seconds':round(time.monotonic()-start,3), 'transport_error_type':type(error).__name__}
    rows.append(row)
    output.write_text(json.dumps({'run_id':run_id,'rows':rows},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(row,ensure_ascii=True),flush=True)
    if 'transport_error_type' in row:
        break
print('Saved:',output,flush=True)
