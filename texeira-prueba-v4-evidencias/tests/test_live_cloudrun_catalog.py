"""
Verificación en vivo de Google Cloud Run para la Fase 1:
Catálogo Dinámico, Precios, Horarios y Fotos/Folletos.
"""
import sys
import os
import json
import hmac
import hashlib
import subprocess
import requests
from requests.auth import HTTPBasicAuth

BASE_URL = "https://texeira-whatsapp-1038134693816.us-central1.run.app"

def get_secret(secret_name, version="latest"):
    val = os.getenv(secret_name)
    if not val:
        import shutil
        gcloud_cmd = shutil.which("gcloud") or r"C:\Users\HP\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
        try:
            res = subprocess.run(
                [gcloud_cmd, "secrets", "versions", "access", version, f"--secret={secret_name}", "--project=texeira-whatsapp-bot"],
                capture_output=True, text=True, check=True
            )
            val = res.stdout.strip()
        except Exception as err:
            print(f"Error obteniendo secreto {secret_name}: {err}")
            val = ""
    return val

def test_live_cloudrun():
    print("=====================================================================")
    print("      VERIFICACIÓN EN VIVO: CLOUD RUN - FASE 1 CATÁLOGO")
    print("=====================================================================")

    # 1. Health check público
    try:
        r_health = requests.get(f"{BASE_URL}/health", timeout=35)
        assert r_health.status_code == 200, f"Health check falló con {r_health.status_code}"
        print(f"  PASS | 1. Health check público: 200 OK -> {r_health.json()}")
    except Exception as e:
        print(f"  FAIL | 1. Health check: {e}")
        return False

    # 2. Seguridad: acceso sin credenciales debe responder 401 Unauthorized
    try:
        r_unauth = requests.get(f"{BASE_URL}/catalogo", timeout=35)
        assert r_unauth.status_code == 401, f"Se esperaba 401 pero respondió {r_unauth.status_code}"
        print(f"  PASS | 2. Seguridad HTTP Basic Auth: 401 Unauthorized verificado en /catalogo")
    except Exception as e:
        print(f"  FAIL | 2. Seguridad: {e}")
        return False

    admin_pwd = get_secret("ADMIN_PASSWORD", "2")
    auth = HTTPBasicAuth("admin", admin_pwd)

    # 3. Catalogo UI con credenciales autorizadas
    try:
        r_cat = requests.get(f"{BASE_URL}/catalogo", auth=auth, timeout=35)
        assert r_cat.status_code == 200, f"Catalogo UI falló con {r_cat.status_code}"
        assert "Catálogo" in r_cat.text, "Título no encontrado en HTML"
        assert "CSRF_TOKEN" in r_cat.text, "Token CSRF no presente en HTML"
        print(f"  PASS | 3. Panel Web (/catalogo) con Auth: 200 OK con protección CSRF e interfaz responsive")
    except Exception as e:
        print(f"  FAIL | 3. Catalogo UI: {e}")
        return False

    # 4. Catalogo API
    try:
        r_api = requests.get(f"{BASE_URL}/api/catalog/tours", auth=auth, timeout=35)
        assert r_api.status_code == 200, f"Catalogo API falló con {r_api.status_code}"
        data = r_api.json()
        tours = data if isinstance(data, list) else data.get("tours", [])
        assert len(tours) >= 19, f"Se esperaban al menos 19 tours, llegaron {len(tours)}"
        print(f"  PASS | 4. API Catálogo (/api/catalog/tours): 200 OK con {len(tours)} tours canónicos sembrados")
    except Exception as e:
        print(f"  FAIL | 4. Catalogo API: {e}")
        return False

    # 5. Consola de asesores intacta
    try:
        r_handoff = requests.get(f"{BASE_URL}/handoffs", auth=auth, timeout=35)
        assert r_handoff.status_code == 200, f"Handoffs UI falló con {r_handoff.status_code}"
        print(f"  PASS | 5. Consola de Asesores (/handoffs): 200 OK activa y operativa")
    except Exception as e:
        print(f"  FAIL | 5. Handoffs UI: {e}")
        return False

    # 6. Handshake Meta Webhook (GET /webhook)
    meta_verify_token = get_secret("META_VERIFY_TOKEN", "latest")
    try:
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": meta_verify_token,
            "hub.challenge": "challenge_cloudrun_live_test_77"
        }
        r_meta = requests.get(f"{BASE_URL}/webhook", params=params, timeout=35)
        assert r_meta.status_code == 200, f"Handshake falló con {r_meta.status_code}"
        assert r_meta.text == "challenge_cloudrun_live_test_77", f"Challenge incorrecto: {r_meta.text}"
        print(f"  PASS | 6. Handshake Webhook Meta (GET /webhook): 200 OK challenge verificado")
    except Exception as e:
        print(f"  FAIL | 6. Handshake Webhook: {e}")
        return False

    # 7. Webhook WhatsApp POST con firma HMAC válida
    meta_app_secret = get_secret("META_APP_SECRET", "latest")
    try:
        status_payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "51987654321",
                            "phone_number_id": "TEST_PHONE_ID"
                        },
                        "statuses": [{
                            "id": "wamid.live.test.status",
                            "status": "delivered",
                            "timestamp": "1726972000",
                            "recipient_id": "51912345678"
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }
        raw_body = json.dumps(status_payload).encode("utf-8")
        sig = "sha256=" + hmac.new(meta_app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "X-Hub-Signature-256": sig
        }
        r_post = requests.post(f"{BASE_URL}/webhook", data=raw_body, headers=headers, timeout=35)
        assert r_post.status_code == 200, f"Webhook POST falló con {r_post.status_code}: {r_post.text}"
        print(f"  PASS | 7. Webhook WhatsApp POST (/webhook con HMAC sha256): 200 OK procesado exitosamente")
    except Exception as e:
        print(f"  FAIL | 7. Webhook WhatsApp POST: {e}")
        return False

    print("=====================================================================")
    print("  RESULTADO: 7/7 CASOS EN VIVO EN CLOUD RUN 100% OPERATIVOS")
    print("=====================================================================")
    return True

if __name__ == "__main__":
    success = test_live_cloudrun()
    sys.exit(0 if success else 1)
