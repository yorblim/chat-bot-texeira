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

if __name__ == '__main__':
    unittest.main()
