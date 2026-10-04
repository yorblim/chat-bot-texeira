"""Panel/API -> DB -> actual bot routing. Synthetic data; use run_isolated.py."""
import os
import unittest
import hashlib
import hmac
import json
from unittest.mock import patch
if os.environ.get('TEXEIRA_ISOLATED_TEST') != '1':
    raise SystemExit('Run: python tests/run_isolated.py test_catalog_connected_flow.py')
import app
import catalog_service as service
from fastapi.testclient import TestClient


class ConnectedCatalogTests(unittest.TestCase):
    def setUp(self):
        app.database.init_db(app.SQLITE_DB_PATH)
        self.client = TestClient(app.app)
        self.addCleanup(self.client.close)
        self.token = self.client.get('/api/catalog/csrf-token').json()['csrf_token']
        self.headers = {'X-Catalog-CSRF': self.token}

    def save(self, **fields):
        data = dict(entity_id='city-tour-cusco', name='City Tour Cusco',
                    aliases=['city tour'], official_price='123', currency='PEN',
                    schedule='09:15-15:45', duration='6 horas',
                    includes='Guía privado y merienda', excludes='Transporte privado', is_active=True)
        data.update(fields)
        response = self.client.post('/api/catalog/tours', json=data, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)

    def ask(self, question):
        return app.rag_chain(question, 'connected-' + self.id())

    def test_panel_schedule_replaces_historical_fact(self):
        self.save()
        reply = self.ask('¿Qué horario tiene City Tour?')
        self.assertIn('09:15-15:45', reply['response'])
        self.assertNotIn('10:00-14:00', reply['response'])

    def test_panel_inclusions_replace_historical_fact(self):
        self.save()
        reply = self.ask('¿Qué incluye City Tour?')
        self.assertIn('merienda', reply['response'])

    def test_custom_tour_appears_in_listing(self):
        self.save(entity_id='synthetic-mirador', name='Mirador de Prueba', aliases=['mirador de prueba'], includes='Vista panoramica')
        reply = self.ask('¿Qué incluye Mirador de Prueba?')
        self.assertIn('Vista panoramica', reply['response'])

    def test_partial_edit_preserves_inclusions_and_cleared_schedule_stays_unknown(self):
        self.save()
        self.assertTrue(service.upsert_tour(dict(entity_id='city-tour-cusco', name='City Tour Cusco', official_price='140'))[0])
        self.assertIn('merienda', self.ask('¿Qué incluye City Tour?')['response'])
        self.assertTrue(service.upsert_tour(dict(entity_id='city-tour-cusco', name='City Tour Cusco', schedule=''))[0])
        self.assertTrue(self.ask('¿Qué horario tiene City Tour?')['needs_agency_confirmation'])

    def test_api_rates_are_used_by_bot_and_update_without_restart(self):
        self.save()
        path = '/api/catalog/tours/city-tour-cusco/rates'
        rate = dict(rate_name='Estudiante prueba', rate_category='student', price='50',
                    currency='PEN', conditions='Carnet vigente', is_active=True)
        saved = self.client.post(path, json=rate, headers=self.headers)
        self.assertEqual(saved.status_code, 200, saved.text)
        rate['id'] = saved.json()['rate_id']
        try:
            rows = self.client.get(path + '?all=1').json()
            self.assertTrue(any(r['id'] == rate['id'] for r in rows))
            reply = self.ask('Precio del City Tour para estudiantes')
            self.assertIn('50 PEN', reply['response'])
            self.assertIn('Carnet vigente', reply['response'])
            rate['price'] = '55'
            self.assertEqual(self.client.post(path, json=rate, headers=self.headers).status_code, 200)
            self.assertIn('55 PEN', self.ask('Precio del City Tour para estudiantes')['response'])
        finally:
            self.client.delete('/api/catalog/rates/' + str(rate['id']), headers=self.headers)

    def test_nonprice_question_about_children_is_not_answered_with_price(self):
        self.save()
        reply = self.ask('¿El City Tour es seguro para niños?')
        self.assertNotIn(reply.get('response_route'), ('evidence_special_rate', 'evidence_no_special_rate', 'evidence_tour_overview'))
        self.assertTrue(reply.get('needs_agency_confirmation'))

    def test_missing_rate_requires_confirmation(self):
        self.save()
        reply = self.ask('Precio del City Tour para niños')
        self.assertTrue(reply.get('needs_agency_confirmation'))
        self.assertFalse(reply.get('resolved_autonomously'))

    def test_database_failure_does_not_restore_static_offers(self):
        with patch.object(service, 'get_all_tours', side_effect=RuntimeError('synthetic outage')):
            reply = self.ask('¿Qué tours tienen?')
        self.assertIn(reply['response_route'], ('catalog_unavailable', 'evidence_catalog_error'))
        self.assertTrue(reply['needs_agency_confirmation'])

    def test_panel_edit_reaches_actual_whatsapp_handler(self):
        self.save(official_price='147')
        body = json.dumps({'entry': [{'changes': [{'value': {'messages': [{
            'id': 'synthetic-connected-price', 'from': '51900000000', 'type': 'text',
            'text': {'body': 'Precio del City Tour'}, 'timestamp': '1'
        }]}}]}]}).encode()
        signature = 'sha256=' + hmac.new(b'synthetic', body, hashlib.sha256).hexdigest()
        with patch.object(app, 'META_APP_SECRET', 'synthetic'), \
             patch.object(app, 'send_whatsapp_message', return_value=True) as send, \
             patch.object(app, 'send_whatsapp_image') as image:
            response = self.client.post('/webhook', content=body, headers={'X-Hub-Signature-256': signature})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn('147 PEN', str(send.call_args))
            image.assert_not_called()

    def test_rates_reject_invalid_and_nonexistent_parents(self):
        self.save()
        base = dict(entity_id='city-tour-cusco', rate_category='student',
                    rate_name='Synthetic', price='50', currency='PEN', is_active=True)
        for invalid in ({'price': '-1'}, {'price': 'NaN'}, {'price': 'gratis'},
                        {'valid_from': '2026-99-30'},
                        {'valid_from': '2026-09-30', 'valid_to': '2026-09-01'},
                        {'currency': 'XXX'}, {'is_active': 'false'},
                        {'entity_id': 'does-not-exist'}, {'id': 999999}):
            with self.subTest(invalid=invalid):
                self.assertFalse(service.upsert_tour_rate(dict(base, **invalid))[0])


    def test_new_tour_creation_category_navigation_and_deactivation_cycle(self):
        """Punto 8 del informe:
        Tour nuevo activo -> aparece en su categoría y puede seleccionarse -> datos guardados consultables;
        Tour desactivado -> no ofertado en la categoría ni en consultas.
        """
        eid = 'canon-tinajani-trek'
        tour_payload = dict(
            entity_id=eid,
            name='Cañón de Tinajani Trek',
            aliases=['tinajani', 'canon de tinajani'],
            official_price='180',
            currency='PEN',
            schedule='06:00-18:00',
            duration='Día completo',
            includes='Transporte turístico, guía profesional y almuerzo campestre',
            excludes='Entradas personales',
            is_active=True
        )
        resp = self.client.post('/api/catalog/tours', json=tour_payload, headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)

        # 2. Navegar por categorías: clasificado como 'treks' debido a 'Trek' en el nombre
        # Con 10 tours y 2 por página, el nuevo tour se encuentra en la página índice 4 (página 5 de 5 en UI)
        cat_reply = self.ask('categoria treks pagina 4')
        self.assertEqual(cat_reply.get('response_route'), 'evidence_category_tours')
        self.assertIn('Cañón de Tinajani Trek', cat_reply['response'])

        # 3. Consulta de datos guardados del tour nuevo
        price_reply = self.ask('¿Cuánto cuesta el Cañón de Tinajani Trek?')
        self.assertIn('180 PEN', price_reply['response'])

        inc_reply = self.ask('¿Qué incluye Cañón de Tinajani Trek?')
        self.assertIn('almuerzo campestre', inc_reply['response'])

        # 4. Desactivar el tour
        tour_payload['is_active'] = False
        resp_deact = self.client.post('/api/catalog/tours', json=tour_payload, headers=self.headers)
        self.assertEqual(resp_deact.status_code, 200, resp_deact.text)

        # 5. Ya no debe aparecer en la categoría
        cat_reply_deact = self.ask('categoria treks pagina 4')
        self.assertNotIn('Cañón de Tinajani Trek', cat_reply_deact['response'])

        # 6. Preguntar directamente por el tour desactivado
        reply_deact_ask = self.ask('¿Cuánto cuesta el Cañón de Tinajani Trek?')
        self.assertTrue(
            reply_deact_ask.get('response_route') in ('evidence_inactive_tour', 'evidence_unknown', 'unknown') or
            'no disponible' in reply_deact_ask['response'].lower() or
            'inactivo' in reply_deact_ask['response'].lower() or
            'asesor' in reply_deact_ask['response'].lower() or
            reply_deact_ask.get('needs_agency_confirmation')
        )


if __name__ == '__main__':
    unittest.main()
