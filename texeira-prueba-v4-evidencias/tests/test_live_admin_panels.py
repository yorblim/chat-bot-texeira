"""Verificación en vivo de paneles administrativos autenticados en Cloud Run."""
import base64
import json
import subprocess
import urllib.request

def main():
    gcloud_cmd = r"C:\Users\HP\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
    res_pass = subprocess.run(
        [gcloud_cmd, "secrets", "versions", "access", "2", "--secret=ADMIN_PASSWORD", "--project=texeira-whatsapp-bot"],
        capture_output=True, text=True
    )
    admin_password = res_pass.stdout.strip()
    auth_str = base64.b64encode(f"admin:{admin_password}".encode()).decode()
    headers = {"Authorization": f"Basic {auth_str}"}
    base_url = "https://texeira-whatsapp-1038134693816.us-central1.run.app"

    endpoints = [
        ("/handoffs", "text/html"),
        ("/catalogo", "text/html"),
        ("/dashboard", "text/html"),
        ("/operational-metrics", "text/html"),
        ("/api/catalog/tours", "application/json"),
        ("/operational-metrics/data", "application/json"),
        ("/handoffs/data", "application/json"),
    ]

    print("=========================================================")
    print("VERIFICACION EN VIVO: PANELES ADMINISTRATIVOS (CLOUD RUN)")
    print("=========================================================")

    for ep, ctype in endpoints:
        req = urllib.request.Request(f"{base_url}{ep}", headers=headers)
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
            content_type = r.headers.get("Content-Type", "").split(";")[0]
            print(f"PASS | {ep:25} -> {r.status} {r.reason} | {content_type} | {len(raw)} bytes")
            if "html" in ctype:
                txt = raw.decode("utf-8")
                assert "admin-nav" in txt, f"Falta barra de navegacion en {ep}"
                assert "Texeira Travel" in txt, f"Falta marca institucional en {ep}"
            elif ep == "/api/catalog/tours":
                tours = json.loads(raw.decode("utf-8"))
                print(f"       Tours canonicos en Neon: {len(tours)} (OK)")
                assert len(tours) >= 18, f"Tours incompletos: {len(tours)}"
            elif ep == "/operational-metrics/data":
                metrics = json.loads(raw.decode("utf-8"))
                print(f"       Metricas operativas en vivo: {metrics.get('received')} recibidos, {metrics.get('api_accepted')} aceptados")
            elif ep == "/handoffs/data":
                rows = json.loads(raw.decode("utf-8"))
                print(f"       Solicitudes registradas en vivo: {len(rows)}")

    print("\nTODOS LOS PANELES Y ENDPOINTS RESPONDIERON 200 OK.")

if __name__ == "__main__":
    main()
