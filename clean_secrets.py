import subprocess
import os
import tempfile

env = os.environ.copy()
env['PYTHONIOENCODING'] = 'utf-8'

secrets = ['META_VERIFY_TOKEN', 'META_ACCESS_TOKEN', 'META_PHONE_NUMBER_ID', 'META_APP_SECRET', 'GROQ_API_KEY']
for s in secrets:
    cmd_get = f'gcloud secrets versions access latest --secret={s} --project=texeira-whatsapp-bot'
    res = subprocess.run(cmd_get, shell=True, capture_output=True, env=env)
    b = res.stdout
    if b.startswith(b'\xef\xbb\xbf'):
        b = b[3:]
    text = b.decode('utf-8', errors='ignore').strip()
    clean_bytes = text.encode('utf-8')
    
    with tempfile.NamedTemporaryFile(delete=False, mode='wb') as tmp:
        tmp.write(clean_bytes)
        tmp_path = tmp.name
    try:
        cmd_add = f'gcloud secrets versions add {s} --data-file="{tmp_path}" --project=texeira-whatsapp-bot'
        res2 = subprocess.run(cmd_add, shell=True, capture_output=True, env=env)
        print(f'{s}: updated new version -> code={res2.returncode}')
        if res2.returncode != 0:
            print(f'  error: {res2.stderr.decode("utf-8", errors="ignore")}')
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
