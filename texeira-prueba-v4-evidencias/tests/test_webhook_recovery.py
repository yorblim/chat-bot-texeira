"""Recuperación de fallos y protección HTTP con datos sintéticos, sin red externa."""
import hashlib
import hmac
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['TEXEIRA_ENABLE_WHATSAPP'] = 'false'
import app
import database
import operational_metrics
import whatsapp_entry
from fastapi.testclient import TestClient


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = str(Path(self.temp.name) / 'webhook.db')
        for target, name, value in [(os, 'environ', dict(os.environ, DATABASE_URL='', ADMIN_USER='', ADMIN_PASSWORD='', K_SERVICE='', ALLOW_CLOUD_RUN=''))]:
            p = patch.object(target, name, value); p.start(); self.addCleanup(p.stop)
        database.init_db(self.db)
        for target, name, value in [(app, 'SQLITE_DB_PATH', self.db), (app, 'META_APP_SECRET', 'synthetic'),
                                    (operational_metrics, 'DB', Path(self.temp.name) / 'metrics.db')]:
            p = patch.object(target, name, value); p.start(); self.addCleanup(p.stop)
        self.client = TestClient(app.app)
        self.addCleanup(self.client.close)

    def send(self, mid='retry', text='¿Qué incluye City Tour?'):
        # También debe recuperarse un reintento cuyo timestamp supere 120 segundos.
        raw = json.dumps({'entry': [{'changes': [{'value': {'messages': [
            {'id': mid, 'from': '51900000000', 'type': 'text', 'timestamp': '1', 'text': {'body': text}}
        ]}}]}]}).encode()
        sig = 'sha256=' + hmac.new(b'synthetic', raw, hashlib.sha256).hexdigest()
        return self.client.post('/webhook', content=raw, headers={'X-Hub-Signature-256': sig})

    def test_processing_failure_retries_then_deduplicates(self):
        answer = {'response': 'Tour disponible', 'is_fallback': False, 'response_route': 'evidence_confirmed'}
        with patch.object(app, 'rag_chain', side_effect=[RuntimeError('private-error'), answer]) as rag, \
             patch.object(app, 'send_whatsapp_message', return_value=True) as send, \
             patch.object(app, 'send_whatsapp_image') as image:
            response = self.send()
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('private-error', response.text)
            self.assertEqual(self.send().status_code, 200)
            self.assertTrue(self.send().json()['dedup'])
            self.assertEqual(rag.call_count, 2)
            send.assert_called_once()
            image.assert_not_called()

    def test_rejected_send_is_retryable_and_interaction_is_unique(self):
        with patch.object(app, 'rag_chain', return_value={'response': 'Hola', 'is_fallback': False}), \
             patch.object(app, 'send_whatsapp_message', side_effect=[False, True]) as send:
            self.assertEqual(self.send().status_code, 503)
            self.assertEqual(self.send().status_code, 200)
            self.assertEqual(send.call_count, 2)
            self.assertEqual(database.get_metrics_summary(self.db)['total_interactions'], 1)

    def test_send_exception_does_not_mark_completed(self):
        with patch.object(app, 'rag_chain', return_value={'response': 'Hola', 'is_fallback': False}), \
             patch.object(app, 'send_whatsapp_message', side_effect=[RuntimeError('offline'), True]):
            self.assertEqual(self.send().status_code, 503)
            self.assertEqual(self.send().status_code, 200)
            self.assertTrue(self.send().json()['dedup'])

    def test_busy_receipt_does_not_ack_or_process(self):
        state, owner = database.claim_webhook('retry', 'synthetic', self.db)
        self.assertEqual(state, 'claimed')
        with patch.object(app, 'rag_chain') as rag:
            self.assertEqual(self.send().status_code, 503)
            rag.assert_not_called()
        database.finish_webhook('retry', owner, False, self.db)

    def test_lists_and_help_send_neither_images_nor_phone_numbers(self):
        import re
        with patch.object(app, 'get_llm', side_effect=AssertionError('No proveedor externo')), \
             patch.object(app, 'send_whatsapp_message', return_value=True) as send, \
             patch.object(app, 'send_whatsapp_image') as image:
            for index, question in enumerate(['¿Qué tours tienen?', 'Me ayudas']):
                self.assertEqual(self.send(str(index), question).status_code, 200)
                self.assertIsNone(re.search(r'\b\d{9,}\b', send.call_args.kwargs['text']))
            image.assert_not_called()

    def test_public_ready_entry_and_direct_app_protect_internal_routes(self):
        with patch.dict(os.environ, ADMIN_USER='review', ADMIN_PASSWORD='synthetic'), \
             patch.dict(whatsapp_entry._state, ready=True, local_app=app.app, error=None):
            for target in [app.app, whatsapp_entry.app]:
                client = TestClient(target)  # No startup: evita cargar embeddings/proveedores.
                try:
                    for method, path in [('GET', '/history/synthetic'), ('DELETE', '/history/synthetic'),
                                         ('GET', '/metrics'), ('POST', '/test-chat'), ('GET', '/dashboard')]:
                        self.assertEqual(client.request(method, path).status_code, 401, path)
                    self.assertEqual(client.get('/history/synthetic', auth=('review', 'synthetic')).status_code, 200)
                finally:
                    client.close()
        with patch.dict(os.environ, K_SERVICE='synthetic', ADMIN_USER='', ADMIN_PASSWORD=''):
            self.assertEqual(self.client.get('/metrics').status_code, 401)


if __name__ == '__main__':
    unittest.main()
