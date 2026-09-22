"""
test_catalog_dynamic.py — Validación automatizada del Catálogo Dinámico, Precios, Horarios y Multimedia.

Prueba de punta a punta:
  1. Siembra inicial e integridad de los 19 tours canónicos.
  2. Creación de un tour dinámico con palabras clave y horario.
  3. Detección de entidad dinámica con detect_entity_from_question().
  4. Respuesta determinista de tarifa oficial confirmada.
  5. Actualización en caliente de precio sin reiniciar el servicio.
  6. Subida y recuperación de foto y folleto PDF (disco + DB).
  7. Eliminación y limpieza garantizada en bloque finally.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import catalog_service
from trial_support import detect_entity_from_question
from src.evidence import get_facts, is_product_confirmed

TEST_ENTITY_ID = "eval-dyn-huacachina"


def run_tests():
    print("=====================================================================")
    print("      VALIDACIÓN DEL CATÁLOGO DINÁMICO Y PRECIOS VIGENTES")
    print("=====================================================================")

    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            print(f"  PASS | {name}")
            passed += 1
        else:
            print(f"  FAIL | {name} - {detail}")
            failed += 1

    try:
        # 1. Verificar siembra e inicialización
        catalog_service.init_catalog_db()
        tours = catalog_service.get_all_tours(active_only=True)
        check("1. Siembra inicial: al menos 19 tours canónicos", len(tours) >= 19, f"Total: {len(tours)}")

        city_tour = catalog_service.get_tour_by_id("city-tour-cusco")
        check("2. Tour canónico presente: City Tour Cusco", city_tour is not None and city_tour["name"] == "City Tour Cusco")

        # 2. Registrar un tour personalizado
        test_payload = {
            "entity_id": TEST_ENTITY_ID,
            "name": "Tour Huacachina & Tubulares",
            "aliases": ["huacachina", "tubulares", "dunas ica"],
            "official_price": "35",
            "currency": "USD",
            "schedule": "10:00-18:00",
            "duration": "1 día",
            "includes": "Transporte y paseo en tubulares",
            "excludes": "Tasa de embarque",
            "is_active": True,
        }
        ok, res_id = catalog_service.upsert_tour(test_payload)
        check("3. Creación de tour dinámico exitosa", ok and res_id == TEST_ENTITY_ID)

        created_tour = catalog_service.get_tour_by_id(TEST_ENTITY_ID)
        check("4. Tour guardado con datos correctos", created_tour is not None and created_tour["official_price"] == "35")

        # 3. Detección de entidad dinámica
        detected = detect_entity_from_question("¿Tienen información de los tubulares en huacachina?")
        check("5. Detección de entidad dinámica por alias", detected == TEST_ENTITY_ID, f"Detectado: {detected}")

        # 4. Confirmación de producto y precio oficial
        is_conf = is_product_confirmed(TEST_ENTITY_ID)
        check("6. Producto dinámico marcado como confirmado", is_conf)

        price_facts = get_facts(TEST_ENTITY_ID, "official_price")
        check("7. Hecho de precio oficial confirmado generado", len(price_facts) == 1 and "35 USD" in price_facts[0].value)

        # 5. Actualización en caliente de precio
        test_payload["official_price"] = "45"
        ok_up, _ = catalog_service.upsert_tour(test_payload)
        price_facts_up = get_facts(TEST_ENTITY_ID, "official_price")
        check("8. Actualización en caliente de tarifa (45 USD)", ok_up and price_facts_up[0].value == "45 USD")

        # 6. Subida y recuperación de assets (foto y folleto)
        fake_jpg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb"
        ok_photo, photo_filename = catalog_service.save_asset(
            entity_id=TEST_ENTITY_ID,
            asset_type="photo",
            filename="dunas.jpg",
            content_bytes=fake_jpg,
        )
        check("9. Guardado de foto de tour exitoso", ok_photo and photo_filename.endswith(".jpg"))

        recovered_photo = catalog_service.get_asset_bytes(photo_filename, "photo")
        check("10. Recuperación de foto con mime type correcto", recovered_photo is not None and recovered_photo[1] == "image/jpeg")

        fake_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        ok_pdf, pdf_filename = catalog_service.save_asset(
            entity_id=TEST_ENTITY_ID,
            asset_type="brochure",
            filename="folleto_ica.pdf",
            content_bytes=fake_pdf,
        )
        check("11. Guardado de folleto PDF exitoso", ok_pdf and pdf_filename.endswith(".pdf"))

        recovered_pdf = catalog_service.get_asset_bytes(pdf_filename, "brochure")
        check("12. Recuperación de folleto con mime application/pdf", recovered_pdf is not None and recovered_pdf[1] == "application/pdf")

    finally:
        # 7. Limpieza estricta de datos sintéticos
        print("\n[LIMPIEZA] Purgando entidad de prueba y assets sintéticos...")
        try:
            catalog_service.delete_tour(TEST_ENTITY_ID)
            # Limpiar archivos de disco si se crearon
            for d, f in [
                (catalog_service.IMAGES_DIR, f"{TEST_ENTITY_ID}_photo.jpg"),
                (catalog_service.BROCHURES_DIR, f"{TEST_ENTITY_ID}_brochure.pdf"),
            ]:
                p = d / f
                if p.exists():
                    try:
                        p.unlink()
                    except Exception:
                        pass
            print("  PASS | Limpieza completada con éxito.")
        except Exception as e:
            print(f"  FAIL | Error en limpieza: {e}")

    print("\n=====================================================================")
    print(f"RESULTADO: {passed} PASS / {failed} FAIL")
    print("=====================================================================")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
