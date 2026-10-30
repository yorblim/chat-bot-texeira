"""Pruebas integrales de los 6 ajustes de consistencia 24/7 vs. horario laboral humano (UTC-5).

Valida uno por uno:
  1. Alineación de métrica `after_hours_count` y etiqueta `after_hours_label` (09:00–18:00 Lun–Sáb UTC-5)
     entre `database.py`, `RUBRICA_EVALUACION_ACADEMICA.md` y `admin_dashboard.py`.
  2. Conversión exacta de reloj UTC -> Cusco/Perú (UTC-5 fijo) y configuración dinámica en `/api/catalog/settings`.
  3. Mensajes honestos en madrugada/domingo (ES / EN / PT) sin prometer atención humana inmediata a las 3:00 a. m.
     y recordando que el asistente virtual sigue activo 24/7.
  4. Modo silencioso nocturno (`advisor_quiet_after_hours`) para no despertar el celular del asesor a las 3:00 a. m.
  5. Anexado quirúrgico de datos de pasajeros/hotel en tickets `pending` sin interceptar preguntas sobre tours.
  6. Detección de expiración de ventana de 24 h de Meta WhatsApp Cloud API (`error 131047`) en `/handoffs/data`.
"""
import hashlib
import hmac
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["TEXEIRA_ENABLE_WHATSAPP"] = "false"

import admin_dashboard
import app
import catalog_service
import conversation_memory
import database
import handoff_support as handoff
import operational_metrics
from auth_middleware import SESSION_COOKIE_NAME, create_session_token, panel_csrf_token
from db_adapter import get_db_session
from fastapi.testclient import TestClient


class AfterHoursAndConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.logs_db = str(base / "logs_test.db")
        self.requests_db = base / "requests_test.db"
        self.metrics_db = base / "metrics_test.db"

        env_clean = dict(
            os.environ,
            DATABASE_URL="",
            ADMIN_USER="",
            ADMIN_PASSWORD="",
            K_SERVICE="",
            ALLOW_CLOUD_RUN="",
            HANDOFF_PAUSE_TIMEOUT_HOURS="24",
        )
        p_env = patch.object(os, "environ", env_clean)
        p_env.start()
        self.addCleanup(p_env.stop)

        database.init_db(self.logs_db)
        isolated_mem = conversation_memory.ConversationMemory(lambda: self.logs_db, 20)

        patches = [
            patch.object(app, "SQLITE_DB_PATH", self.logs_db),
            patch.object(app, "META_APP_SECRET", "synthetic_secret_247"),
            patch.object(app, "conversation_history", isolated_mem),
            patch.object(handoff, "DB", self.requests_db),
            patch.object(handoff, "is_postgres", return_value=False),
            patch.object(operational_metrics, "DB", self.metrics_db),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        handoff._HOOKS.update(
            add_to_history=app.add_to_history,
            get_history=app.get_history,
            detect_language=app.detect_language,
        )

        # Limpiar ajustes dinámicos de agencia antes y después de cada test
        self._clean_agency_settings()
        self.addCleanup(self._clean_agency_settings)

        self.client = TestClient(app.app)
        self.addCleanup(self.client.close)

    def _clean_agency_settings(self):
        try:
            catalog_service.init_catalog_db()
            with get_db_session() as conn:
                conn.execute(
                    "DELETE FROM agency_settings WHERE key IN ("
                    "'advisor_whatsapp_phone', 'advisor_notifications_enabled', "
                    "'advisor_hours_enabled', 'advisor_hours_start', "
                    "'advisor_hours_end', 'advisor_workdays', 'advisor_quiet_after_hours')"
                )
        except Exception:
            pass

    def _post_wa_text(self, mid: str, phone: str, text: str):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"phone_number_id": "synthetic_phone_id"},
                        "contacts": [{"wa_id": phone}],
                        "messages": [{
                            "id": mid,
                            "from": phone,
                            "type": "text",
                            "timestamp": "1700000000",
                            "text": {"body": text},
                        }],
                    },
                }]
            }],
        }
        raw = json.dumps(payload).encode("utf-8")
        sig = "sha256=" + hmac.new(b"synthetic_secret_247", raw, hashlib.sha256).hexdigest()
        return self.client.post("/webhook", content=raw, headers={"X-Hub-Signature-256": sig})

    # ------------------------------------------------------------------
    # PROBLEMA 1: Alineación database.py <-> Rúbrica <-> admin_dashboard.py
    # ------------------------------------------------------------------
    def test_1_metrics_and_dashboard_label_aligned_with_cusco_mon_sat_09_18(self):
        # Insertar 4 interacciones con timestamps UTC exactos:
        # 1) Viernes 2026-10-30 15:00 UTC -> 10:00 Cusco (DENTRO de horario)
        # 2) Viernes 2026-10-30 08:15 UTC -> 03:15 Cusco (FUERA: madrugada)
        # 3) Viernes 2026-10-30 23:30 UTC -> 18:30 Cusco (FUERA: noche >= 18:00)
        # 4) Domingo 2026-11-01 16:00 UTC -> 11:00 Cusco Domingo (FUERA: domingo)
        rows = [
            ("2026-10-30 15:00:00", "u1", "Hola dentro"),
            ("2026-10-30 08:15:00", "u2", "Hola madrugada"),
            ("2026-10-30 23:30:00", "u3", "Hola noche"),
            ("2026-11-01 16:00:00", "u4", "Hola domingo"),
        ]
        with get_db_session(self.logs_db) as conn:
            for ts, uid, msg in rows:
                conn.execute(
                    """INSERT INTO interactions (
                        timestamp, user_id, channel, detected_language,
                        user_message, bot_response, resolved_autonomously,
                        latency_ms, escalated_to_human, is_predefined_response,
                        interaction_type, is_rate_limit
                    ) VALUES (?, ?, 'whatsapp', 'es', ?, 'ok', 1, 50.0, 0, 1, 'predefined', 0)""",
                    (ts, uid, msg),
                )

        summary = database.get_metrics_summary(self.logs_db)
        self.assertEqual(summary["total_interactions"], 4)
        self.assertEqual(summary["after_hours_count"], 3)
        self.assertEqual(summary["after_hours_pct"], 75.0)
        self.assertEqual(summary["after_hours_label"], "Fuera de Horario (18:00 - 09:00 · Dom)")

        html = admin_dashboard.get_dashboard_html(summary, [])
        self.assertIn("Fuera de Horario (18:00 - 09:00 · Dom)", html)
        self.assertNotIn("18:00 - 08:00", html)

    # ------------------------------------------------------------------
    # PROBLEMA 2: Conversión UTC -> UTC-5 Cusco + Configuración dinámica
    # ------------------------------------------------------------------
    def test_2_utc_to_peru_tz_and_dynamic_catalog_settings(self):
        # Viernes 08:30 UTC == 03:30 Cusco -> fuera de horario
        st_madrugada = handoff.get_advisor_schedule_status(now="2026-10-30T08:30:00+00:00")
        self.assertTrue(st_madrugada["after_hours"])
        self.assertFalse(st_madrugada["is_open"])
        self.assertEqual(st_madrugada["local_time"], "03:30")

        # Viernes 16:00 UTC == 11:00 Cusco -> dentro de horario
        st_manana = handoff.get_advisor_schedule_status(now="2026-10-30T16:00:00+00:00")
        self.assertFalse(st_manana["after_hours"])
        self.assertTrue(st_manana["is_open"])
        self.assertEqual(st_manana["local_time"], "11:00")

        # Domingo 16:00 UTC == 11:00 Cusco Domingo -> fuera de horario en Lun-Sáb
        st_domingo = handoff.get_advisor_schedule_status(now="2026-11-01T16:00:00+00:00")
        self.assertTrue(st_domingo["after_hours"])

        # Guardar horario personalizado vía /api/catalog/settings
        with patch.dict(os.environ, {"ADMIN_USER": "admin", "ADMIN_PASSWORD": "test-password-247"}):
            client_auth = TestClient(app.app, follow_redirects=False)
            token, _ = create_session_token("admin", remember=False)
            client_auth.cookies.set(SESSION_COOKIE_NAME, token)
            csrf = client_auth.get("/api/catalog/csrf-token").json()["csrf_token"]

            # Hora inválida debe rechazarse con 400
            bad_res = client_auth.post(
                "/api/catalog/settings",
                headers={"X-Catalog-CSRF": csrf},
                json={"advisor_hours_start": "29:99"},
            )
            self.assertEqual(bad_res.status_code, 400)

            save_res = client_auth.post(
                "/api/catalog/settings",
                headers={"X-Catalog-CSRF": csrf},
                json={
                    "advisor_hours_enabled": True,
                    "advisor_hours_start": "08:00",
                    "advisor_hours_end": "20:00",
                    "advisor_workdays": "everyday",
                    "advisor_quiet_after_hours": True,
                },
            )
            self.assertEqual(save_res.status_code, 200)
            cfg = client_auth.get("/api/catalog/settings").json()
            self.assertEqual(cfg["advisor_hours_start"], "08:00")
            self.assertEqual(cfg["advisor_hours_end"], "20:00")
            self.assertEqual(cfg["advisor_workdays"], "everyday")

        # Con 'everyday' 08:00-20:00, el domingo a las 11:00 Cusco ahora está ABIERTO
        st_domingo_open = handoff.get_advisor_schedule_status(now="2026-11-01T16:00:00+00:00")
        self.assertFalse(st_domingo_open["after_hours"])
        self.assertTrue(st_domingo_open["is_open"])

    # ------------------------------------------------------------------
    # PROBLEMA 3: Respuesta honesta en madrugada (ES/EN/PT) + bot 24/7
    # ------------------------------------------------------------------
    def test_3_after_hours_honest_messages_es_en_pt(self):
        ns = {"get_history": lambda uid: [], "conversation_history": {}}
        madrugada_utc = "2026-10-30T08:15:00+00:00"  # 03:15 Cusco
        dia_utc = "2026-10-30T16:15:00+00:00"        # 11:15 Cusco

        res_es = handoff.apply_request(
            ns,
            {"handoff_requested": True, "handoff_language": "es"},
            "turista_es_3am",
            "whatsapp",
            "Quiero reservar Valle Sagrado",
            now=madrugada_utc,
        )
        self.assertTrue(res_es["handoff_registered"])
        self.assertTrue(res_es["after_hours"])
        self.assertIn("03:15", res_es["response"])
        self.assertIn("09:00 a 18:00", res_es["response"])
        self.assertIn("24/7", res_es["response"])
        self.assertIn("aún no está confirmada", res_es["response"])
        self.assertNotIn("a la brevedad", res_es["response"])

        res_en = handoff.apply_request(
            ns,
            {"handoff_requested": True, "handoff_language": "en"},
            "turista_en_3am",
            "whatsapp",
            "I want to book Sacred Valley",
            now=madrugada_utc,
        )
        self.assertTrue(res_en["after_hours"])
        self.assertIn("Human advisor hours", res_en["response"])
        self.assertIn("03:15", res_en["response"])
        self.assertIn("24/7", res_en["response"])
        self.assertNotIn("shortly", res_en["response"])

        res_pt = handoff.apply_request(
            ns,
            {"handoff_requested": True, "handoff_language": "pt"},
            "turista_pt_3am",
            "whatsapp",
            "Quero reservar Valle Sagrado",
            now=madrugada_utc,
        )
        self.assertTrue(res_pt["after_hours"])
        self.assertIn("Horário de atendimento humano", res_pt["response"])
        self.assertIn("03:15", res_pt["response"])
        self.assertIn("24/7", res_pt["response"])

        # En horario laboral (11:15 Cusco) NO aparece el aviso de fuera de horario
        res_day = handoff.apply_request(
            ns,
            {"handoff_requested": True, "handoff_language": "es"},
            "turista_es_11am",
            "whatsapp",
            "Quiero reservar Valle Sagrado",
            now=dia_utc,
        )
        self.assertFalse(res_day["after_hours"])
        self.assertNotIn("Horario de atención humana", res_day["response"])

    # ------------------------------------------------------------------
    # PROBLEMA 4: Silencio de notificaciones push al celular a las 3:00 a. m.
    # ------------------------------------------------------------------
    def test_4_quiet_hours_silences_3am_push_but_keeps_pending_ticket(self):
        catalog_service.set_agency_setting("advisor_notifications_enabled", "true")
        catalog_service.set_agency_setting("advisor_quiet_after_hours", "true")
        mock_send = MagicMock(return_value=True)
        ns = {
            "get_history": lambda uid: [],
            "conversation_history": {},
            "send_whatsapp_message": mock_send,
        }

        # A las 03:20 Cusco: ticket creado en pending, pero celular del asesor NO suena
        res_night = handoff.apply_request(
            ns,
            {"handoff_requested": True, "handoff_language": "es"},
            "user_night_push",
            "whatsapp",
            "Quiero hablar con un asesor",
            now="2026-10-30T08:20:00+00:00",
        )
        self.assertTrue(res_night["handoff_registered"])
        self.assertEqual(mock_send.call_count, 0)

        # A las 10:20 Cusco: ticket creado Y celular del asesor SÍ recibe notificación push
        res_morning = handoff.apply_request(
            ns,
            {"handoff_requested": True, "handoff_language": "es"},
            "user_morning_push",
            "whatsapp",
            "Quiero hablar con un asesor",
            now="2026-10-30T15:20:00+00:00",
        )
        self.assertTrue(res_morning["handoff_registered"])
        self.assertEqual(mock_send.call_count, 1)

    # ------------------------------------------------------------------
    # PROBLEMA 5: Datos de pasajeros en ticket pending sin colisionar con RAG
    # ------------------------------------------------------------------
    def test_5_pending_passenger_details_appended_without_intercepting_tour_questions(self):
        phone = "51922333444"
        outbound = []

        def fake_wa_send(*, text="", to_phone=None, **kwargs):
            outbound.append({"text": text, "to_phone": to_phone})
            return True

        with patch.object(app, "send_whatsapp_message", side_effect=fake_wa_send), \
             patch("src.services.whatsapp.send_whatsapp_message", side_effect=fake_wa_send), \
             patch.object(handoff, "notify_advisor", return_value=True):

            # 1. Turista solicita reservar Valle Sagrado -> crea ticket pending
            r1 = self._post_wa_text("wamid.p1", phone, "Quiero reservar Valle Sagrado")
            self.assertEqual(r1.status_code, 200)
            rows = self.client.get("/handoffs/data").json()
            self.assertEqual(len(rows), 1)
            ticket_id = rows[0]["id"]
            self.assertEqual(rows[0]["status"], "pending")

            # 2. Turista envía sus datos de reserva sueltos -> se anexan al ticket sin caer en fallback
            r2 = self._post_wa_text(
                "wamid.p2",
                phone,
                "Mi nombre es Laura Gómez, somos 3 adultos, estamos en el Hotel Sonesta Cusco",
            )
            self.assertEqual(r2.status_code, 200)
            self.assertIn(f"#{ticket_id}", outbound[-1]["text"])
            self.assertIn("Anoté estos datos", outbound[-1]["text"])

            rows_after = self.client.get("/handoffs/data").json()
            self.assertIn("[Datos del cliente]: Mi nombre es Laura Gómez", rows_after[0]["note"])
            self.assertIn("Hotel Sonesta Cusco", rows_after[0]["note"])

            # 3. Turista hace una pregunta normal sobre el tour mientras sigue pending -> responde el bot 24/7
            r3 = self._post_wa_text("wamid.p3", phone, "¿Qué incluye Valle Sagrado?")
            self.assertEqual(r3.status_code, 200)
            self.assertNotIn("Anoté estos datos", outbound[-1]["text"])
            self.assertIn("Valle Sagrado", outbound[-1]["text"])

            # 4. También funciona en /test-chat
            tc1 = self.client.post(
                "/test-chat",
                json={"user_id": "tc_pending_user", "message": "Quiero reservar City Tour"},
            ).json()
            self.assertTrue(tc1["escalated_to_human"])
            tc_ticket = tc1["handoff_id"]

            tc2 = self.client.post(
                "/test-chat",
                json={"user_id": "tc_pending_user", "message": "Somos 2 adultos, Hotel Novotel Cusco"},
            ).json()
            self.assertEqual(tc2["route"], "human_request_details")
            self.assertIn(f"#{tc_ticket}", tc2["response"])

    # ------------------------------------------------------------------
    # PROBLEMA 6: Alerta de ventana de 24 h de Meta WhatsApp en /handoffs
    # ------------------------------------------------------------------
    def test_6_whatsapp_24h_window_expiry_in_handoffs_data_and_panel(self):
        # Crear ticket antiguo (> 26 horas) y ticket reciente (1 hora)
        old_row, _ = handoff.create_request("51977888999", "whatsapp", "[Reserva] Machu Picchu", [])
        fresh_row, _ = handoff.create_request("51966555444", "whatsapp", "[Reserva] City Tour", [])

        old_iso = (datetime.now(timezone.utc) - timedelta(hours=26, minutes=30)).isoformat()
        with handoff.connection() as conn:
            conn.execute(
                "UPDATE requests SET created_at=?, updated_at=? WHERE id=?",
                (old_iso, old_iso, old_row["id"]),
            )

        rows = self.client.get("/handoffs/data").json()
        by_id = {r["id"]: r for r in rows}

        self.assertTrue(by_id[old_row["id"]]["window_24h_expired"])
        self.assertGreaterEqual(by_id[old_row["id"]]["hours_since_customer"], 26.0)
        self.assertEqual(by_id[old_row["id"]]["customer_wa_url"], "https://wa.me/51977888999")

        self.assertFalse(by_id[fresh_row["id"]]["window_24h_expired"])
        self.assertLess(by_id[fresh_row["id"]]["hours_since_customer"], 1.0)

        panel_html = self.client.get("/handoffs").text
        self.assertIn("window-expired-banner", panel_html)
        self.assertIn("131047", panel_html)


if __name__ == "__main__":
    unittest.main()
