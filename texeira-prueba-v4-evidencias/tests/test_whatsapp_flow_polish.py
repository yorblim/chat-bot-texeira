"""tests/test_whatsapp_flow_polish.py — Validación integral del flujo de WhatsApp de Texeira Travel.

Comprueba los 10 recorridos obligatorios exigidos por la especificación:
1. Saludo → catálogo → categoría → tour → detalles → tarifa.
2. Tour A → tour B → botón antiguo de A (preservación de entidad).
3. Desactivar un tour después de mostrar sus botones → pulsar un botón antiguo (sin bucles ni botones comerciales).
4. Tour desactivado → elegir otra opción → continuar normalmente.
5. Alta de tour activo y modificación de sus datos → consulta del dato actualizado (catálogo dinámico).
6. Foto disponible, inexistente y envío fallido (multimedia coherente).
7. Solicitud al asesor → repetición sin duplicar ticket → continuación normal de la conversación.
8. Catálogo vacío y error de lectura BD como situaciones distintas (sin falsas atribuciones).
9. Mensajes libres, preguntas de seguimiento ("¿y el precio?") y referencias ambiguas ("el otro").
10. Recorridos equivalentes en español e inglés.
"""
import os
import sys
import json
import sqlite3
import unittest
from unittest.mock import patch, MagicMock

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import app
import catalog_service
import handoff_support
import database
from starlette.testclient import TestClient


class TestWhatsAppFlowPolish(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["META_ACCESS_TOKEN"] = "EAABtest_token_valid_12345"
        os.environ["META_PHONE_NUMBER_ID"] = "109876543210"
        database.init_db(app.SQLITE_DB_PATH)
        try:
            catalog_service.init_catalog_db()
            catalog_service.upsert_tour({
                "entity_id": "camino-inka",
                "name": "Camino Inca Clásico 4D/3N",
                "official_price": "790",
                "currency": "USD",
                "schedule": "",
                "duration": "4 días / 3 noches",
                "includes": "",
                "excludes": "",
                "is_active": True
            })
            catalog_service.upsert_tour({
                "entity_id": "choquequirao",
                "name": "Choquequirao Trek",
                "is_active": True
            })
        except Exception:
            pass

    def setUp(self):
        self.client = TestClient(app.app)
        self.test_uid = "51999888777"
        app.clear_history(self.test_uid)
        with handoff_support.connection() as conn:
            conn.execute("DELETE FROM requests WHERE user_id=?", (self.test_uid,))
            conn.commit()

    def _send_wa_message(self, text: str, user_id: str = None) -> dict:
        uid = user_id or self.test_uid
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"phone_number_id": "109876543210"},
                        "contacts": [{"wa_id": uid}],
                        "messages": [{
                            "from": uid,
                            "id": f"wamid.test_{os.urandom(4).hex()}",
                            "timestamp": "1727415000",
                            "type": "text",
                            "text": {"body": text}
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }
        with patch.object(app, "META_APP_SECRET", "test_meta_secret_123"), \
             patch("hmac.compare_digest", return_value=True), \
             patch.object(app, "send_whatsapp_message", return_value=True) as mock_msg, \
             patch.object(app, "send_whatsapp_image", return_value=True) as mock_img:
            resp = self.client.post("/webhook", json=payload)
            sent_text = mock_msg.call_args[1]["text"] if mock_msg.called else ""
            sent_buttons = mock_msg.call_args[1].get("buttons", []) if mock_msg.called else []
            return {
                "status_code": resp.status_code,
                "sent_text": sent_text,
                "sent_buttons": sent_buttons,
                "mock_msg": mock_msg,
                "mock_img": mock_img,
            }

    def _send_wa_button_reply(self, button_id: str, button_title: str, user_id: str = None) -> dict:
        uid = user_id or self.test_uid
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"phone_number_id": "109876543210"},
                        "contacts": [{"wa_id": uid}],
                        "messages": [{
                            "from": uid,
                            "id": f"wamid.btn_{os.urandom(4).hex()}",
                            "timestamp": "1727415000",
                            "type": "interactive",
                            "interactive": {
                                "type": "button_reply",
                                "button_reply": {
                                    "id": button_id,
                                    "title": button_title
                                }
                            }
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }
        with patch.object(app, "META_APP_SECRET", "test_meta_secret_123"), \
             patch("hmac.compare_digest", return_value=True), \
             patch.object(app, "send_whatsapp_message", return_value=True) as mock_msg, \
             patch.object(app, "send_whatsapp_image", return_value=True) as mock_img:
            resp = self.client.post("/webhook", json=payload)
            sent_text = mock_msg.call_args[1]["text"] if mock_msg.called else ""
            sent_buttons = mock_msg.call_args[1].get("buttons", []) if mock_msg.called else []
            return {
                "status_code": resp.status_code,
                "sent_text": sent_text,
                "sent_buttons": sent_buttons,
                "mock_msg": mock_msg,
                "mock_img": mock_img,
            }

    # =========================================================================
    # RECORRIDO 1: Saludo → catálogo → categoría → tour → detalles → tarifa
    # =========================================================================
    def test_journey_1_greeting_to_rates(self):
        # Asegurar estado canónico sin horario registrado para Camino Inca
        catalog_service.upsert_tour(dict(
            entity_id="camino-inka",
            name="Camino Inca Clásico 4D/3N",
            official_price="790",
            currency="USD",
            schedule="",
            duration="4 días / 3 noches",
            is_active=True
        ))

        # 1. Saludo
        res1 = self._send_wa_message("Hola")
        self.assertEqual(res1["status_code"], 200)
        self.assertIn("Soy el asistente virtual de Texeira Travel", res1["sent_text"])
        btn_ids_1 = [b["id"] for b in res1["sent_buttons"]]
        self.assertTrue(any("btn_tours:es" in bid for bid in btn_ids_1))

        # 2. Categorías (Pulsar "Ver Tours")
        res2 = self._send_wa_button_reply("btn_tours:es", "🗺️ Ver Tours")
        self.assertEqual(res2["status_code"], 200)
        self.assertIn("Catálogo de Experiencias", res2["sent_text"])
        btn_ids_2 = [b["id"] for b in res2["sent_buttons"]]
        self.assertTrue(any("btn_cat:treks:es" in bid for bid in btn_ids_2))
        self.assertTrue(any("btn_cat:cusco:es" in bid for bid in btn_ids_2))

        # 3. Tours de categoría (Pulsar categoría "treks")
        res3 = self._send_wa_button_reply("btn_cat:treks:es", "🏔️ Machu Picchu")
        self.assertEqual(res3["status_code"], 200)
        self.assertIn("Machu Picchu", res3["sent_text"])
        btn_ids_3 = [b["id"] for b in res3["sent_buttons"]]
        # Debe incluir botones para tours y salida/paginación
        self.assertTrue(any("btn_tour:machu-picchu-tren:es" in bid or "btn_tour:camino-inka:es" in bid for bid in btn_ids_3))
        self.assertTrue(any(bid.startswith("btn_cat_page:") or bid.startswith("btn_cats:") for bid in btn_ids_3))

        # 4. Ficha de tour: Caso SIN horario registrado (Camino Inca Clásico canónico)
        res4 = self._send_wa_button_reply("btn_tour:camino-inka:es", "Camino Inca")
        self.assertEqual(res4["status_code"], 200)
        text4 = res4["sent_text"]
        self.assertIn("Camino Inca", text4)
        self.assertIn("Duración", text4)
        self.assertIn("Tarifa oficial", text4)
        # Honestidad estricta de fuentes: Camino Inca tiene schedule_status unknown, no debe alucinar horario
        self.assertNotIn("Horario", text4)
        # Cero cortes con puntos suspensivos en el cuerpo
        self.assertNotIn("...", text4)
        self.assertNotIn("…", text4)
        btn_ids_4 = [b["id"] for b in res4["sent_buttons"]]
        btn_titles_4 = [b["title"] for b in res4["sent_buttons"]]
        self.assertTrue(any("btn_inc:camino-inka:es" in bid for bid in btn_ids_4))
        self.assertTrue(any("btn_photo:camino-inka:es" in bid for bid in btn_ids_4))
        self.assertTrue(any("btn_book:camino-inka:es" in bid for bid in btn_ids_4))
        # Botón debe ser exactamente "Solicitar reserva"
        self.assertTrue(any("Solicitar reserva" in title for title in btn_titles_4))
        self.assertFalse(any(title == "🙋‍♂️ Reservar" for title in btn_titles_4))

        # 4b. Ficha de tour: Caso SIN horario confirmado en catálogo oficial (Machu Picchu en Tren)
        res4_mp = self._send_wa_button_reply("btn_tour:machu-picchu-tren:es", "Machu Picchu")
        self.assertEqual(res4_mp["status_code"], 200)
        text4_mp = res4_mp["sent_text"]
        self.assertIn("Machu Picchu", text4_mp)
        self.assertIn("Duración", text4_mp)
        # Catálogo vigente tiene schedule_status: unknown; no debe inventar horario fijo ni 04:00
        self.assertNotIn("Horario", text4_mp)
        self.assertNotIn("04:00", text4_mp)

        # 4c. Ficha de tour: Caso CON horario registrado (mediante fixture sintético explícito en base aislada)
        catalog_service.upsert_tour({
            "entity_id": "tour-fixture-horario",
            "name": "Tour Demo Confirmado",
            "schedule": "08:00 - 13:00",
            "duration": "5 horas",
            "is_active": True
        })
        res4_sched = self._send_wa_button_reply("btn_tour:tour-fixture-horario:es", "Tour Demo Confirmado")
        self.assertEqual(res4_sched["status_code"], 200)
        text4_sched = res4_sched["sent_text"]
        self.assertIn("Tour Demo Confirmado", text4_sched)
        self.assertIn("Duración", text4_sched)
        self.assertIn("Horario", text4_sched)
        self.assertIn("08:00 - 13:00", text4_sched)

        # 5. Inclusiones (Pulsar "Qué incluye")
        # 5a. Caso datos no confirmados en fuentes oficiales (Camino Inca canónico): honestidad sin alucinación
        res5 = self._send_wa_button_reply("btn_inc:camino-inka:es", "📄 Qué incluye")
        self.assertEqual(res5["status_code"], 200)
        text5 = res5["sent_text"]
        self.assertIn("confirmamos contigo directamente", text5)
        self.assertNotIn("...", text5)
        btn_ids_5 = [b["id"] for b in res5["sent_buttons"]]
        self.assertTrue(any("btn_rates:camino-inka:es" in bid for bid in btn_ids_5))
        self.assertTrue(any("btn_book:camino-inka:es" in bid for bid in btn_ids_5))

        # 5b. Caso datos confirmados en catálogo (Machu Picchu en Tren)
        res5_mp = self._send_wa_button_reply("btn_inc:machu-picchu-tren:es", "📄 Qué incluye")
        self.assertEqual(res5_mp["status_code"], 200)
        text5_mp = res5_mp["sent_text"]
        self.assertIn("Incluye", text5_mp)
        self.assertNotIn("...", text5_mp)

        # 6. Tarifas (Pulsar "Tarifas")
        res6 = self._send_wa_button_reply("btn_rates:camino-inka:es", "💰 Tarifas")
        self.assertEqual(res6["status_code"], 200)
        text6 = res6["sent_text"]
        self.assertTrue(any(curr in text6 for curr in ["USD", "$", "790"]))
        btn_ids_6 = [b["id"] for b in res6["sent_buttons"]]
        self.assertTrue(any("btn_book:camino-inka:es" in bid for bid in btn_ids_6))

    # =========================================================================
    # RECORRIDO 2: Tour A → tour B → botón antiguo de A
    # =========================================================================
    def test_journey_2_tour_binding_preservation(self):
        uid = "51911112222"
        app.clear_history(uid)

        # 1. Usuario consulta sobre Camino Inca (Tour A)
        self._send_wa_message("informacion de Camino Inca", user_id=uid)

        # 2. Usuario consulta sobre City Tour (Tour B)
        self._send_wa_message("informacion de City Tour Cusco", user_id=uid)

        # 3. Usuario pulsa el botón del primer tour (Camino Inca: Qué incluye)
        res_btn = self._send_wa_button_reply("btn_inc:camino-inka:es", "📄 Qué incluye", user_id=uid)
        self.assertEqual(res_btn["status_code"], 200)
        sent_text = res_btn["sent_text"]

        # Debe responder sobre Camino Inca, NUNCA sobre City Tour
        self.assertIn("Camino Inca", sent_text)
        self.assertNotIn("City Tour", sent_text)

        # Los nuevos botones deben conservar camino-inka
        btn_ids = [b["id"] for b in res_btn["sent_buttons"]]
        self.assertTrue(all("camino-inka" in bid for bid in btn_ids if "btn_cats" not in bid and "btn_advisor" not in bid))

    # =========================================================================
    # RECORRIDO 3: Desactivar un tour después de mostrar sus botones → pulsar botón antiguo
    # =========================================================================
    def test_journey_3_deactivated_tour_clicking_old_button(self):
        uid = "51922223333"
        app.clear_history(uid)

        # Desactivar explícitamente choquequirao en el catálogo dinámico
        catalog_service.upsert_tour(dict(entity_id="choquequirao", name="Choquequirao Trek", is_active=False))
        try:
            # 1. Pulsar botón antiguo de Tarifas sobre tour desactivado
            res_rates = self._send_wa_button_reply("btn_rates:choquequirao:es", "💰 Tarifas", user_id=uid)
            self.assertEqual(res_rates["status_code"], 200)
            text_rates = res_rates["sent_text"]

            # Comprobar qué DEBE aparecer:
            self.assertIn("Choquequirao", text_rates)
            self.assertIn("no figura actualmente en nuestro catálogo activo", text_rates)
            self.assertIn("asesor", text_rates)

            # Comprobar qué NO DEBE aparecer en botones:
            # NUNCA ofrecer fotos, tarifas ni reservas sobre un tour inactivo
            btn_ids = [b["id"] for b in res_rates["sent_buttons"]]
            self.assertFalse(any("btn_rates" in bid for bid in btn_ids))
            self.assertFalse(any("btn_inc" in bid for bid in btn_ids))
            self.assertFalse(any("btn_photo" in bid for bid in btn_ids))
            self.assertFalse(any("btn_book" in bid for bid in btn_ids))
            # SOLO salidas útiles hacia otros tours y asesor
            self.assertTrue(any("btn_tours" in bid for bid in btn_ids))
            self.assertTrue(any("btn_advisor" in bid for bid in btn_ids))

            # 2. Pulsar botón antiguo de Solicitar Reserva sobre tour desactivado
            res_book = self._send_wa_button_reply("btn_book:choquequirao:es", "Solicitar reserva", user_id=uid)
            self.assertEqual(res_book["status_code"], 200)
            text_book = res_book["sent_text"]
            self.assertIn("no figura actualmente en nuestro catálogo activo", text_book)
            # NO debe crear un ticket comercial de reserva
            with handoff_support.connection() as conn:
                row = conn.execute("SELECT * FROM requests WHERE user_id=? AND question LIKE '%Choquequirao%'", (uid,)).fetchone()
                self.assertIsNone(row)
        finally:
            catalog_service.upsert_tour(dict(entity_id="choquequirao", name="Choquequirao Trek", is_active=True))

    # =========================================================================
    # RECORRIDO 4: Tour desactivado → elegir otra opción → continuar normalmente
    # =========================================================================
    def test_journey_4_inactive_tour_to_other_options(self):
        uid = "51922224444"
        app.clear_history(uid)

        # 1. Usuario pregunta por Choquequirao desactivado
        catalog_service.upsert_tour(dict(entity_id="choquequirao", name="Choquequirao Trek", is_active=False))
        try:
            res1 = self._send_wa_message("Quiero información de Choquequirao", user_id=uid)
            self.assertIn("no figura actualmente en nuestro catálogo activo", res1["sent_text"])
            btn_ids1 = [b["id"] for b in res1["sent_buttons"]]
            self.assertTrue(any("btn_tours" in bid for bid in btn_ids1))

            # 2. El cliente pulsa "Ver otros tours"
            res2 = self._send_wa_button_reply("btn_tours:es", "Ver otros tours", user_id=uid)
            self.assertIn("Catálogo de Experiencias", res2["sent_text"])
            btn_ids2 = [b["id"] for b in res2["sent_buttons"]]
            self.assertTrue(any("btn_cat:cusco:es" in bid for bid in btn_ids2))

            # 3. Elige categoría Cusco
            res3 = self._send_wa_button_reply("btn_cat:cusco:es", "🌄 Clásicos Cusco", user_id=uid)
            self.assertIn("Montañas y Clásicos", res3["sent_text"])
            self.assertIn("Montaña de 7 Colores", res3["sent_text"])

            # 4. Selecciona un tour activo (Montaña de 7 Colores) y continúa con fluidez
            res4 = self._send_wa_button_reply("btn_tour:montana-7-colores:es", "Montaña de 7 Colores", user_id=uid)
            self.assertIn("Montaña de 7 Colores", res4["sent_text"])
            self.assertIn("Duración", res4["sent_text"])
            self.assertIn("Horario", res4["sent_text"])
            btn_ids4 = [b["id"] for b in res4["sent_buttons"]]
            self.assertTrue(any("btn_book:montana-7-colores:es" in bid for bid in btn_ids4))
        finally:
            catalog_service.upsert_tour(dict(entity_id="choquequirao", name="Choquequirao Trek", is_active=True))

    # =========================================================================
    # RECORRIDO 5: Alta de tour activo y modificación de datos → consulta actualizada
    # =========================================================================
    def test_journey_5_dynamic_tour_lifecycle(self):
        uid = "51955551111"
        app.clear_history(uid)

        new_eid = f"canon-tinajani-{os.urandom(2).hex()}"
        # 1. Crear nuevo tour activo sin tocar código estático
        ok, msg = catalog_service.upsert_tour({
            "entity_id": new_eid,
            "name": "Cañón de Tinajani",
            "aliases": ["tinajani", "canon de tinajani"],
            "official_price": "60",
            "currency": "USD",
            "duration": "1 día completo",
            "schedule": "06:00 a 18:00",
            "includes": "Transporte turístico, guía profesional, almuerzo campestre",
            "is_active": True,
        })
        self.assertTrue(ok)

        try:
            # 2. Consultar el nuevo tour
            res1 = self._send_wa_message(f"informacion de Cañón de Tinajani", user_id=uid)
            text1 = res1["sent_text"]
            self.assertIn("Cañón de Tinajani", text1)
            self.assertIn("60 USD", text1)
            self.assertIn("06:00 a 18:00", text1)

            # 3. Modificar el precio y horario del tour
            ok2, _ = catalog_service.upsert_tour({
                "entity_id": new_eid,
                "name": "Cañón de Tinajani",
                "official_price": "75",
                "currency": "USD",
                "schedule": "05:30 a 18:30",
                "is_active": True,
            })
            self.assertTrue(ok2)

            # 4. Consultar inmediatamente: debe reflejar el precio y horario actualizado
            app.clear_history(uid)
            res2 = self._send_wa_message(f"precio de Cañón de Tinajani", user_id=uid)
            text2 = res2["sent_text"]
            self.assertIn("75 USD", text2)
            self.assertNotIn("60 USD", text2)
        finally:
            # Limpiar tour de prueba
            catalog_service.upsert_tour({"entity_id": new_eid, "name": "Cañón de Tinajani", "is_active": False})

    # =========================================================================
    # RECORRIDO 6: Foto disponible, inexistente y envío fallido
    # =========================================================================
    def test_journey_6_multimedia_matrix(self):
        uid = "51933334444"
        app.clear_history(uid)

        # Caso 6A: Foto disponible (machu-picchu-tren) con éxito en Meta API
        with patch.object(app, "META_APP_SECRET", "test_meta_secret_123"), \
             patch("hmac.compare_digest", return_value=True), \
             patch.object(app, "send_whatsapp_message", return_value=True) as mock_msg, \
             patch.object(app, "send_whatsapp_image", return_value=True) as mock_img:
            payload = {
                "object": "whatsapp_business_account",
                "entry": [{
                    "changes": [{
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "109876543210"},
                            "contacts": [{"wa_id": uid}],
                            "messages": [{
                                "from": uid,
                                "id": f"wamid.photo_{os.urandom(4).hex()}",
                                "type": "interactive",
                                "interactive": {
                                    "type": "button_reply",
                                    "button_reply": {"id": "btn_photo:machu-picchu-tren:es", "title": "📸 Ver Fotos"}
                                }
                            }]
                        },
                        "field": "messages"
                    }]
                }]
            }
            resp = self.client.post("/webhook", json=payload)
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(mock_img.called)
            text = mock_msg.call_args[1]["text"]
            self.assertIn("fotografía oficial", text)
            # Acciones válidas para foto entregada:
            buttons = mock_msg.call_args[1].get("buttons", [])
            b_ids = [b["id"] for b in buttons]
            self.assertTrue(any("btn_rates" in b for b in b_ids))
            self.assertTrue(any("btn_book" in b for b in b_ids))

        # Caso 6B: Foto inexistente (camino-inka no tiene imagen oficial en línea)
        app.clear_history(uid)
        with patch.object(app, "META_APP_SECRET", "test_meta_secret_123"), \
             patch("hmac.compare_digest", return_value=True), \
             patch.object(app, "send_whatsapp_message", return_value=True) as mock_msg, \
             patch.object(app, "send_whatsapp_image", return_value=True) as mock_img:
            payload = {
                "object": "whatsapp_business_account",
                "entry": [{
                    "changes": [{
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "109876543210"},
                            "contacts": [{"wa_id": uid}],
                            "messages": [{
                                "from": uid,
                                "id": f"wamid.photo_{os.urandom(4).hex()}",
                                "type": "interactive",
                                "interactive": {
                                    "type": "button_reply",
                                    "button_reply": {"id": "btn_photo:camino-inka:es", "title": "📸 Ver Fotos"}
                                }
                            }]
                        },
                        "field": "messages"
                    }]
                }]
            }
            resp = self.client.post("/webhook", json=payload)
            self.assertEqual(resp.status_code, 200)
            self.assertFalse(mock_img.called)
            text = mock_msg.call_args[1]["text"]
            self.assertNotIn("Te compartimos la fotografía oficial", text)
            self.assertIn("Actualmente no disponemos de fotos en línea", text)
            # Botones NO deben ofrecer de nuevo foto que no existe
            buttons = mock_msg.call_args[1].get("buttons", [])
            b_ids = [b["id"] for b in buttons]
            self.assertFalse(any("btn_photo" in b for b in b_ids))
            self.assertTrue(any("btn_rates" in b for b in b_ids))

        # Caso 6C: Error de envío en Meta API (send_whatsapp_image retorna False)
        app.clear_history(uid)
        with patch.object(app, "META_APP_SECRET", "test_meta_secret_123"), \
             patch("hmac.compare_digest", return_value=True), \
             patch.object(app, "send_whatsapp_message", return_value=True) as mock_msg, \
             patch.object(app, "send_whatsapp_image", return_value=False) as mock_img:
            payload = {
                "object": "whatsapp_business_account",
                "entry": [{
                    "changes": [{
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "109876543210"},
                            "contacts": [{"wa_id": uid}],
                            "messages": [{
                                "from": uid,
                                "id": f"wamid.photo_{os.urandom(4).hex()}",
                                "type": "interactive",
                                "interactive": {
                                    "type": "button_reply",
                                    "button_reply": {"id": "btn_photo:machu-picchu-tren:es", "title": "📸 Ver Fotos"}
                                }
                            }]
                        },
                        "field": "messages"
                    }]
                }]
            }
            resp = self.client.post("/webhook", json=payload)
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(mock_img.called)
            text = mock_msg.call_args[1]["text"]
            self.assertNotIn("Te compartimos la fotografía oficial", text)
            self.assertIn("inconveniente al cargar la fotografía", text)
            # Botones deben incluir reintento controlado de foto
            buttons = mock_msg.call_args[1].get("buttons", [])
            b_ids = [b["id"] for b in buttons]
            self.assertTrue(any("btn_photo" in b for b in b_ids))

    # =========================================================================
    # RECORRIDO 7: Solicitud al asesor → repetición → continuación de la conversación
    # =========================================================================
    def test_journey_7_handoff_repeat_and_continue(self):
        uid = "51944445555"
        app.clear_history(uid)
        with handoff_support.connection() as conn:
            conn.execute("DELETE FROM requests WHERE user_id=?", (uid,))
            conn.commit()

        # 1. Solicitud de reserva
        res1 = self._send_wa_button_reply("btn_book:camino-inka:es", "Solicitar reserva", user_id=uid)
        self.assertEqual(res1["status_code"], 200)
        sent_text1 = res1["sent_text"]
        self.assertIn("Registré tu solicitud", sent_text1)
        self.assertIn("pendiente de atención por un asesor", sent_text1)
        self.assertIn("tu reserva aún no está confirmada", sent_text1)

        # Comprobar creación de ticket en BD
        with handoff_support.connection() as conn:
            row = conn.execute("SELECT * FROM requests WHERE user_id=? AND channel='whatsapp'", (uid,)).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["status"], "pending")

        # 2. Repetición del clic: no duplica ticket e informa estado
        res2 = self._send_wa_button_reply("btn_book:camino-inka:es", "Solicitar reserva", user_id=uid)
        self.assertEqual(res2["status_code"], 200)
        sent_text2 = res2["sent_text"]
        self.assertIn("Ya tienes una solicitud registrada", sent_text2)
        with handoff_support.connection() as conn:
            count = conn.execute("SELECT COUNT(*) as c FROM requests WHERE user_id=?", (uid,)).fetchone()["c"]
            self.assertEqual(count, 1)

        # 3. Continuación libre de la conversación mientras la solicitud está abierta
        res3 = self._send_wa_message("¿Tienen tours en Puno o el Lago Titicaca?", user_id=uid)
        self.assertEqual(res3["status_code"], 200)
        text3 = res3["sent_text"]
        self.assertTrue(any(k in text3.lower() for k in ["titicaca", "puno", "islas"]))

    # =========================================================================
    # RECORRIDO 8: Catálogo vacío y error de lectura BD como situaciones distintas
    # =========================================================================
    def test_journey_8_empty_catalog_vs_read_error(self):
        # Situación 8A: Catálogo vacío (0 tours activos devueltos normalmente)
        with patch("catalog_service.get_all_tours", return_value=[]):
            btn_empty = app.get_quick_buttons(route="evidence_catalog_empty", lang="es")
            self.assertEqual(len(btn_empty), 1)
            self.assertTrue(any("btn_advisor" in b["id"] for b in btn_empty))

        # Situación 8B: Error de lectura de BD (excepción no controlada al consultar la base)
        btn_err = app.get_quick_buttons(route="evidence_catalog_error", lang="es")
        self.assertEqual(len(btn_err), 2)
        # Permite contactar asesor y reintentar, sin inventar que los tours fueron desactivados
        self.assertTrue(any("btn_advisor" in b["id"] for b in btn_err))
        self.assertTrue(any("btn_tours" in b["id"] for b in btn_err))

    # =========================================================================
    # RECORRIDO 9: Mensajes libres, preguntas de seguimiento y referencias ambiguas
    # =========================================================================
    def test_journey_9_free_text_followup_and_ambiguity(self):
        uid = "51988889999"
        app.clear_history(uid)

        # 1. Mensaje libre con intención clara
        res1 = self._send_wa_message("Hola, quiero saber del Camino Inca", user_id=uid)
        self.assertEqual(res1["status_code"], 200)
        self.assertIn("Camino Inca", res1["sent_text"])

        # 2. Pregunta de seguimiento elíptica ("¿y el precio?") conservando entidad
        res2 = self._send_wa_message("¿y el precio?", user_id=uid)
        self.assertEqual(res2["status_code"], 200)
        # Conserva contexto de Camino Inca y devuelve la tarifa oficial confirmada
        self.assertTrue(any(curr in res2["sent_text"] for curr in ["USD", "$", "790"]))

        # 2b. Precio sin confirmar: para tours sin tarifa fija registrada, explica y ofrece asesor
        app.clear_history(uid)
        self._send_wa_message("Hola, quiero saber de la montaña de 7 colores", user_id=uid)
        res_unconf = self._send_wa_message("¿cuál es la tarifa?", user_id=uid)
        self.assertEqual(res_unconf["status_code"], 200)
        self.assertIn("Montaña de 7 Colores", res_unconf["sent_text"])
        self.assertIn("confirmamos", res_unconf["sent_text"])
        self.assertIn("asesor", res_unconf["sent_text"])

        # 3. Referencia ambigua ("el otro" tras mencionar dos opciones)
        app.clear_history(uid)
        self._send_wa_message("Me gusta el Camino Inca pero también el City Tour", user_id=uid)
        res_ambi = self._send_wa_message("¿tienes fotos del otro?", user_id=uid)
        self.assertEqual(res_ambi["status_code"], 200)
        text_ambi = res_ambi["sent_text"]
        # Debe pedir aclaración específica sin adivinar
        self.assertTrue("¿A cuál de los tours te refieres?" in text_ambi or "¿De cuál de nuestros tours deseas consultar?" in text_ambi)
        btn_ids_ambi = [b["id"] for b in res_ambi["sent_buttons"]]
        # Debe ofrecer botones para ambos tours candidatos
        self.assertTrue(any("camino-inka" in bid for bid in btn_ids_ambi))
        self.assertTrue(any("city-tour-cusco" in bid for bid in btn_ids_ambi))

    # =========================================================================
    # RECORRIDO 10: Recorridos equivalentes en español e inglés
    # =========================================================================
    def test_journey_10_english_full_journey(self):
        uid = "51966667777"
        app.clear_history(uid)
        with handoff_support.connection() as conn:
            conn.execute("DELETE FROM requests WHERE user_id=?", (uid,))
            conn.commit()

        # 1. Greeting
        res1 = self._send_wa_message("Hello", user_id=uid)
        self.assertIn("virtual assistant", res1["sent_text"])
        btn_ids_1 = [b["id"] for b in res1["sent_buttons"]]
        self.assertTrue(any("btn_tours:en" in bid for bid in btn_ids_1))

        # 2. Categories
        res2 = self._send_wa_button_reply("btn_tours:en", "🗺️ View Tours", user_id=uid)
        self.assertIn("Tour Experiences", res2["sent_text"])
        btn_ids_2 = [b["id"] for b in res2["sent_buttons"]]
        self.assertTrue(any("btn_cat:treks:en" in bid for bid in btn_ids_2))

        # 3. Category tours
        res3 = self._send_wa_button_reply("btn_cat:treks:en", "🏔️ Machu Picchu", user_id=uid)
        self.assertIn("Machu Picchu", res3["sent_text"])
        btn_titles_3 = [b["title"] for b in res3["sent_buttons"]]
        self.assertTrue(any("More tours" in t or "Categories" in t for t in btn_titles_3))

        # 4. Tour overview
        res4 = self._send_wa_button_reply("btn_tour:camino-inka:en", "Inca Trail", user_id=uid)
        text4 = res4["sent_text"]
        self.assertIn("Inca Trail", text4)
        self.assertIn("Duration", text4)
        self.assertIn("Official rate", text4)
        btn_titles_4 = [b["title"] for b in res4["sent_buttons"]]
        self.assertTrue(any("Request reservation" in t for t in btn_titles_4))
        self.assertFalse(any("Reservar" in t for t in btn_titles_4))

        # 5. Reservation request
        res5 = self._send_wa_button_reply("btn_book:camino-inka:en", "Request reservation", user_id=uid)
        text5 = res5["sent_text"]
        self.assertIn("registered your request", text5)
        self.assertIn("reservation is not yet confirmed", text5)

        # 6. Deactivated tour inquiry in English
        catalog_service.upsert_tour(dict(entity_id="choquequirao", name="Choquequirao Trek", is_active=False))
        try:
            res_deact = self._send_wa_message("Do you have Choquequirao available?", user_id=uid)
            text_deact = res_deact["sent_text"]
            self.assertIn("is not currently in our active catalog", text_deact)
            btn_ids_deact = [b["id"] for b in res_deact["sent_buttons"]]
            self.assertTrue(any("btn_tours:en" in bid for bid in btn_ids_deact))
            self.assertTrue(any("btn_advisor:en" in bid for bid in btn_ids_deact))
            self.assertFalse(any("btn_book" in bid for bid in btn_ids_deact))
        finally:
            catalog_service.upsert_tour(dict(entity_id="choquequirao", name="Choquequirao Trek", is_active=True))

    # =========================================================================
    # REGRESIÓN: CSRF, atención humana y métricas operativas
    # =========================================================================
    def test_journey_regression_security_and_metrics(self):
        # 1. CSRF en endpoints administrativos
        resp_csrf = self.client.post("/api/catalog/tours", json={"entity_id": "eval-csrf-test", "name": "Test CSRF"})
        self.assertEqual(resp_csrf.status_code, 403)

        # 2. Atención humana: bloqueo de cierre sin atender
        with handoff_support.connection() as conn:
            tid = f"reg_{os.urandom(4).hex()}"
            conn.execute("INSERT INTO requests(id, user_id, channel, question, context, status, created_at, updated_at) "
                         "VALUES(?, ?, 'whatsapp', 'pregunta prueba', '[]', 'pending', datetime('now'), datetime('now'))",
                         (tid, "test_user_reg"))
            conn.commit()

        with self.assertRaises(ValueError):
            handoff_support.update_request(tid, "closed", "Asesor Test", "Nota de cierre")

        handoff_support.update_request(tid, "in_progress", "Asesor Test", "Tomado en atención")
        handoff_support.update_request(tid, "closed", "Asesor Test", "Atendido correctamente")

        with handoff_support.connection() as conn:
            row = conn.execute("SELECT status FROM requests WHERE id=?", (tid,)).fetchone()
            self.assertEqual(row["status"], "closed")

        # 3. Métricas operativas
        import operational_metrics as op
        ev_id = op.start()
        self.assertIsNotNone(ev_id)
        op.finish(ev_id, "api_accepted", 50.0, 100.0, {"route": "test"})
        m = op.summary()
        self.assertIn("api_accepted", m)
        self.assertTrue(m["api_accepted"] >= 1)

    # =========================================================================
    # REVISIÓN POLISH: Prueba directa de apply_request con tour inactivo
    # =========================================================================
    def test_apply_request_inactive_tour_direct(self):
        """Comprueba directamente la rama de rechazo de tour inactivo en apply_request():
        - Devuelve dict estructurado (no None)
        - route == 'evidence_inactive_tour'
        - handoff_registered == False
        - resolved_autonomously == False
        - No crea una reserva ni rompe la respuesta
        """
        catalog_service.upsert_tour(dict(entity_id="choquequirao", name="Choquequirao Trek", is_active=False))
        try:
            with handoff_support.connection() as conn:
                before_count = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]

            res = handoff_support.apply_request(
                ns=app.__dict__,
                result={"handoff_requested": True, "handoff_language": "es"},
                user_id="direct_inactive_test",
                channel="whatsapp",
                question="quiero reservar Choquequirao Trek"
            )

            self.assertIsNotNone(res)
            self.assertIsInstance(res, dict)
            self.assertEqual(res.get("route"), "evidence_inactive_tour")
            self.assertFalse(res.get("handoff_registered"))
            self.assertFalse(res.get("resolved_autonomously"))
            self.assertIn("no figura actualmente en nuestro catálogo activo", res.get("response", ""))

            with handoff_support.connection() as conn:
                after_count = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
            self.assertEqual(before_count, after_count)
        finally:
            catalog_service.upsert_tour(dict(entity_id="choquequirao", name="Choquequirao Trek", is_active=True))

    # =========================================================================
    # REVISIÓN POLISH: Navegación de categorías pulsando botones emitidos reales
    # =========================================================================
    def test_journey_category_navigation_real_buttons(self):
        """Navegación interactiva pulsando exclusivamente los botones realmente emitidos:
        - Acceso a categorías y selección de una categoría con múltiples páginas
        - En página 0: botones de tours y 'Más tours'
        - En página intermedia: botón de tour, 'Más tours' y salida inmediata 'Categorías'
        - Probar salida inmediata pulsando 'Categorías' desde página intermedia sin recorrer todas las páginas
        - Volver a entrar y recorrer hasta el final comprobando que todos los tours activos sean accesibles,
          los desactivados no se ofrezcan, y se conserven tour e idioma.
        """
        uid = "51977778888"
        app.clear_history(uid)

        # Desactivamos explícitamente un tour para verificar que los desactivados NO se ofrezcan
        catalog_service.upsert_tour(dict(entity_id="choquequirao", name="Choquequirao Trek", is_active=False))
        try:
            # 1. Solicitar ver categorías
            res_cat = self._send_wa_button_reply("btn_tours:es", "🗺️ Ver Tours", user_id=uid)
            self.assertEqual(res_cat["status_code"], 200)
            btn_ids = [b["id"] for b in res_cat["sent_buttons"]]
            self.assertTrue(any("btn_cat:treks:es" in bid for bid in btn_ids))

            # 2. Entrar a Treks pulsando el botón real emitido
            res_p0 = self._send_wa_button_reply("btn_cat:treks:es", "🏔️ Machu Picchu y Treks", user_id=uid)
            self.assertEqual(res_p0["status_code"], 200)
            p0_buttons = res_p0["sent_buttons"]
            p0_ids = [b["id"] for b in p0_buttons]
            self.assertTrue(any("btn_tour:machu-picchu-tren:es" in bid for bid in p0_ids))
            self.assertTrue(any("btn_tour:camino-inka:es" in bid for bid in p0_ids))
            mas_btn = next((b for b in p0_buttons if b["id"].startswith("btn_cat_page:")), None)
            self.assertIsNotNone(mas_btn)

            # 3. Avanzar a página 1 intermedia pulsando el botón REALMENTE emitido
            res_p1 = self._send_wa_button_reply(mas_btn["id"], mas_btn["title"], user_id=uid)
            self.assertEqual(res_p1["status_code"], 200)
            p1_buttons = res_p1["sent_buttons"]
            p1_ids = [b["id"] for b in p1_buttons]

            # Comprobar coherencia de texto y botones en página intermedia
            self.assertIn("Página 2 de", res_p1["sent_text"])
            self.assertIn("Machu Picchu by Car", res_p1["sent_text"])
            self.assertTrue(any("btn_tour:machu-picchu-car:es" in bid for bid in p1_ids))

            # Comprobar presencia de salida inmediata 'Categorías' en página intermedia
            cats_btn = next((b for b in p1_buttons if b["id"].startswith("btn_cats:")), None)
            self.assertIsNotNone(cats_btn, "En páginas intermedias debe existir el botón ⬅️ Categorías")

            # 4. Probar salida inmediata pulsando el botón emitido 'Categorías' desde página intermedia
            res_exit = self._send_wa_button_reply(cats_btn["id"], cats_btn["title"], user_id=uid)
            self.assertEqual(res_exit["status_code"], 200)
            self.assertIn("Catálogo de Experiencias", res_exit["sent_text"])
            exit_ids = [b["id"] for b in res_exit["sent_buttons"]]
            self.assertTrue(any("btn_cat:treks:es" in bid for bid in exit_ids))

            # 5. Volver a entrar y recorrer toda la categoría hasta el final verificando accesibilidad
            res_curr = self._send_wa_button_reply("btn_cat:treks:es", "🏔️ Machu Picchu y Treks", user_id=uid)
            visited_tours = set()
            page_count = 0

            while page_count < 10:
                page_count += 1
                curr_buttons = res_curr["sent_buttons"]
                for b in curr_buttons:
                    if b["id"].startswith("btn_tour:"):
                        parts = b["id"].split(":")
                        visited_tours.add(parts[1])
                        self.assertEqual(parts[2], "es", "Se debe conservar el idioma")

                next_btn = next((b for b in curr_buttons if b["id"].startswith("btn_cat_page:")), None)
                if not next_btn:
                    self.assertTrue(any(b["id"].startswith("btn_cats:") for b in curr_buttons))
                    break
                res_curr = self._send_wa_button_reply(next_btn["id"], next_btn["title"], user_id=uid)

            # Comprobar que todos los tours activos de la categoría fueron visitados
            self.assertIn("machu-picchu-tren", visited_tours)
            self.assertIn("camino-inka", visited_tours)
            self.assertIn("salkantay-trek", visited_tours)
            self.assertIn("inka-jungle", visited_tours)
            self.assertIn("machu-picchu-car", visited_tours)
            self.assertNotIn("choquequirao", visited_tours)
        finally:
            catalog_service.upsert_tour(dict(entity_id="choquequirao", name="Choquequirao Trek", is_active=True))


if __name__ == "__main__":
    unittest.main()
