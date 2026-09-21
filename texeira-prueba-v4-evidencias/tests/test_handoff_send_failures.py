"""Regresiones de envío: solo datos temporales y proveedor simulado."""
import asyncio
import os
import re
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
import app
import handoff_support as h


class SendFailures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, DATABASE_URL='', ADMIN_USER='', ADMIN_PASSWORD='', ALLOW_CLOUD_RUN='')
        self.env.start()
        self.db = patch.object(h, 'DB', Path(self.tmp.name) / 'requests.db')
        self.db.start()
        self.sender = patch('src.services.whatsapp.send_whatsapp_message', return_value=True)
        self.send = self.sender.start()
        self.ticket = h.create_request('synthetic-recipient', 'whatsapp', 'test', [])[0]['id']

    def tearDown(self):
        self.sender.stop()
        self.db.stop()
        self.env.stop()
        self.tmp.cleanup()

    def state(self):
        with h.connection() as conn:
            return dict(conn.execute('SELECT * FROM requests WHERE id=?', (self.ticket,)).fetchone())

    def post(self, **overrides):
        body = dict(status='closed', advisor='Prueba', note='Respuesta de prueba', send_to_customer=True)
        body.update(overrides)
        async def call():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app), base_url='http://test') as client:
                page = (await client.get('/handoffs')).text
                token = re.search(r"'X-Handoff-CSRF':'([^']+)'", page).group(1)
                return await client.post('/handoffs/' + self.ticket, headers={'X-Handoff-CSRF': token}, json=body)
        return asyncio.run(call())

    def test_invalid_transition_does_not_send(self):
        self.assertEqual(self.post().status_code, 400)
        self.send.assert_not_called()
        self.assertEqual(self.state()['status'], 'pending')

    def test_invalid_advisor_and_boolean_do_not_send(self):
        h.update_request(self.ticket, 'in_progress', 'Prueba', '')
        self.assertEqual(self.post(advisor=' ').status_code, 400)
        self.assertEqual(self.post(send_to_customer='false').status_code, 400)
        self.send.assert_not_called()

    def test_failure_rolls_back_all_fields(self):
        h.update_request(self.ticket, 'in_progress', 'Original', 'Nota anterior')
        before = self.state()
        self.send.return_value = False
        response = self.post()
        self.assertEqual(response.status_code, 502)
        self.assertFalse(response.json()['ok'])
        self.assertEqual(self.state(), before)

    def test_exception_rolls_back_without_leaking_provider_error(self):
        h.update_request(self.ticket, 'in_progress', 'Original', '')
        before = self.state()
        self.send.side_effect = TimeoutError('sensitive-provider-detail')
        response = self.post()
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('sensitive-provider-detail', response.text)
        self.assertEqual(self.state(), before)

    def test_success_then_repeated_close_sends_once(self):
        h.update_request(self.ticket, 'in_progress', 'Prueba', '')
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.state()['status'], 'closed')
        self.assertEqual(self.post().status_code, 400)
        self.send.assert_called_once()

    def test_internal_note_never_sends(self):
        h.update_request(self.ticket, 'in_progress', 'Prueba', '')
        self.assertEqual(self.post(send_to_customer=False).status_code, 200)
        self.send.assert_not_called()

    def test_concurrent_closures_send_once(self):
        h.update_request(self.ticket, 'in_progress', 'Prueba', '')
        def close(_):
            try:
                h.update_request(self.ticket, 'closed', 'Prueba', 'Respuesta', True)
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(close, range(2)))
        self.assertEqual(sorted(results), [False, True])
        self.send.assert_called_once()


if __name__ == '__main__':
    unittest.main()
