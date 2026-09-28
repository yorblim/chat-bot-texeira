"""Independent edge cases for 6951168; use tests/run_isolated.py."""
import os
import json
import hmac
import hashlib
import unittest
from unittest.mock import patch
assert os.environ.get('TEXEIRA_ISOLATED_TEST') == '1'
import app
import catalog_service
from fastapi.testclient import TestClient

class Review(unittest.TestCase):
    def setUp(self):
        app.database.init_db(app.SQLITE_DB_PATH)
        self.client = TestClient(app.app)
        self.addCleanup(self.client.close)
        self.uid = 'synthetic-' + self._testMethodName

    def click(self, button):
        body = json.dumps({'entry':[{'changes':[{'value':{'messages':[{
            'id': self.uid, 'from': self.uid, 'type':'interactive',
            'interactive':{'type':'button_reply','button_reply':{'id':button,'title':'Rates'}}
        }]}}]}]}).encode()
        sig = 'sha256=' + hmac.new(b'synthetic', body, hashlib.sha256).hexdigest()
        with patch.object(app, 'META_APP_SECRET', 'synthetic'), \
             patch.object(app, 'send_whatsapp_message', return_value=True) as send, \
             patch.object(app.database, 'log_interaction') as log:
            response = self.client.post('/webhook', content=body, headers={'X-Hub-Signature-256':sig})
            self.assertEqual(response.status_code, 200, response.text)
            return send.call_args.kwargs, log.call_args.kwargs

    def test_empty_catalog_does_not_offer_tours(self):
        with patch.object(catalog_service, 'get_all_tours', return_value=[]):
            buttons = app._get_active_catalog_tour_buttons('es')
        self.assertFalse(any(b['id'].startswith('btn_tour:') for b in buttons), buttons)

    def test_city_tour_rates_preserve_explicit_english(self):
        sent, log = self.click('btn_rates:city-tour-cusco:en')
        self.assertEqual(log['detected_language'], 'en', sent)
        self.assertTrue(all(b['id'].endswith(':en') for b in sent['buttons']), sent)

    def test_clarification_is_not_resolved(self):
        app.rag_chain('informacion de Camino Inca', self.uid)
        app.rag_chain('informacion de City Tour', self.uid)
        sent, log = self.click('btn_inc')
        self.assertFalse(log['resolved_autonomously'], sent)

if __name__ == '__main__':
    unittest.main()
