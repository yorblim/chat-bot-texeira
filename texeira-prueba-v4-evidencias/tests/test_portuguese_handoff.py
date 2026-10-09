"""PT handoff regressions with temporary requests and no external transport.

Run only through tests/run_isolated.py. The locale is injected here: these tests
verify handoff continuity, not automatic language detection or model quality.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

if os.environ.get('TEXEIRA_ISOLATED_TEST') != '1':
    raise RuntimeError('Run with tests/run_isolated.py')

from fastapi import FastAPI
import catalog_service
import handoff_support as handoff
import trial_support


class PortugueseHandoff(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.patches = [
            patch.object(handoff, 'DB', Path(self.tmp.name) / 'requests.db'),
            patch.object(handoff, 'is_postgres', return_value=False),
            patch.object(trial_support, 'detect_entity_from_question', side_effect=self.entity),
            patch.object(catalog_service, 'get_tour', return_value={'name': 'Camino Inca Clásico 4D/3N'}),
            patch.object(catalog_service, 'is_deactivated_tour', return_value=False),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        notification = patch.object(handoff, 'notify_advisor')
        self.notify = notification.start()
        self.addCleanup(notification.stop)
        self.history = {}
        self.ns = {
            'get_history': lambda uid: self.history.get(uid, []),
            'conversation_history': self.history,
            'ADVISOR_NOTIFICATIONS_ENABLED': False,
            'send_whatsapp_message': Mock(side_effect=AssertionError('No external transport')),
        }

    def tearDown(self):
        self.notify.assert_not_called()
        self.ns['send_whatsapp_message'].assert_not_called()

    @staticmethod
    def entity(text):
        return 'camino-inka' if 'camino inca' in text.lower() else None

    def add_turn(self, uid, question, response):
        self.history.setdefault(uid, []).extend([
            {'role': 'human', 'content': question},
            {'role': 'ai', 'content': response},
        ])

    def installed_chain(self, original=None):
        def no_original(*args):
            raise AssertionError('Explicit request must not invoke RAG/LLM')
        self.ns.update(
            app=FastAPI(), rag_chain=original or no_original,
            detect_language=lambda question: 'pt', add_history_turn=self.add_turn,
        )
        handoff.install(self.ns)
        return self.ns['rag_chain']

    def apply(self, question='consultar assessor', uid='synthetic-pt', lang='pt'):
        self.add_turn(uid, question, 'Registrando uma solicitação de atendimento humano.')
        result = handoff.apply_request(
            self.ns, {'handoff_requested': True, 'handoff_language': lang},
            uid, 'whatsapp', question,
        )
        self.assertFalse(result['resolved_autonomously'])
        if result.get('handoff_registered'):
            self.assertEqual(self.history[uid][-1]['content'], result['response'])
        return result

    def test_explicit_portuguese_requests(self):
        for question in (
            'consultar assessor', 'assessor', 'quero falar com um assessor',
            'Gostaria de falar com uma pessoa', 'Preciso de um atendente',
            'atendimento humano por favor', 'ajuda humana',
            'solicitar reserva do passeio Camino Inca', 'solicitar uma reserva',
            'Gostaria de reservar Camino Inca',
            'Não quero caminhar, mas quero falar com um assessor',
        ):
            with self.subTest(question=question):
                self.assertTrue(handoff.requested(question))

    def test_portuguese_refusals_are_not_requests(self):
        for question in (
            'Não quero falar com um assessor', 'Não preciso de um assessor',
            'sem assessor', 'não consultar assessor',
            'Não quero solicitar reserva do passeio Camino Inca',
            'Não quero fazer uma reserva', 'Não desejo reservar',
            'Não me liguem', 'Não me transfiram',
            'Não me transfira', 'Não gostaria de falar com o assessor',
        ):
            with self.subTest(question=question):
                self.assertFalse(handoff.requested(question))

    def test_quoted_advice_and_conditional_are_not_requests(self):
        for question in (
            'Recomendo consultar assessor para obter detalhes',
            'Recomendamos falar com um assessor',
            'Se precisar, quero falar com um assessor',
            'O passeio inclui guia ou assessor?',
        ):
            with self.subTest(question=question):
                self.assertFalse(handoff.requested(question))

    def test_initial_ack_and_handoff_metadata_are_portuguese(self):
        result = self.installed_chain()('consultar assessor', 'synthetic-ack')
        self.assertEqual(result['handoff_language'], 'pt')
        self.assertTrue(result['handoff_requested'])
        self.assertFalse(result['resolved_autonomously'])
        self.assertEqual(result['response'], 'Registrando uma solicitação de atendimento humano.')
        self.assertEqual(self.history['synthetic-ack'][-1]['content'], result['response'])

    def test_negative_request_keeps_original_route(self):
        original = Mock(return_value={'response': 'Você pode continuar consultando os passeios.'})
        result = self.installed_chain(original)('Não quero falar com um assessor', 'synthetic-negative')
        original.assert_called_once()
        self.assertNotIn('handoff_requested', result)

    def test_uncertainty_adds_portuguese_advisor_guidance_once(self):
        def original(question, uid):
            text = 'Não posso confirmar este dado nos documentos disponíveis.'
            self.add_turn(uid, question, text)
            return {'response': text, 'needs_agency_confirmation': True, 'resolved_autonomously': False}
        result = self.installed_chain(original)('Qual equipamento está documentado?', 'synthetic-unknown')
        self.assertIn('Escreva 👉 *assessor*', result['response'])
        self.assertNotIn('Escribe', result['response'])
        self.assertFalse(result['resolved_autonomously'])
        self.assertNotIn('handoff_requested', result)
        self.assertEqual(self.history['synthetic-unknown'][-1]['content'], result['response'])

    def test_existing_portuguese_advisor_guidance_is_not_repeated(self):
        original = Mock(return_value={
            'response': 'Confirme este dado com um assessor.',
            'needs_agency_confirmation': True, 'resolved_autonomously': False,
        })
        result = self.installed_chain(original)('E o equipamento?', 'synthetic-guidance')
        self.assertEqual(result['response'], 'Confirme este dado com um assessor.')

    def test_new_and_repeated_advisor_request_keep_one_ticket(self):
        first = self.apply()
        second = self.apply()
        self.assertTrue(first['handoff_registered'])
        self.assertEqual(first['handoff_id'], second['handoff_id'])
        self.assertIn('aguarda atendimento humano', first['response'])
        self.assertIn('Você já tem uma solicitação', second['response'])
        with handoff.connection() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 1)

    def test_in_progress_advisor_request_preserves_portuguese_status(self):
        first = self.apply()
        handoff.update_request(first['handoff_id'], 'in_progress', 'Teste', '')
        second = self.apply()
        self.assertEqual(second['handoff_id'], first['handoff_id'])
        self.assertEqual(second['handoff_status'], 'in_progress')
        self.assertIn('já está em atendimento', second['response'])
        self.assertIn('ainda não foi encerrada', second['response'])

    def test_booking_is_a_request_and_never_a_confirmed_reservation(self):
        question = 'solicitar reserva do passeio Camino Inca'
        first = self.apply(question)
        second = self.apply(question)
        self.assertEqual(first['handoff_id'], second['handoff_id'])
        for result in (first, second):
            self.assertIn('sua reserva ainda não está confirmada', result['response'].lower())
            self.assertIn('assessor', result['response'])
        handoff.update_request(first['handoff_id'], 'in_progress', 'Teste', '')
        third = self.apply(question)
        self.assertEqual(third['handoff_id'], first['handoff_id'])
        self.assertIn('já está em atendimento', third['response'])
        self.assertIn('Sua reserva ainda não está confirmada', third['response'])

    def test_booking_without_tour_does_not_invent_a_tour(self):
        result = self.apply('solicitar uma reserva', uid='synthetic-no-tour')
        self.assertIn('Registrei sua solicitação de reserva', result['response'])
        self.assertNotIn('Camino Inca', result['response'])
        self.assertIn('sua reserva ainda não está confirmada', result['response'])

    def test_inactive_tour_does_not_register_a_booking(self):
        with patch.object(catalog_service, 'is_deactivated_tour', return_value=True):
            result = self.apply('solicitar reserva do passeio Camino Inca')
        self.assertFalse(result['handoff_registered'])
        self.assertEqual(result['response_route'], 'evidence_inactive_tour')
        self.assertIn('não está disponível no nosso catálogo ativo', result['response'])
        self.assertEqual(self.history['synthetic-pt'][-1]['content'], result['response'])
        with handoff.connection() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 0)

    def test_registration_failure_does_not_claim_a_ticket(self):
        with patch.object(handoff, 'create_request', side_effect=RuntimeError('sensitive-detail')):
            result = self.apply(uid='synthetic-failure')
        self.assertFalse(result['handoff_registered'])
        self.assertEqual(result['handoff_status'], 'registration_failed')
        self.assertIn('Não consegui registrar', result['response'])
        self.assertNotIn('sensitive-detail', result['response'])
        self.assertNotIn('handoff_id', result)
        self.assertEqual(self.history['synthetic-failure'][-1]['content'], result['response'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
