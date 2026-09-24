"""
test_catalog_api.py — Prueba de integración API para el Catálogo Dinámico de Texeira Travel.

Prueba los endpoints HTTP FastAPI de /catalogo, /api/catalog/tours, subida de archivos
y entrega estática/DB de fotos y folletos PDF.
"""

import sys
import io
from pathlib import Path
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app as fastapi_app
import catalog_service

client = TestClient(fastapi_app.app)
TEST_API_EID = "eval-api-tour-paracas"


def run_api_tests():
    print("=====================================================================")
    print("     PRUEBA DE ENDPOINTS API: CATÁLOGO Y ASSETS MULTIMEDIA")
    print("=====================================================================")

    passed = 0
    failed = 0

    def check(name, cond, detail=""):
        nonlocal passed, failed
        if cond:
            print(f"  PASS | {name}")
            passed += 1
        else:
            print(f"  FAIL | {name} - {detail}")
            failed += 1

    try:
        # 1. GET /catalogo (UI HTML)
        resp_ui = client.get("/catalogo")
        check("1. GET /catalogo responde 200 OK", resp_ui.status_code == 200)
        check("2. HTML contiene título del catálogo", "Catálogo de Tours y Tarifas" in resp_ui.text)

        # 2. Extraer CSRF token del HTML
        import re
        csrf_match = re.search(r'const CSRF_TOKEN = "([^"]+)";', resp_ui.text)
        csrf_token = csrf_match.group(1) if csrf_match else ""
        check("3. Token CSRF generado en el panel", len(csrf_token) > 10, f"Token: {csrf_token}")

        # 3. GET /api/catalog/tours
        resp_list = client.get("/api/catalog/tours")
        check("4. GET /api/catalog/tours responde 200 OK", resp_list.status_code == 200)
        tours = resp_list.json()
        check("5. Listado contiene al menos 19 tours", len(tours) >= 19, f"Total: {len(tours)}")

        # 4. POST /api/catalog/tours con payload válido
        payload = {
            "entity_id": TEST_API_EID,
            "name": "Tour Islas Ballestas & Paracas",
            "aliases": ["paracas", "ballestas", "candelabro"],
            "official_price": "28",
            "currency": "USD",
            "schedule": "08:00-11:00",
            "duration": "3 horas",
            "includes": "Lancha a motor, chaleco, guía oficial",
            "excludes": "Impuesto SERNANP",
        }
        resp_create = client.post(
            "/api/catalog/tours",
            json=payload,
            headers={"X-Catalog-CSRF": csrf_token}
        )
        check("6. Creación de tour vía POST responde 200 OK", resp_create.status_code == 200 and resp_create.json().get("ok"))

        # 6. GET /api/catalog/tours/{entity_id}
        resp_get = client.get(f"/api/catalog/tours/{TEST_API_EID}")
        check("7. GET /api/catalog/tours/{id} retorna tour creado", resp_get.status_code == 200 and resp_get.json().get("name") == payload["name"])

        # 7. Subida de imagen POST /api/catalog/upload/{id}
        fake_image = io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdbparacas_test_image")
        resp_img_upload = client.post(
            f"/api/catalog/upload/{TEST_API_EID}",
            files={"file": ("ballestas.jpg", fake_image, "image/jpeg")},
            data={"asset_type": "photo"},
            headers={"X-Catalog-CSRF": csrf_token}
        )
        check("8. Subida de foto responde 200 OK", resp_img_upload.status_code == 200 and resp_img_upload.json().get("ok"))
        photo_filename = resp_img_upload.json().get("filename")

        # 8. Servir imagen GET /images/{filename}
        resp_img_serve = client.get(f"/images/{photo_filename}")
        check("9. GET /images/{filename} sirve la imagen con 200 OK", resp_img_serve.status_code == 200 and "image" in resp_img_serve.headers.get("content-type", ""))

        # 9. Subida de folleto PDF POST /api/catalog/upload/{id}
        fake_pdf = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\nparacas_brochure")
        resp_pdf_upload = client.post(
            f"/api/catalog/upload/{TEST_API_EID}",
            files={"file": ("folleto_paracas.pdf", fake_pdf, "application/pdf")},
            data={"asset_type": "brochure"},
            headers={"X-Catalog-CSRF": csrf_token}
        )
        check("10. Subida de folleto PDF responde 200 OK", resp_pdf_upload.status_code == 200 and resp_pdf_upload.json().get("ok"))
        pdf_filename = resp_pdf_upload.json().get("filename")

        # 10. Servir folleto GET /brochures/{filename}
        resp_pdf_serve = client.get(f"/brochures/{pdf_filename}")
        check("11. GET /brochures/{filename} sirve el PDF con 200 OK", resp_pdf_serve.status_code == 200 and resp_pdf_serve.headers.get("content-type") == "application/pdf")

        # 11. Eliminar tour DELETE /api/catalog/tours/{id}
        resp_del = client.delete(
            f"/api/catalog/tours/{TEST_API_EID}",
            headers={"X-Catalog-CSRF": csrf_token}
        )
        check("12. DELETE /api/catalog/tours/{id} responde 200 OK", resp_del.status_code == 200 and resp_del.json().get("ok"))

    finally:
        print("\n[LIMPIEZA] Eliminando archivos de prueba de disco y base de datos...")
        try:
            catalog_service.delete_tour(TEST_API_EID)
            catalog_service.delete_tour("hack")
            for d, f in [
                (catalog_service.IMAGES_DIR, f"{TEST_API_EID}_photo.jpg"),
                (catalog_service.BROCHURES_DIR, f"{TEST_API_EID}_brochure.pdf"),
            ]:
                p = d / f
                if p.exists():
                    p.unlink()
            print("  PASS | Limpieza de prueba API completada.")
        except Exception as e:
            print(f"  FAIL | Error en limpieza API: {e}")

    print("\n=====================================================================")
    print(f"RESULTADO: {passed} PASS / {failed} FAIL")
    print("=====================================================================")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_api_tests()
