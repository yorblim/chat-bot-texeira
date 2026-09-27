"""CSRF entre instancias/reinicios; sin DB, proveedores ni datos reales."""
import os
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import FastAPI
from fastapi.testclient import TestClient

fake_service = ModuleType('catalog_service')
fake_service.IMAGES_DIR = Path('.')
fake_service.BROCHURES_DIR = Path('.')
fake_service.init_catalog_db = Mock()
fake_service.upsert_tour = Mock(return_value=(True, 'synthetic-tour'))
with patch.dict(sys.modules, {'catalog_service': fake_service}):
    import catalog_support
from auth_middleware import install_auth, panel_csrf_token


class CatalogCsrfTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            'ADMIN_USER': 'test-admin', 'ADMIN_PASSWORD': 'synthetic-test-password',
            'K_SERVICE': 'synthetic-cloud-service',
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        fake_service.upsert_tour.reset_mock()

    def client(self):
        app = FastAPI()
        install_auth(app)
        catalog_support.install(app)
        return TestClient(app)

    @property
    def auth(self):
        return ('test-admin', os.environ['ADMIN_PASSWORD'])

    def token(self, client):
        response = client.get('/api/catalog/csrf-token', auth=self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        return response.json()['csrf_token']

    def test_token_from_other_instance_or_before_restart_is_accepted(self):
        first = self.client()
        token = self.token(first)
        second = self.client()
        self.assertEqual(token, self.token(second))
        response = second.post('/api/catalog/tours', json={}, auth=self.auth,
                               headers={'X-Catalog-CSRF': token})
        self.assertEqual(response.status_code, 200)
        fake_service.upsert_tour.assert_called_once()

    def test_missing_and_wrong_tokens_cannot_mutate(self):
        client = self.client()
        for headers in ({}, {'X-Catalog-CSRF': 'wrong'}):
            response = client.post('/api/catalog/tours', json={}, auth=self.auth, headers=headers)
            self.assertEqual(response.status_code, 403)
        fake_service.upsert_tour.assert_not_called()

    def test_token_does_not_replace_authentication(self):
        client = self.client()
        token = self.token(client)
        for path in ('/catalogo', '/api/catalog/csrf-token'):
            self.assertEqual(client.get(path).status_code, 401)
        response = client.post('/api/catalog/tours', json={}, headers={'X-Catalog-CSRF': token})
        self.assertEqual(response.status_code, 401)
        fake_service.upsert_tour.assert_not_called()

    def test_password_rotation_invalidates_old_token(self):
        old = self.token(self.client())
        os.environ['ADMIN_PASSWORD'] = 'new-synthetic-password'
        client = self.client()
        self.assertNotEqual(old, self.token(client))
        self.assertEqual(client.post('/api/catalog/tours', json={}, auth=self.auth,
                         headers={'X-Catalog-CSRF': old}).status_code, 403)

    def test_page_uses_current_token_and_disables_cache(self):
        client = self.client()
        response = client.get('/catalogo', auth=self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertIn(self.token(client), response.text)

    def test_panels_have_stable_but_distinct_tokens(self):
        self.assertEqual(panel_csrf_token('handoff'), panel_csrf_token('handoff'))
        self.assertNotEqual(panel_csrf_token('handoff'), panel_csrf_token('catalog'))


if __name__ == '__main__':
    unittest.main()
