import unittest
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fastapi.testclient import TestClient
from app import app, rag_chain
import catalog_service
import catalog_ui


class TestTourAvailabilityAndSoldOut(unittest.TestCase):
    def setUp(self):
        catalog_service.init_catalog_db()
        self.client = TestClient(app)

    def tearDown(self):
        # Restaurar estado por defecto si algún tour fue modificado
        try:
            catalog_service.upsert_tour({
                'entity_id': 'camino-inka',
                'name': 'Camino Inka Clásico 4D/3N',
                'availability': 'available'
            })
            catalog_service.upsert_tour({
                'entity_id': 'city-tour-cusco',
                'name': 'City Tour Cusco',
                'availability': 'available'
            })
        except Exception:
            pass

    # ----------------------------------------------------
    # 1. Catálogo y Persistencia de Disponibilidad
    # ----------------------------------------------------
    def test_catalog_service_availability_crud(self):
        tour = catalog_service.get_tour('city-tour-cusco')
        self.assertIsNotNone(tour)
        self.assertEqual(tour.get('availability'), 'available')
        self.assertFalse(catalog_service.is_sold_out_tour('city-tour-cusco'))
        self.assertFalse(catalog_service.is_limited_tour('city-tour-cusco'))

        # Actualizar a limited
        ok, msg = catalog_service.upsert_tour({
            'entity_id': 'city-tour-cusco',
            'name': 'City Tour Cusco',
            'availability': 'limited'
        })
        self.assertTrue(ok)
        updated = catalog_service.get_tour('city-tour-cusco')
        self.assertEqual(updated.get('availability'), 'limited')
        self.assertTrue(catalog_service.is_limited_tour('city-tour-cusco'))
        self.assertFalse(catalog_service.is_sold_out_tour('city-tour-cusco'))

        # Actualizar a sold_out
        ok, msg = catalog_service.upsert_tour({
            'entity_id': 'city-tour-cusco',
            'name': 'City Tour Cusco',
            'availability': 'sold_out'
        })
        self.assertTrue(ok)
        updated_so = catalog_service.get_tour('city-tour-cusco')
        self.assertEqual(updated_so.get('availability'), 'sold_out')
        self.assertTrue(catalog_service.is_sold_out_tour('city-tour-cusco'))
        self.assertFalse(catalog_service.is_limited_tour('city-tour-cusco'))

        # Restaurar a available
        ok, msg = catalog_service.upsert_tour({
            'entity_id': 'city-tour-cusco',
            'name': 'City Tour Cusco',
            'availability': 'available'
        })
        self.assertTrue(ok)
        self.assertFalse(catalog_service.is_sold_out_tour('city-tour-cusco'))

    # ----------------------------------------------------
    # 2. Panel Administrativo (/catalogo)
    # ----------------------------------------------------
    def test_catalog_ui_contains_availability_controls(self):
        html = catalog_ui.get_catalog_html(csrf_token="test_token")
        self.assertIn('formAvailability', html)
        self.assertIn('badge-available', html)
        self.assertIn('badge-limited', html)
        self.assertIn('badge-sold-out', html)
        self.assertIn('Cupos limitados', html)
        self.assertIn('Agotado', html)

    # ----------------------------------------------------
    # 3. Consultas Conversacionales de Disponibilidad
    # ----------------------------------------------------
    def test_general_availability_query(self):
        res = rag_chain("¿Tienen disponibilidad de tours?", user_id="test_avail_1")
        self.assertEqual(res.get('route'), 'evidence_availability')
        self.assertIn("Disponibilidad y Cupos", res['response'])
        self.assertIn("Tours Diarios", res['response'])
        self.assertIn("Machu Picchu", res['response'])
        self.assertIn("asesor", res['response'].lower())

    def test_camino_inca_february_closure_faq(self):
        res = rag_chain("¿Tienen disponibilidad para el Camino Inca en febrero?", user_id="test_avail_feb")
        self.assertEqual(res.get('route'), 'evidence_availability')
        self.assertIn("febrero", res['response'].lower())
        self.assertIn("mantenimiento", res['response'].lower())
        self.assertIn("Inka Jungle", res['response'])

    def test_camino_inca_quota_and_daily_spots(self):
        res = rag_chain("¿Hay cupos disponibles para el Camino Inca?", user_id="test_avail_inca")
        self.assertEqual(res.get('route'), 'evidence_availability')
        self.assertIn("500", res['response'])
        self.assertIn("SERNANP", res['response'])

    def test_machu_picchu_train_availability(self):
        res = rag_chain("¿Hay disponibilidad para Machu Picchu en tren?", user_id="test_avail_mp")
        self.assertEqual(res.get('route'), 'evidence_availability')
        self.assertIn("Machu Picchu", res['response'])
        self.assertIn("horarios", res['response'].lower())
        self.assertIn("tren", res['response'].lower())

    def test_daily_tours_availability_explanation(self):
        res = rag_chain("¿Tienen cupos para el tour del Valle Sagrado?", user_id="test_avail_vs")
        self.assertEqual(res.get('route'), 'evidence_availability')
        self.assertIn("salidas diarias", res['response'].lower())
        self.assertIn("24 a 48 horas", res['response'].lower())

    def test_catalog_marked_sold_out_response(self):
        # Marcar City Tour como sold_out temporalmente
        catalog_service.upsert_tour({
            'entity_id': 'city-tour-cusco',
            'name': 'City Tour Cusco',
            'availability': 'sold_out'
        })
        res = rag_chain("¿Tienen disponibilidad para City Tour Cusco?", user_id="test_avail_so")
        self.assertEqual(res.get('route'), 'evidence_availability')
        self.assertIn("agotado", res['response'].lower())
        self.assertIn("sin cupos", res['response'].lower())

    def test_catalog_marked_limited_response(self):
        catalog_service.upsert_tour({
            'entity_id': 'city-tour-cusco',
            'name': 'City Tour Cusco',
            'availability': 'limited'
        })
        res = rag_chain("¿Hay disponibilidad para City Tour?", user_id="test_avail_lim")
        self.assertEqual(res.get('route'), 'evidence_availability')
        self.assertIn("cupos limitados", res['response'].lower())

    def test_multilingual_english_availability(self):
        res = rag_chain("Do you have spots available for Inca Trail in February?", user_id="test_avail_en")
        self.assertEqual(res.get('route'), 'evidence_availability')
        self.assertIn("February", res['response'])
        self.assertIn("maintenance", res['response'].lower())
        self.assertIn("advisor", res['response'].lower())

    # ----------------------------------------------------
    # 4. Reserva de Tour Agotado en Handoff
    # ----------------------------------------------------
    def test_booking_sold_out_tour_handoff(self):
        catalog_service.upsert_tour({
            'entity_id': 'city-tour-cusco',
            'name': 'City Tour Cusco',
            'availability': 'sold_out'
        })
        from handoff_support import apply_request
        rag_res = rag_chain("Quiero reservar City Tour Cusco", user_id="test_booking_so_user")
        self.assertTrue(rag_res.get('handoff_requested'))
        res = apply_request(app.__dict__, rag_res, "test_booking_so_user", "whatsapp", "Quiero reservar City Tour Cusco")
        self.assertTrue(res.get('handoff_registered'))
        self.assertIn("sin cupos", res['response'].lower())
        self.assertIn("lista de espera", res['response'].lower())


if __name__ == '__main__':
    unittest.main()
