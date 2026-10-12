"""Test de verificación para FAQ críticas de Cusco:
1. Recomendación para el primer día / soroche / aclimatación (City Tour o Maras Moray).
2. Métodos de pago oficiales (BCP, Interbank, Visa/Mastercard, Efectivo en oficina).
3. Contacto directo con el asesor comercial en solicitudes de atención humana.
"""
import sys
import unittest
sys.path.insert(0, '.')
from app import rag_chain


class TestFAQAcclimatizationAndPayments(unittest.TestCase):

    def test_acclimatization_queries_recommend_soft_tours(self):
        queries = [
            "¿Qué me recomiendas hacer el primer día en Cusco?",
            "¿Cómo me puedo aclimatar al llegar?",
            "¿Qué hago si me da soroche?",
            "What do you recommend for my first day in Cusco?",
            "O que você recomenda para o primeiro dia em Cusco?"
        ]
        for q in queries:
            with self.subTest(query=q):
                res = rag_chain(q, f"test-aclimat-{hash(q)}")
                self.assertEqual(res.get("response_route"), "evidence_recommendation")
                rec_ids = res.get("recommended_tour_ids") or []
                self.assertIn("city-tour-cusco", rec_ids)
                self.assertIn("maras-moray", rec_ids)
                resp = res.get("response", "")
                self.assertTrue("City Tour" in resp or "City tour" in resp)
                self.assertTrue("Maras" in resp)

    def test_payment_methods_queries(self):
        queries = [
            "¿Cuáles son los métodos de pago?",
            "¿Cómo puedo pagar los tours?",
            "What payment methods do you accept?",
            "Quais são as formas de pagamento?"
        ]
        for q in queries:
            with self.subTest(query=q):
                res = rag_chain(q, f"test-payment-{hash(q)}")
                self.assertEqual(res.get("response_route"), "evidence_unknown")
                resp = res.get("response", "")
                self.assertTrue("BCP" in resp or "Bank Transfer" in resp or "Transferência" in resp)
                self.assertTrue("Carmen Quicllu" in resp)


if __name__ == "__main__":
    unittest.main()
