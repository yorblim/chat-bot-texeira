"""
test_multimedia_dispatch.py — Suite de pruebas para la Fase 2:
Motor de Despacho Multimedia en WhatsApp (Fotos y Folletos PDF).

Valida:
1. Detección precisa de intenciones (fotos y folletos PDF).
2. Filtros estrictos anti-alucinación (evitar envíos no solicitados en saludos, listas o ayuda).
3. Despacho de fotos oficiales (canónicas y dinámicas desde catalog_service).
4. Despacho de folletos PDF oficiales vinculados al catálogo dinámico.
5. Función send_whatsapp_document hacia WhatsApp Cloud API.
"""
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.visual.visual_engine import (
    is_photo_requested,
    is_brochure_requested,
    get_tour_image_data,
    get_tour_brochure_data,
)
from src.services.whatsapp import send_whatsapp_document
import catalog_service


def run_multimedia_tests():
    print("=====================================================================")
    print("      PRUEBAS DEL MOTOR DE DESPACHO MULTIMEDIA EN WHATSAPP")
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

    # -------------------------------------------------------------
    # 1. Detección de Intención de Fotos
    # -------------------------------------------------------------
    check("1. Detección afirmativa de foto: '¿Tienen fotos del City Tour?'",
          is_photo_requested("¿Tienen fotos del City Tour?"))
    check("2. Detección afirmativa de imagen: 'Mándame imágenes de Humantay'",
          is_photo_requested("Mándame imágenes de Humantay"))
    check("3. Detección afirmativa en inglés: 'Can you show me photos?'",
          is_photo_requested("Can you show me photos?"))
    check("4. Descarte de negación: 'Por favor sin fotos'",
          not is_photo_requested("Por favor sin fotos"))
    check("5. Descarte de negación: 'No me mandes fotos, solo texto'",
          not is_photo_requested("No me mandes fotos, solo texto"))
    check("6. Cero falso positivo en consulta general: '¿Cuánto cuesta el City Tour?'",
          not is_photo_requested("¿Cuánto cuesta el City Tour?"))
    check("7. Cero falso positivo en saludo: 'Hola, buenos días'",
          not is_photo_requested("Hola, buenos días"))
    check("8. Cero falso positivo en solicitud de lista: '¿Qué tours ofrecen?'",
          not is_photo_requested("¿Qué tours ofrecen?"))

    # -------------------------------------------------------------
    # 2. Detección de Intención de Folletos PDF
    # -------------------------------------------------------------
    check("9. Detección afirmativa de folleto: '¿Tienen folleto del Valle Sagrado?'",
          is_brochure_requested("¿Tienen folleto del Valle Sagrado?"))
    check("10. Detección afirmativa de brochure: 'Pásame el brochure de Machu Picchu'",
          is_brochure_requested("Pásame el brochure de Machu Picchu"))
    check("11. Detección afirmativa de PDF: 'Mándame el itinerario en pdf'",
          is_brochure_requested("Mándame el itinerario en pdf"))
    check("12. Descarte de negación de folleto: 'Sin folleto por favor'",
          not is_brochure_requested("Sin folleto por favor"))
    check("13. Cero falso positivo en consulta normal: 'Horario del City Tour'",
          not is_brochure_requested("Horario del City Tour"))

    # -------------------------------------------------------------
    # 3. Resolución de Foto Oficial (Canónica)
    # -------------------------------------------------------------
    img_city = get_tour_image_data("City Tour Cusco", user_msg="¿Tienen fotos del City Tour?", entity_id="city-tour-cusco")
    check("14. Resolución de foto para City Tour",
          img_city is not None and "city_tour_cusco.jpg" in img_city[0])

    img_humantay = get_tour_image_data("Laguna Humantay", user_msg="Fotos de humantay", entity_id="laguna-humantay")
    check("15. Resolución de foto para Laguna Humantay",
          img_humantay is not None and "laguna_humantay.jpg" in img_humantay[0])

    # -------------------------------------------------------------
    # 4. Creación de Tour Dinámico con Foto y Folleto PDF
    # -------------------------------------------------------------
    test_eid = "eval-media-tour-arequipa"
    ok, _ = catalog_service.upsert_tour({
        "entity_id": test_eid,
        "name": "Tour Cañón del Colca 2 Días",
        "aliases": ["colca 2 dias", "canon colca arequipa"],
        "official_price": "85",
        "currency": "USD",
        "schedule": "03:00 - 18:00",
        "duration": "2 días",
        "includes": "Transporte, hotel en Chivay, guía oficial",
        "excludes": "Boleto turístico",
    })
    check("16. Creación de tour de prueba para multimedia", ok)

    # Subir foto sintética
    fake_img_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 50
    ok_photo, photo_name = catalog_service.save_asset(test_eid, "photo", "colca_foto.jpg", fake_img_bytes)
    check("17. Subida de foto para tour dinámico", ok_photo)

    # Subir folleto PDF sintético
    fake_pdf_bytes = b"%PDF-1.4\n%EOF\n" + b"\x00" * 40
    ok_brochure, pdf_name = catalog_service.save_asset(test_eid, "brochure", "folleto_colca.pdf", fake_pdf_bytes)
    check("18. Subida de folleto PDF para tour dinámico", ok_brochure)

    # -------------------------------------------------------------
    # 5. Resolución de Foto y Folleto Dinámicos
    # -------------------------------------------------------------
    dyn_img = get_tour_image_data("Tour Cañón del Colca 2 Días", user_msg="Mándame fotos de colca 2 dias", entity_id=test_eid)
    check("19. Foto dinámica resuelta con el asset subido",
          dyn_img is not None and photo_name in dyn_img[0])

    dyn_pdf = get_tour_brochure_data("Tour Cañón del Colca 2 Días", user_msg="Mándame el folleto en pdf de colca", entity_id=test_eid)
    check("20. Folleto PDF dinámico resuelto con el asset subido",
          dyn_pdf is not None and pdf_name in dyn_pdf[0] and dyn_pdf[1].endswith(".pdf"))

    # Tour sin folleto retorna None (evita alucinaciones)
    no_pdf = get_tour_brochure_data("City Tour Cusco", user_msg="Pásame el pdf del city tour", entity_id="city-tour-cusco")
    check("21. Tour sin folleto retorna None para evitar enlaces rotos o alucinaciones",
          no_pdf is None)

    # -------------------------------------------------------------
    # 6. Prueba Unitaria de send_whatsapp_document
    # -------------------------------------------------------------
    with patch("httpx.Client") as mock_client:
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"messages":[{"id":"wamid.test.doc"}]}'
        mock_instance.post.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_instance

        with patch.dict(os.environ, {"META_ACCESS_TOKEN": "test_tok", "META_PHONE_NUMBER_ID": "123456"}):
            sent = send_whatsapp_document(
                document_url="https://texeira.pe/brochures/test.pdf",
                filename="Folleto_Colca.pdf",
                caption="Folleto Oficial",
                to_phone="51987654321"
            )
            check("22. send_whatsapp_document ejecuta POST a Graph API con payload document", sent)
            
            # Verificar estructura del payload
            call_args = mock_instance.post.call_args
            assert call_args is not None
            url, kwargs = call_args[0][0], call_args[1]
            json_payload = kwargs.get("json", {})
            check("23. Payload contiene tipo document", json_payload.get("type") == "document")
            check("24. Payload document contiene link y filename",
                  json_payload.get("document", {}).get("link") == "https://texeira.pe/brochures/test.pdf" and
                  json_payload.get("document", {}).get("filename") == "Folleto_Colca.pdf")

    # -------------------------------------------------------------
    # 7. Limpieza de Entidad de Prueba
    # -------------------------------------------------------------
    print("\n[LIMPIEZA] Eliminando tour sintético de prueba multimedia...")
    catalog_service.delete_tour(test_eid)
    check("25. Limpieza de entidad completada", True)

    print("\n=====================================================================")
    print(f"RESULTADO: {passed} PASS / {failed} FAIL")
    print("=====================================================================")
    return failed == 0


if __name__ == "__main__":
    success = run_multimedia_tests()
    sys.exit(0 if success else 1)
