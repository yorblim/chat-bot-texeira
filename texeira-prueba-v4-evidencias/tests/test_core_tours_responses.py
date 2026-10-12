"""Prueba unitaria de respuestas de catálogo para los tours principales."""
import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["TEXEIRA_ENABLE_WHATSAPP"] = "false"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import app

class TestCoreToursResponses(unittest.TestCase):
    def test_city_tour_price(self):
        res = app.rag_chain("precio de City Tour", "test_core_1")
        resp = res.get("response", "").lower()
        self.assertIn("15", resp)
        self.assertIn("city tour", resp)

    def test_city_tour_overview(self):
        res = app.rag_chain("Información de City Tour", "test_core_2")
        resp = res.get("response", "").lower()
        self.assertIn("medio día", resp)
        self.assertNotIn("4 días", resp)

    def test_valle_sagrado_price(self):
        res = app.rag_chain("precio de Valle Sagrado", "test_core_3")
        resp = res.get("response", "").lower()
        self.assertIn("25", resp)

    def test_valle_sagrado_overview(self):
        res = app.rag_chain("Información de Valle Sagrado", "test_core_4")
        resp = res.get("response", "").lower()
        self.assertIn("full day", resp)
        self.assertIn("07:30-18:30", resp)

    def test_humantay_price(self):
        res = app.rag_chain("precio de Laguna Humantay", "test_core_5")
        resp = res.get("response", "").lower()
        self.assertIn("30", resp)

    def test_humantay_overview(self):
        res = app.rag_chain("Información de Laguna Humantay", "test_core_6")
        resp = res.get("response", "").lower()
        self.assertIn("full day", resp)
        self.assertIn("04:30-17:00", resp)

    def test_montana_7_colores_price(self):
        res = app.rag_chain("precio de Montaña de 7 Colores", "test_core_7")
        resp = res.get("response", "").lower()
        self.assertIn("30", resp)

    def test_machu_picchu_tren_price(self):
        res = app.rag_chain("precio de Machu Picchu en Tren", "test_core_8")
        resp = res.get("response", "").lower()
        self.assertIn("290", resp)

    def test_machu_picchu_tren_overview(self):
        res = app.rag_chain("Información de Machu Picchu en Tren", "test_core_9")
        resp = res.get("response", "").lower()
        self.assertIn("full day", resp)

if __name__ == "__main__":
    unittest.main()
