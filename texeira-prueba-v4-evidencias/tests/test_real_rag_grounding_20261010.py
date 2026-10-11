"""Prompt grounding regressions using the observed three-product catalog snapshot.

Run through tests/run_isolated.py. No external model or WhatsApp transport is
called. The mock model returns a NONFACTUAL marker; assertions inspect the
actual context delivered to the generation seam, not simulated answer quality.

Generated evidence documents deliberately represent an obsolete retrieval
index. Current catalog overrides, including explicit empty fields, must take
precedence before a model sees that context. Unrelated and inactive products
must not supply equipment or services to a question about another tour.
"""
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

if os.environ.get("TEXEIRA_ISOLATED_TEST") != "1":
    raise RuntimeError("Run through tests/run_isolated.py; temporary state required")

import app
import catalog_service
import database
import trial_support
from langchain_core.documents import Document
from src.evidence import build_context_for_entity

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "docs" / "evaluaciones" / "CATALOGO_REFERENCIA_LLM_20261010T060618Z_3bb459a1.json"
GENERATED_EVIDENCE_SOURCE = "evidence-v4-2026-09-11"
NONFACTUAL_RESPONSE = "NONFACTUAL_GENERATION_SEAM_REACHED"


class RealRagGrounding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database.init_db(app.SQLITE_DB_PATH)
        catalog_service.init_catalog_db()
        cls.fixture = {row["entity_id"]: row for row in json.loads(SNAPSHOT.read_text(encoding="utf-8"))}
        if set(cls.fixture) != {"camino-inka", "inka-jungle", "maras-moray"}:
            raise AssertionError("Reference snapshot must contain precisely the authorized products")
        all_rows = catalog_service.get_all_tours(active_only=False, strict=True)
        for row in all_rows:
            entity_id = row["entity_id"]
            payload = cls.fixture.get(entity_id, {
                "entity_id": entity_id, "name": row["name"], "is_active": False,
            })
            ok, detail = catalog_service.upsert_tour(payload)
            if not ok:
                raise RuntimeError("Unable to prepare temporary snapshot fixture: " + str(detail))
        # upsert records supplied fields as edits. Restore the snapshot's exact
        # override metadata rather than accidentally editing all fixture fields.
        with catalog_service.get_db_session() as connection:
            for entity_id, row in cls.fixture.items():
                connection.execute("DELETE FROM catalog_field_overrides WHERE entity_id = ?", (entity_id,))
                for field in row.get("overridden_fields", []):
                    connection.execute(
                        "INSERT INTO catalog_field_overrides (entity_id, field) VALUES (?, ?)",
                        (entity_id, field),
                    )
        catalog_service.invalidate_catalog_cache()
        active_ids = {row["entity_id"] for row in catalog_service.get_all_tours(active_only=True, strict=True)}
        if active_ids != set(cls.fixture):
            raise AssertionError("Unexpected active products in the isolated fixture")
        maras = catalog_service.get_tour_by_id("maras-moray")
        if maras["includes"] or maras["excludes"] or not {"includes", "excludes"}.issubset(maras["overridden_fields"]):
            raise AssertionError("Maras includes/excludes must remain explicitly cleared")

    def setUp(self):
        self.user_id = "synthetic-grounding-" + uuid4().hex
        app.clear_history(self.user_id)
        self.addCleanup(app.clear_history, self.user_id)
        self.retrieval = Mock(return_value=[])
        self.enterContext(patch.object(app, "get_retriever", return_value=SimpleNamespace(invoke=self.retrieval)))
        self.enterContext(patch.object(trial_support, "retriever", side_effect=AssertionError("No real index in seam tests")))
        self.generation = Mock(return_value=SimpleNamespace(content=NONFACTUAL_RESPONSE))
        self.llm_factory = self.enterContext(patch.object(app, "get_llm", return_value=SimpleNamespace(invoke=self.generation)))

    def generated_document(self, entity_id, extra=""):
        tour = catalog_service.get_tour_by_id(entity_id)
        return Document(
            page_content=build_context_for_entity(entity_id, include_dynamic=False) + extra,
            metadata={
                "tour_id": entity_id, "tour_name": tour["name"],
                "source": GENERATED_EVIDENCE_SOURCE, "category": "evidence_based",
            },
        )

    def send_and_capture_context(self, question, documents):
        self.retrieval.return_value = documents
        result = app.rag_chain(question, self.user_id)
        self.last_result = result
        self.assertEqual(result.get("response_route"), "rag_llm", result)
        self.generation.assert_called_once()
        messages = self.generation.call_args.args[0]
        self.assertEqual(messages[-1], ("human", question))
        self.assertIn(NONFACTUAL_RESPONSE, result["response"])
        system = messages[0][1]
        self.assertIn("\nContexto: ", system)
        return system.split("\nContexto: ", 1)[1].rsplit("\nPregunta: ", 1)[0]

    def test_explicitly_cleared_maras_inclusions_are_not_restored_from_static_index(self):
        doc = self.generated_document("maras-moray")
        self.assertIn("includes/guia_profesional", doc.page_content)
        self.assertIn("bus_turistico_o_cuatrimotos", doc.page_content)
        context = self.send_and_capture_context(
            "How should I prepare for Maras Moray and what services are documented?", [doc],
        )
        self.assertNotIn("includes/guia_profesional", context)
        self.assertNotIn("bus_turistico_o_cuatrimotos", context)
        self.assertIn("50 USD", context)
        self.assertIn("08:40-14:00", context)
        self.assertIn("salineras", context.lower())

    def test_explicitly_cleared_exclusions_do_not_reappear_as_old_generated_facts(self):
        doc = self.generated_document(
            "maras-moray", "\n- excludes/REMOVED_EXCLUSION_SENTINEL: confirmado por F1",
        )
        context = self.send_and_capture_context("How should I prepare for Maras Moray?", [doc])
        self.assertNotIn("REMOVED_EXCLUSION_SENTINEL", context)
        self.assertIn("50 USD", context)

    def test_catalog_edits_replace_obsolete_generated_services_without_losing_current_jungle_services(self):
        doc = self.generated_document(
            "inka-jungle", "\n- includes/REMOVED_SERVICE_SENTINEL: confirmado por F2",
        )
        context = self.send_and_capture_context("How should I prepare for Inka Jungle?", [doc])
        self.assertNotIn("REMOVED_SERVICE_SENTINEL", context)
        self.assertIn("460 USD", context)
        self.assertIn("rafting", context.lower())
        self.assertRegex(context.lower(), r"zip\s*line")

    def test_unrelated_active_tour_is_not_used_as_equipment_context_for_inca_trail(self):
        unrelated = Document(
            page_content="FOREIGN_ACTIVE_GEAR_SENTINEL", metadata={"tour_id": "inka-jungle", "tour_name": "Inka Jungle"},
        )
        context = self.send_and_capture_context(
            "How should I prepare for Inca Trail?", [self.generated_document("camino-inka"), unrelated],
        )
        self.assertNotIn("FOREIGN_ACTIVE_GEAR_SENTINEL", context)
        self.assertIn("790 USD", context)

    def test_inactive_tour_is_not_used_as_equipment_context_for_inca_trail(self):
        inactive = Document(
            page_content="INACTIVE_ATV_HELMET_SENTINEL",
            metadata={"tour_id": "maras-moray-cuatrimoto", "tour_name": "Inactive ATV", "source": GENERATED_EVIDENCE_SOURCE},
        )
        context = self.send_and_capture_context(
            "How should I prepare for Inca Trail?", [self.generated_document("camino-inka"), inactive],
        )
        self.assertNotIn("INACTIVE_ATV_HELMET_SENTINEL", context)
        self.assertNotIn("maras-moray-cuatrimoto", context)

    def test_comparison_fetches_both_named_products_and_excludes_other_products(self):
        inca = self.generated_document("camino-inka")
        jungle = self.generated_document("inka-jungle")
        unrelated = Document(page_content="FOREIGN_COMPARISON_SENTINEL", metadata={"tour_id": "maras-moray"})
        self.retrieval.side_effect = lambda query: [jungle] if query == "inka-jungle" else [inca, unrelated]
        context = self.send_and_capture_context(
            "Compara Camino Inca con Inka Jungle para alguien que disfruta naturaleza.", [inca, unrelated],
        )
        self.assertIn("790 USD", context)
        self.assertIn("460 USD", context)
        self.assertIn("camino-inka", context)
        self.assertIn("inka-jungle", context)
        self.assertIn("rafting", context.lower())
        self.assertNotIn("FOREIGN_COMPARISON_SENTINEL", context)
        self.assertNotIn("ID: maras-moray", context)
        self.assertIn("inka-jungle", [call.args[0] for call in self.retrieval.call_args_list])

    def test_only_unrelated_documents_do_not_enable_a_model_answer(self):
        self.retrieval.return_value = [Document(page_content="FOREIGN_ONLY_SENTINEL", metadata={"tour_id": "inka-jungle"})]
        result = app.rag_chain("How should I prepare for Inca Trail?", self.user_id)
        self.generation.assert_not_called()
        self.llm_factory.assert_not_called()
        self.assertFalse(result.get("context_used"), result)
        self.assertFalse(result.get("resolved_autonomously"), result)
        self.assertTrue(result.get("is_fallback") or result.get("needs_confirmation"), result)

    def test_matching_unknown_document_source_retains_its_content(self):
        doc = Document(
            page_content="TARGET_SOURCE_PIPELINE_SENTINEL_NOT_A_TOUR_FACT",
            metadata={"tour_id": "camino-inka", "source": "approved-target-document-fixture"},
        )
        context = self.send_and_capture_context("How should I prepare for Inca Trail?", [doc])
        self.assertIn("TARGET_SOURCE_PIPELINE_SENTINEL_NOT_A_TOUR_FACT", context)
        self.assertIn("790 USD", context)

    def test_compound_price_and_cleared_inclusions_preserves_both_question_parts(self):
        context = self.send_and_capture_context(
            "precio de Maras Moray y qué incluye", [self.generated_document("maras-moray")],
        )
        self.assertIn("50 USD", context)
        self.assertRegex(context, r"(?i)(?:incluye|includes)[^\n]*SIN DATO VIGENTE")
        self.assertNotIn("includes/guia_profesional", context)
        self.assertFalse(self.last_result.get("resolved_autonomously"), self.last_result)
        self.assertTrue(self.last_result.get("needs_confirmation"), self.last_result)
        self.assertTrue(self.last_result.get("needs_agency_confirmation"), self.last_result)


if __name__ == "__main__":
    unittest.main()
