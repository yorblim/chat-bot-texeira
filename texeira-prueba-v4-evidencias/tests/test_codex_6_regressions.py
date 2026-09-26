"""
test_codex_6_regressions.py — Pruebas de regresión para las 6 correcciones de Codex (commit 915e4e1)

Cubre exhaustivamente:
1. CSRF (catalog_support.py): Exigir token CSRF válido en mutaciones (POST /api/catalog/tours,
   POST /api/catalog/upload/{id}, DELETE /api/catalog/tours/{id}). Basic Auth e IP local no lo evaden.
2. Tours desactivados (verified_routes.py): Tours inactivos no reaparecen en listados, consultas directas
   ni solicitudes multimedia.
3. Horarios vigentes (src/evidence.py): Horarios actualizados se reflejan inmediatamente con origen ADMIN_VIGENTE
   sin falsos conflictos históricos y sin reiniciar el servicio.
4. Atención humana (handoff_support.py): Frases negativas no escalan; 'advisor' y variantes activan atención humana.
5. Fotos rechazadas (src/visual/visual_engine.py): Negaciones de fotos/imágenes con y sin tilde no envían imágenes,
   verificado con proveedor simulado.
6. Multimedia desactualizada (catalog_service.py): Versionado por hash e invalidación entre dos cachés independientes.
"""

import os
import sys
import io
import time
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
import app as fastapi_app
import catalog_service
import handoff_support
import verified_routes
from src import evidence
from src.visual import visual_engine

client = TestClient(fastapi_app.app)


def run_all_regressions():
    print("=====================================================================")
    print("   PRUEBAS DE REGRESIÓN: 6 CORRECCIONES CODEX (COMMIT 915e4e1)      ")
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

    # =========================================================================
    # 1. CSRF — catalog_support.py
    # =========================================================================
    print("\n--- 1. CSRF EN MUTACIONES DEL CATÁLOGO ---")
    test_csrf_eid = "eval-csrf-protection-tour"
    test_payload = {
        "entity_id": test_csrf_eid,
        "name": "Tour de Prueba CSRF",
        "aliases": ["csrf", "seguridad"],
        "official_price": "50",
        "currency": "USD",
        "schedule": "08:00 - 12:00",
        "duration": "4 horas",
        "includes": "Guía, transporte",
        "excludes": "Almuerzo"
    }

    try:
        # 1.1 Rechazo sin token CSRF en POST /api/catalog/tours
        r_no_csrf = client.post("/api/catalog/tours", json=test_payload)
        check("1.1 POST /api/catalog/tours sin token CSRF retorna 403", r_no_csrf.status_code == 403, f"Status: {r_no_csrf.status_code}")

        # 1.2 Rechazo con token CSRF incorrecto
        r_bad_csrf = client.post(
            "/api/catalog/tours",
            json=test_payload,
            headers={"X-Catalog-CSRF": "token_invalido_totalmente_falso_12345"}
        )
        check("1.2 POST /api/catalog/tours con token CSRF erróneo retorna 403", r_bad_csrf.status_code == 403, f"Status: {r_bad_csrf.status_code}")

        # 1.3 Basic Auth NO se salta la validación CSRF
        r_auth_no_csrf = client.post(
            "/api/catalog/tours",
            json=test_payload,
            headers={"Authorization": "Basic YWRtaW46c2VjcmV0"}
        )
        check("1.3 Basic Auth sin token CSRF no se salta validación (403)", r_auth_no_csrf.status_code == 403, f"Status: {r_auth_no_csrf.status_code}")

        # 1.4 IP local / TestClient NO se salta la validación CSRF
        check("1.4 Cliente local sin token CSRF es rechazado", r_no_csrf.status_code == 403)

        # 1.5 Subida de archivo sin CSRF retorna 403
        fake_img = io.BytesIO(b"\xff\xd8\xff\xe0test_bytes")
        r_upload_no_csrf = client.post(
            f"/api/catalog/upload/{test_csrf_eid}",
            files={"file": ("test.jpg", fake_img, "image/jpeg")},
            data={"asset_type": "photo"}
        )
        check("1.5 POST /api/catalog/upload sin token CSRF retorna 403", r_upload_no_csrf.status_code == 403, f"Status: {r_upload_no_csrf.status_code}")

        # 1.6 Eliminación sin CSRF retorna 403
        r_del_no_csrf = client.delete(f"/api/catalog/tours/{test_csrf_eid}")
        check("1.6 DELETE /api/catalog/tours sin token CSRF retorna 403", r_del_no_csrf.status_code == 403, f"Status: {r_del_no_csrf.status_code}")

        # 1.7 Obtener token CSRF legítimo y verificar mutación exitosa (200 OK)
        r_token = client.get("/api/catalog/csrf-token")
        check("1.7 Endpoint GET /api/catalog/csrf-token responde 200", r_token.status_code == 200)
        valid_csrf = r_token.json().get("csrf_token", "")
        check("1.8 Token CSRF obtenido es válido y no vacío", len(valid_csrf) > 10)

        r_create_ok = client.post(
            "/api/catalog/tours",
            json=test_payload,
            headers={"X-Catalog-CSRF": valid_csrf}
        )
        check("1.9 POST /api/catalog/tours con token CSRF válido responde 200 OK", r_create_ok.status_code == 200 and r_create_ok.json().get("ok"))

        r_del_ok = client.delete(
            f"/api/catalog/tours/{test_csrf_eid}",
            headers={"X-Catalog-CSRF": valid_csrf}
        )
        check("1.10 DELETE /api/catalog/tours con token CSRF válido responde 200 OK", r_del_ok.status_code == 200 and r_del_ok.json().get("ok"))

        # 1.11 Validación con credenciales Basic Auth configuradas
        old_u = os.environ.get('ADMIN_USER')
        old_p = os.environ.get('ADMIN_PASSWORD')
        try:
            os.environ['ADMIN_USER'] = 'admin_test'
            os.environ['ADMIN_PASSWORD'] = 'secret_test_456'
            import base64
            auth_header = "Basic " + base64.b64encode(b"admin_test:secret_test_456").decode()
            bad_auth_header = "Basic " + base64.b64encode(b"admin_test:wrong").decode()

            # Sin Basic Auth -> 401
            r_no_auth = client.post("/api/catalog/tours", json=test_payload, headers={"X-Catalog-CSRF": valid_csrf})
            check("1.11 POST sin Basic Auth cuando está configurado retorna 401", r_no_auth.status_code == 401)

            # Con Basic Auth erróneo -> 401
            r_bad_auth = client.post("/api/catalog/tours", json=test_payload, headers={"Authorization": bad_auth_header, "X-Catalog-CSRF": valid_csrf})
            check("1.12 POST con Basic Auth erróneo retorna 401", r_bad_auth.status_code == 401)

            # Con Basic Auth válido pero sin CSRF -> 403 (Basic Auth no bypassa CSRF)
            r_auth_no_csrf_req = client.post("/api/catalog/tours", json=test_payload, headers={"Authorization": auth_header})
            check("1.13 POST con Basic Auth válido pero sin CSRF retorna 403", r_auth_no_csrf_req.status_code == 403)

            # Con Basic Auth válido + CSRF erróneo -> 403
            r_auth_bad_csrf_req = client.post("/api/catalog/tours", json=test_payload, headers={"Authorization": auth_header, "X-Catalog-CSRF": "token_falso"})
            check("1.14 POST con Basic Auth válido + CSRF falso retorna 403", r_auth_bad_csrf_req.status_code == 403)

            # Con ambos válidos -> 200 OK
            r_auth_csrf_ok = client.post("/api/catalog/tours", json=test_payload, headers={"Authorization": auth_header, "X-Catalog-CSRF": valid_csrf})
            check("1.15 POST con Basic Auth válido y CSRF válido responde 200 OK", r_auth_csrf_ok.status_code == 200 and r_auth_csrf_ok.json().get("ok"))

            # DELETE con Basic Auth y CSRF -> 200 OK
            r_del_both_ok = client.delete(f"/api/catalog/tours/{test_csrf_eid}", headers={"Authorization": auth_header, "X-Catalog-CSRF": valid_csrf})
            check("1.16 DELETE con Basic Auth válido y CSRF válido responde 200 OK", r_del_both_ok.status_code == 200 and r_del_both_ok.json().get("ok"))

            # GET /api/catalog/csrf-token sin Basic Auth -> 401
            r_token_unauth = client.get("/api/catalog/csrf-token")
            check("1.17 GET /api/catalog/csrf-token sin Basic Auth retorna 401", r_token_unauth.status_code == 401)

            # GET /api/catalog/csrf-token con Basic Auth -> 200 OK
            r_token_auth = client.get("/api/catalog/csrf-token", headers={"Authorization": auth_header})
            check("1.18 GET /api/catalog/csrf-token con Basic Auth responde 200 OK", r_token_auth.status_code == 200 and r_token_auth.json().get("ok"))
        finally:
            if old_u is not None: os.environ['ADMIN_USER'] = old_u
            else: os.environ.pop('ADMIN_USER', None)
            if old_p is not None: os.environ['ADMIN_PASSWORD'] = old_p
            else: os.environ.pop('ADMIN_PASSWORD', None)

    finally:
        try:
            catalog_service.delete_tour(test_csrf_eid)
        except Exception:
            pass

    # =========================================================================
    # 2. TOURS DESACTIVADOS — verified_routes.py
    # =========================================================================
    print("\n--- 2. TOURS DESACTIVADOS ---")
    test_deact_eid = "city-tour-cusco"
    # Guardamos copia del estado original
    orig_tour = catalog_service.get_tour_by_id(test_deact_eid)

    try:
        # Desactivamos City Tour Cusco (is_active = 0)
        deact_payload = dict(orig_tour) if orig_tour else {"entity_id": test_deact_eid, "name": "City Tour Cusco"}
        deact_payload["is_active"] = 0
        catalog_service.save_tour(deact_payload)

        # 2.1 get_all_tours(active_only=True) no debe incluir el tour desactivado
        active_tours = catalog_service.get_all_tours(active_only=True)
        active_ids = {t["entity_id"] for t in active_tours}
        check("2.1 Tour desactivado no aparece en get_all_tours(active_only=True)", test_deact_eid not in active_ids)

        # 2.2 Endpoint GET /api/catalog/tours no debe listar el tour desactivado
        r_api_list = client.get("/api/catalog/tours")
        api_tours_ids = {t["entity_id"] for t in r_api_list.json()}
        check("2.2 Tour desactivado no aparece en GET /api/catalog/tours", test_deact_eid not in api_tours_ids)

        # 2.3 Listado conversacional no debe ofrecer el tour desactivado
        catalog_resp = fastapi_app.rag_chain("¿Qué tours tienen?")["response"]
        check("2.3 Tour desactivado no aparece en el listado conversacional del bot", "City Tour Cusco" not in catalog_resp)

        # 2.4 Consulta directa por precio no debe confirmar el tour como activo
        query_price = fastapi_app.rag_chain("¿Cuánto cuesta el City Tour Cusco?")
        check("2.4 Consulta de precio para tour desactivado enruta a evidence_inactive_tour", query_price.get("route") == "evidence_inactive_tour" or query_price.get("response_route") == "evidence_inactive_tour")
        check("2.5 Respuesta informa no disponibilidad y ofrece asesor", "no se encuentra disponible" in query_price.get("response", "") and "asesor" in query_price.get("response", ""))
        check("2.6 Respuesta no confirma precio oficial activo", "oficial de" not in query_price.get("response", "") and "$" not in query_price.get("response", ""))

        # 2.7 Consulta directa por horario de tour desactivado
        query_sched = fastapi_app.rag_chain("¿Cuál es el horario del City Tour Cusco?")
        check("2.7 Consulta de horario para tour desactivado enruta a evidence_inactive_tour", query_sched.get("route") == "evidence_inactive_tour" or query_sched.get("response_route") == "evidence_inactive_tour")

        # 2.8 Solicitud de fotos para tour desactivado no debe resolver asset multimedia
        img_data = visual_engine.get_tour_image_data("fotos del city tour", user_msg="fotos del city tour", entity_id=test_deact_eid)
        check("2.8 get_tour_image_data retorna None para tour desactivado", img_data is None)

        # 2.9 Solicitud de folleto para tour desactivado no debe resolver PDF
        doc_data = visual_engine.get_tour_brochure_data("brochure city tour", user_msg="brochure city tour", entity_id=test_deact_eid)
        check("2.9 get_tour_brochure_data retorna None para tour desactivado", doc_data is None)

        # 2.10 facts de tour desactivado no se ofrecen como confirmados
        facts = evidence.get_facts(test_deact_eid)
        check("2.10 evidence.get_facts retorna lista vacía para tour desactivado", len(facts) == 0)
        check("2.11 is_product_confirmed es False para tour desactivado", not evidence.is_product_confirmed(test_deact_eid))

    finally:
        # Restaurar tour a activo
        if orig_tour:
            orig_tour["is_active"] = 1
            catalog_service.save_tour(orig_tour)
        else:
            catalog_service.save_tour({"entity_id": test_deact_eid, "name": "City Tour Cusco", "is_active": 1})

    # =========================================================================
    # 3. HORARIOS VIGENTES — src/evidence.py
    # =========================================================================
    print("\n--- 3. HORARIOS VIGENTES ACTUALIZADOS ---")
    test_sched_eid = "city-tour-cusco"
    orig_tour_sched = catalog_service.get_tour_by_id(test_sched_eid)
    orig_schedule = orig_tour_sched.get("schedule", "13:00 - 18:30 hrs") if orig_tour_sched else "13:00 - 18:30 hrs"

    try:
        # 3.1 Actualizar horario en caliente sin reiniciar el servidor
        new_schedule = "08:30 - 12:30 hrs (Turno Mañana Especial)"
        update_payload = dict(orig_tour_sched) if orig_tour_sched else {"entity_id": test_sched_eid, "name": "City Tour Cusco"}
        update_payload["schedule"] = new_schedule
        update_payload["is_active"] = 1
        catalog_service.save_tour(update_payload)

        # 3.2 Verificar reflejo inmediato en facts
        facts = evidence.get_facts(test_sched_eid)
        sched_facts = [f for f in facts if f.field == "schedule"]
        check("3.1 get_facts contiene exactamente 1 hecho de horario", len(sched_facts) == 1)
        if sched_facts:
            check("3.2 Horario actualizado coincide con el valor nuevo", sched_facts[0].value == new_schedule)
            check("3.3 Trazabilidad de origen es ADMIN_VIGENTE", sched_facts[0].source_id == "ADMIN_VIGENTE")

        # 3.3 No presentar datos históricos como vigentes ni generar falsos conflictos
        sched_conflicts = evidence.detect_conflicts(test_sched_eid, field="schedule")
        check("3.4 detect_conflicts no genera falso conflicto sobre horario ADMIN_VIGENTE", len(sched_conflicts) == 0)

        # 3.4 Respuesta conversacional refleja el horario vigente actualizado
        query_res = fastapi_app.rag_chain("¿Cuál es el horario del City Tour Cusco?")
        check("3.5 Consulta de horario enruta a evidence_schedule", query_res.get("route") == "evidence_schedule" or query_res.get("response_route") == "evidence_schedule")
        check("3.6 Respuesta contiene el horario nuevo actualizado", "08:30 - 12:30" in query_res.get("response", ""))
        check("3.7 Respuesta NO contiene el horario histórico antiguo", "18:30" not in query_res.get("response", ""))

    finally:
        # Restaurar horario original
        if orig_tour_sched:
            orig_tour_sched["schedule"] = orig_schedule
            catalog_service.save_tour(orig_tour_sched)

    # =========================================================================
    # 4. ATENCIÓN HUMANA — handoff_support.py
    # =========================================================================
    print("\n--- 4. ATENCIÓN HUMANA (HANDOFF) ---")
    # 4.1 Pruebas negativas en español (NO deben escalar)
    neg_es = [
        "No quiero hablar con un asesor",
        "No deseo un asesor",
        "No me comuniquen con un asesor",
        "Por favor no me llame un asesor",
        "No contactar con asesor",
        "no quiero asesor",
        "Sin asesor por favor",
    ]
    for phrase in neg_es:
        check(f"4.1 Negativo ES: '{phrase}' no escala", not handoff_support.requested(phrase))

    # 4.2 Pruebas negativas en inglés (NO deben escalar)
    neg_en = [
        "I do not want to speak to an advisor",
        "I don't want an advisor",
        "Do not transfer me to an advisor",
        "No advisor please",
        "Don't call me",
        "No agent please",
        "without advisor",
    ]
    for phrase in neg_en:
        check(f"4.2 Negativo EN: '{phrase}' no escala", not handoff_support.requested(phrase))

    # 4.3 Pruebas positivas en español (SÍ deben escalar)
    pos_es = [
        "asesor",
        "asesores",
        "quiero hablar con un asesor",
        "comunícame con un asesor",
        "deseo contactar a un asesor",
        "ayuda humana",
        "atención de una persona",
    ]
    for phrase in pos_es:
        check(f"4.3 Positivo ES: '{phrase}' sí escala", handoff_support.requested(phrase))

    # 4.4 Pruebas positivas en inglés (SÍ deben escalar)
    pos_en = [
        "advisor",
        "advisors",
        "agent",
        "agents",
        "human advisor",
        "human agent",
        "I want to speak to an advisor",
        "speak to an agent",
        "talk to a person",
    ]
    for phrase in pos_en:
        check(f"4.4 Positivo EN: '{phrase}' sí escala", handoff_support.requested(phrase))

    # 4.5 Prueba de flujo a través de /test-chat
    r_test_neg = client.post("/test-chat", json={"user_id": "user-neg-test", "message": "No quiero hablar con un asesor"})
    check("4.5 /test-chat con rechazo de asesor no genera handoff", r_test_neg.status_code == 200 and not r_test_neg.json().get("escalated_to_human"))

    r_test_pos = client.post("/test-chat", json={"user_id": "user-pos-test", "message": "advisor"})
    check("4.5 /test-chat con 'advisor' genera handoff correctamente", r_test_pos.status_code == 200 and r_test_pos.json().get("escalated_to_human"))

    # =========================================================================
    # 5. FOTOS RECHAZADAS — src/visual/visual_engine.py
    # =========================================================================
    print("\n--- 5. FOTOS RECHAZADAS Y DESPACHO SIMULADO ---")
    # 5.1 Detección con negaciones y variantes de acentos
    photo_negatives = [
        "No quiero fotografías",
        "No quiero imágenes",
        "Por favor sin fotos",
        "Don't send pictures",
        "I do not want photos",
        "No photos please",
        "No quiero fotografías del City Tour",
        "No quiero images del City Tour",
        "no quiero fotografias del city tour",
        "no quiero imagenes del city tour",
        "Sin imágenes del tour",
        "Don't send pictures of City Tour",
        "without pictures",
    ]
    for phrase in photo_negatives:
        check(f"5.1 Detección negativa: '{phrase}' es False", not visual_engine.is_photo_requested(phrase))

    # 5.2 Detección afirmativa
    photo_positives = [
        "Quiero fotografías",
        "Mándame fotos",
        "Can you show me pictures?",
        "Send me photographs please",
        "Quiero fotografías del City Tour",
        "Quiero images del City Tour",
        "Mándame fotos de Machu Picchu",
    ]
    for phrase in photo_positives:
        check(f"5.2 Detección afirmativa: '{phrase}' es True", visual_engine.is_photo_requested(phrase))

    # 5.3 Simulación de despacho WhatsApp (verificar que no se llama send_whatsapp_image)
    with patch("app.send_whatsapp_image") as mock_send_image, \
         patch("app.send_whatsapp_message", return_value=True) as mock_send_text:

        # Simular flujo de procesamiento de mensaje WhatsApp para "No quiero fotografías del City Tour"
        from app import rag_chain, detect_language, format_whatsapp_text

        msg_rejected = "No quiero fotografías del City Tour"
        rag_res = rag_chain(msg_rejected, user_id="wa-test-5-1")
        route = rag_res.get("response_route") or rag_res.get("route") or ""
        detected_eid = rag_res.get("entity_id") or ""

        # Lógica exacta de despacho multimedia de app.py
        if visual_engine.is_photo_requested(msg_rejected) and route not in {'social', 'help', 'evidence_unknown', 'evidence_conflict', 'evidence_contact', 'evidence_listing', 'evidence_inactive_tour'}:
            img_info = visual_engine.get_tour_image_data(msg_rejected + " " + rag_res["response"], user_msg=msg_rejected, entity_id=detected_eid)
            if img_info:
                mock_send_image(image_url=img_info[0], caption=img_info[1])

        check("5.3 Despacho simulado: send_whatsapp_image NO fue llamado para fotos rechazadas", not mock_send_image.called)

        # Verificación positiva: para "Quiero fotos del City Tour", sí debe llamarse
        msg_accepted = "Quiero fotos del City Tour"
        rag_res_pos = rag_chain(msg_accepted, user_id="wa-test-5-2")
        route_pos = rag_res_pos.get("response_route") or rag_res_pos.get("route") or ""
        detected_eid_pos = rag_res_pos.get("entity_id") or ""

        if visual_engine.is_photo_requested(msg_accepted) and route_pos not in {'social', 'help', 'evidence_unknown', 'evidence_conflict', 'evidence_contact', 'evidence_listing', 'evidence_inactive_tour'}:
            img_info = visual_engine.get_tour_image_data(msg_accepted + " " + rag_res_pos["response"], user_msg=msg_accepted, entity_id=detected_eid_pos)
            if img_info:
                mock_send_image(image_url=img_info[0], caption=img_info[1])

        check("5.4 Despacho simulado: send_whatsapp_image SÍ fue llamado para solicitud afirmativa", mock_send_image.called)

    # =========================================================================
    # 6. MULTIMEDIA DESACTUALIZADA — catalog_service.py
    # =========================================================================
    print("\n--- 6. MULTIMEDIA DESACTUALIZADA ENTRE DOS CACHÉS INDEPENDIENTES ---")
    test_multi_eid = "eval-cache-sync-tour"
    v1_bytes = b"PHOTO_V1_INITIAL_RESOLUTION_DATA_BYTES"
    v2_bytes = b"PHOTO_V2_UPDATED_HIGH_RES_DATA_BYTES_NEW_VERSION"

    temp_cache_dir_A = tempfile.mkdtemp(prefix="cache_inst_A_")
    temp_cache_dir_B = tempfile.mkdtemp(prefix="cache_inst_B_")

    orig_images_dir = catalog_service.IMAGES_DIR

    try:
        # Crear tour para la prueba
        catalog_service.save_tour({
            "entity_id": test_multi_eid,
            "name": "Tour de Prueba Caché Multi-instancia",
            "aliases": ["sync-test"],
            "is_active": 1
        })

        # --- INSTANCIA A: Sube Versión 1 de la Foto ---
        catalog_service.IMAGES_DIR = Path(temp_cache_dir_A)
        catalog_service.invalidate_catalog_cache()

        ok_v1, filename_v1 = catalog_service.save_tour_asset(
            entity_id=test_multi_eid,
            asset_type="photo",
            filename="foto_tour.jpg",
            content_bytes=v1_bytes
        )
        check("6.1 Instancia A sube Foto V1 exitosamente con nombre versionado", ok_v1 and filename_v1.startswith(f"{test_multi_eid}_photo_"))
        file_path_A = Path(temp_cache_dir_A) / filename_v1
        check("6.2 Foto V1 guardada en disco de Instancia A", file_path_A.exists() and file_path_A.read_bytes() == v1_bytes)

        # --- INSTANCIA B: Descarga y sirve Foto V1 desde la BD ---
        catalog_service.IMAGES_DIR = Path(temp_cache_dir_B)
        catalog_service.invalidate_catalog_cache()

        # Instancia B no tiene el archivo en su disco local aún
        file_path_B_v1 = Path(temp_cache_dir_B) / filename_v1
        check("6.3 Instancia B inicialmente no tiene el archivo en disco local", not file_path_B_v1.exists())

        # Instancia B recupera el asset
        retrieved_v1 = catalog_service.get_asset_bytes(filename_v1, "photo")
        check("6.4 Instancia B recupera bytes de Foto V1 sincronizados desde la BD", retrieved_v1 is not None and retrieved_v1[0] == v1_bytes)
        check("6.5 Instancia B guardó en su disco local la copia V1", file_path_B_v1.exists() and file_path_B_v1.read_bytes() == v1_bytes)

        # Pausa breve para garantizar que timestamp de DB avance
        time.sleep(0.05)

        # --- INSTANCIA A: Actualiza a Versión 2 de la Foto ---
        catalog_service.IMAGES_DIR = Path(temp_cache_dir_A)
        catalog_service.invalidate_catalog_cache()

        ok_v2, filename_v2 = catalog_service.save_tour_asset(
            entity_id=test_multi_eid,
            asset_type="photo",
            filename="foto_tour.jpg",
            content_bytes=v2_bytes
        )
        check("6.6 Instancia A actualiza a Foto V2 con nuevo hash inmutable", ok_v2 and filename_v2 != filename_v1)

        # --- INSTANCIA B: Consulta de nuevo ---
        catalog_service.IMAGES_DIR = Path(temp_cache_dir_B)
        # La instancia B debe detectar que el tour ahora referencia filename_v2
        tour_on_B = catalog_service.get_tour(test_multi_eid)
        check("6.7 Instancia B detecta automáticamente filename_v2 tras invalidación verificable", tour_on_B.get("photo_filename") == filename_v2)

        # Instancia B recupera los bytes del nuevo asset
        retrieved_v2 = catalog_service.get_asset_bytes(filename_v2, "photo")
        check("6.8 Instancia B recupera bytes de Foto V2 (no la copia local antigua V1)", retrieved_v2 is not None and retrieved_v2[0] == v2_bytes)
        file_path_B_v2 = Path(temp_cache_dir_B) / filename_v2
        check("6.9 Instancia B tiene en disco local la versión V2 actualizada", file_path_B_v2.exists() and file_path_B_v2.read_bytes() == v2_bytes)

    finally:
        catalog_service.IMAGES_DIR = orig_images_dir
        catalog_service.delete_tour(test_multi_eid)
        shutil.rmtree(temp_cache_dir_A, ignore_errors=True)
        shutil.rmtree(temp_cache_dir_B, ignore_errors=True)

    print("\n=====================================================================")
    print(f"RESULTADO FINAL: {passed} PASS / {failed} FAIL")
    print("=====================================================================")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_all_regressions()
