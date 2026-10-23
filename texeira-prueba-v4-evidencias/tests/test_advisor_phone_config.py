import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from handoff_support import (
    get_advisor_whatsapp_phone,
    get_advisor_whatsapp_link_text,
    apply_request,
)

class TestAdvisorPhoneConfig(unittest.TestCase):

    def setUp(self):
        try:
            from db_adapter import get_db_session
            from catalog_service import init_catalog_db
            init_catalog_db()
            with get_db_session() as conn:
                conn.execute("DELETE FROM agency_settings WHERE key IN ('advisor_whatsapp_phone', 'advisor_notifications_enabled')")
        except Exception:
            pass

    def tearDown(self):
        try:
            from db_adapter import get_db_session
            with get_db_session() as conn:
                conn.execute("DELETE FROM agency_settings WHERE key IN ('advisor_whatsapp_phone', 'advisor_notifications_enabled')")
        except Exception:
            pass

    def test_default_phone_when_env_not_set(self):
        with patch.dict(os.environ, {}, clear=True):
            phone = get_advisor_whatsapp_phone()
            self.assertEqual(phone, "51953767860")
            link_es = get_advisor_whatsapp_link_text("es")
            self.assertIn("https://wa.me/51953767860", link_es)

    def test_custom_advisor_phone_env(self):
        with patch.dict(os.environ, {"ADVISOR_PHONE": "51984679715"}):
            phone = get_advisor_whatsapp_phone()
            self.assertEqual(phone, "51984679715")
            link_es = get_advisor_whatsapp_link_text("es")
            self.assertIn("https://wa.me/51984679715", link_es)

    def test_9_digit_normalization(self):
        with patch.dict(os.environ, {"ADVISOR_PHONE": "984679715"}):
            phone = get_advisor_whatsapp_phone()
            self.assertEqual(phone, "51984679715")
            link_en = get_advisor_whatsapp_link_text("en")
            self.assertIn("https://wa.me/51984679715", link_en)
            self.assertIn("contact our advisor directly on WhatsApp", link_en)

    def test_phone_with_formatting_cleaned(self):
        with patch.dict(os.environ, {"ADVISOR_WHATSAPP_PHONE": "+51 984-679-715"}):
            phone = get_advisor_whatsapp_phone()
            self.assertEqual(phone, "51984679715")
            link_pt = get_advisor_whatsapp_link_text("pt")
            self.assertIn("https://wa.me/51984679715", link_pt)
            self.assertIn("falar diretamente com nosso assessor no WhatsApp", link_pt)

    def test_disabled_advisor_phone(self):
        for val in ["disabled", "none", "false", "0", "off", ""]:
            with patch.dict(os.environ, {"ADVISOR_PHONE": val}):
                phone = get_advisor_whatsapp_phone()
                self.assertIsNone(phone, f"Fallo al deshabilitar con valor: {val}")
                link = get_advisor_whatsapp_link_text("es")
                self.assertEqual(link, "")

    def test_handoff_response_contains_configured_link(self):
        with patch.dict(os.environ, {"ADVISOR_PHONE": "51911223344"}):
            ns = {
                'get_history': lambda uid: [],
                'conversation_history': {},
            }
            res_input = {'handoff_requested': True, 'handoff_language': 'es'}
            res = apply_request(ns, res_input, 'test_user_cfg_link', 'whatsapp', 'quiero hablar con un asesor')
            self.assertEqual(res.get('handoff_registered'), True)
            self.assertIn("https://wa.me/51911223344", res.get('response', ''))

    def test_handoff_response_omits_link_when_disabled(self):
        with patch.dict(os.environ, {"ADVISOR_PHONE": "disabled"}):
            ns = {
                'get_history': lambda uid: [],
                'conversation_history': {},
            }
            res_input = {'handoff_requested': True, 'handoff_language': 'es'}
            res = apply_request(ns, res_input, 'test_user_cfg_nolink', 'whatsapp', 'quiero hablar con un asesor')
            self.assertEqual(res.get('handoff_registered'), True)
            self.assertNotIn("wa.me", res.get('response', ''))
            self.assertIn("pendiente de atención humana", res.get('response', ''))

    def test_db_setting_priority_over_env(self):
        from catalog_service import set_agency_setting
        set_agency_setting("advisor_whatsapp_phone", "51988887777")
        with patch.dict(os.environ, {"ADVISOR_PHONE": "51900000000"}):
            phone = get_advisor_whatsapp_phone()
            self.assertEqual(phone, "51988887777")
            link_es = get_advisor_whatsapp_link_text("es")
            self.assertIn("https://wa.me/51988887777", link_es)

    def test_db_setting_normalization(self):
        from catalog_service import set_agency_setting
        set_agency_setting("advisor_whatsapp_phone", "+51 987-654-321")
        phone = get_advisor_whatsapp_phone()
        self.assertEqual(phone, "51987654321")

    def test_api_catalog_settings_routes(self):
        with patch.dict(os.environ, {"ADMIN_USER": "admin", "ADMIN_PASSWORD": "test-password-2026"}):
            from fastapi.testclient import TestClient
            import app
            from auth_middleware import create_session_token, SESSION_COOKIE_NAME, panel_csrf_token

            client = TestClient(app.app, follow_redirects=False)
            # 1. No auth -> 401
            res_unauth = client.get("/api/catalog/settings")
            self.assertEqual(res_unauth.status_code, 401)

            # 2. Get CSRF token with valid session
            token, _ = create_session_token("admin", remember=False)
            client.cookies.set(SESSION_COOKIE_NAME, token)

            # Usamos el panel csrf token correspondiente al catálogo
            csrf_token = panel_csrf_token("catalog")

            # 3. GET settings
            res_get = client.get("/api/catalog/settings")
            self.assertEqual(res_get.status_code, 200)
            self.assertTrue(res_get.json().get("ok"))

            # 4. POST settings
            res_post = client.post(
                "/api/catalog/settings",
                headers={"X-Catalog-CSRF": csrf_token},
                json={
                    "advisor_whatsapp_phone": "51977665544",
                    "advisor_notifications_enabled": True,
                },
            )
            self.assertEqual(res_post.status_code, 200)
            self.assertTrue(res_post.json().get("ok"))

            # 5. Verify GET updated
            res_get_updated = client.get("/api/catalog/settings")
            data = res_get_updated.json()
            self.assertEqual(data.get("advisor_whatsapp_phone"), "51977665544")
            self.assertEqual(data.get("advisor_notifications_enabled"), True)

            # 6. Verify handoff support reflects the new phone
            phone_updated = get_advisor_whatsapp_phone()
            self.assertEqual(phone_updated, "51977665544")


if __name__ == '__main__':
    unittest.main()

