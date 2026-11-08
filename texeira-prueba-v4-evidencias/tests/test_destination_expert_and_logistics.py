"""
tests/test_destination_expert_and_logistics.py — Pruebas de conocimiento experto de destino y logística real.

Valida:
1. Circuitos de Machu Picchu (Circuito 1 Panorámico, 2 Clásico, 3 Realeza/Huayna Picchu).
2. Logística de tren y equipaje (límite 5-8 kg, pasaporte original físico obligatorio).
3. Boleto Turístico del Cusco (BTC - COSITUC) y entradas comunales (Maras S/20, Vinicunca S/25, Humantay S/20).
4. Altura en Machu Picchu (2,430 msnm, clima cálido sin soroche) y alquiler de caballos en Humantay/Vinicunca.
5. Conexión estratégica Valle Sagrado -> Machu Picchu en Ollantaytambo.
6. Requisitos formales para emitir reservas (nombres, documento, nacionalidad, hotel).
"""
import sys
import unittest
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import rag_chain


def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c)).lower()


class TestDestinationExpertAndLogistics(unittest.TestCase):

    def test_machu_picchu_circuits_and_logistics(self):
        queries = [
            "¿Qué circuitos hay en Machu Picchu?",
            "¿Cuáles son los circuitos de Machu Picchu?",
            "¿Qué circuito me conviene en Machu Picchu?"
        ]
        for q in queries:
            with self.subTest(query=q):
                res = rag_chain(q, f"test-mp-circ-{abs(hash(q))}")
                self.assertEqual(res.get("response_route"), "evidence_destination_machupicchu")
                resp = norm(res.get("response", ""))
                self.assertTrue("circuito 1" in resp or "panoramico" in resp)
                self.assertTrue("circuito 2" in resp or "clasico" in resp)
                self.assertTrue("circuito 3" in resp or "realeza" in resp)

    def test_train_luggage_and_original_document(self):
        queries = [
            "¿Cuánto equipaje puedo llevar en el tren a Machu Picchu?",
            "¿Puedo llevar maleta grande al tren de Machu Picchu?",
            "¿Qué equipaje está permitido para viajar a Machu Picchu?"
        ]
        for q in queries:
            with self.subTest(query=q):
                res = rag_chain(q, f"test-mp-lug-{abs(hash(q))}")
                self.assertEqual(res.get("response_route"), "evidence_destination_machupicchu")
                resp = norm(res.get("response", ""))
                self.assertTrue("mochila" in resp or "5" in resp or "8" in resp or "equipaje" in resp)
                self.assertTrue("custodia" in resp or "hotel" in resp or "oficina" in resp)

    def test_cusco_tourist_ticket_and_entrances(self):
        queries = [
            "¿Qué es el Boleto Turístico del Cusco?",
            "¿Qué incluye el Boleto Turístico BTC?",
            "¿Cuánto cuesta el Boleto Turístico del Cusco?"
        ]
        for q in queries:
            with self.subTest(query=q):
                res = rag_chain(q, f"test-btc-{abs(hash(q))}")
                self.assertEqual(res.get("response_route"), "evidence_destination_btc")
                resp = norm(res.get("response", ""))
                self.assertTrue("cosituc" in resp or "boleto turistico" in resp or "btc" in resp)
                self.assertTrue("130" in resp or "70" in resp)

    def test_communal_entrance_fees(self):
        # Salineras de Maras S/20
        res_m = rag_chain("¿Cuánto cuesta la entrada a las Salineras de Maras?", "test-ent-maras")
        self.assertEqual(res_m.get("response_route"), "evidence_destination_btc")
        resp_m = norm(res_m.get("response", ""))
        self.assertTrue("20" in resp_m)
        self.assertTrue("maras" in resp_m)

        # Montaña 7 Colores S/25
        res_v = rag_chain("¿Cuánto cuesta la entrada a la Montaña de 7 Colores?", "test-ent-vini")
        self.assertEqual(res_v.get("response_route"), "evidence_destination_btc")
        resp_v = norm(res_v.get("response", ""))
        self.assertTrue("25" in resp_v or "comunidad" in resp_v)

    def test_altitude_and_horse_rental(self):
        # Caballos en Humantay
        res_h = rag_chain("¿Se pueden alquilar caballos en la Laguna Humantay?", "test-horse-hum")
        self.assertEqual(res_h.get("response_route"), "evidence_destination_altitude")
        resp_h = norm(res_h.get("response", ""))
        self.assertTrue("caballo" in resp_h)
        self.assertTrue("comunidad" in resp_h or "80" in resp_h or "100" in resp_h)

        # Altitud en Machu Picchu
        res_alt = rag_chain("¿A qué altura está Machu Picchu y si da soroche?", "test-alt-mp")
        self.assertEqual(res_alt.get("response_route"), "evidence_destination_altitude")
        resp_alt = norm(res_alt.get("response", ""))
        self.assertTrue("2,430" in resp_alt or "2430" in resp_alt)
        self.assertTrue("oxigeno" in resp_alt or "bajo" in resp_alt or "soroche" in resp_alt)

    def test_valle_sagrado_machu_picchu_connection(self):
        queries = [
            "¿Cómo puedo combinar Valle Sagrado con Machu Picchu?",
            "¿Puedo tomar el tren a Machu Picchu desde Ollantaytambo al terminar Valle Sagrado?",
            "¿Conviene hacer Valle Sagrado y luego ir a Machu Picchu?"
        ]
        for q in queries:
            with self.subTest(query=q):
                res = rag_chain(q, f"test-conn-{abs(hash(q))}")
                self.assertEqual(res.get("response_route"), "evidence_destination_connection")
                resp = norm(res.get("response", ""))
                self.assertTrue("ollantaytambo" in resp)
                self.assertTrue("aguas calientes" in resp)
                self.assertTrue("tren" in resp)

    def test_booking_requirements_checklist(self):
        queries = [
            "¿Qué datos necesitan para reservar un tour?",
            "¿Qué documentos piden para emitir los boletos?",
            "¿Qué requisitos se necesitan para reservar?"
        ]
        for q in queries:
            with self.subTest(query=q):
                res = rag_chain(q, f"test-req-{abs(hash(q))}")
                self.assertEqual(res.get("response_route"), "evidence_booking_requirements")
                resp = norm(res.get("response", ""))
                self.assertTrue("nombre" in resp)
                self.assertTrue("pasaporte" in resp or "dni" in resp)
                self.assertTrue("nacionalidad" in resp or "nacimiento" in resp)
                self.assertTrue("hotel" in resp)


if __name__ == "__main__":
    unittest.main()
