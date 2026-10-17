"""Recomendaciones y listas curadas respetan el estado de disponibilidad del catálogo.

- Un tour 'sold_out' nunca aparece como recomendación y se informa aparte.
- 'Tours más visitados' y 'aclimatación' añaden un aviso si algún tour citado
  está agotado o con cupos limitados.
- Las etiquetas de listados están localizadas (ES/EN/PT/FR/IT).
"""
import os
import sys
import time
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import rag_chain  # noqa: E402
import catalog_service  # noqa: E402
from verified_routes import availability_badge, build_availability_notice  # noqa: E402

TOURS_TOUCHED = ['city-tour-cusco', 'maras-moray']


def _uid(tag):
    return f"test_sorec_{tag}_{int(time.time() * 1000)}"


class TestSoldOutRecommendations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog_service.init_catalog_db()
        cls.original = {}
        for eid in TOURS_TOUCHED:
            t = catalog_service.get_tour(eid)
            cls.original[eid] = (t.get('name'), t.get('availability', 'available'))

    def tearDown(self):
        for eid, (name, avail) in self.original.items():
            catalog_service.upsert_tour({'entity_id': eid, 'name': name, 'availability': avail})

    def _set(self, eid, status):
        ok, msg = catalog_service.upsert_tour({
            'entity_id': eid, 'name': self.original[eid][0], 'availability': status,
        })
        self.assertTrue(ok, msg)

    # --- Recomendaciones dinámicas ---
    def test_sold_out_tour_excluded_from_recommendations(self):
        self._set('city-tour-cusco', 'sold_out')
        res = rag_chain("Recomiéndame un tour de medio día sin caminatas", user_id=_uid('half'))
        text = res['response']
        self.assertEqual(res.get('route'), 'evidence_recommendation')
        self.assertNotIn("• *City Tour Cusco*", text)
        self.assertIn("Agotado temporalmente (no incluido)", text)
        self.assertIn("City Tour Cusco", text)

    def test_limited_tour_shows_badge_in_recommendations(self):
        self._set('maras-moray', 'limited')
        res = rag_chain("Recomiéndame un tour de medio día sin caminatas", user_id=_uid('lim'))
        self.assertIn("[🟡 Cupos limitados]", res['response'])

    def test_available_recommendations_have_no_availability_notes(self):
        res = rag_chain("Recomiéndame un tour de medio día sin caminatas", user_id=_uid('ok'))
        self.assertNotIn("Agotado", res['response'])
        self.assertNotIn("Cupos limitados", res['response'])

    # --- Respuestas curadas ---
    def test_most_visited_warns_when_tour_sold_out(self):
        self._set('city-tour-cusco', 'sold_out')
        res = rag_chain("¿Cuáles son los tours más visitados?", user_id=_uid('mv'))
        text = res['response']
        self.assertIn("Tours Más Visitados", text)
        self.assertIn("Disponibilidad actual", text)
        self.assertIn("City Tour Cusco*: 🔴 agotado temporalmente", text)

    def test_most_visited_english_notice(self):
        self._set('city-tour-cusco', 'sold_out')
        res = rag_chain("What are your most popular tours?", user_id=_uid('mven'))
        self.assertIn("Current availability", res['response'])
        self.assertIn("temporarily sold out", res['response'])

    def test_most_visited_without_notice_when_all_available(self):
        res = rag_chain("¿Cuáles son los tours más visitados?", user_id=_uid('mvok'))
        self.assertNotIn("Disponibilidad actual", res['response'])

    def test_acclimatization_warns_when_tour_sold_out(self):
        self._set('city-tour-cusco', 'sold_out')
        res = rag_chain("primer dia en cusco que me recomiendas aclimatacion", user_id=_uid('alt'))
        self.assertIn("Disponibilidad actual", res['response'])
        self.assertIn("agotado temporalmente", res['response'])

    # --- Helpers ---
    def test_badges_are_localized(self):
        self.assertEqual(availability_badge('sold_out', 'pt'), ' [🔴 Esgotado]')
        self.assertEqual(availability_badge('sold_out', 'en'), ' [🔴 Sold out]')
        self.assertEqual(availability_badge('limited', 'fr'), ' [🟡 Places limitées]')
        self.assertEqual(availability_badge('available', 'es'), '')
        self.assertEqual(availability_badge(None, 'es'), '')

    def test_notice_builder_returns_sold_ids(self):
        tours = {
            'a': {'name': 'Tour A', 'availability': 'sold_out'},
            'b': {'name': 'Tour B', 'availability': 'limited'},
            'c': {'name': 'Tour C', 'availability': 'available'},
        }
        notice, sold = build_availability_notice(['a', 'b', 'c', 'zz'], tours, 'es', lambda e: tours[e]['name'])
        self.assertEqual(sold, ['a'])
        self.assertIn("*Tour A*: 🔴 agotado temporalmente", notice)
        self.assertIn("*Tour B*: 🟡 cupos limitados", notice)
        self.assertNotIn("Tour C", notice)
        empty, none_sold = build_availability_notice(['c'], tours, 'es', lambda e: tours[e]['name'])
        self.assertEqual((empty, none_sold), ('', []))


if __name__ == '__main__':
    unittest.main()
