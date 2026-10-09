"""Structural regressions: open questions and the scoped PT recommendation flow.

Run only through tests/run_isolated.py. The real app.rag_chain and temporary
catalog/memory are exercised. Retrieval returns an empty list unless the single
pipeline reachability test supplies a NONFACTUAL sentinel document. Generation
is blocked except for that test's NONFACTUAL return marker. No external API,
production catalog, WhatsApp transport or actual language-model quality is tested.

Expected tour IDs and catalog values are declared here, independently of the
application's duration/hiking/intent classifiers. Fixtures are synthetic: only
Camino Inca (4 days), Inka Jungle (4 days) and Maras-Moray (half day) are active.
The Maras 08:40-14:00 schedule reproduces a declared pilot observation. The
price/inclusion sentinels below are synthetic, never published agency facts.

PT coverage is specifically recommendation templates and their duration/schedule,
preference clarification, unavailable alternatives, rejection and turn continuity.
Direct PT prices/facts remain outside this regression's scope. Label/template
assertions are not a certification of arbitrary Portuguese fluency or RAG quality.
"""
import json
import os
import re
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

if os.environ.get("TEXEIRA_ISOLATED_TEST") != "1":
    raise RuntimeError("Run tests/run_isolated.py; temporary database required")

import app
import catalog_service
import database
import trial_support
from langchain_core.documents import Document

FIXTURE = {
    "camino-inka": {
        "name": "Camino Inca Clásico 4D/3N", "duration": "4 días / 3 noches",
        "schedule": "04:45-05:10", "official_price": "917", "currency": "USD",
        "includes": "TEST_GUIDE_INCA", "excludes": "TEST_SLEEPINGBAG_INCA",
        "aliases": ["camino inca", "camino inka", "inca trail", "inka trail"],
    },
    "inka-jungle": {
        "name": "Inka Jungle to Machu Picchu", "duration": "4 días / 3 noches",
        "schedule": "06:10-06:30", "official_price": "418", "currency": "USD",
        "includes": "TEST_GUIDE_JUNGLE", "excludes": "TEST_EXTRA_JUNGLE",
        "aliases": ["inka jungle", "inca jungle"],
    },
    "maras-moray": {
        "name": "Maras - Moray", "duration": "Medio día", "schedule": "08:40-14:00",
        "official_price": "137", "currency": "PEN", "includes": "TEST_GUIDE_MARAS",
        "excludes": "TEST_TICKET_MARAS", "aliases": ["maras moray", "maras-moray", "moray maras"],
    },
}
MARAS = {"maras-moray"}
TREKS = {"camino-inka", "inka-jungle"}

OPEN_QUESTIONS = [
    ("es_prepare", "es", "¿Cómo me preparo para Camino Inca?"),
    ("es_equipment", "es", "que equipo debo llevar a camino inca"),
    ("es_pack", "es", "que debo empacar para inka jungle"),
    ("es_wear", "es", "que ropa debo usar en maras moray"),
    ("es_preparation", "es", "preparacion para camino inca"),
    ("es_backpack", "es", "que debo poner en la mochila para inka jungle"),
    ("en_reported_prepare_gear", "en", "How should I prepare for the Inca Trail and what gear is documented?"),
    ("en_prepare", "en", "How can I prepare for Inca Trail?"),
    ("en_gear", "en", "What gear do I need for Inca Trail?"),
    ("en_bring", "en", "What should I bring to Inca Trail?"),
    ("en_wear", "en", "What should I wear on Inca Trail?"),
    ("en_pack", "en", "What should I pack for Inka Jungle?"),
    ("en_preparation", "en", "Preparation for Inca Trail please"),
    ("en_effort", "en", "How difficult is Inca Trail?"),
    ("pt_prepare", "pt", "Como devo me preparar para Camino Inca?"),
    ("pt_equipment", "pt", "Que equipamento devo levar para Camino Inca?"),
    ("pt_wear", "pt", "Que roupa devo usar em Maras Moray?"),
    ("pt_backpack", "pt", "O que devo colocar na mochila para Inka Jungle?"),
    ("pt_preparation", "pt", "Como me preparar para Inka Jungle?"),
    ("pt_shoes", "pt", "Que calçado devo levar para Camino Inca?"),
    ("pt_prepare_short", "pt", "Preparação para Camino Inca"),
    ("es_open_with_fact", "es", "¿Qué debo llevar y qué incluye Camino Inca para prepararme?"),
    ("en_open_with_fact", "en", "What gear does Inca Trail include and how should I prepare?"),
    ("pt_open_with_fact", "pt", "Que equipamento está incluído em Camino Inca e como devo me preparar?"),
]

COMPARISONS = [
    ("es", "Compara Camino Inca con Inka Jungle para alguien que disfruta naturaleza."),
    ("en", "What is the difference between Inca Trail and Inka Jungle?"),
    ("pt", "Qual é a diferença entre Camino Inca e Inka Jungle?"),
    ("es_with_recommendation", "Compara Camino Inca con Inka Jungle, ¿cuál recomiendas?"),
    ("en_with_fact", "Compare what Inca Trail and Inka Jungle include."),
]

RULE_CONTROLS = [
    ("es_name", "es", "Camino Inca", "evidence_tour_overview", "camino-inka", ("917 USD", "4 días / 3 noches", "Duración")),
    ("es_overview", "es", "informacion de inka jungle", "evidence_tour_overview", "inka-jungle", ("418 USD", "Duración")),
    ("es_general_request", "es", "Hola, quiero saber del Camino Inca", "evidence_tour_overview", "camino-inka", ("917 USD", "Duración")),
    ("es_price", "es", "precio camino inca", "evidence_confirmed_price", "camino-inka", ("917 USD",)),
    ("es_schedule", "es", "horario maras moray", "evidence_schedule", "maras-moray", ("08:40-14:00",)),
    ("en_name", "en", "Inca Trail details", "evidence_tour_overview", "camino-inka", ("917 USD", "Official rate")),
    ("en_general_request", "en", "information about Inca Trail", "evidence_tour_overview", "camino-inka", ("917 USD", "Official rate")),
    ("en_price", "en", "Inca Trail price", "evidence_confirmed_price", "camino-inka", ("917 USD", "Official rate")),
    ("en_schedule", "en", "Maras Moray schedule", "evidence_schedule", "maras-moray", ("08:40-14:00", "Schedule")),
    ("en_duration", "en", "Inka Jungle duration", "evidence_duration", "inka-jungle", ("4 days / 3 nights", "Duration")),
]


class OpenQuestionsAndPortuguese(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database.init_db(app.SQLITE_DB_PATH)
        catalog_service.init_catalog_db()
        cls.snapshot = {tour["entity_id"]: tour for tour in catalog_service.get_all_tours(active_only=False, strict=True)}
        if not set(FIXTURE).issubset(cls.snapshot):
            raise RuntimeError("Temporary canonical catalog lacks fixture products")
        for entity_id, original in cls.snapshot.items():
            payload = {"entity_id": entity_id, "name": original["name"], "is_active": False}
            if entity_id in FIXTURE:
                payload.update(FIXTURE[entity_id])
                payload["is_active"] = True
            ok, detail = catalog_service.upsert_tour(payload)
            if not ok:
                raise RuntimeError("Unable to prepare synthetic fixture: " + str(detail))
        active_ids = {tour["entity_id"] for tour in catalog_service.get_all_tours(active_only=True, strict=True)}
        if active_ids != set(FIXTURE):
            raise AssertionError("Only three fixture products may be active: " + repr(active_ids))

    @classmethod
    def tearDownClass(cls):
        for tour in cls.snapshot.values():
            ok, detail = catalog_service.upsert_tour(tour)
            if not ok:
                raise RuntimeError("Unable to restore temporary catalog: " + str(detail))

    def setUp(self):
        self.uid = "synthetic-open-pt-" + uuid4().hex
        app.clear_history(self.uid)
        self.addCleanup(app.clear_history, self.uid)
        self.retrieval_invoke = Mock(name="empty_context_retrieval", return_value=[])
        self.retrieval_factory = self.enterContext(patch.object(
            app, "get_retriever", return_value=SimpleNamespace(invoke=self.retrieval_invoke)))
        self.real_retriever = self.enterContext(patch.object(
            trial_support, "retriever", side_effect=AssertionError("A real index must not be opened")))
        self.generation_factory = self.enterContext(patch.object(
            app, "get_llm", side_effect=AssertionError("No generation is allowed without context")))
        self.questions = []

    def send(self, question):
        self.questions.append(question)
        try:
            result = app.rag_chain(question, self.uid)
        except Exception as exc:
            print("OPEN_PT_CASE " + json.dumps({
                "test": self._testMethodName, "question": question, "exception": str(exc),
                "retrieval_factory_calls": self.retrieval_factory.call_count,
                "retrieval_invoke_calls": self.retrieval_invoke.call_count,
                "generation_factory_calls": self.generation_factory.call_count,
            }, ensure_ascii=False), flush=True)
            raise
        print("OPEN_PT_CASE " + json.dumps({
            "test": self._testMethodName, "question": question,
            "detected_language": app.detect_language(question), "result": result,
            "retrieval_factory_calls": self.retrieval_factory.call_count,
            "retrieval_invoke_calls": self.retrieval_invoke.call_count,
            "generation_factory_calls": self.generation_factory.call_count,
        }, ensure_ascii=False), flush=True)
        self.real_retriever.assert_not_called()
        return result

    def assert_open_without_context(self, question):
        result = self.send(question)
        self.assertGreaterEqual(self.retrieval_factory.call_count, 1, result)
        self.assertGreaterEqual(self.retrieval_invoke.call_count, 1, result)
        self.generation_factory.assert_not_called()
        self.assertFalse(result.get("context_used"), result)
        self.assertFalse(result.get("resolved_autonomously"), result)
        self.assertNotEqual(result.get("response_route"), "evidence_tour_overview", result)
        self.assertTrue(result.get("is_fallback") or result.get("needs_confirmation"), result)

    def assert_pt_template(self, result):
        # These assertions check only the authored template language, NOT the
        # linguistic quality of a model-generated Portuguese answer.
        text = result["response"]
        self.assertRegex(text.lower(), r"recomenda|prefer[eê]nci|op[cç][oõ]es|gosta|interessa|tempo|outras|nenhum")
        self.assertNotRegex(text.lower(), r"según|escribe|¿quieres|no quedan|no puedo confirmar|nuestro equipo|would you like|based on")

    def assert_recommendation(self, question, expected_ids, pending=False, duration_token=None, shared_time_reply=False):
        result = self.send(question)
        if not shared_time_reply:
            self.assertEqual(app.detect_language(question), "pt", question)
        # The effective language must remain PT even if the isolated spelling
        # of a shared ES/PT time-only reply is intrinsically ambiguous.
        self.assertEqual(result.get("language"), "pt", result)
        self.assertEqual(result.get("response_route"), "evidence_recommendation", result)
        self.assertEqual(set(result.get("recommended_tour_ids", [])), set(expected_ids), result)
        self.assertEqual(result.get("resolved_autonomously"), not pending, result)
        self.assertEqual(result.get("needs_confirmation"), pending, result)
        self.assertFalse(result.get("needs_agency_confirmation"), result)
        self.assertFalse(result.get("is_escalation"), result)
        self.retrieval_factory.assert_not_called()
        self.retrieval_invoke.assert_not_called()
        self.generation_factory.assert_not_called()
        self.assert_pt_template(result)
        titles = re.findall(r"^\s*• \*([^*\n]+)\*", result["response"], re.MULTILINE)
        self.assertEqual(len(titles), len(expected_ids), result)
        self.assertEqual(len(titles), len(set(titles)), result)
        if pending:
            self.assertIn("?", result["response"], result)
        if duration_token:
            self.assertIn(duration_token, result["response"].lower(), result)
        return result

    def test_pt_reported_recommendation_exact(self):
        result = self.assert_recommendation(
            "Recomende um passeio de meio dia, não quero fazer caminhadas.", MARAS,
            duration_token="meio dia")
        self.assertIn("08:40-14:00", result["response"])
        self.assertNotIn("Medio día", result["response"])
        self.assertNotIn("Half day", result["response"])

    def test_pt_no_accents_recommendation_variant(self):
        self.assert_recommendation("recomende um passeio de meio dia nao quero fazer caminhadas", MARAS, duration_token="meio dia")

    def test_pt_negative_constraint_and_latest_explicit_change(self):
        self.assert_recommendation("Recomende meio dia sem caminhadas", MARAS)
        self.assert_recommendation("Agora tenho 4 dias", set(), pending=True)
        self.assert_recommendation("Agora quero caminhar, quatro dias", TREKS, duration_token="4 dias")

    def test_pt_negative_infinitive_survives_time_only_followup(self):
        self.assert_recommendation("Quero meio dia, não quero caminhar", MARAS)
        self.assert_recommendation("Agora tenho quatro dias", set(), pending=True)

    def test_pt_explicit_reverse_preference_resets_time_and_hiking(self):
        self.assert_recommendation("Recomende quatro dias, quero caminhadas", TREKS)
        self.assert_recommendation("Agora não quero caminhar, tenho meio dia", MARAS)

    def test_pt_rejection_does_not_repeat_offered_product(self):
        self.assert_recommendation("Meio dia sem caminhadas, o que você recomenda?", MARAS)
        self.assert_recommendation("Nenhum, quero outras opções", set(), pending=True)
        self.assert_recommendation("Outras opções por favor", set(), pending=True)

    def test_pt_duration_change_after_rejection_can_offer_new_products(self):
        self.assert_recommendation("Recomende passeios para quatro dias com caminhadas", TREKS)
        self.assert_recommendation("Nenhum desses passeios", set(), pending=True)
        self.assert_recommendation("Agora quero meio dia sem caminhadas", MARAS)

    def test_pt_missing_preferences_asks_without_claiming_resolution(self):
        result = self.assert_recommendation("Quais passeios você recomenda?", set(), pending=True)
        self.assertRegex(result["response"].lower(), r"paisagens|hist[oó]ric|caminhad")

    def test_pt_exact_one_day_has_no_verified_candidate(self):
        self.assert_recommendation("Recomende um passeio de um dia, sem caminhadas", set(), pending=True)

    def test_pt_question_is_not_an_explicit_change_of_hiking_preference(self):
        self.assert_recommendation("Quero meio dia, sem caminhadas", MARAS)
        self.assert_recommendation("Há caminhadas?", MARAS)

    def test_open_question_about_inactive_tour_cannot_bypass_catalog_status(self):
        result = self.send("How should I prepare for Laguna Humantay?")
        self.assertEqual(result.get("response_route"), "evidence_inactive_tour", result)
        self.assertEqual(result.get("entity_id"), "laguna-humantay", result)
        self.assertFalse(result.get("resolved_autonomously"), result)
        self.retrieval_factory.assert_not_called()
        self.retrieval_invoke.assert_not_called()
        self.generation_factory.assert_not_called()

    def test_unknown_question_words_with_named_tour_are_not_a_bare_tour_name(self):
        self.assert_open_without_context("Can Inca Trail accommodate an unusual request?")

    def test_general_hiking_recommendation_without_entity_retains_recommendation_route(self):
        result = self.send("Recommend a one day tour with hiking")
        self.assertEqual(result.get("response_route"), "evidence_recommendation", result)
        self.assertEqual(result.get("recommended_tour_ids"), [], result)
        self.assertFalse(result.get("resolved_autonomously"), result)
        self.assertTrue(result.get("needs_confirmation"), result)
        self.retrieval_factory.assert_not_called()
        self.retrieval_invoke.assert_not_called()
        self.generation_factory.assert_not_called()

    def use_nonfactual_context_and_generation_marker(self, response_marker):
        """Instrumented pipeline seam; neither document nor output is a tour fact."""
        self.retrieval_invoke.return_value = [Document(
            page_content="PIPELINE_SENTINEL_CONTEXT_NOT_A_TOUR_FACT",
            metadata={"tour_id": "camino-inka", "tour_name": FIXTURE["camino-inka"]["name"]},
        )]
        generation_invoke = Mock(return_value=SimpleNamespace(content=response_marker))
        self.generation_factory.side_effect = None
        self.generation_factory.return_value = SimpleNamespace(invoke=generation_invoke)
        return generation_invoke

    def test_pt_explicit_absence_of_evidence_is_not_resolved(self):
        response_marker = "SENTINELA_SEM_EVIDÊNCIA: Não posso confirmar esse detalhe com os dados disponíveis."
        generation_invoke = self.use_nonfactual_context_and_generation_marker(response_marker)
        result = self.send("Como devo me preparar para Camino Inca?")
        self.assertEqual(result.get("response_route"), "rag_llm", result)
        generation_invoke.assert_called_once()
        self.assertIn(response_marker, result["response"])
        self.assertFalse(result.get("resolved_autonomously"), result)
        self.assertTrue(result.get("needs_confirmation"), result)
        self.assertTrue(result.get("needs_agency_confirmation"), result)

    def test_pt_positive_pipeline_marker_is_not_falsely_degraded(self):
        response_marker = "SENTINELA_POSITIVA_DE_ROTA: a etapa de geração foi alcançada. Não preciso de mais nada."
        generation_invoke = self.use_nonfactual_context_and_generation_marker(response_marker)
        result = self.send("Que equipamento devo levar para Camino Inca?")
        self.assertEqual(result.get("response_route"), "rag_llm", result)
        generation_invoke.assert_called_once()
        self.assertIn(response_marker, result["response"])
        self.assertFalse(result.get("is_fallback"), result)
        self.assertFalse(result.get("needs_agency_confirmation"), result)
        self.assertFalse(result.get("needs_confirmation"), result)
        self.assertTrue(result.get("resolved_autonomously"), result)
        # This is a negative detector control, never a model-quality approval.

    def test_pt_shared_numeric_time_reply_preserves_language_and_negative_constraint(self):
        self.assert_recommendation("Recomende meio dia, não quero caminhar", MARAS)
        self.assert_recommendation("4 dias", set(), pending=True, shared_time_reply=True)

    def test_shared_culture_preference_preserves_portuguese_conversation(self):
        self.assert_recommendation("Quais passeios você recomenda?", set(), pending=True)
        result = self.send("cultura")
        self.assertEqual(result.get("language"), "pt", result)
        self.assertEqual(result.get("response_route"), "evidence_recommendation", result)
        self.assertTrue(result.get("recommended_tour_ids"), result)
        self.assertTrue(set(result["recommended_tour_ids"]).issubset(set(FIXTURE)), result)
        self.assert_pt_template(result)
        self.retrieval_factory.assert_not_called()
        self.generation_factory.assert_not_called()

    def test_actual_pt_generation_prompt_contains_query_and_same_language_instruction(self):
        generation_invoke = self.use_nonfactual_context_and_generation_marker("NONFACTUAL_GENERATION_SENTINEL")
        question = "Que roupa devo usar em Maras Moray?"
        result = self.send(question)
        self.assertEqual(result.get("response_route"), "rag_llm", result)
        generation_invoke.assert_called_once()
        messages = generation_invoke.call_args.args[0]
        system_messages = [content for role, content in messages if role == "system"]
        human_messages = [content for role, content in messages if role == "human"]
        self.assertEqual(len(system_messages), 1)
        self.assertIn(question, system_messages[0])
        self.assertEqual(human_messages[-1], question)
        self.assertEqual(app.detect_language(question), "pt")
        self.assertRegex(system_messages[0].lower(), r"portugu[eéê]s")
        self.assertRegex(system_messages[0].lower(), r"responde[^\n]{0,120}mismo idioma")

    def test_open_question_reaches_generation_only_with_a_nonfactual_context_sentinel(self):
        generation_invoke = self.use_nonfactual_context_and_generation_marker("NONFACTUAL_GENERATION_SENTINEL")
        result = self.send("How should I prepare for the Inca Trail and what gear is documented?")
        self.retrieval_factory.assert_called_once()
        self.assertGreaterEqual(self.retrieval_invoke.call_count, 1)
        self.generation_factory.assert_called_once()
        generation_invoke.assert_called_once()
        self.assertEqual(result.get("response_route"), "rag_llm", result)
        self.assertNotEqual(result.get("response_route"), "evidence_tour_overview", result)
        # No factual correctness or autonomous-resolution claim is made about
        # NONFACTUAL_GENERATION_SENTINEL: this check proves pipeline reachability.


def make_open_test(question):
    def test(self):
        self.assert_open_without_context(question)
    return test


def make_rule_test(language, question, route, entity, tokens):
    def test(self):
        result = self.send(question)
        self.assertEqual(result.get("response_route"), route, result)
        self.assertEqual(result.get("entity_id"), entity, result)
        self.assertTrue(result.get("resolved_autonomously"), result)
        self.retrieval_factory.assert_not_called()
        self.retrieval_invoke.assert_not_called()
        self.generation_factory.assert_not_called()
        for token in tokens:
            self.assertIn(token, result["response"], result)
    return test


for case_id, language, question in OPEN_QUESTIONS:
    setattr(OpenQuestionsAndPortuguese, "test_open_" + case_id, make_open_test(question))
for language, question in COMPARISONS:
    setattr(OpenQuestionsAndPortuguese, "test_comparison_" + language, make_open_test(question))
for case_id, language, question, route, entity, tokens in RULE_CONTROLS:
    setattr(OpenQuestionsAndPortuguese, "test_rule_" + case_id, make_rule_test(language, question, route, entity, tokens))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    unittest.main(verbosity=2)
