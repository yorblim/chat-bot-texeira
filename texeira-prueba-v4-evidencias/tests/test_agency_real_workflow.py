"""
tests/test_agency_real_workflow.py — Pruebas de flujo comercial de agencia de viajes real.

Valida:
1. Consultas sobre anticipos y proceso de reserva (50% de depósito, pasaportes, fecha y hotel).
2. Consultas sobre políticas de cancelación y reprogramación (48h, boletos no reembolsables de Machu Picchu).
3. Métodos de pago oficiales incluyendo billeteras digitales (Yape, Plin, BCP, Interbank).
4. Preguntas proactivas de calificación al solicitar reserva (fechas, pasajeros, hotel).
"""
import sys
import unittest
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import rag_chain
import handoff_support as handoff


def strip_accents(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c)).lower()


class TestAgencyRealWorkflow(unittest.TestCase):

    def test_deposit_and_booking_process(self):
        queries = [
            "¿Cuánto es el adelanto para reservar?",
            "¿Cuánto se paga para reservar?",
            "¿Qué necesito para reservar?",
            "How much is the deposit to book?",
            "Qual é o sinal para reservar?"
        ]
        for q in queries:
            with self.subTest(query=q):
                res = rag_chain(q, f"test-dep-{hash(q)}")
                self.assertEqual(res.get("response_route"), "evidence_unknown")
                resp = res.get("response", "")
                self.assertTrue("50%" in resp)
                norm = strip_accents(resp)
                self.assertTrue("carmen quicllu" in norm or "agencia" in norm or "agency" in norm)

    def test_cancellation_policy(self):
        queries = [
            "¿Cuáles son las políticas de cancelación?",
            "¿Qué pasa si cancelo mi viaje?",
            "Políticas de reembolso",
            "What is your cancellation policy?",
            "Quais são as políticas de cancelamento?"
        ]
        for q in queries:
            with self.subTest(query=q):
                res = rag_chain(q, f"test-cancel-{hash(q)}")
                self.assertEqual(res.get("response_route"), "evidence_unknown")
                resp = res.get("response", "")
                self.assertTrue("48" in resp or "Machu Picchu" in resp)
                norm = strip_accents(resp)
                self.assertTrue("agencia" in norm or "agency" in norm)

    def test_payment_methods_with_digital_wallets(self):
        queries = [
            "¿Aceptan Yape o Plin?",
            "¿Puedo pagar con Yape?",
            "¿Cuáles son los métodos de pago?"
        ]
        for q in queries:
            with self.subTest(query=q):
                res = rag_chain(q, f"test-pay-{hash(q)}")
                self.assertEqual(res.get("response_route"), "evidence_unknown")
                resp = res.get("response", "")
                self.assertTrue("BCP" in resp)
                self.assertTrue("Yape" in resp)
                self.assertTrue("Carmen Quicllu" in resp)

    def test_qualification_prompts_on_reservation_request(self):
        # Cuando el cliente solicita reservar, handoff.apply_request invita a brindar fechas, pasajeros y hotel
        ns = {
            'get_history': lambda uid: [],
            'conversation_history': {},
            'detect_language': lambda q: 'es',
        }
        res_handoff = handoff.apply_request(
            ns,
            {"handoff_requested": True, "handoff_language": "es"},
            "turista_res_test",
            "whatsapp",
            "Quiero reservar Machu Picchu",
            now="2026-11-05T16:00:00+00:00"  # 11:00 AM Cusco
        )
        self.assertTrue(res_handoff.get("handoff_registered"))
        resp = res_handoff.get("response", "")
        self.assertTrue("fecha de viaje" in resp.lower())
        self.assertTrue("pasajeros" in resp.lower() or "personas" in resp.lower())
        self.assertTrue("hotel" in resp.lower())


if __name__ == "__main__":
    unittest.main()
