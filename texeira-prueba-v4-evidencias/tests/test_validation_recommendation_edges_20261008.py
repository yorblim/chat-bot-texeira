"""Independent recommendation regressions for the 00047 local pilot.

Run only with tests/run_isolated.py. The runner supplies a temporary catalog,
SQLite and blocked external networking. Administrative duration edits below are
synthetic test conditions; they are not changes to verified tourism information.
No TestClient, real provider, embedding model or existing index is used.
"""
import json
import os
import re
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

if os.environ.get("TEXEIRA_ISOLATED_TEST") != "1":
    raise RuntimeError("Run with tests/run_isolated.py")

import app
import catalog_service
import database
import trial_support
from conversation_memory import ConversationMemory


class RecommendationEdges(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database.init_db(app.SQLITE_DB_PATH)
        catalog_service.init_catalog_db()

    def setUp(self):
        self.uid = "synthetic-recommendation-" + uuid4().hex
        app.clear_history(self.uid)
        self.snapshot = {
            tour["entity_id"]: tour
            for tour in catalog_service.get_all_tours(active_only=False, strict=True)
        }
        self.addCleanup(self.restore_catalog)
        self.addCleanup(app.clear_history, self.uid)
        self.retrieval_invoke = Mock(name="synthetic_empty_retrieval", return_value=[])
        self.llm_invoke = Mock(
            name="synthetic_nonfactual_generation",
            return_value=SimpleNamespace(content="SIMULATED NONFACTUAL RESPONSE"),
        )
        self.get_retriever = self.enterContext(patch.object(
            app, "get_retriever",
            return_value=SimpleNamespace(invoke=self.retrieval_invoke),
        ))
        self.get_llm = self.enterContext(patch.object(
            app, "get_llm", return_value=SimpleNamespace(invoke=self.llm_invoke),
        ))
        self.real_retriever = self.enterContext(patch.object(
            trial_support, "retriever",
            side_effect=AssertionError("The real retriever/index must not be opened"),
        ))
        for entity_id in self.snapshot:
            self.update_tour(entity_id, is_active=False)

    def restore_catalog(self):
        for tour in self.snapshot.values():
            ok, detail = catalog_service.upsert_tour(tour)
            self.assertTrue(ok, detail)

    def update_tour(self, entity_id, **changes):
        tour = catalog_service.get_tour_by_id(entity_id)
        self.assertIsNotNone(tour, entity_id)
        ok, detail = catalog_service.upsert_tour({
            "entity_id": entity_id, "name": tour["name"], **changes,
        })
        self.assertTrue(ok, detail)

    def activate(self, *entity_ids):
        for entity_id in entity_ids:
            self.update_tour(entity_id, is_active=True)

    def send(self, question, expected_route="evidence_recommendation"):
        result = app.rag_chain(question, self.uid)
        print("CASETRACE " + json.dumps({
            "case": self._testMethodName,
            "user_id": self.uid,
            "input": question,
            "result": result,
            "synthetic_retriever_calls": self.get_retriever.call_count,
            "synthetic_retrieval_calls": self.retrieval_invoke.call_count,
            "synthetic_llm_factory_calls": self.get_llm.call_count,
            "synthetic_generation_calls": self.llm_invoke.call_count,
        }, ensure_ascii=False))
        self.assertEqual(result.get("response_route"), expected_route, result)
        self.get_retriever.assert_not_called()
        self.retrieval_invoke.assert_not_called()
        self.get_llm.assert_not_called()
        self.llm_invoke.assert_not_called()
        self.real_retriever.assert_not_called()
        self.assertNotIn("![", result["response"], result)
        for phone in trial_support.CATALOG["agency"]["phones"]:
            self.assertNotIn(phone, result["response"], result)
        return result

    def offered_ids(self, result):
        names = re.findall(r"^\s*• \*([^*\n]+)\*", result["response"], re.MULTILINE)
        known_names = {}
        for tour in catalog_service.get_all_tours(active_only=True, strict=True):
            entity_id = tour["entity_id"]
            display_names = [tour["name"], app._get_tour_display_name(entity_id, is_en=True)]
            for name in display_names:
                if name:
                    known_names[trial_support.normalize(name)] = entity_id
        offered = []
        for name in names:
            self.assertIn(trial_support.normalize(name), known_names, name)
            offered.append(known_names[trial_support.normalize(name)])
        self.assertEqual(len(offered), len(set(offered)), result)
        return set(offered)

    def assert_pending_without_offers(self, result):
        self.assertFalse(self.offered_ids(result), result)
        self.assertTrue(result.get("needs_confirmation"), result)
        self.assertFalse(result.get("resolved_autonomously"), result)
        self.assertFalse(result.get("needs_agency_confirmation"), result)

    def test_cleared_duration_cannot_match_an_exact_day_request(self):
        self.activate("city-tour-cusco")
        self.update_tour("city-tour-cusco", duration="")
        saved = catalog_service.get_tour_by_id("city-tour-cusco")
        self.assertEqual(saved["duration"], "")
        self.assertIn("duration", saved["overridden_fields"])
        result = self.send("Recomiéndame un tour de 2 días")
        self.assert_pending_without_offers(result)
        self.assertNotIn(self.snapshot["city-tour-cusco"]["name"], result["response"])

    def test_uninterpretable_duration_cannot_default_to_one_day(self):
        self.activate("city-tour-cusco")
        self.update_tour("city-tour-cusco", duration="Duración pendiente de precisar")
        result = self.send("Recomiéndame un tour de un día")
        self.assert_pending_without_offers(result)

    def test_missing_duration_without_override_cannot_invent_full_day(self):
        entity_id = "synthetic-without-duration"
        ok, detail = catalog_service.upsert_tour({
            "entity_id": entity_id,
            "name": "Synthetic candidate without duration",
            "is_active": True,
        })
        self.assertTrue(ok, detail)
        self.addCleanup(self.update_tour, entity_id, is_active=False)
        saved = catalog_service.get_tour_by_id(entity_id)
        self.assertEqual(saved["duration"], "")
        self.assertNotIn("duration", saved["overridden_fields"])
        result = self.send("Recomiéndame un tour de un día")
        self.assert_pending_without_offers(result)
        self.assertNotIn("Full Day", result["response"])

    def test_nights_alone_do_not_verify_an_exact_number_of_days(self):
        self.activate("machu-picchu-car")
        self.update_tour("machu-picchu-car", duration="1 noche")
        result = self.send("Recomiéndame un tour de 2 días")
        self.assert_pending_without_offers(result)

    def test_english_catalog_duration_matches_two_days(self):
        self.activate("city-tour-cusco")
        self.update_tour("city-tour-cusco", duration="2 days")
        result = self.send("What tour do you recommend for 2 days?")
        self.assertEqual(self.offered_ids(result), {"city-tour-cusco"})
        self.assertIn("2 days", result["response"])
        self.assertTrue(result.get("resolved_autonomously"), result)

    def test_english_catalog_duration_does_not_match_one_day(self):
        self.activate("city-tour-cusco")
        self.update_tour("city-tour-cusco", duration="2 days")
        result = self.send("What tour do you recommend for one day?")
        self.assert_pending_without_offers(result)

    def test_short_english_time_reply_uses_the_recommendation_route(self):
        self.activate("machu-picchu-car")
        first = self.send("What tours do you recommend?")
        self.assert_pending_without_offers(first)
        result = self.send("2 days")
        self.assertEqual(self.offered_ids(result), {"machu-picchu-car"})
        self.assertIn("2 days", result["response"])
        self.assertNotIn("2 días", result["response"])
        self.assertNotIn("Según lo que buscas", result["response"])
        self.assertTrue(result.get("resolved_autonomously"), result)

    def test_package_availability_question_is_not_a_time_preference(self):
        self.activate("machu-picchu-car")
        for question in ("¿Tienen paquete de 7 días?", "Do you have a 7 day package?"):
            with self.subTest(question=question):
                app.clear_history(self.uid)
                result = self.send(question, expected_route="evidence_unknown")
                self.assertTrue(result.get("needs_agency_confirmation"), result)
                self.assertFalse(result.get("resolved_autonomously"), result)
                self.assertFalse(self.offered_ids(result), result)
                followup = self.send("Me gustan los paisajes")
                self.assertEqual(self.offered_ids(followup), {"machu-picchu-car"})

    def test_latest_explicit_hiking_preference_revokes_an_earlier_negative(self):
        self.activate("laguna-humantay", "valle-sagrado")
        first = self.send("Me gustan los paisajes, no quiero caminatas, tengo un día")
        self.assertEqual(self.offered_ids(first), {"valle-sagrado"})
        result = self.send("Ahora sí quiero caminatas")
        self.assertIn("laguna-humantay", self.offered_ids(result))

    def test_question_about_hiking_does_not_revoke_a_negative_preference(self):
        self.activate("laguna-humantay", "valle-sagrado")
        first = self.send("No quiero caminatas, tengo un día")
        self.assertEqual(self.offered_ids(first), {"valle-sagrado"})
        result = self.send("¿Hay caminatas?")
        self.assertEqual(self.offered_ids(result), {"valle-sagrado"})

    def test_explicit_english_hiking_preference_revokes_an_earlier_negative(self):
        self.activate("laguna-humantay", "valle-sagrado")
        first = self.send("I do not want hiking and have one day")
        self.assertEqual(self.offered_ids(first), {"valle-sagrado"})
        result = self.send("Now I want hiking")
        self.assertEqual(self.offered_ids(result), {"laguna-humantay"})

    def test_negative_hiking_preference_survives_a_time_only_followup(self):
        self.activate("laguna-humantay", "valle-sagrado")
        first = self.send("No quiero caminatas")
        self.assertEqual(self.offered_ids(first), {"valle-sagrado"})
        result = self.send("Un día")
        self.assertEqual(self.offered_ids(result), {"valle-sagrado"})

    def test_latest_negative_hiking_preference_replaces_an_earlier_positive(self):
        self.activate("laguna-humantay", "valle-sagrado")
        first = self.send("Me gustan los paisajes y caminatas, tengo un día")
        self.assertIn("laguna-humantay", self.offered_ids(first))
        negative = self.send("Ahora no quiero caminatas")
        self.assertEqual(self.offered_ids(negative), {"valle-sagrado"})
        result = self.send("Un día")
        self.assertEqual(self.offered_ids(result), {"valle-sagrado"})

    def test_natural_negative_hiking_statements_replace_and_preserve_prior_preference(self):
        self.activate("laguna-humantay", "valle-sagrado")
        initial_preferences = (
            ("Me gustan los paisajes, no quiero caminatas, tengo un día", False),
            ("Me gustan los paisajes y caminatas, tengo un día", True),
        )
        negatives = (
            "No quiero hacer caminatas",
            "No me gustan las caminatas",
            "I don't want to hike",
            "I don't like hiking",
        )
        for initial, initially_hiking in initial_preferences:
            for statement in negatives:
                with self.subTest(initial=initial, negative=statement):
                    app.clear_history(self.uid)
                    first = self.send(initial)
                    if initially_hiking:
                        self.assertIn("laguna-humantay", self.offered_ids(first))
                    else:
                        self.assertEqual(self.offered_ids(first), {"valle-sagrado"})
                    negative = self.send(statement)
                    self.assertEqual(self.offered_ids(negative), {"valle-sagrado"})
                    followup = self.send("Un día")
                    self.assertEqual(self.offered_ids(followup), {"valle-sagrado"})

    def prepare_alternatives(self):
        pool = {
            "laguna-humantay", "montana-7-colores", "valle-sagrado",
            "machu-picchu-tren", "puente-qeswachaca",
        }
        self.activate(*pool)
        self.assert_pending_without_offers(self.send("¿Qué tours me recomiendas?"))
        first = self.send("Paisajes, tengo un día")
        offered = self.offered_ids(first)
        self.assertTrue(offered, first)
        self.assertLess(len(offered), len(pool), first)
        self.assertLessEqual(offered, pool)
        return pool, offered

    def test_rec05_rejection_offers_only_remaining_compatible_options(self):
        pool, rejected = self.prepare_alternatives()
        result = self.send("Ninguno, necesito que me recomiendes otras opciones")
        self.assertEqual(self.offered_ids(result), pool - rejected)
        self.assertTrue(result.get("resolved_autonomously"), result)

    def test_rec05_repeated_rejection_explains_exhaustion_and_asks_a_useful_question(self):
        pool, rejected = self.prepare_alternatives()
        second = self.send("Ninguno, necesito que me recomiendes otras opciones")
        self.assertEqual(self.offered_ids(second), pool - rejected)
        result = self.send("Ninguno, necesito que me recomiendes otras opciones")
        self.assert_pending_without_offers(result)
        self.assertRegex(
            trial_support.normalize(result["response"]),
            r"no (?:quedan|hay|tenemos|disponemos)|agotad|sin (?:mas |otras )?opciones",
        )
        self.assertIn("?", result["response"], result)

    def test_request_for_other_options_after_recommendations_excludes_prior_offers(self):
        pool, prior = self.prepare_alternatives()
        result = self.send("Otras opciones")
        self.assertEqual(self.offered_ids(result), pool - prior)

    def test_legacy_recommendation_without_metadata_is_not_repeated_when_rejected(self):
        pool, rejected = self.prepare_alternatives()
        app.conversation_history.mutate(self.uid, lambda messages: [
            {key: value for key, value in message.items() if key != "metadata"}
            for message in messages
        ])
        self.assertTrue(all("metadata" not in message for message in app.get_history(self.uid)))
        result = self.send("Ninguno, necesito que me recomiendes otras opciones")
        offered = self.offered_ids(result)
        self.assertFalse(offered & rejected, result)
        self.assertLessEqual(offered, pool - rejected)
        if offered:
            self.assertTrue(result.get("resolved_autonomously"), result)
        else:
            self.assert_pending_without_offers(result)
            self.assertIn("?", result["response"], result)

    def test_renamed_tour_remains_rejected_after_memory_is_reopened(self):
        pool, rejected = self.prepare_alternatives()
        second = self.send("Ninguno, necesito que me recomiendes otras opciones")
        self.assertEqual(self.offered_ids(second), pool - rejected)
        renamed_id = sorted(rejected)[0]
        self.update_tour(renamed_id, name="Synthetic renamed display name")
        persisted = app.get_history(self.uid)
        state = persisted[-1].get("metadata", {}).get("recommendation_state", {})
        self.assertIn(renamed_id, state.get("rejected_ids", []))
        reopened = ConversationMemory(lambda: app.SQLITE_DB_PATH, app.MAX_HISTORY_TURNS * 2)
        with patch.object(app, "conversation_history", reopened):
            self.assertEqual(app.get_history(self.uid), persisted)
            result = self.send("Recomiéndame con las mismas preferencias")
            self.assertEqual(self.offered_ids(result), pool - rejected)
            self.assertNotIn(renamed_id, result.get("recommended_tour_ids", []))

    def test_category_listing_is_not_a_rejected_recommendation(self):
        self.activate("montana-7-colores", "valle-sagrado")
        listing = self.send("categoria cusco", expected_route="evidence_category_tours")
        for entity_id in ("montana-7-colores", "valle-sagrado"):
            self.assertIn(self.snapshot[entity_id]["name"], listing["response"])
        result = self.send(
            "Ninguno, necesito que me recomiendes otras opciones, paisajes, tengo un día"
        )
        self.assertEqual(self.offered_ids(result), {"montana-7-colores", "valle-sagrado"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
