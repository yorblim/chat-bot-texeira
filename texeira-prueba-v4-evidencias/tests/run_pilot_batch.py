"""Run a finite offline regression batch and preserve its evidence.

Every child uses run_isolated.py. No live API, WhatsApp send or LLM provider
is called by this launcher. Existing suites can contain simulated providers;
their success must not be described as live model quality or delivery.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SUITES = (
    "test_conversation_robustness_batch.py",
    "test_validation_recommendation_edges_20261008.py",
    "test_normalize_query.py",
    "test_whatsapp_flow_polish.py",
    "test_interactive_whatsapp_buttons.py",
    "test_catalog_connected_flow.py",
    "test_dedup.py",
)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def readable(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def parse_records(output):
    cases, summaries, errors = [], [], []
    for line in output.splitlines():
        for marker, destination in (
            ("ROBUSTNESS_CASE ", cases),
            ("ROBUSTNESS_SUMMARY ", summaries),
        ):
            if line.startswith(marker):
                try:
                    value = json.loads(line[len(marker):])
                    if not isinstance(value, dict):
                        raise ValueError("Expected an object")
                    destination.append(value)
                except (ValueError, TypeError) as exc:
                    errors.append(str(exc))
    return cases, summaries, errors


def validate_bank(cases, summaries):
    """Reject contradictory logs even when a child mistakenly exits zero."""
    errors = []
    if not cases or len(summaries) != 1:
        return ["Bank must emit cases and exactly one summary"]
    identifiers = set()
    counts = dict(passed=0, failed=0, pending_review=0)
    messages = 0
    for case in cases:
        identifier = case.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            errors.append("Missing or repeated case id")
        else:
            identifiers.add(identifier)
        status = case.get("status")
        if status not in counts:
            errors.append(f"Invalid case status: {identifier}")
            continue
        counts[status] += 1
        inputs, outputs = case.get("inputs"), case.get("outputs")
        if not isinstance(inputs, list) or not inputs or not all(isinstance(q, str) for q in inputs):
            errors.append(f"Missing actual inputs: {identifier}")
        else:
            messages += len(inputs)
            if not isinstance(outputs, list) or len(outputs) != len(inputs):
                errors.append(f"Output/actual-input count mismatch: {identifier}")
        if status == "passed":
            checks = case.get("checks")
            if not isinstance(checks, list) or not checks or not all(
                isinstance(c, dict) and isinstance(c.get("name"), str)
                and c.get("passed") is True for c in checks
            ):
                errors.append(f"Passed case without successful checks: {identifier}")
            if case.get("exception"):
                errors.append(f"Passed case has an exception: {identifier}")
        if status == "pending_review" and not case.get("reason"):
            errors.append(f"Pending exploration needs a reason: {identifier}")
    expected = dict(total_cases=len(cases), total_messages=messages, **counts)
    for name, value in expected.items():
        observed = summaries[0].get(name)
        if type(observed) is not int or observed != value:
            errors.append(f"Summary mismatch: {name}")
    if counts["failed"]:
        errors.append(f"Bank contains {counts['failed']} failed case(s)")
    return errors


def git_metadata():
    def query(*args):
        result = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, encoding="utf-8",
            errors="replace", timeout=15, check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    return {"head_before_run": query("rev-parse", "HEAD"),
            "branch": query("branch", "--show-current"),
            "working_tree_before_run": query("status", "--short"),
            "note": "HEAD alone does not identify uncommitted tests or application changes."}


def source_hashes():
    # Include real application source and the test harness; no secrets/data files.
    files = [p for p in ROOT.glob("*.py") if p.is_file()]
    files += [p for p in (ROOT / "src").rglob("*.py") if p.is_file()]
    files += [ROOT / "tests" / name for name in (*SUITES, "run_isolated.py", "run_pilot_batch.py")]
    return {str(p.relative_to(ROOT)).replace("\\", "/"):
            hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(files)) if p.is_file()}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", action="append", choices=SUITES,
                        help="Optional subset; default runs all seven suites.")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    if not 30 <= args.timeout_seconds <= 600:
        parser.error("timeout must be between 30 and 600 seconds")
    selected = list(dict.fromkeys(args.suite or SUITES))
    missing = [name for name in selected if not (ROOT / "tests" / name).is_file()]
    if missing:
        parser.error("Missing suite(s): " + ", ".join(missing))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
    logs = ROOT / "logs"
    reports = ROOT / "docs" / "evaluaciones"
    logs.mkdir(exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    report_path = reports / ("ROBUSTEZ_AUTOMATICA_" + run_id + ".json")
    before = source_hashes()
    report = {
        "run_id": run_id, "started_at_utc": utc_now(), "modality": "aislada",
        "environment": "temporary SQLite/catalog/index; external networking blocked by run_isolated.py",
        "git": git_metadata(), "source_sha256_before": before,
        "production_revision_verified": None,
        "real_llm_quality_verified": False, "whatsapp_delivery_verified": False,
        "formal_42_case_registry_updated": False,
        "precision_current_bot_percent": None, "suites": [],
        "limitations": [
            "Regression successes are structural assertions, not customer accuracy or human validation.",
            "Existing suites may mock retrieval/generation, transport or signature checks.",
            "Language exploration pending review must not be counted as approved fluency.",
            "A finite bank cannot cover every typo, language or user question.",
            "A timed-out child may not execute temporary-state cleanup; inspect any timeout instead of assuming cleanup.",
            "Source hashes cover selected Python sources, not the entire data/index/fixture environment.",
        ],
    }
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    for index, name in enumerate(selected, 1):
        print(f"[{index}/{len(selected)}] Starting {name}", flush=True)
        started = utc_now()
        timeout = False
        execution_error = None
        try:
            process = subprocess.run(
                [sys.executable, str(ROOT / "tests" / "run_isolated.py"), name],
                cwd=ROOT, env=env, capture_output=True, encoding="utf-8",
                errors="replace", timeout=args.timeout_seconds, check=False,
            )
            code, stdout, stderr = process.returncode, process.stdout, process.stderr
        except subprocess.TimeoutExpired as exc:
            timeout = True
            code, stdout, stderr = None, readable(exc.stdout), readable(exc.stderr)
            stderr += "\nBatch launcher timeout: process terminated."
        except OSError as exc:
            code, stdout, stderr = None, "", str(exc)
            execution_error = str(exc)
        output = stdout + "\n--- STDERR ---\n" + stderr
        log_path = logs / ("piloto_automatico_" + run_id + "_" + Path(name).stem + ".log")
        with log_path.open("x", encoding="utf-8") as handle:
            handle.write(output)
        cases, summaries, record_errors = parse_records(stdout)
        test_count = re.search(r"Ran (\d+) tests?\b", output)
        passed = code == 0 and not record_errors
        # The new bank has a structured contract: no unconditional PASS if it
        # exits cleanly without actually recording any case and a summary.
        if name == "test_conversation_robustness_batch.py":
            record_errors.extend(validate_bank(cases, summaries))
            passed = passed and not record_errors
        entry = {
            "suite": name, "started_at_utc": started, "finished_at_utc": utc_now(),
            "exit_code": code, "timed_out": timeout, "execution_error": execution_error,
            "status": "passed" if passed else "failed",
            "unittest_method_count": int(test_count.group(1)) if test_count else None,
            "log": str(log_path.relative_to(ROOT)).replace("\\", "/"),
            "cases": cases, "case_summaries": summaries, "record_parse_errors": record_errors,
        }
        report["suites"].append(entry)
        print(f"[{index}/{len(selected)}] {entry['status'].upper()} {name}", flush=True)
    after = source_hashes()
    report["source_sha256_after"] = after
    report["changed_source_paths"] = sorted(p for p in before.keys() | after.keys()
                                             if before.get(p) != after.get(p))
    report["source_changed_during_run"] = before != after
    report["finished_at_utc"] = utc_now()
    report["all_selected_suites_passed"] = (
        all(s["status"] == "passed" for s in report["suites"]) and before == after
    )
    with report_path.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print("BATCH_REPORT " + str(report_path), flush=True)
    print("No live messages or model quality certification; review failed/pending cases in the report.", flush=True)
    return 0 if report["all_selected_suites_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
