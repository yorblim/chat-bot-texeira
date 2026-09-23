"""
tests/test_multimedia_and_prices_integration.py
Validación integral de visualización de fotos, folletos PDF y tarifas en el bot.
"""
import sys
import os
import json
import asyncio
from pathlib import Path

# Configurar entorno
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

os.environ['TEXEIRA_ENABLE_WHATSAPP'] = 'false'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

import app
import catalog_service

PASSED = 0
FAILED = 0

def check(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS | {name}")
    else:
        FAILED += 1
        print(f"  FAIL | {name} -> {detail}")

async def run_tests():
    global PASSED, FAILED
    print("=" * 65)
    print("  VERIFICACIÓN: FOTOS, FOLLETOS Y PRECIOS DINÁMICOS EN EL BOT")
    print("=" * 65)

    # -------------------------------------------------------------
    # 1. CONSULTA DE FOTOS PARA TOUR CANÓNICO (City Tour Cusco)
    # -------------------------------------------------------------
    r_foto = app.rag_chain("¿Tienen fotos del City Tour?", "user_test_photo")
    check("1. Route evidence_photo detectada", r_foto.get("route") == "evidence_photo")
    check("2. Entity city-tour-cusco identificada", r_foto.get("entity_id") == "city-tour-cusco")
    check("3. Mensaje cordial de foto", "imagen" in r_foto.get("response", "").lower() or "foto" in r_foto.get("response", "").lower())

    # Probar endpoint test_chat para UI web (debe incluir markdown de imagen)
    chat_req = app.TestChatRequest(user_id="user_test_photo_web", message="¿Tienen fotos del City Tour?")
    resp_raw = await app.test_chat(chat_req)
    resp_data = json.loads(resp_raw.body)
    check("4. test_chat incluye markdown de imagen ![...](...)", "![" in resp_data.get("response", "") and "/images/" in resp_data.get("response", ""))

    # -------------------------------------------------------------
    # 2. CONSULTA DE FOLLETOS PARA TOUR SIN FOLLETO
    # -------------------------------------------------------------
    r_nofolleto = app.rag_chain("¿Tienen folleto del City Tour?", "user_test_nofolleto")
    check("5. Route evidence_brochure para folleto", r_nofolleto.get("route") == "evidence_brochure")
    check("6. Aviso transparente cuando no hay PDF en línea", "no cuenta con folleto en pdf" in r_nofolleto.get("response", "").lower())

    # -------------------------------------------------------------
    # 3. PRECIO: SIN TARIFA (Machu Picchu) vs CON TARIFA VIGENTE
    # -------------------------------------------------------------
    r_mp_price = app.rag_chain("¿Cuánto cuesta Machu Picchu en tren?", "user_test_mp_price")
    check("7. Tour sin tarifa configurada requiere confirmación", "asesor" in r_mp_price.get("response", "").lower() or "agencia" in r_mp_price.get("response", "").lower() or "confirmamos" in r_mp_price.get("response", "").lower())
    check("8. Route evidence_unknown para tour sin tarifa", r_mp_price.get("route") == "evidence_unknown")

    # Configurar tarifa de prueba para City Tour (40 USD)
    t_city_orig = catalog_service.get_tour_by_id("city-tour-cusco")
    catalog_service.upsert_tour({**t_city_orig, "official_price": "40", "currency": "USD"})
    r_city_price = app.rag_chain("¿Cuánto cuesta el City Tour?", "user_test_city_price")
    check("9. Tour con tarifa configurada responde con precio oficial", "40 USD" in r_city_price.get("response", "") or "40 usd" in r_city_price.get("response", "").lower())
    check("10. Route evidence_confirmed_price", r_city_price.get("route") == "evidence_confirmed_price")

    # Restaurar City Tour sin precio
    catalog_service.upsert_tour({**t_city_orig, "official_price": "", "currency": "USD"})

    # -------------------------------------------------------------
    # 4. CREACIÓN DE TOUR DINÁMICO COMPLETO (Foto + Folleto + Precio)
    # -------------------------------------------------------------
    test_eid = "tour-test-completo"
    tour_created, _ = catalog_service.upsert_tour({
        "entity_id": test_eid,
        "name": "Tour Ruta Mágica Andina",
        "aliases": ["ruta magica", "ruta andina", "magica andina"],
        "official_price": "55",
        "currency": "USD",
        "schedule": "08:00 - 16:00",
        "duration": "1 día"
    })
    check("11. Tour dinámico creado exitosamente", tour_created)

    # Subir foto sintética
    fake_img = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00" + b"\x00" * 30
    ok_p, photo_fn = catalog_service.save_asset(test_eid, "photo", "magica_foto.jpg", fake_img)
    check("12. Foto guardada para tour dinámico", ok_p)

    # Subir folleto PDF sintético
    fake_pdf = b"%PDF-1.4\n%EOF\n" + b"\x00" * 30
    ok_b, brochure_fn = catalog_service.save_asset(test_eid, "brochure", "folleto_magico.pdf", fake_pdf)
    check("13. Folleto guardado para tour dinámico", ok_b)

    # Consultar precio del tour dinámico recién creado
    r_dyn_price = app.rag_chain("¿Cuánto cuesta el Tour Ruta Mágica Andina?", "user_test_dyn")
    check("14. Bot responde precio del tour dinámico (55 USD)", "55 USD" in r_dyn_price.get("response", "") or "55 usd" in r_dyn_price.get("response", "").lower())

    # Consultar fotos del tour dinámico
    r_dyn_foto = app.rag_chain("¿Tienen fotos de la Ruta Mágica?", "user_test_dyn")
    check("15. Bot confirma fotos del tour dinámico", r_dyn_foto.get("route") == "evidence_photo")

    # Verificar que test_chat sirve el link de la foto
    chat_dyn = await app.test_chat(app.TestChatRequest(user_id="user_test_dyn_web", message="Mándame fotos de la Ruta Mágica"))
    data_dyn = json.loads(chat_dyn.body)
    check("16. test_chat incluye URL de la foto subida", photo_fn in data_dyn.get("response", ""))

    # Consultar folleto del tour dinámico
    r_dyn_doc = app.rag_chain("Pásame el folleto en PDF de la Ruta Mágica", "user_test_dyn")
    check("17. Bot confirma folleto PDF del tour dinámico", r_dyn_doc.get("route") == "evidence_brochure")

    # Verificar que test_chat sirve el link descargable del PDF
    chat_pdf = await app.test_chat(app.TestChatRequest(user_id="user_test_dyn_pdf", message="Mándame el folleto en pdf de la ruta magica"))
    data_pdf = json.loads(chat_pdf.body)
    check("18. test_chat incluye link de descarga [PDF: Descargar Folleto PDF...]", brochure_fn in data_pdf.get("response", "") and "Descargar Folleto PDF" in data_pdf.get("response", ""))

    # -------------------------------------------------------------
    # 5. LIMPIEZA
    # -------------------------------------------------------------
    print("\n[LIMPIEZA] Eliminando tour sintético de prueba...")
    catalog_service.delete_tour(test_eid)
    check("19. Limpieza de entidad de prueba completada", catalog_service.get_tour_by_id(test_eid) is None)

    print("=" * 65)
    print(f"RESULTADO: {PASSED} PASS / {FAILED} FAIL / {PASSED+FAILED} TOTAL")
    print("=" * 65)
    return FAILED == 0

if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
