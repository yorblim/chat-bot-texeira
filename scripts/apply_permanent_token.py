import subprocess
import os
import tempfile

env = os.environ.copy()
env['PYTHONIOENCODING'] = 'utf-8'

token = "EAAT52KsZBIywBSdvqRfcMFYJns1o0Ki4rc0bWiarkVq7tiXSMcWlE596L6hBp0ryn31mqLcShOM80fVoSAL6cLNyCORQdtE7tNUsEzerb8MP5hCOSR8I9hXpDKWYt4ofQhZAnkk32aZBfi5vaM4ShRCSGlXbEMZCOv50y6ZBtoSL00X6eRq5Hlw3rCOZBKYnOVflwQGp8CbHZCHi0yZADnY0tjMWajMZCANBqZBKoj".strip()

# Write to temp file without BOM
with tempfile.NamedTemporaryFile(delete=False, mode='wb') as tmp:
    tmp.write(token.encode('utf-8'))
    tmp_path = tmp.name

gcloud_path = r"C:\Users\HP\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
cmd_add = f'"{gcloud_path}" secrets versions add META_ACCESS_TOKEN --data-file="{tmp_path}" --project=texeira-whatsapp-bot'
res = subprocess.run(cmd_add, shell=True, capture_output=True, text=True, env=env)
os.remove(tmp_path)
print("Secret Manager output:")
print(res.stdout)
if res.stderr:
    print("Stderr:", res.stderr)

# Also update local .env file in texeira-prueba-v4-evidencias if present
env_paths = [
    r"c:\Users\HP\Desktop\Chat bot\texeira-prueba-v4-evidencias\.env",
    r"c:\Users\HP\Desktop\Chat bot\.env"
]
for ep in env_paths:
    if os.path.exists(ep):
        with open(ep, "r", encoding="utf-8") as f:
            lines = f.readlines()
        new_lines = []
        found = False
        for l in lines:
            if l.startswith("META_ACCESS_TOKEN="):
                new_lines.append(f"META_ACCESS_TOKEN={token}\n")
                found = True
            else:
                new_lines.append(l)
        if not found:
            new_lines.append(f"\nMETA_ACCESS_TOKEN={token}\n")
        with open(ep, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(f"Updated {ep}")
