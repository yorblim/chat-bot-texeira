"""tests/test_whatsapp_flow_polish.py — Validación exhaustiva del flujo de WhatsApp de Texeira Travel.

Comprueba los 8 recorridos exigidos por el requerimiento de calidad:
1. Saludo → categorías → tour → inclusiones → tarifa.
2. Consultar dos tours y pulsar un botón del primero: preserva el tour original.
3. Foto disponible, foto inexistente y error de envío a Meta API.
4. Solicitar reserva: ticket con tour y contexto, sin confirmar reserva ni pago.
5. Repetir la solicitud: sin tickets duplicados, informando estado del ticket abierto.
6. Recorrido equivalente en inglés (Request reservation, English tour card, etc.).
7. Tour desactivado y categoría vacía / catálogo vacío.
8. Regresión de CSRF, catálogo dinámico, atención humana y métricas operativas.
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
        os.environ["META_APP_SECRET"] = "test_meta_secret_123"
        database.init_db(app.SQLITE_DB_PATH)
        try:
            catalog_service.init_catalog_db()
        except Exception:
            pass

    def setUp(self):
        self.client = TestClient(app.app)
        self.test_uid = "51999888777"
        app.clear_history(self.test_uid)
        # Limpiar tickets previos del usuario de prueba
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
    # RECORRIDO 1: Saludo → categorías → tour → inclusiones → tarifa
    # =========================================================================
    def test_journey_1_greeting_to_rates(self):
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
        self.assertIn("Camino Inca", res3["sent_text"])
        btn_ids_3 = [b["id"] for b in res3["sent_buttons"]]
        # Debe incluir botón para regresar a categorías y botón para tour
        self.assertTrue(any("btn_cats:es" in bid for bid in btn_ids_3))
        self.assertTrue(any("btn_tour:camino-inka:es" in bid for bid in btn_ids_3))

        # 4. Ficha de tour (Pulsar "Camino Inca Clásico")
        res4 = self._send_wa_button_reply("btn_tour:camino-inka:es", "Camino Inca")
        self.assertEqual(res4["status_code"], 200)
        text4 = res4["sent_text"]
        self.assertIn("Camino Inca", text4)
        self.assertIn("Duración", text4)
        self.assertIn("Horario", text4)
        self.assertIn("Tarifa oficial", text4)
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

        # 5. Inclusiones (Pulsar "Qué incluye")
        res5 = self._send_wa_button_reply("btn_inc:camino-inka:es", "📄 Qué incluye")
        self.assertEqual(res5["status_code"], 200)
        text5 = res5["sent_text"]
        self.assertIn("Incluye", text5)
        # Elementos completos por viñetas, sin cortes
        self.assertNotIn("...", text5)
        btn_ids_5 = [b["id"] for b in res5["sent_buttons"]]
        self.assertTrue(any("btn_rates:camino-inka:es" in bid for bid in btn_ids_5))
        self.assertTrue(any("btn_book:camino-inka:es" in bid for bid in btn_ids_5))

        # 6. Tarifas (Pulsar "Tarifas")
        res6 = self._send_wa_button_reply("btn_rates:camino-inka:es", "💰 Tarifas")
        self.assertEqual(res6["status_code"], 200)
        text6 = res6["sent_text"]
        self.assertTrue(any(curr in text6 for curr in ["USD", "$", "790"]))
        btn_ids_6 = [b["id"] for b in res6["sent_buttons"]]
        self.assertTrue(any("btn_book:camino-inka:es" in bid for bid in btn_ids_6))

    # =========================================================================
    # RECORRIDO 2: Consultar dos tours y pulsar un botón del primero
    # =========================================================================
    def test_journey_2_tour_binding_preservation(self):
        uid = "51911112222"
        app.clear_history(uid)

        # 1. Usuario consulta sobre Camino Inca
        self._send_wa_message("informacion de Camino Inca", user_id=uid)

        # 2. Usuario consulta sobre City Tour
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
    # RECORRIDO 3: Foto disponible, foto inexistente y error de envío
    # =========================================================================
    def test_journey_3_photo_available_unavailable_and_error(self):
        uid = "51933334444"
        app.clear_history(uid)

        # Caso 3A: Foto disponible (machu-picchu-tren) con éxito en Meta API
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
            # Debe intentar enviar la imagen a Meta API
            self.assertTrue(mock_img.called)
            img_call_kwargs = mock_img.call_args[1]
            self.assertIn("machu_picchu", img_call_kwargs["image_url"].lower())
            # Mensaje de texto acompaña confirmando entrega oficial
            text = mock_msg.call_args[1]["text"]
            self.assertIn("fotografía oficial", text)
            self.assertIn("Machu Picchu", text)

        # Caso 3B: Foto inexistente (camino-inka no tiene imagen oficial en línea)
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
            # NUNCA debe invocar send_whatsapp_image para una foto inexistente
            self.assertFalse(mock_img.called)
            # NO debe afirmar falsamente que envió una foto
            text = mock_msg.call_args[1]["text"]
            self.assertNotIn("Aquí tienes una imagen", text)
            self.assertNotIn("Te compartimos la fotografía oficial", text)
            self.assertIn("Actualmente no disponemos de fotos en línea", text)
            self.assertIn("asesor", text)

        # Caso 3C: Error de envío en Meta API (send_whatsapp_image retorna False)
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
            # Si Meta API falló, NO debe afirmar que envió la imagen
            text = mock_msg.call_args[1]["text"]
            self.assertNotIn("Te compartimos la fotografía oficial", text)
            self.assertIn("inconveniente al cargar la fotografía", text)
            self.assertIn("asesor", text)

    # =========================================================================
    # RECORRIDO 4: Solicitar reserva (ticket con tour y contexto, sin confirmar)
    # =========================================================================
    def test_journey_4_reservation_request_and_ticket_creation(self):
        uid = "51944445555"
        app.clear_history(uid)
        with handoff_support.connection() as conn:
            conn.execute("DELETE FROM requests WHERE user_id=?", (uid,))
            conn.commit()

        # Conversación previa para dar contexto
        self._send_wa_message("Hola, buenas tardes", user_id=uid)
        self._send_wa_message("Cuánto cuesta el Camino Inca Clásico 4D/3N?", user_id=uid)

        # Solicitud de reserva pulsando el botón formal
        res = self._send_wa_button_reply("btn_book:camino-inka:es", "Solicitar reserva", user_id=uid)
        self.assertEqual(res["status_code"], 200)
        sent_text = res["sent_text"]

        # 1. Mensaje al usuario: no confirma disponibilidad, pago ni reserva
        self.assertIn("Registré tu solicitud", sent_text)
        self.assertIn("Camino Inca", sent_text)
        self.assertIn("pendiente de atención por un asesor", sent_text)
        self.assertIn("tu reserva aún no está confirmada", sent_text)
        self.assertNotIn("tu reserva está confirmada", sent_text.lower())
        self.assertNotIn("pago recibido", sent_text.lower())
        self.assertNotIn("cupos asegurados", sent_text.lower())

        # 2. Comprobar que el ticket se registró en base de datos con el tour y contexto
        with handoff_support.connection() as conn:
            row = conn.execute("SELECT * FROM requests WHERE user_id=? AND channel='whatsapp'", (uid,)).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["status"], "pending")
            self.assertIn("Camino Inca", row["question"])
            # Contexto de la conversación registrado
            ctx = json.loads(row["context"])
            self.assertTrue(len(ctx) >= 1)

    # =========================================================================
    # RECORRIDO 5: Repetir la solicitud sin tickets duplicados
    # =========================================================================
    def test_journey_5_no_duplicate_tickets_on_repeat(self):
        uid = "51955556666"
        app.clear_history(uid)
        with handoff_support.connection() as conn:
            conn.execute("DELETE FROM requests WHERE user_id=?", (uid,))
            conn.commit()

        # Primera solicitud
        res1 = self._send_wa_button_reply("btn_book:camino-inka:es", "Solicitar reserva", user_id=uid)
        self.assertEqual(res1["status_code"], 200)

        with handoff_support.connection() as conn:
            count1 = conn.execute("SELECT COUNT(*) as c FROM requests WHERE user_id=?", (uid,)).fetchone()["c"]
            self.assertEqual(count1, 1)

        # Repetición de la solicitud
        res2 = self._send_wa_button_reply("btn_book:camino-inka:es", "Solicitar reserva", user_id=uid)
        self.assertEqual(res2["status_code"], 200)
        sent_text2 = res2["sent_text"]

        # No se debe crear ticket duplicado
        with handoff_support.connection() as conn:
            count2 = conn.execute("SELECT COUNT(*) as c FROM requests WHERE user_id=?", (uid,)).fetchone()["c"]
            self.assertEqual(count2, 1)

        # Informa estado del ticket abierto y reitera que la reserva no está confirmada
        self.assertIn("Ya tienes una solicitud registrada", sent_text2)
        self.assertIn("pendiente de atención", sent_text2)
        self.assertIn("tu reserva aún no está confirmada", sent_text2.lower())

    # =========================================================================
    # RECORRIDO 6: Recorrido equivalente en inglés
    # =========================================================================
    def test_journey_6_english_journey(self):
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
        self.assertIn("Inca Trail", res3["sent_text"])
        btn_titles_3 = [b["title"] for b in res3["sent_buttons"]]
        self.assertTrue(any("Categories" in t for t in btn_titles_3))

        # 4. Tour overview
        res4 = self._send_wa_button_reply("btn_tour:camino-inka:en", "Inca Trail", user_id=uid)
        text4 = res4["sent_text"]
        self.assertIn("Inca Trail", text4)
        self.assertIn("Duration", text4)
        self.assertIn("Official rate", text4)
        btn_titles_4 = [b["title"] for b in res4["sent_buttons"]]
        self.assertTrue(any("Request reservation" in t for t in btn_titles_4))

        # 5. Reservation request
        res5 = self._send_wa_button_reply("btn_book:camino-inka:en", "Request reservation", user_id=uid)
        text5 = res5["sent_text"]
        self.assertIn("registered your request", text5)
        self.assertIn("reservation is not yet confirmed", text5)

    # =========================================================================
    # RECORRIDO 7: Tour desactivado y catálogo vacío
    # =========================================================================
    def test_journey_7_deactivated_tour_and_empty_catalog(self):
        # Desactivar temporalmente camino-inka
        catalog_service.upsert_tour(dict(entity_id="camino-inka", name="Camino Inca", is_active=False))
        try:
            # En la categoría treks, camino-inka no debe aparecer
            res = self._send_wa_button_reply("btn_cat:treks:es", "🏔️ Machu Picchu")
            self.assertNotIn("Camino Inca Clásico", res["sent_text"])
            btn_ids = [b["id"] for b in res["sent_buttons"]]
            self.assertFalse(any("camino-inka" in bid for bid in btn_ids))
            self.assertTrue(any("machu-picchu-tren" in bid for bid in btn_ids))
        finally:
            catalog_service.upsert_tour(dict(entity_id="camino-inka", name="Camino Inca", is_active=True))

        # Catálogo vacío simulado: get_all_tours retorna []
        with patch("catalog_service.get_all_tours", return_value=[]):
            btn_empty = app.get_quick_buttons(route="evidence_listing", lang="es")
            self.assertEqual(len(btn_empty), 1)
            self.assertTrue(any("btn_advisor" in b["id"] for b in btn_empty))

    # =========================================================================
    # RECORRIDO 8: Regresión de CSRF, catálogo, atención humana y métricas
    # =========================================================================
    def test_journey_8_regressions(self):
        # 1. CSRF en endpoints administrativos (/api/catalog/tours sin token CSRF es rechazado con 403)
        resp_csrf = self.client.post("/api/catalog/tours", json={"entity_id": "eval-csrf-test", "name": "Test CSRF"})
        self.assertEqual(resp_csrf.status_code, 403)

        # 2. Catálogo dinámico: persistencia y consulta
        rates = catalog_service.get_tour_rates("machu-picchu-tren", active_only=True)
        self.assertIsNotNone(rates)

        # 3. Atención humana: bloqueo de cierre sin atender
        with handoff_support.connection() as conn:
            tid = f"reg_{os.urandom(4).hex()}"
            conn.execute("INSERT INTO requests(id, user_id, channel, question, context, status, created_at, updated_at) "
                         "VALUES(?, ?, 'whatsapp', 'pregunta prueba', '[]', 'pending', datetime('now'), datetime('now'))",
                         (tid, "test_user_reg"))
            conn.commit()

        # Intentar cerrar ticket pendiente directamente sin tomarlo en atención debe fallar
        with self.assertRaises(ValueError):
            handoff_support.update_request(tid, "closed", "Asesor Test", "Nota de cierre")

        # Tomarlo en atención primero
        handoff_support.update_request(tid, "in_progress", "Asesor Test", "Tomado en atención")
        # Ahora sí se puede cerrar
        handoff_support.update_request(tid, "closed", "Asesor Test", "Atendido correctamente")

        with handoff_support.connection() as conn:
            row = conn.execute("SELECT status FROM requests WHERE id=?", (tid,)).fetchone()
            self.assertEqual(row["status"], "closed")

        # 4. Métricas operativas
        import operational_metrics as op
        ev_id = op.start()
        self.assertIsNotNone(ev_id)
        op.finish(ev_id, "api_accepted", 50.0, 100.0, {"route": "test"})
        m = op.summary()
        self.assertIn("api_accepted", m)
        self.assertTrue(m["api_accepted"] >= 1)


if __name__ == "__main__":
    unittest.main()
