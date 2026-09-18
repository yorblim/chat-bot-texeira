"""Rutas locales con LLM simulado, o solo casos pendientes con servidor real."""
import os
import json
import sys
import time
import uuid
from pathlib import Path
from datetime import datetime

root = Path(__file__).parent
cases = []
for line in (root/'EVALUACION_10_CASOS.md').read_text(encoding='utf-8').splitlines():
    if line.startswith('| C') and line[3:5].isdigit():
        cells = [x.strip() for x in line.split('|')]
        case_id, conversation = cells[1].split(' / ')
        cases.append((case_id, conversation, cells[2]))
assert len(cases) == 10
mode = sys.argv[1] if len(sys.argv) > 1 else 'local'
assert mode in {'local', 'live'}
run = datetime.now().strftime('%Y%m%d-%H%M%S')
rows = []
output = root/f'evaluation-ten-{mode}-{run}.json'
if mode == 'local':
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['ANONYMIZED_TELEMETRY'] = 'False'
    import app
    class FakeLLM:
        calls = 0
        def invoke(self, messages):
            self.calls += 1
            return type('Answer', (), {'content': 'SIMULATED_RESPONSE_NOT_EVALUABLE'})()
    fake = FakeLLM()
    app.get_llm = lambda: fake
else:
    import urllib.request
    prior = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
    selected = {r['id'] for r in prior['rows'] if r['llm_simulated_calls'] > 0}
    cases = [c for c in cases if c[0] in selected]

for case_id, conversation, question in cases:
    start = time.perf_counter()
    row = {'id':case_id, 'conversation':conversation, 'question':question}
    if mode == 'local':
        before = fake.calls
        result = app.rag_chain(question, user_id=f'eval-{run}-{conversation}')
        row.update(result=result, detected_language=app.detect_language(question), llm_simulated_calls=fake.calls-before)
    else:
        payload = {'message':question, 'user_id':f'eval-{run}-{conversation}', 'client_message_id':str(uuid.uuid4())}
        req = urllib.request.Request('http://127.0.0.1:8020/test-chat', data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                row.update(http_status=response.status, result=json.load(response))
        except Exception as error:
            row['infrastructure_error'] = type(error).__name__
    row['seconds'] = round(time.perf_counter()-start, 3)
    rows.append(row)
    output.write_text(json.dumps({'mode':mode, 'rows':rows}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(case_id, row.get('llm_simulated_calls', ''), row['seconds'], flush=True)
    if 'infrastructure_error' in row: break
print(output, flush=True)
