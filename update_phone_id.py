import subprocess
import os
import tempfile

env = os.environ.copy()
env['PYTHONIOENCODING'] = 'utf-8'

# Actualizar META_PHONE_NUMBER_ID con el valor correcto del portal de Meta
updates = {
    'META_PHONE_NUMBER_ID': '1344977292012714',
}

for secret_name, new_value in updates.items():
    clean_bytes = new_value.encode('utf-8')
    with tempfile.NamedTemporaryFile(delete=False, mode='wb') as tmp:
        tmp.write(clean_bytes)
        tmp_path = tmp.name
    try:
        cmd = f'gcloud secrets versions add {secret_name} --data-file="{tmp_path}" --project=texeira-whatsapp-bot'
        res = subprocess.run(cmd, shell=True, capture_output=True, env=env)
        if res.returncode == 0:
            print(f'{secret_name}: actualizado a -> {new_value}')
        else:
            print(f'{secret_name}: ERROR -> {res.stderr.decode("utf-8", errors="ignore")}')
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
