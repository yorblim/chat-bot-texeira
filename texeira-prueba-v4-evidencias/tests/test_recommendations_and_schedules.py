"""tests/test_recommendations_and_schedules.py — Pruebas de recomendaciones y horarios de categorías.

Verifica los 5 puntos exigidos en docs/REVISION_RECOMENDACIONES_20261001.md:
1. El listado emitido por el bot no se interpreta como selección del cliente.
2. Peticiones de recomendación («que tours me recomiedas», «cuales me recomienedas»),
   rechazos («ninguno necesito que em recomiendes») y «otras opciones» continúan sin bucle.
3. Pregunta breve por preferencias si faltan; orienta con tours activos verificados al recibirlas.
4. Separación de duración y horario en categorías con campos vigentes (sin horarios antiguos).
5. Reproducción exacta de la conversación del usuario, variantes en inglés, preservación de
   aclaración legítima («fotos del otro») y actualización dinámica de horarios.
"""
import os
import sys
import unittest
from unittest.mock import patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import app
import catalog_service
import database
from starlette.testclient import TestClient


class TestRecommendationsAndSchedules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["META_ACCESS_TOKEN"] = "EAABtest_token_valid_12345"
        os.environ["META_PHONE_NUMBER_ID"] = "109876543210"
        database.init_db(app.SQLITE_DB_PATH)
        try:
            catalog_service.init_catalog_db()
        except Exception:
            pass

    def setUp(self):
        from types import SimpleNamespace
        app.get_llm = lambda: SimpleNamespace(invoke=lambda m: SimpleNamespace(content="Estamos ubicados en Carmen Quicllu #250 Cusco. Texeira Travel."))
        self.client = TestClient(app.app)
        self.test_uid = f"51999{os.urandom(3).hex()}"
        app.clear_history(self.test_uid)

    def _send(self, text: str, user_id: str = None) -> dict:
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
            }

    # -------------------------------------------------------------------------
    # 1. Reproducción de la conversación exacta y resolución del bucle de aclaración
    # -------------------------------------------------------------------------
    def test_reproduce_exact_pilot_conversation_no_clarification_loop(self):
        # Reproducir el escenario del piloto donde la categoría muestra Montaña de 7 Colores y Valle Sagrado
        all_tours = catalog_service.get_all_tours(active_only=False)
        for t in all_tours:
            if t["entity_id"] in ("laguna-humantay", "city-tour-cusco", "maras-moray"):
                catalog_service.upsert_tour({**t, "is_active": False})

        try:
            # Paso 1: Usuario consulta categoría Cusco
            r1 = self._send("categoria cusco")
            self.assertEqual(r1["status_code"], 200)
            self.assertIn("Montaña de 7 Colores", r1["sent_text"])
            self.assertIn("Valle Sagrado", r1["sent_text"])
            # Verificar horarios vigentes en el listado y ausencia de respaldo antiguo
            self.assertIn("04:30–17:00", r1["sent_text"].replace("-", "–"))
            self.assertIn("07:30–18:30", r1["sent_text"].replace("-", "–"))
            self.assertNotIn("04:00-18:30", r1["sent_text"])
            self.assertNotIn("07:00-18:30", r1["sent_text"])

            # Paso 2: Usuario escribe «que tours me recomiedas» (con errata real)
            r2 = self._send("que tours me recomiedas")
            self.assertEqual(r2["status_code"], 200)
            # NO debe caer en aclaración ambigua entre Montaña y Valle Sagrado
            self.assertNotIn("¿A cuál de los tours te refieres?", r2["sent_text"])
            self.assertNotIn("Conversamos sobre", r2["sent_text"])
            # Debe solicitar brevemente preferencias/tiempo
            self.assertTrue(
                "paisajes, sitios históricos o caminatas" in r2["sent_text"] or
                "interesa más" in r2["sent_text"] or
                "tiempo tienes" in r2["sent_text"]
            )

            # Paso 3: Usuario insiste «cuales me recomienedas» (segunda errata real)
            r3 = self._send("cuales me recomienedas")
            self.assertEqual(r3["status_code"], 200)
            self.assertNotIn("¿A cuál de los tours te refieres?", r3["sent_text"])
            self.assertNotIn("Conversamos sobre", r3["sent_text"])
            self.assertTrue("interesa más" in r3["sent_text"] or "tiempo tienes" in r3["sent_text"])

            # Paso 4: Usuario dice «ninguno necesito que em recomiendes» (rechazo + errata)
            r4 = self._send("ninguno necesito que em recomiendes")
            self.assertEqual(r4["status_code"], 200)
            self.assertNotIn("¿A cuál de los tours te refieres?", r4["sent_text"])
            self.assertNotIn("Conversamos sobre", r4["sent_text"])
            self.assertTrue("interesa más" in r4["sent_text"] or "tiempo tienes" in r4["sent_text"])

            # Paso 5: Usuario proporciona preferencias de interés
            r5 = self._send("me gustan los paisajes y caminatas")
            self.assertEqual(r5["status_code"], 200)
            # Debe orientar con datos de tours activos sin inventar
            self.assertIn("Montaña de 7 Colores", r5["sent_text"])
            self.assertTrue("04:30" in r5["sent_text"] or "Vinicunca" in r5["sent_text"])
        finally:
            for t in all_tours:
                catalog_service.upsert_tour({**t, "is_active": True})

    # -------------------------------------------------------------------------
    # 2. Variantes en inglés
    # -------------------------------------------------------------------------
    def test_english_recommendation_and_rejection_flow(self):
        uid_en = f"51998{os.urandom(3).hex()}"
        # Paso 1: Category
        r1 = self._send("category cusco", user_id=uid_en)
        self.assertEqual(r1["status_code"], 200)
        self.assertIn("Cusco", r1["sent_text"])

        # Paso 2: Recommendation inquiry
        r2 = self._send("what tours do you recommend", user_id=uid_en)
        self.assertEqual(r2["status_code"], 200)
        self.assertNotIn("Which tour are you referring to?", r2["sent_text"])
        self.assertTrue("landscapes, historical sites, or hiking" in r2["sent_text"])
        self.assertTrue("How much time" in r2["sent_text"])

        # Paso 3: Rejection variant
        r3 = self._send("neither, recommend me something", user_id=uid_en)
        self.assertEqual(r3["status_code"], 200)
        self.assertNotIn("Which tour are you referring to?", r3["sent_text"])
        self.assertTrue("landscapes" in r3["sent_text"])

        # Paso 4: Provide preferences in English
        r4 = self._send("I prefer historical sites and have one day", user_id=uid_en)
        self.assertEqual(r4["status_code"], 200)
        self.assertTrue("City Tour Cusco" in r4["sent_text"] or "Machu Picchu" in r4["sent_text"])

    # -------------------------------------------------------------------------
    # 3. Preservación de aclaración genuina («fotos del otro»)
    # -------------------------------------------------------------------------
    def test_genuine_ambiguity_preserved_when_referring_to_the_other(self):
        uid_amb = f"51997{os.urandom(3).hex()}"
        # El cliente humano compara explícitamente dos tours en su turno
        r1 = self._send("Me gusta el Camino Inca pero también el City Tour", user_id=uid_amb)
        self.assertEqual(r1["status_code"], 200)

        # Pregunta atributiva ambigua: "fotos del otro"
        r2 = self._send("¿tienes fotos del otro?", user_id=uid_amb)
        self.assertEqual(r2["status_code"], 200)
        # SÍ debe pedir aclaración porque la consulta es genuinamente ambigua
        self.assertTrue(
            "¿A cuál de los tours te refieres?" in r2["sent_text"] or
            "Conversamos sobre" in r2["sent_text"]
        )

    # -------------------------------------------------------------------------
    # 4. Cambio de tema y «otras opciones» después de listado
    # -------------------------------------------------------------------------
    def test_topic_change_and_other_options_after_listing(self):
        uid_tc = f"51996{os.urandom(3).hex()}"
        self._send("categoria cusco", user_id=uid_tc)

        # Caso A: Pregunta por otra opción / tours alternativos
        r_other = self._send("otras opciones", user_id=uid_tc)
        self.assertEqual(r_other["status_code"], 200)
        self.assertNotIn("¿A cuál de los tours te refieres?", r_other["sent_text"])
        self.assertTrue(
            "Catálogo de Experiencias" in r_other["sent_text"] or
            "categorías" in r_other["sent_text"].lower() or
            "interesa más" in r_other["sent_text"]
        )

        # Caso B: Pregunta de contacto / ubicación
        r_contact = self._send("¿Dónde queda su oficina?", user_id=uid_tc)
        self.assertEqual(r_contact["status_code"], 200)
        self.assertNotIn("¿A cuál de los tours te refieres?", r_contact["sent_text"])
        self.assertIn("Texeira Travel", r_contact["sent_text"])

        # Caso C: Consulta directa de precio de un tour
        r_price = self._send("¿Cuánto cuesta el City Tour?", user_id=uid_tc)
        self.assertEqual(r_price["status_code"], 200)
        self.assertNotIn("¿A cuál de los tours te refieres?", r_price["sent_text"])
        self.assertIn("City Tour", r_price["sent_text"])

    # -------------------------------------------------------------------------
    # 5. Separación de duración y horario y reflejo inmediato de cambios de catálogo
    # -------------------------------------------------------------------------
    def test_dynamic_catalog_schedule_update_reflected_in_listing(self):
        uid_sch = f"51995{os.urandom(3).hex()}"
        # Lectura inicial de categoría
        r_init = self._send("categoria cusco", user_id=uid_sch)
        self.assertIn("Montaña de 7 Colores", r_init["sent_text"])
        # Formato separado: (Duración | Horario)
        self.assertRegex(r_init["sent_text"], r"Montaña de 7 Colores\* \(Full Day \| 04:30[–-]17:00\)")

        # Modificación dinámica del horario de Montaña de 7 Colores en el catálogo
        orig_tour = catalog_service.get_tour_by_id("montana-7-colores") or {}
        new_data = dict(orig_tour)
        new_data["schedule"] = "05:00-16:30"
        catalog_service.upsert_tour(new_data)

        try:
            r_updated = self._send("categoria cusco", user_id=uid_sch)
            # El cambio debe verse reflejado inmediatamente
            self.assertIn("05:00-16:30", r_updated["sent_text"])
            self.assertRegex(r_updated["sent_text"], r"Montaña de 7 Colores\* \(Full Day \| 05:00-16:30\)")
        finally:
            # Restaurar horario original
            new_data["schedule"] = "04:30-17:00"
            catalog_service.upsert_tour(new_data)


if __name__ == "__main__":
    unittest.main()
