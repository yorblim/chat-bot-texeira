"""Bounded, inspectable exploration of the current RAG; not an accuracy score.

Default execution is DRY: real offline retrieval, NONFACTUAL generation sentinel,
no secret access, network, WhatsApp, or production writes. --live explicitly enables
up to ten single-attempt calls to the existing Groq model. Every semantic judgment
stays pending. Local memory, catalog and copied index are deleted after the run.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
ACTIVE_IDS = frozenset({"camino-inka", "inka-jungle", "maras-moray"})
PROVIDER = "groq"
MODEL = "qwen/qwen3.8-27b"
BASE_URL = "https://api.groq.com/openai/v1"
MAX_CALLS = 10
DRY_SENTINEL = "[DRY_RUN_NONFACTUAL_GENERATION: no factual answer was generated or approved]"
CASES = (
    ("EXP-139", "pt", "Recomende um passeio de meio dia, não quero fazer caminhadas."),
    ("EXP-140", "pt", "Quanto custa o passeio Maras Moray e o que está incluído?"),
    ("EXP-141", "fr", "Je cherche une excursion d'une demi-journée sans randonnée."),
    ("EXP-142", "fr", "Quel est le prix du chemin de l'Inca ?"),
    ("EXP-143", "it", "Consigliami un tour di mezza giornata senza escursioni a piedi."),
    ("EXP-144", "it", "A che ora parte il tour Maras Moray?"),
    ("EXP-145", "mixed", "I have medio día y no quiero hiking, what do you recommend?"),
    ("EXP-146", "mixed", "precio de Inca Trail please, sin inventar discounts"),
    ("EXP-147", "es_open", "Compara Camino Inca con Inka Jungle para alguien que disfruta naturaleza."),
    ("EXP-148", "en_open", "How should I prepare for the Inca Trail and what gear is documented?"),
)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def protected_hashes():
    """Read-only fingerprints of sources, index and protected historical results."""
    paths = list(ROOT.glob("*.py")) + list((ROOT / "src").rglob("*.py"))
    paths += list((ROOT / "data").glob("*.json"))
    paths += [path for path in (ROOT / "chroma_catalogo_20260926_db").rglob("*") if path.is_file()]
    for name in (
        "evaluaciones/RESULTADOS_POSPRUEBA_TESIS_20260921.json",
        "evaluaciones/INFORME_POSPRUEBA_TESIS_20260921.md",
        "evaluaciones/RESULTADOS_POSPRUEBA_TESIS_20261004_RECALIBRADO.json",
        "REGISTRO_VALIDACION_WHATSAPP_00047.json",
    ):
        path = ROOT / "docs" / name
        if path.is_file():
            paths.append(path)
    return {str(path.relative_to(ROOT)): sha256(path) for path in sorted(set(paths))}


def load_snapshot(path):
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, list) or not value:
        raise ValueError("Catalog snapshot must be a nonempty JSON array")
    if any(not isinstance(row, dict) or not row.get("entity_id") for row in value):
        raise ValueError("Every snapshot row must contain an entity_id")
    ids = [row["entity_id"] for row in value]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate snapshot entity identifiers")
    if {row["entity_id"] for row in value if row.get("is_active")} != ACTIVE_IDS:
        raise ValueError("Exactly the three authorized catalog products must be active")
    permitted = {
        "entity_id", "name", "aliases", "official_price", "currency", "schedule", "duration",
        "includes", "excludes", "is_active", "is_canonical", "created_at", "updated_at",
        "photo_filename", "brochure_filename", "overridden_fields",
    }
    if any(set(row) - permitted for row in value):
        raise ValueError("Unexpected catalog fields; do not accept credentials or binary assets")
    for row in value:
        if not isinstance(row.get("aliases", []), list):
            raise ValueError("Catalog aliases must be an array")
        overrides = row.get("overridden_fields", [])
        if not isinstance(overrides, list) or set(overrides) - {"official_price", "schedule", "duration", "includes", "excludes"}:
            raise ValueError("Invalid explicit catalog overrides")
    return value


def messages_for_report(messages):
    return [
        {"role": item[0], "content": item[1]} if isinstance(item, (tuple, list)) else
        {"role": getattr(item, "type", "unknown"), "content": getattr(item, "content", "")}
        for item in messages
    ]


class CompletionPacer:
    """Conservative rolling output-token quota; reserve the full 900-token cap.

    Token totals are recorded separately. Missing usage triggers a full minute
    between calls. Sleeps never exceed sixty seconds and are announced on stdout.
    This is throttling, not a promise of provider quota availability.
    """
    def __init__(self, clock=time.monotonic, sleep=time.sleep, announce=print):
        self.clock, self.sleep, self.announce = clock, sleep, announce
        self.samples = []
        self.waits = []

    def before_call(self):
        while self.samples:
            now = self.clock()
            self.samples = [(stamp, count) for stamp, count in self.samples if now - stamp < 60]
            if not self.samples or sum(count for _, count in self.samples) + 900 <= 900:
                return
            delay = min(60.0, max(0.0, 60.0 - (now - self.samples[0][0])))
            if delay <= 0:
                return
            self.waits.append(round(delay, 3))
            self.announce(json.dumps({"phase": "provider_quota_wait", "seconds": round(delay, 1)}), flush=True)
            self.sleep(delay)

    def after_call(self, completion_tokens):
        count = completion_tokens if isinstance(completion_tokens, (int, float)) and completion_tokens >= 0 else 900
        self.samples.append((self.clock(), count))


class AuditedLlm:
    """Count each single-attempt invocation, including failures swallowed by RAG."""
    def __init__(self, client=None, live=False, max_calls=MAX_CALLS, pacer=None):
        if not 1 <= max_calls <= MAX_CALLS:
            raise ValueError("Call budget must be between one and ten")
        if live and client is None:
            raise ValueError("Live mode requires the existing provider client")
        self.client, self.live, self.max_calls = client, live, max_calls
        self.pacer = pacer or CompletionPacer()
        self.records = []
        self.halted = False

    def invoke(self, messages, **kwargs):
        if self.halted:
            raise RuntimeError("Evaluation stopped after its first generation error")
        if len(self.records) >= self.max_calls:
            self.halted = True
            raise RuntimeError("Strict real-generation budget exhausted")
        record = {
            "call_index": len(self.records) + 1, "input_messages": messages_for_report(messages),
            "execution": "real_provider" if self.live else "nonfactual_dry_sentinel",
            "started_at": utc_now(), "status": "started",
        }
        self.records.append(record)
        started = time.perf_counter()
        try:
            if self.live:
                self.pacer.before_call()
                started = time.perf_counter()
            answer = self.client.invoke(messages, **kwargs) if self.live else SimpleNamespace(
                content=DRY_SENTINEL, response_metadata={}, usage_metadata={})
            metadata = getattr(answer, "response_metadata", {}) or {}
            usage = metadata.get("token_usage") or getattr(answer, "usage_metadata", {}) or {}
            record.update(
                status="completed", raw_response=answer.content, token_usage=usage,
                reported_model=metadata.get("model_name"), finish_reason=metadata.get("finish_reason"),
            )
            if self.live:
                self.pacer.after_call(usage.get("completion_tokens", usage.get("output_tokens")))
            return answer
        except Exception as exc:
            # Never serialize provider exception messages, headers, keys or URLs.
            self.halted = True
            record.update(status="provider_error", error_type=type(exc).__name__,
                          http_status=getattr(exc, "status_code", None))
            raise
        finally:
            record["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
            record["finished_at"] = utc_now()


class AuditedRetriever:
    def __init__(self, retriever):
        self.retriever, self.records = retriever, []
        self.halted = False

    def invoke(self, query):
        started = time.perf_counter()
        record = {"query": query, "documents": [], "status": "started"}
        self.records.append(record)
        try:
            docs = self.retriever.invoke(query)
            record.update(status="completed", documents=[{"content": doc.page_content, "metadata": doc.metadata} for doc in docs])
            return docs
        except Exception as exc:
            self.halted = True
            record.update(status="retrieval_error", error_type=type(exc).__name__)
            raise
        finally:
            record["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)


def obtain_groq_key():
    """Read the configured secret into process memory only, exclusively in --live."""
    binary = shutil.which("gcloud") or shutil.which("gcloud.cmd")
    if not binary:
        candidate = Path.home() / "AppData/Local/Google/Cloud SDK/google-cloud-sdk/bin/gcloud.cmd"
        binary = str(candidate) if candidate.is_file() else None
    if not binary:
        raise RuntimeError("Existing gcloud executable is unavailable")
    command = [binary, "secrets", "versions", "access", "latest", "--secret=GROQ_API_KEY",
               "--project=texeira-whatsapp-bot"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=45, check=False)
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError("Unable to read the existing Groq secret; no provider call made")
    return result.stdout.strip()


def install_snapshot(catalog_service, snapshot):
    """Reproduce administrative values and exact empty-field override semantics."""
    catalog_service.init_catalog_db()
    from db_adapter import get_db_session, is_postgres
    if is_postgres():
        raise RuntimeError("An evaluation may not use PostgreSQL")
    with get_db_session() as conn:
        conn.execute("UPDATE catalog_tours SET is_active=0")
        conn.execute("DELETE FROM catalog_field_overrides")
        columns = {row[1] for row in conn.execute("PRAGMA table_info(catalog_tours)").fetchall()}
        for tour in snapshot:
            if not conn.execute("SELECT entity_id FROM catalog_tours WHERE entity_id=?", (tour["entity_id"],)).fetchone():
                raise ValueError("Snapshot product is not present in the canonical local catalog")
            fields = [field for field in tour if field in columns and field != "entity_id"]
            values = [json.dumps(tour[field], ensure_ascii=False) if field == "aliases" else tour[field] for field in fields]
            conn.execute("UPDATE catalog_tours SET " + ",".join(field + "=?" for field in fields) + " WHERE entity_id=?",
                         tuple(values + [tour["entity_id"]]))
            for field in tour.get("overridden_fields", []):
                conn.execute("INSERT INTO catalog_field_overrides(entity_id,field) VALUES (?,?)", (tour["entity_id"], field))
    catalog_service.invalidate_catalog_cache()
    restored = {tour["entity_id"]: tour for tour in catalog_service.get_all_tours(active_only=True, strict=True)}
    if set(restored) != ACTIVE_IDS:
        raise AssertionError("The isolated catalog contains unexpected active products")
    for tour in snapshot:
        if tour.get("is_active"):
            for field in ("official_price", "currency", "schedule", "duration", "includes", "excludes", "aliases", "overridden_fields"):
                expected, actual = tour.get(field, [] if field in {"aliases", "overridden_fields"} else ""), restored[tour["entity_id"]].get(field)
                if field == "overridden_fields":
                    expected, actual = sorted(expected), sorted(actual or [])
                if actual != expected:
                    raise AssertionError("Snapshot field was changed by local initialization: " + field)


def close_temporary_chroma(temporary_root):
    module = sys.modules.get("chromadb.api.shared_system_client")
    if module is None:
        return 0
    cache = module.SharedSystemClient._identifier_to_system
    closed = set()
    for key, system in list(cache.items()):
        settings = system.settings
        if not settings.is_persistent or not Path(settings.persist_directory).resolve().is_relative_to(Path(temporary_root).resolve()):
            continue
        if id(system) not in closed:
            system.stop()
            closed.add(id(system))
        if cache.get(key) is system:
            del cache[key]
    return len(closed)


def select_cases(case_ids=(), max_cases=10):
    if not 1 <= max_cases <= len(CASES):
        raise ValueError("Case count must be between one and ten")
    known = {case[0] for case in CASES}
    if len(case_ids) != len(set(case_ids)) or set(case_ids) - known:
        raise ValueError("Unknown or duplicate exploration case identifiers")
    return [case for case in CASES if not case_ids or case[0] in case_ids][:max_cases]


def run(args):
    snapshot_path = Path(args.catalog_snapshot).resolve()
    snapshot = load_snapshot(snapshot_path)
    selected = select_cases(args.case_id, args.max_cases)
    output_dir = ROOT / "docs" / "evaluaciones"
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
    report_path = output_dir / ("EVALUACION_RAG_REAL_" if args.live else "EVALUACION_RAG_DRY_")
    report_path = report_path.with_name(report_path.name + run_id + ".json")
    before = protected_hashes()
    report = {
        "started_at": utc_now(), "run_id": run_id, "mode": "real_provider_exploration" if args.live else "offline_dry_sentinel",
        "provider": PROVIDER, "model": MODEL, "max_invocations": args.max_calls, "max_retries": 0,
        "request_timeout_seconds": 45, "max_output_tokens": 900, "catalog_snapshot": str(snapshot_path),
        "catalog_snapshot_sha256": sha256(snapshot_path), "active_entity_ids": sorted(ACTIVE_IDS),
        "whatsapp_sends": 0, "production_database_writes": 0, "semantic_precision": None,
        "semantic_approval": False, "cases": [], "generation_calls": [], "status": "started",
        "source_hashes_before": before,
        "limitations": [
            "Ten original finite explorations are not exhaustive and do not estimate general precision.",
            "All semantic/language judgments require review against supplied sources and administrative snapshot.",
            "Dry output is a nonfactual sentinel, never evidence of a real model response.",
            "Direct rag_chain evaluation does not verify WhatsApp buttons, transport, or phone delivery.",
        ],
    }
    env_before, cwd_before = dict(os.environ), Path.cwd()
    auditor = None
    trial_support = None
    original_configure = None
    original_connect, original_connect_ex = socket.socket.connect, socket.socket.connect_ex
    fatal = False

    def save():
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    try:
        key = obtain_groq_key() if args.live else "DRY_NON_SECRET"
        allowed_addresses = set()
        if args.live:
            allowed_addresses = {row[4][0] for row in socket.getaddrinfo("api.groq.com", 443, type=socket.SOCK_STREAM)}
        with tempfile.TemporaryDirectory(prefix="texeira-real-rag-") as directory:
            temporary = Path(directory)
            try:
                os.chdir(temporary)
                os.environ.update(
                    DATABASE_URL="", TEXEIRA_STATE_DIR=directory, SQLITE_DB_PATH=str(temporary / "memory.db"),
                    TEXEIRA_ENABLE_WHATSAPP="false", TEXEIRA_ENABLE_MESSENGER="false",
                    TEXEIRA_ENABLE_ADVISOR_NOTIFICATIONS="false", ADVISOR_WHATSAPP_PHONE="",
                    HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", ANONYMIZED_TELEMETRY="False",
                    CHROMA_HYBRID_DIR=str(temporary / "index"), CHROMA_PERSIST_DIR=str(temporary / "index"),
                    LLM_PROVIDER=PROVIDER, LLM_MODEL=MODEL, GROQ_API_BASE=BASE_URL, GROQ_API_KEY=key,
                    ADMIN_USER="", ADMIN_PASSWORD="", K_SERVICE="", ALLOW_CLOUD_RUN="",
                )
                sys.path.insert(0, str(ROOT))
                import runtime_settings
                original_configure = runtime_settings.configure
                runtime_settings.configure = lambda env=None, values=None: original_configure(env=env, values={})

                def guarded_connect(sock, address):
                    if isinstance(address, tuple):
                        host, port = address[:2]
                        if host in {"127.0.0.1", "::1"} or (args.live and port == 443 and (host == "api.groq.com" or host in allowed_addresses)):
                            return original_connect(sock, address)
                    raise RuntimeError("External network outside the explicit Groq evaluation is prohibited")

                def guarded_connect_ex(sock, address):
                    guarded_connect(sock, address)
                    return 0

                socket.socket.connect, socket.socket.connect_ex = guarded_connect, guarded_connect_ex
                import catalog_service
                catalog_service.CATALOG_JSON_PATH = temporary / "catalog.json"
                shutil.copyfile(ROOT / "data" / "tours_catalog.json", catalog_service.CATALOG_JSON_PATH)
                catalog_service.IMAGES_DIR, catalog_service.BROCHURES_DIR = temporary / "images", temporary / "brochures"
                catalog_service.IMAGES_DIR.mkdir()
                catalog_service.BROCHURES_DIR.mkdir()
                import trial_support as support
                trial_support = support
                support.INDEX = temporary / "index"
                shutil.copytree(ROOT / "chroma_catalogo_20260926_db", support.INDEX)
                support.retriever.cache_clear()
                # Module initialization can print implementation details; discard it.
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    import app
                    import database
                    database.init_db(app.SQLITE_DB_PATH)
                    install_snapshot(catalog_service, snapshot)
                    real_retriever = app.get_retriever()
                if real_retriever is None:
                    raise RuntimeError("The existing offline retrieval index is unavailable")
                if app.LLM_PROVIDER != PROVIDER or app.LLM_MODEL != MODEL:
                    raise RuntimeError("Unexpected configured provider or model")
                client = None
                if args.live:
                    # Same deployed provider/model/options; explicitly disable SDK retries.
                    client = app.ChatOpenAI(model=app.LLM_MODEL, temperature=0.1, max_tokens=900,
                                            timeout=45, max_retries=0, api_key=key, base_url=BASE_URL)
                # RAG's implementation prints are discarded below; quota progress
                # remains visible without exposing prompts, responses or secrets.
                pacer = CompletionPacer(announce=lambda message, **kwargs: print(message, file=sys.__stdout__, **kwargs))
                auditor = AuditedLlm(client=client, live=args.live, max_calls=args.max_calls, pacer=pacer)
                retriever_audit = AuditedRetriever(real_retriever)
                app.get_llm = lambda: auditor
                app.get_retriever = lambda: retriever_audit
                report["generation_calls"] = auditor.records
                for case_id, declared_language, question in selected:
                    started = time.perf_counter()
                    call_start, retrieval_start = len(auditor.records), len(retriever_audit.records)
                    user_id = "synthetic-rag-" + run_id + "-" + case_id
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        result = app.rag_chain(question, user_id=user_id)
                    calls = auditor.records[call_start:]
                    successful = [call for call in calls if call["status"] == "completed"]
                    route = result.get("response_route")
                    row = {
                        "case_id": case_id, "declared_input_language": declared_language, "question": question,
                        "detected_language": app.detect_language(question), "result": result,
                        "retrieval": retriever_audit.records[retrieval_start:], "generation_calls": calls,
                        "real_llm_calls": len(calls) if args.live else 0,
                        "dry_generation_calls": 0 if args.live else len(calls),
                        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                        "review_status": "pending", "semantic_passed": None,
                        "structural_checks": {
                            "response_is_nonempty_string": isinstance(result.get("response"), str) and bool(result["response"].strip()),
                            "rag_llm_route_has_its_own_successful_call": route != "rag_llm" or bool(successful),
                            "current_question_preserved_in_all_model_prompts": all(call["input_messages"][-1]["content"] == question for call in calls),
                            "call_budget_respected": len(auditor.records) <= args.max_calls,
                        },
                    }
                    report["cases"].append(row)
                    report["status"] = "running"
                    save()
                    print(json.dumps({"case_id": case_id, "route": route, "generation_calls": len(calls),
                                      "review_status": "pending", "mode": report["mode"]}), flush=True)
                    # rag_chain catches provider failures; the auditor is authoritative.
                    if auditor.halted or any(call["status"] == "provider_error" for call in calls):
                        fatal = True
                        report["status"] = "stopped_after_first_generation_error"
                        break
                    if retriever_audit.halted:
                        fatal = True
                        report["status"] = "stopped_after_retrieval_error"
                        break
                    if not all(row["structural_checks"].values()):
                        fatal = True
                        report["status"] = "stopped_after_structural_failure"
                        break
                if not fatal:
                    report["status"] = "completed_pending_semantic_review"
            finally:
                if trial_support is not None:
                    trial_support.retriever.cache_clear()
                report["temporary_chroma_systems_closed"] = close_temporary_chroma(temporary)
                os.chdir(cwd_before)
    except Exception as exc:
        fatal = True
        report.update(status="stopped_after_evaluation_error", error_type=type(exc).__name__)
        # Messages may contain configuration/credentials; record only exception class.
    finally:
        socket.socket.connect, socket.socket.connect_ex = original_connect, original_connect_ex
        if original_configure is not None:
            sys.modules["runtime_settings"].configure = original_configure
        os.chdir(cwd_before)
        os.environ.clear()
        os.environ.update(env_before)
        after = protected_hashes()
        changed = sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))
        report.update(finished_at=utc_now(), source_hashes_after=after, changed_protected_paths=changed,
                      protected_sources_unchanged=not changed, total_real_llm_calls=len(auditor.records) if args.live and auditor else 0,
                      total_dry_generation_calls=len(auditor.records) if not args.live and auditor else 0,
                      provider_quota_wait_seconds=auditor.pacer.waits if auditor else [])
        if changed:
            fatal = True
            report["status"] = "protected_sources_changed_during_run"
        save()
    print(json.dumps({"report": str(report_path), "status": report["status"], "cases_recorded": len(report["cases"]),
                      "real_calls": report["total_real_llm_calls"], "semantic_precision": None}), flush=True)
    return 1 if fatal else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-snapshot", required=True, help="Read-only catalog JSON array obtained separately")
    parser.add_argument("--live", action="store_true", help="Explicitly allow existing Groq secret access and bounded generation")
    parser.add_argument("--max-calls", type=int, default=10, choices=range(1, 11))
    parser.add_argument("--max-cases", type=int, default=10, choices=range(1, 11))
    parser.add_argument("--case-id", action="append", default=[], help="Optional original EXP-139..EXP-148 subset")
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
