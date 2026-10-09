"""Finite, reproducible conversational robustness bank, with no external calls.

Run: python tests/run_isolated.py test_conversation_robustness_batch.py

This is an application/routing/catalog regression test, NOT an evaluation of
real LLM quality, WhatsApp delivery, accessibility or universal language support.
The three active product IDs and their durations reproduce a declared pilot
condition. Prices, inclusions, exclusions and pickup times below are synthetic
sentinels, not agency facts. The Maras schedule reproduces the observed 08:40-
14:00 catalog condition. Every other catalog product is explicitly inactive.

Expected IDs and facts are declared by the test author. No application intent,
duration or hiking classifier is used to calculate an expected answer. Retrieval
and generation sentinels RAISE; they never return a prewritten factual answer.
Every scenario is isolated by user ID. Failed cases continue to the end and make
the process exit nonzero. Exploratory multilingual/open questions are printed as
pending_review, never passed on keyword matching or mocked generation.
Only stdout is written. The caller can retain JSON lines as a durable artifact.
"""
from contextlib import ExitStack
from dataclasses import dataclass, field
import json
import os
import re
import sys
import time
import unicodedata
from unittest.mock import Mock, patch
from uuid import uuid4

if os.environ.get("TEXEIRA_ISOLATED_TEST") != "1":
    raise RuntimeError("Use tests/run_isolated.py; this test requires a temporary database")

import app
import catalog_service
import database
import trial_support

FIXTURE_NAME = "synthetic_three_active_pilot_profile_v1"
FIXTURE = {
    "camino-inka": {
        "name": "Camino Inca Clásico 4D/3N", "duration": "4 días / 3 noches",
        "official_price": "917", "currency": "USD", "schedule": "04:45-05:10",
        "includes": "TEST_GUIDE_INCA; TEST_ENTRY_INCA",
        "excludes": "TEST_SLEEPINGBAG_INCA", "aliases": ["camino inca", "camino inka", "inca trail", "inka trail"],
    },
    "inka-jungle": {
        "name": "Inka Jungle to Machu Picchu", "duration": "4 días / 3 noches",
        "official_price": "418", "currency": "USD", "schedule": "06:10-06:30",
        "includes": "TEST_GUIDE_JUNGLE; TEST_TRANSPORT_JUNGLE",
        "excludes": "TEST_EXTRA_JUNGLE", "aliases": ["inka jungle", "inca jungle"],
    },
    "maras-moray": {
        "name": "Maras - Moray", "duration": "Medio día", "schedule": "08:40-14:00",
        "official_price": "137", "currency": "PEN",
        "includes": "TEST_TRANSPORT_MARAS; TEST_GUIDE_MARAS",
        "excludes": "TEST_TICKET_MARAS", "aliases": ["maras moray", "maras-moray", "moray maras"],
    },
}
THREE = frozenset(FIXTURE)
TREKS = frozenset({"camino-inka", "inka-jungle"})
MARAS = frozenset({"maras-moray"})


@dataclass(frozen=True)
class Expect:
    route: str
    ids: frozenset = frozenset()
    entity: str = ""
    contains: tuple = ()
    pending: bool = False
    language: str = ""
    kind: str = "route"


@dataclass(frozen=True)
class Case:
    case_id: str
    group: str
    language: str
    turns: tuple
    exploration: bool = False
    mutations: dict = field(default_factory=dict)


def rec(ids=(), pending=False, language="es"):
    return Expect("evidence_recommendation", frozenset(ids), pending=pending,
                  language=language, kind="recommendation")


def fact(entity, kind, language="es"):
    data = FIXTURE[entity]
    if kind == "price":
        return Expect("evidence_confirmed_price", entity=entity,
                      contains=(data["official_price"] + " " + data["currency"],), language=language, kind="fact")
    if kind in {"includes", "excludes"}:
        required = tuple(x.strip() for x in data[kind].split(";"))
    elif kind == "duration" and language == "en":
        required = ("Half day",) if entity == "maras-moray" else ("4 days / 3 nights",)
    else:
        required = (data[kind],)
    return Expect("evidence_" + kind, entity=entity, contains=required, language=language, kind="fact")


def inactive(entity, language="es"):
    return Expect("evidence_inactive_tour", entity=entity, pending=True, language=language, kind="inactive")


def build_bank():
    cases = []

    def singles(group, language, questions, expectation):
        for question in questions:
            # IDs are stable with bank order, while run_id/user_id are UUIDs.
            cases.append(Case("ROB-%03d" % (len(cases) + 1), group, language,
                              ((question, expectation),)))

    # Explicit recommendation wording, including errors reported by the user.
    singles("recommendation_missing_preferences", "es", [
        "¿Qué tours me recomiendas?", "que tours me recomiedas", "cuales me recomienedas",
        "ninguno necesito que em recomiendes", "RECOMIENDAME ALGO", "me sugieres algun tour",
        "que me aconsejas para visitar", "recomndame un tour", "  recomendame   algo  ",
        "q tours me recomiendas", "recomiendame porfa", "necesito que me sugieras opciones",
    ], rec(pending=True))
    singles("recommendation_missing_preferences", "en", [
        "What tours do you recommend?", "can you suggest a tour", "RECOMMEND SOMETHING",
        "what would you advise", "pls recommend a tour", "any recommendations?",
    ], rec(pending=True, language="en"))

    singles("half_day_no_hiking", "es", [
        "Recomiéndame un tour de medio día, no quiero hacer caminatas.",
        "recomiendame algo medio dia sin caminatas", "MEDIO DIA SIN SENDERISMO",
        "tengo medio dia y no me gustan las caminatas", "medio dia no quiero caminar",
        "me sugieres un tour de medio dia sin hacer caminatas", "  medio   dia   sin   caminatas  ",
        "recomiedame un tour de medio dia no quiero caminatas",
        "kiero un tour de medio dia sin caminatas", "solo medio dia y nada de trekking",
        "medio día, no deseo realizar caminatas", "medio dia no tengo ganas de hacer caminatas",
    ], rec(MARAS))
    singles("half_day_no_hiking", "en", [
        "Recommend a half day tour. I don't want to hike.", "half day without hiking",
        "I have half day and do not want hiking", "HALF DAY I DO NOT LIKE HIKING",
        "suggest half day without walking", "half day no hiking pls",
    ], rec(MARAS, language="en"))

    singles("exact_four_days_hiking", "es", [
        "Tengo 4 días y quiero hacer caminatas", "4 dias quiero senderismo",
        "recomiendame trekking de 4 dias", "quiero aventura 4 días", "  4   dias  con caminatas  ",
        "tengo cuatro dias quiero caminatas", "busco caminatas de 4d", "4 dias me gusta caminar",
    ], rec(TREKS))
    singles("exact_four_days_hiking", "en", [
        "I have 4 days and want hiking", "recommend a trek for 4 days", "4 days I want to hike",
        "SUGGEST HIKING FOR 4 DAYS", "I like hiking and have four days",
    ], rec(TREKS, language="en"))

    singles("no_active_exact_match", "es", [
        "Recomiéndame un tour de un día. No quiero hacer caminatas.",
        "tengo 2 dias sin caminatas", "recomiendame un tour de 3 dias", "5 dias para hacer senderismo",
        "quiero un tour de 4 dias pero sin caminatas", "un dia completo nada de caminatas",
    ], rec(pending=True))
    singles("no_active_exact_match", "en", [
        "Recommend a one day tour without hiking", "I have 2 days and want hiking",
        "I have 4 days and do not like hiking", "suggest a full day without hiking",
    ], rec(pending=True, language="en"))

    # The oracle requires fixture values and entity IDs, not merely a nonempty answer.
    singles("current_price", "es", [
        "¿Cuánto cuesta Camino Inca?", "precio camino inka", "CUANTO CUESTA CAMINO INCA",
        "q cuesta camnio inca", "tarifa del camino inca porfa", "cuanto sale camino inca",
    ], fact("camino-inka", "price"))
    singles("current_price", "en", [
        "What is the price of the Inca Trail?", "inca trail rates", "how much does inca trail cost",
        "inca trail how much pls", "HOW MUCH IS INKA TRAIL", "price of inca tral",
    ], fact("camino-inka", "price", "en"))
    singles("current_price", "es", [
        "precio maras moray", "cuanto cuesta moray maras", "TARIFAS MARAS-MORAY", "q precio tiene maras moray",
    ], fact("maras-moray", "price"))
    singles("current_price", "en", [
        "How much is Inka Jungle?", "inka jungle rates please", "PRICE INCA JUNGLE", "inka jungle cost",
    ], fact("inka-jungle", "price", "en"))
    singles("current_schedule", "es", [
        "horario de maras moray", "a que hora sale maras-moray", "HORARIO MORAY MARAS", "q horario tiene maras moray",
    ], fact("maras-moray", "schedule"))
    singles("current_schedule", "en", [
        "Inca Trail schedule", "what time is inka trail departure", "INKA TRAIL TIMETABLE", "inca trail departure please",
    ], fact("camino-inka", "schedule", "en"))
    singles("current_inclusions", "es", [
        "que incluye maras moray", "¿Qué incluye Maras-Moray?", "Q INCLUYE MORAY MARAS", "inclusiones maras moray porfa",
    ], fact("maras-moray", "includes"))
    singles("current_inclusions", "en", [
        "What does Inka Jungle include?", "inka jungle inclusions", "WHAT IS INCLUDED IN INCA JUNGLE", "include services inka jungle",
    ], fact("inka-jungle", "includes", "en"))
    singles("current_exclusions", "es", [
        "que no incluye camino inca", "exclusiones camino inka", "CAMINO INCA NO INCLUYE QUE", "¿Qué no está incluido en Camino Inca?",
    ], fact("camino-inka", "excludes"))
    singles("current_duration", "en", [
        "How long is the Inca Trail?", "inca trail duration", "DURATION INKA TRAIL", "how long does inka trail last",
    ], fact("camino-inka", "duration", "en"))

    singles("inactive_products", "es", [
        "precio de laguna humantay", "que incluye humantay", "HORARIO HUMANTAY", "fotos de laguna humantay",
    ], inactive("laguna-humantay"))
    singles("inactive_products", "en", [
        "Rainbow Mountain price", "what does rainbow mountain include", "rainbow mountain schedule", "photos of rainbow mountain",
    ], inactive("montana-7-colores", "en"))

    def multi(group, language, turns, mutations=None):
        cases.append(Case("ROB-%03d" % (len(cases) + 1), group, language, tuple(turns), mutations=mutations or {}))

    multi("preference_followups", "es", [
        ("recomiendame medio dia sin caminatas por favor", rec(MARAS)),
        ("ahora tengo 4 dias", rec(pending=True)),
        ("ahora si quiero hacer caminatas", rec(TREKS)),
    ])
    multi("preference_followups", "en", [
        ("Suggest a half day, I do not want hiking", rec(MARAS, language="en")),
        ("4 days", rec(pending=True, language="en")),
        ("Now I want hiking", rec(TREKS, language="en")),
    ])
    multi("preference_followups", "es", [
        ("quiero senderismo 4 dias", rec(TREKS)),
        ("ya no quiero hacer caminatas", rec(pending=True)),
        ("medio dia", rec(MARAS)),
    ])
    multi("preference_followups", "en", [
        ("I want hiking and have 4 days to visit", rec(TREKS, language="en")),
        ("I do not want to hike anymore", rec(pending=True, language="en")),
        ("half day", rec(MARAS, language="en")),
    ])
    multi("no_preferences_then_reply", "es", [
        ("que me recomiendas para el viaje", rec(pending=True)), ("sin caminatas y medio dia", rec(MARAS)),
    ])
    multi("no_preferences_then_reply", "en", [
        ("Any tours you recommend for me?", rec(pending=True, language="en")),
        ("4 days with hiking", rec(TREKS, language="en")),
    ])
    multi("reject_and_exhaust", "es", [
        ("recomiendame algo sin caminar de medio dia", rec(MARAS)),
        ("Ninguno, dame otras opciones.", rec(pending=True)),
        ("otras opciones por favor", rec(pending=True)),
    ])
    multi("reject_and_exhaust", "en", [
        ("Please suggest a half day tour without hiking", rec(MARAS, language="en")),
        ("None of them. Other options please", rec(pending=True, language="en")),
        ("other tours", rec(pending=True, language="en")),
    ])
    multi("reject_and_change_time", "es", [
        ("quiero hacer caminatas 4 dias me recomiendas", rec(TREKS)),
        ("ninguna de esas opciones", rec(pending=True)),
        ("ahora medio dia sin caminatas", rec(MARAS)),
    ])
    multi("reject_and_change_time", "en", [
        ("Recommend hiking, I have 4 days", rec(TREKS, language="en")),
        ("neither of those tours", rec(pending=True, language="en")),
        ("Now half day, without hiking", rec(MARAS, language="en")),
    ])

    overview_inca = Expect("evidence_tour_overview", entity="camino-inka", kind="fact")
    overview_maras = Expect("evidence_tour_overview", entity="maras-moray", kind="fact")
    ambiguous_es = Expect("evidence_ambiguous", pending=True, language="es", kind="ambiguous")
    ambiguous_en = Expect("evidence_ambiguous", pending=True, language="en", kind="ambiguous")
    for q, language, expectation in [
        ("precio del otro", "es", ambiguous_es), ("fotos del otro", "es", ambiguous_es),
        ("que incluye el otro", "es", ambiguous_es), ("horario del otro", "es", ambiguous_es),
        ("price of the other one", "en", ambiguous_en), ("photos of the other", "en", ambiguous_en),
        ("what does the other one include", "en", ambiguous_en), ("schedule of the second one", "en", ambiguous_en),
    ]:
        multi("ambiguous_cross_tour_followup", language, [
            ("informacion camino inca", overview_inca), ("informacion maras moray", overview_maras), (q, expectation),
        ])

    multi("explicit_catalog_change_price", "es", [
        ("precio de maras-moray actualizado", Expect("evidence_confirmed_price", entity="maras-moray",
          contains=("281 PEN",), kind="fact", language="es")),
    ], {"maras-moray": {"official_price": "281"}})
    multi("explicit_catalog_change_schedule", "es", [
        ("nuevo horario maras moray", Expect("evidence_schedule", entity="maras-moray",
          contains=("09:35-15:25",), kind="fact", language="es")),
    ], {"maras-moray": {"schedule": "09:35-15:25"}})
    multi("explicit_catalog_cleared_duration", "es", [
        ("recomiendame medio dia no quiero caminar por favor", rec(pending=True)),
    ], {"maras-moray": {"duration": ""}})
    multi("explicit_catalog_deactivation", "es", [
        ("precio actual de maras moray", inactive("maras-moray")),
    ], {"maras-moray": {"is_active": False}})

    # This catches a constraint that a single half-day query can accidentally hide:
    # changing only the duration must retain "no quiero caminar" across turns.
    multi("negative_walking_infinitive_followup", "es", [
        ("recomiendame medio dia, no quiero caminar", rec(MARAS)),
        ("ahora tengo 4 días", rec(pending=True)),
    ])
    # An explicitly synthetic one-day Maras condition makes a missing numeric
    # interpretation observable, instead of hiding it behind only four-day treks.
    for language, question in [
        ("es", "recomiendame cuatro días sin caminatas"),
        ("en", "recommend four days without hiking"),
        ("es", "recomiendame 4 días sin caminatas"),
        ("en", "recommend 4 days without hiking"),
    ]:
        multi("exact_duration_counterexample_fixture", language,
              [(question, rec(pending=True, language=language))],
              {"maras-moray": {"duration": "1 día"}})

    # These are deliberately NOT part of the deterministic pass/fail denominator.
    # Running with a sentinel records the selected path only. Real retrieval and
    # generation and a human language/factual rubric must evaluate them later.
    for language, question in [
        ("pt", "Recomende um passeio de meio dia, não quero fazer caminhadas."),
        ("pt", "Quanto custa o passeio Maras Moray e o que está incluído?"),
        ("fr", "Je cherche une excursion d'une demi-journée sans randonnée."),
        ("fr", "Quel est le prix du chemin de l'Inca ?"),
        ("it", "Consigliami un tour di mezza giornata senza escursioni a piedi."),
        ("it", "A che ora parte il tour Maras Moray?"),
        ("mixed", "I have medio día y no quiero hiking, what do you recommend?"),
        ("mixed", "precio de Inca Trail please, sin inventar discounts"),
        ("es_open", "Compara Camino Inca con Inka Jungle para alguien que disfruta naturaleza."),
        ("en_open", "How should I prepare for the Inca Trail and what gear is documented?"),
    ]:
        cases.append(Case("EXP-%03d" % (len(cases) + 1), "exploratory_real_rag_or_language",
                          language, ((question, None),), exploration=True))
    return cases


def clean_text(value):
    text = unicodedata.normalize("NFKD", str(value)).casefold()
    return "".join(char for char in text if not unicodedata.combining(char))


def check_result(result, expected, question, spies, phones):
    assertions = []

    def check(name, actual, wanted):
        assertions.append({"assertion": name, "actual": actual, "expected": wanted, "passed": actual == wanted})

    route = result.get("response_route", result.get("route"))
    text = str(result.get("response", ""))
    check("route", route, expected.route)
    check("nonempty_response", bool(text.strip()), True)
    check("resolved_autonomously", result.get("resolved_autonomously"), not expected.pending)
    check("pending_flag", result.get("needs_confirmation"), expected.pending)
    check("external_retrieval_or_generation_calls", sum(spy.call_count for spy in spies.values()), 0)
    check("unsolicited_markdown_image", "![" in text, False)
    check("unsolicited_agency_phone", any(phone and phone in text for phone in phones), False)
    if expected.entity:
        check("entity_id", result.get("entity_id"), expected.entity)
    for token in expected.contains:
        check("fixture_fact:" + token, token in text, True)
    if expected.kind == "recommendation":
        check("offered_ids", sorted(result.get("recommended_tour_ids", [])), sorted(expected.ids))
        # Cross-check actual displayed titles independently of returned metadata.
        displayed = re.findall(r"^\s*• \*([^*\n]+)\*", text, re.MULTILINE)
        titles = {
            "camino inca clasico 4d/3n": "camino-inka", "inca trail classic 4d/3n": "camino-inka",
            "inca trail": "camino-inka", "inka jungle": "inka-jungle",
            "camino inca clasico": "camino-inka", "inka jungle to machu picchu": "inka-jungle",
            "maras - moray": "maras-moray", "maras-moray": "maras-moray",
        }
        displayed_ids = [titles.get(clean_text(title), "UNRECOGNIZED:" + title) for title in displayed]
        check("displayed_recommendation_ids", sorted(displayed_ids), sorted(expected.ids))
        check("no_duplicate_recommended_titles", len(displayed_ids), len(set(displayed_ids)))
        check("no_false_human_escalation", result.get("needs_agency_confirmation"), False)
        check("no_false_escalation", result.get("is_escalation"), False)
        if expected.language == "en":
            check("english_recommendation_or_question", bool(re.search(r"Based on|What interests|Would you like", text)), True)
            check("no_spanish_recommendation_label", "recomendaciones verificadas" in text or "¿Quieres" in text, False)
        if not expected.ids:
            check("offers_a_clarifying_question", "?" in text, True)
    if expected.kind == "inactive":
        check("inactive_status_explicit", bool(re.search(r"no figura|no se encuentra disponible|not currently|not available", text)), True)
        check("inactive_not_resolved", result.get("resolved_autonomously"), False)
        if expected.language == "en":
            check("english_inactive_status", bool(re.search(r"not currently|not available", text)), True)
    if expected.kind == "ambiguous":
        check("asks_for_tour_instead_of_guessing", bool(re.search(r"cual de los tours|which tour", clean_text(text))), True)
        entity_ids = set(str(result.get("entity_id", "")).split(","))
        check("ambiguity_candidates", sorted(entity_ids), ["camino-inka", "maras-moray"])
        check("clarification_not_handoff", result.get("needs_agency_confirmation"), False)
        if expected.language == "en":
            check("english_ambiguity_question", "Which tour" in text, True)
    if expected.kind == "fact" and expected.language == "en":
        check("english_factual_label", bool(re.search(r"Official rate|Schedule|Duration|Includes|Does not include", text)), True)
    if expected.kind == "fact":
        own_markers = {item for value in FIXTURE[expected.entity].values() if isinstance(value, str)
                       for item in re.findall(r"TEST_[A-Z_]+", value)}
        other_markers = {item for eid, data in FIXTURE.items() if eid != expected.entity
                         for value in data.values() if isinstance(value, str)
                         for item in re.findall(r"TEST_[A-Z_]+", value)}
        check("no_other_tour_fixture_markers", any(marker in text for marker in other_markers - own_markers), False)
    return assertions


def configure_fixture(snapshot, mutations, changed_ids=None):
    for entity_id, original in snapshot.items():
        if changed_ids is not None and entity_id not in changed_ids:
            continue
        payload = {"entity_id": entity_id, "name": original["name"], "is_active": False}
        if entity_id in FIXTURE:
            payload.update(FIXTURE[entity_id])
            payload["is_active"] = True
        payload.update(mutations.get(entity_id, {}))
        ok, detail = catalog_service.upsert_tour(payload)
        if not ok:
            raise RuntimeError("Unable to configure synthetic catalog: " + str(detail))
    actual_active = {tour["entity_id"] for tour in catalog_service.get_all_tours(active_only=True, strict=True)}
    expected_active = set(THREE) - {eid for eid, edit in mutations.items() if edit.get("is_active") is False}
    if actual_active != expected_active:
        raise AssertionError("Temporary fixture active IDs differ: " + repr(actual_active))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    database.init_db(app.SQLITE_DB_PATH)
    catalog_service.init_catalog_db()
    snapshot = {tour["entity_id"]: tour for tour in catalog_service.get_all_tours(active_only=False, strict=True)}
    if not THREE.issubset(snapshot):
        raise RuntimeError("Temporary seeded catalog lacks the three fixture entities")
    bank = build_bank()
    run_id = str(uuid4())
    phones = list(trial_support.CATALOG.get("agency", {}).get("phones", []))
    records = []
    all_questions = [question for case in bank for question, _ in case.turns]
    unique_questions = set(all_questions)
    if len(unique_questions) < 80:
        raise AssertionError("Bank must contain at least 80 genuinely different input strings")
    fixture_descriptor = {
        "name": FIXTURE_NAME, "is_synthetic": True, "active_ids": sorted(THREE),
        "catalog_values": FIXTURE, "no_production_data": True,
        "scope": "actual rag_chain routing, catalog facts and persisted conversation memory",
        "not_validated": ["real LLM correctness", "real RAG quality", "physical WhatsApp delivery", "all languages", "accessibility"],
    }
    print("ROBUSTNESS_FIXTURE " + json.dumps(fixture_descriptor, ensure_ascii=False))
    try:
        configure_fixture(snapshot, {})
        previous_mutation_ids = set()
        for case in bank:
            configure_fixture(snapshot, case.mutations, previous_mutation_ids | set(case.mutations))
            previous_mutation_ids = set(case.mutations)
            uid = "synthetic-robustness-" + uuid4().hex
            app.clear_history(uid)
            spies = {
                "retriever_factory": Mock(side_effect=AssertionError("UNEXPECTED_REAL_RETRIEVER_FACTORY")),
                "retriever_support": Mock(side_effect=AssertionError("UNEXPECTED_REAL_RETRIEVER_SUPPORT")),
                "llm_factory": Mock(side_effect=AssertionError("UNEXPECTED_REAL_LLM_FACTORY")),
            }
            record = {
                "run_id": run_id, "execution_id": str(uuid4()), "case_id": case.case_id, "id": case.case_id,
                "group": case.group, "language": case.language, "user_alias": uid,
                "fixture": FIXTURE_NAME, "catalog_mutations": case.mutations,
                "mode": "isolated_application", "is_exploratory": case.exploration,
                "turns": [], "status": "pending_review" if case.exploration else "passed",
                "exploratory": case.exploration,
                "reason": "Requires actual retrieval/generation and human language rubric; sentinel observation is not quality validation" if case.exploration else "",
            }
            try:
                with ExitStack() as stack:
                    stack.enter_context(patch.object(app, "get_retriever", spies["retriever_factory"]))
                    stack.enter_context(patch.object(trial_support, "retriever", spies["retriever_support"]))
                    stack.enter_context(patch.object(app, "get_llm", spies["llm_factory"]))
                    for question, expected in case.turns:
                        # Per-turn spy counts are exact, not a hidden cumulative count.
                        for spy in spies.values():
                            spy.reset_mock()
                        started = time.perf_counter()
                        turn = {"input": question, "output": None, "route": None,
                                "assertions": [], "exception": None, "latency_ms": None}
                        try:
                            result = app.rag_chain(question, uid)
                            turn["output"] = result
                            turn["route"] = result.get("response_route", result.get("route"))
                            if expected is not None:
                                turn["assertions"] = check_result(result, expected, question, spies, phones)
                                if not all(item["passed"] for item in turn["assertions"]):
                                    record["status"] = "failed"
                        except Exception as exc:
                            turn["exception"] = {"type": type(exc).__name__, "message": str(exc)}
                            if not case.exploration:
                                record["status"] = "failed"
                        finally:
                            turn["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
                            turn["spy_calls"] = {name: spy.call_count for name, spy in spies.items()}
                            record["turns"].append(turn)
            finally:
                app.clear_history(uid)
            record["inputs"] = [turn["input"] for turn in record["turns"]]
            record["outputs"] = [turn["output"] for turn in record["turns"]]
            record["checks"] = [
                {"name": "turn_%d:%s" % (index + 1, item["assertion"]),
                 "passed": item["passed"], "actual": item["actual"], "expected": item["expected"]}
                for index, turn in enumerate(record["turns"]) for item in turn["assertions"]
            ]
            exceptions = [turn["exception"] for turn in record["turns"] if turn["exception"]]
            record["exception"] = exceptions or None
            record["llm_calls"] = sum(turn["spy_calls"]["llm_factory"] for turn in record["turns"])
            record["retrieval_calls"] = sum(turn["spy_calls"]["retriever_factory"] + turn["spy_calls"]["retriever_support"] for turn in record["turns"])
            records.append(record)
            print("ROBUSTNESS_CASE " + json.dumps(record, ensure_ascii=False, default=str), flush=True)
    finally:
        for tour in snapshot.values():
            ok, detail = catalog_service.upsert_tour(tour)
            if not ok:
                raise RuntimeError("Temporary fixture restore failed: " + str(detail))
    core = [record for record in records if not record["is_exploratory"]]
    summary = {
        "run_id": run_id, "fixture": FIXTURE_NAME, "status": "failed" if any(record["status"] == "failed" for record in core) else "passed",
        "total_cases": len(records), "passed": sum(record["status"] == "passed" for record in records),
        "failed": sum(record["status"] == "failed" for record in records),
        "pending_review": sum(record["status"] == "pending_review" for record in records),
        "total_messages": len(all_questions),
        "core_case_count": len(core), "core_passed": sum(record["status"] == "passed" for record in core),
        "core_failed": sum(record["status"] == "failed" for record in core),
        "exploratory_pending_count": sum(record["is_exploratory"] for record in records),
        "scenario_groups": sorted({record["group"] for record in records}),
        "case_count": len(records), "input_turn_count": len(all_questions),
        "unique_input_string_count": len(unique_questions),
        "repeated_input_turn_count": len(all_questions) - len(unique_questions),
        "duplicates_are_not_additional_coverage": True,
        "transport": "not_used", "provider_calls": "blocked_by_raising_sentinels_and_runner",
        "real_llm_and_multilingual_quality": "not_evaluated", "universal_precision_claim": False,
        "failed_case_ids": [record["case_id"] for record in core if record["status"] == "failed"],
    }
    print("ROBUSTNESS_SUMMARY " + json.dumps(summary, ensure_ascii=False), flush=True)
    return 1 if summary["core_failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
