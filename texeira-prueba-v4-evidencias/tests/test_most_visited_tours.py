"""Pruebas unitarias para la funcionalidad de 'Tours más visitados / más populares / imperdibles'.
Verifica routing, respuestas multilingües (ES, EN, PT, FR, IT), coherencia de recomendaciones,
no regresión de listados genéricos y asignación de botones de acción rápida.
"""
import unittest
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import rag_chain, get_quick_buttons
import verified_routes
import trial_support


class TestMostVisitedTours(unittest.TestCase):

    def test_query_detection_regex(self):
        """Verifica que la función is_most_visited_query detecte variantes clave."""
        positive_queries = [
            "¿Cuáles son los tours más visitados?",
            "tours mas visitados",
            "que tours son los mas visitados",
            "¿Cuáles son los tours más populares?",
            "los tours mas pedidos",
            "cuales son los imperdibles de cusco",
            "cuales son sus top tours",
            "what are the most visited tours?",
            "most popular tours in cusco",
            "must see tours",
            "quais são os passeios mais visitados?",
            "passeios mais populares",
            "passeios imperdíveis",
            "quels sont les circuits les plus visités?",
            "quali sono i tour più visitati?",
        ]
        for q in positive_queries:
            q_norm = trial_support.normalize(q)
            self.assertTrue(
                verified_routes.is_most_visited_query(q_norm),
                f"Falló detección positiva para: '{q}' (norm: '{q_norm}')"
            )

        negative_queries = [
            "Hola",
            "¿Qué tours tienen?",
            "Ver tours",
            "Información de Camino Inca",
            "¿Cuánto cuesta Laguna Humantay?",
            "¿Tienen disponibilidad para febrero?",
        ]
        for q in negative_queries:
            q_norm = trial_support.normalize(q)
            self.assertFalse(
                verified_routes.is_most_visited_query(q_norm),
                f"Falso positivo para: '{q}' (norm: '{q_norm}')"
            )

    def test_response_spanish_most_visited(self):
        """Consulta en español: debe responder con el Top 4 oficial y tip de aclimatación."""
        queries = [
            "¿Cuáles son los tours más visitados?",
            "tours mas visitados",
            "¿Cuáles son los tours más populares?",
            "cuáles son los imperdibles de cusco",
        ]
        for idx, q in enumerate(queries):
            res = rag_chain(q, user_id=f"test_mv_es_{idx}")
            self.assertEqual(res.get("route"), "evidence_recommendation", f"Ruta incorrecta para '{q}'")
            text = res.get("response", "")
            self.assertIn("Tours Más Visitados", text, f"No encontró título en respuesta para '{q}': {text}")
            self.assertIn("Machu Picchu", text)
            self.assertIn("Montaña de 7 Colores", text)
            self.assertIn("Laguna Humantay", text)
            self.assertIn("City Tour Cusco", text)
            self.assertIn("Tip viajero", text)
            self.assertIn("asesor", text.lower())

    def test_response_english_most_visited(self):
        """Consulta en inglés: debe responder en inglés con las 4 experiencias top."""
        res = rag_chain("What are your most popular tours?", user_id="test_mv_en")
        self.assertEqual(res.get("route"), "evidence_recommendation")
        text = res.get("response", "")
        self.assertIn("Most Visited & Must-See Tours", text)
        self.assertIn("Machu Picchu", text)
        self.assertIn("Rainbow Mountain", text)
        self.assertIn("Humantay Lake", text)
        self.assertIn("Cusco City Tour", text)
        self.assertIn("Travel tip", text)
        self.assertIn("advisor", text.lower())

    def test_response_portuguese_most_visited(self):
        """Consulta en portugués: debe responder en portugués con los destinos top."""
        res = rag_chain("Quais são os passeios mais visitados?", user_id="test_mv_pt")
        self.assertEqual(res.get("route"), "evidence_recommendation")
        text = res.get("response", "")
        self.assertIn("Passeios Mais Visitados e Imperdíveis", text)
        self.assertIn("Machu Picchu", text)
        self.assertIn("Montanha de 7 Cores", text)
        self.assertIn("Lagoa Humantay", text)
        self.assertIn("City Tour Cusco", text)
        self.assertIn("Dica de viagem", text)
        self.assertIn("assessor", text.lower())

    def test_quick_buttons_generation(self):
        """Verifica que se generen los botones de acción contextual correspondientes."""
        res = rag_chain("¿Cuáles son los tours más populares?", user_id="test_mv_btn")
        route = res.get("route")
        buttons = get_quick_buttons(route=route, user_message="¿Cuáles son los tours más populares?", lang="es")
        self.assertEqual(len(buttons), 2)
        btn_ids = [b["id"] for b in buttons]
        self.assertIn("btn_tours:es", btn_ids)
        self.assertIn("btn_advisor:es", btn_ids)

    def test_no_regression_general_listing(self):
        """Asegura que consultas generales de catálogo sigan yendo a evidence_listing."""
        res = rag_chain("¿Qué tours tienen?", user_id="test_mv_listing")
        self.assertEqual(res.get("route"), "evidence_listing")
        self.assertIn("Catálogo de Experiencias", res.get("response", ""))


if __name__ == "__main__":
    unittest.main()
