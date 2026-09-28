"""Read-only application review using synthetic data; run with run_isolated.py."""
import os
import sys
import json
import hashlib
import hmac
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from unittest.mock import patch
assert os.environ.get('TEXEIRA_ISOLATED_TEST') == '1'
import app
from fastapi.testclient import TestClient

app.database.init_db(app.SQLITE_DB_PATH)
client = TestClient(app.app)
uid = '51900000000'
app.rag_chain('informacion de Camino Inca', uid)
old_buttons = app.get_quick_buttons(route='evidence_confirmed_price', detected_eid='camino-inka')
app.rag_chain('informacion de City Tour Cusco', uid)

def click(button_id, title, number):
    body = json.dumps({'entry': [{'changes': [{'value': {'metadata': {'phone_number_id': 'synthetic'}, 'messages': [{
        'id': 'synthetic-review-' + str(number), 'from': uid, 'type': 'interactive',
        'interactive': {'type': 'button_reply', 'button_reply': {'id': button_id, 'title': title}},
    }]}}]}]}).encode()
    signature = 'sha256=' + hmac.new(b'synthetic', body, hashlib.sha256).hexdigest()
    with patch.object(app, 'META_APP_SECRET', 'synthetic'), patch.object(app, 'send_whatsapp_message', return_value=True) as send, patch.object(app, 'send_whatsapp_image', return_value=True):
        response = client.post('/webhook', content=body, headers={'X-Hub-Signature-256': signature})
        print('PROBE', json.dumps({'case': number, 'status': response.status_code, 'sent': send.call_args.kwargs if send.called else None}, ensure_ascii=False))

print('OLD_BUTTONS', json.dumps(old_buttons, ensure_ascii=False))
click('btn_inc', 'Qué incluye', 1)
app.clear_history(uid)
app.rag_chain('What does the Inca Trail include?', uid)
click('btn_rates', 'Rates', 2)
client.close()
