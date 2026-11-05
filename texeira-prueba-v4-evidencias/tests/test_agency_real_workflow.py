"""
tests/test_agency_real_workflow.py — Flujo comercial de agencia sin datos inventados.

Valida:
1. Preguntas de anticipo/depósito: se responden informativamente (no abren ticket) y NO inventan
   porcentajes ni plazos; derivan a la agencia y piden datos de calificación.
2. Preguntas de cancelación/reembolso: se derivan a la agencia sin inventar plazos (48 h, etc.).
3. Métodos de pago: solo los ya documentados (BCP, Interbank, Visa/Mastercard, efectivo);
   no se afirma Yape/Plin sin fuente oficial.
4. Al solicitar reserva, el bot pide fecha de viaje, pasajeros y hotel (calificación del lead).
"""
import sys
import unittest
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import rag_chain
import handoff_support as handoff


def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c)).lower()


UNVERIFIED_CLAIMS = ("50%", "48 h", "48 horas", "48 hours", "no reembolsable", "non-refundable", "plin")


class TestAgencyRealWorkflow(unittest.TestCase):

    def test_deposit_questions_do_not_open_ticket_nor_invent_figures(self):
        queries = [
            "¿Cuánto es el adelanto para reservar?",
            "¿Cuánto se paga para reservar?",
            "¿Qué necesito para reservar?",
            "How much is the deposit to book?",
            "Qual é o sinal para reservar?",
        ]
        for q in queries:
            with self.subTest(query=q):
                res = rag_chain(q, f"test-dep-{abs(hash(q))}")
                self.assertEqual(res.get("response_route"), "evidence_unknown")
                resp = norm(res.get("response", ""))
                for claim in UNVERIFIED_CLAIMS:
                    self.assertNotIn(claim, resp)
                self.assertTrue("agencia" in resp or "agency" in resp)

    def test_cancellation_questions_defer_to_agency(self):
        queries = [
            "¿Cuáles son las políticas de cancelación?",
            "¿Qué pasa si cancelo mi viaje?",
            "Políticas de reembolso",
            "What is your cancellation policy?",
            "Quais são as políticas de cancelamento?",
        ]
        for q in queries:
            with self.subTest(query=q):
                res = rag_chain(q, f"test-cancel-{abs(hash(q))}")
                self.assertEqual(res.get("response_route"), "evidence_unknown")
                resp = norm(res.get("response", ""))
                for claim in UNVERIFIED_CLAIMS:
                    self.assertNotIn(claim, resp)
                self.assertTrue("agencia" in resp or "agency" in resp)

    def test_payment_methods_only_documented_channels(self):
        res = rag_chain("¿Cuáles son los métodos de pago?", "test-pay-methods")
        resp = res.get("response", "")
        self.assertIn("BCP", resp)
        self.assertIn("Carmen Quicllu", resp)
        self.assertNotIn("Plin", resp)

        res_yape = rag_chain("Aceptan Yape?", "test-pay-yape")
        self.assertIn("unknown", res_yape.get("response_route", ""))
        self.assertIn("agencia", res_yape.get("response", "").lower())
        self.assertNotIn("Yape y Plin", res_yape.get("response", ""))

    def test_qualification_prompts_on_reservation_request(self):
        ns = {
            'get_history': lambda uid: [],
            'conversation_history': {},
            'detect_language': lambda q: 'es',
        }
        import uuid
        res = handoff.apply_request(
            ns,
            {"handoff_requested": True, "handoff_language": "es"},
            f"turista_res_{uuid.uuid4().hex[:10]}",  # usuario nuevo: sin ticket previo
            "whatsapp",
            "Quiero reservar Machu Picchu",
            now="2026-11-05T16:00:00+00:00",  # 11:00 Cusco
        )
        self.assertTrue(res.get("handoff_registered"))
        resp = res.get("response", "").lower()
        self.assertIn("fecha de viaje", resp)
        self.assertTrue("pasajeros" in resp or "personas" in resp)
        self.assertIn("hotel", resp)


if __name__ == "__main__":
    unittest.main()
