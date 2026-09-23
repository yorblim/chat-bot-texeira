"""
Verificación E2E en Vivo en Google Cloud Run:
Subida de fotos, folletos PDF descargables y tarifas oficiales en el catálogo dinámico,
y su inmediata visualización en las respuestas del bot.
"""
import sys
import os
import io
import subprocess
import requests
from requests.auth import HTTPBasicAuth

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

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

def run_live_tests():
    print("=====================================================================")
    print("   VERIFICACIÓN EN VIVO: PRECIOS, FOTOS Y FOLLETOS EN EL BOT")
    print(f"   URL: {BASE_URL}")
    print("=====================================================================")

    admin_pwd = get_secret("ADMIN_PASSWORD", "2")
    auth = HTTPBasicAuth("admin", admin_pwd)

    test_eid = "tour-valle-milenario-live"
    test_name = "Tour Valle Milenario Andino"
    photo_fn = None
    brochure_fn = None

    try:
        # 1. Crear tour dinámico con tarifa oficial
        print("\n--- 1. Creación de Tour con Tarifa Oficial en Catálogo ---")
        payload = {
            "entity_id": test_eid,
            "name": test_name,
            "aliases": ["valle milenario", "tour valle milenario", "valle milenario andino"],
            "official_price": "68 USD",
            "currency": "USD",
            "schedule": "08:00 AM - 05:00 PM",
            "duration": "1 día completo",
            "includes": "Transporte turístico, almuerzo campestre y guía oficial",
            "excludes": "Gastos personales",
            "is_active": True
        }
        r_create = requests.post(f"{BASE_URL}/api/catalog/tours", auth=auth, json=payload, timeout=35)
        assert r_create.status_code == 200, f"Error al crear tour: {r_create.status_code} - {r_create.text}"
        print("  PASS | 1. Tour dinámico creado exitosamente con tarifa de 68 USD")

        # 2. Subir imagen oficial para el tour
        print("\n--- 2. Subida de Imagen Oficial de Destino ---")
        dummy_img = (
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00'
            b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
            b'\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00'
            b'\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00'
            b'\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9'
        )
        files_img = {"file": ("valle_milenario.jpg", io.BytesIO(dummy_img), "image/jpeg")}
        r_img = requests.post(
            f"{BASE_URL}/api/catalog/upload/{test_eid}",
            auth=auth,
            files=files_img,
            data={"asset_type": "photo"},
            timeout=35
        )
        assert r_img.status_code == 200, f"Error al subir imagen: {r_img.status_code} - {r_img.text}"
        photo_fn = r_img.json().get("filename")
        assert photo_fn, "No se retornó el nombre de archivo de la foto"
        print(f"  PASS | 2. Imagen oficial guardada en el catálogo ({photo_fn})")

        # 3. Subir folleto PDF oficial
        print("\n--- 3. Subida de Folleto PDF Oficial ---")
        dummy_pdf = b"%PDF-1.4\n1 0 obj\n<< /Title (Folleto Valle Milenario) >>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer\n<< /Size 1 >>\nstartxref\n50\n%%EOF"
        files_pdf = {"file": ("folleto_valle_milenario.pdf", io.BytesIO(dummy_pdf), "application/pdf")}
        r_pdf = requests.post(
            f"{BASE_URL}/api/catalog/upload/{test_eid}",
            auth=auth,
            files=files_pdf,
            data={"asset_type": "brochure"},
            timeout=35
        )
        assert r_pdf.status_code == 200, f"Error al subir folleto PDF: {r_pdf.status_code} - {r_pdf.text}"
        brochure_fn = r_pdf.json().get("filename")
        assert brochure_fn, "No se retornó el nombre de archivo del folleto"
        print(f"  PASS | 3. Folleto oficial en PDF guardado en el catálogo ({brochure_fn})")

        # 4. Consultar precio al bot en vivo
        print("\n--- 4. Consulta de Precios al Bot en Vivo (/test-chat) ---")
        r_chat_price = requests.post(
            f"{BASE_URL}/test-chat",
            auth=auth,
            json={"user_id": "live_user_price", "message": "¿Cuánto cuesta el Tour Valle Milenario Andino?"},
            timeout=35
        )
        assert r_chat_price.status_code == 200, f"Error en test-chat: {r_chat_price.status_code}"
        data_price = r_chat_price.json()
        resp_price = data_price.get("response", "")
        print(f"  [Bot]: {resp_price}")
        assert "68 USD" in resp_price or "68 usd" in resp_price.lower(), f"El bot no incluyó el precio oficial (68 USD) en la respuesta: {resp_price}"
        assert data_price.get("route") == "evidence_confirmed_price", f"Ruta inesperada: {data_price.get('route')}"
        print("  PASS | 4. El bot respondió con la tarifa oficial vigente (68 USD) vía ruta evidence_confirmed_price")

        # 5. Consultar fotos al bot en vivo
        print("\n--- 5. Consulta de Fotos al Bot en Vivo (/test-chat) ---")
        r_chat_photo = requests.post(
            f"{BASE_URL}/test-chat",
            auth=auth,
            json={"user_id": "live_user_photo", "message": "¿Tienen fotos del Tour Valle Milenario?"},
            timeout=35
        )
        assert r_chat_photo.status_code == 200, f"Error en test-chat fotos: {r_chat_photo.status_code}"
        data_photo = r_chat_photo.json()
        resp_photo = data_photo.get("response", "")
        print(f"  [Bot]: {resp_photo}")
        assert "![" in resp_photo and "/images/" in resp_photo, f"El bot no incluyó el markdown de imagen: {resp_photo}"
        assert photo_fn in resp_photo, f"El nombre de la foto ({photo_fn}) no está en la respuesta"
        print("  PASS | 5. El bot confirmó el envío de la foto y embebió la imagen en el chat web")

        # 6. Consultar folleto PDF al bot en vivo
        print("\n--- 6. Consulta de Folleto PDF al Bot en Vivo (/test-chat) ---")
        r_chat_doc = requests.post(
            f"{BASE_URL}/test-chat",
            auth=auth,
            json={"user_id": "live_user_doc", "message": "Pásame el folleto en PDF del Tour Valle Milenario"},
            timeout=35
        )
        assert r_chat_doc.status_code == 200, f"Error en test-chat folleto: {r_chat_doc.status_code}"
        data_doc = r_chat_doc.json()
        resp_doc = data_doc.get("response", "")
        print(f"  [Bot]: {resp_doc}")
        assert "/brochures/" in resp_doc, f"El enlace al folleto no está en la respuesta: {resp_doc}"
        assert "Descargar Folleto PDF" in resp_doc, f"El botón/link de descarga no está en la respuesta: {resp_doc}"
        print("  PASS | 6. El bot adjuntó el enlace de descarga directa del folleto PDF oficial")

        # 7. Servir activos multimedia directamente
        print("\n--- 7. Verificación de Endpoints Públicos Multimedia ---")
        r_get_img = requests.get(f"{BASE_URL}/images/{photo_fn}", timeout=35)
        assert r_get_img.status_code == 200, f"Error al servir imagen: {r_get_img.status_code}"
        assert "image" in r_get_img.headers.get("content-type", ""), f"Content-Type erróneo: {r_get_img.headers.get('content-type')}"
        print(f"  PASS | 7a. Endpoint /images/{photo_fn} sirviendo con 200 OK ({len(r_get_img.content)} bytes)")

        r_get_pdf = requests.get(f"{BASE_URL}/brochures/{brochure_fn}", timeout=35)
        assert r_get_pdf.status_code == 200, f"Error al servir PDF: {r_get_pdf.status_code}"
        assert "pdf" in r_get_pdf.headers.get("content-type", "").lower(), f"Content-Type erróneo: {r_get_pdf.headers.get('content-type')}"
        print(f"  PASS | 7b. Endpoint /brochures/{brochure_fn} sirviendo con 200 OK ({len(r_get_pdf.content)} bytes)")

        print("\n=====================================================================")
        print("  ¡TODAS LAS PRUEBAS EN VIVO DE MULTIMEDIA Y PRECIOS PASARON AL 100%!")
        print("=====================================================================")
        return True

    finally:
        # Limpieza del tour de prueba en Cloud Run
        print("\n[LIMPIEZA] Eliminando tour sintético de Cloud Run...")
        try:
            r_del = requests.delete(f"{BASE_URL}/api/catalog/tours/{test_eid}", auth=auth, timeout=35)
            if r_del.status_code == 200:
                print("  PASS | Limpieza completada con éxito.")
            else:
                print(f"  WARN | Limpieza respondió {r_del.status_code}: {r_del.text}")
        except Exception as e:
            print(f"  WARN | Error en limpieza: {e}")

if __name__ == "__main__":
    success = run_live_tests()
    sys.exit(0 if success else 1)
