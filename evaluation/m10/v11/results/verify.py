#!/usr/bin/env python3
"""Verify saved V11 evidence without inference; semantic scoring remains manual.

By default only stdout is written. --results-dir can point at the Chief's live
results. --output-dir must be a new directory, and receives derived reports only.
An incomplete/live run produces a report and exits nonzero, preserving missing slots.
"""

import argparse
import hashlib
import importlib
import json
import math
import statistics
import subprocess
import sys
from collections import Counter
from contextlib import contextmanager, nullcontext
from copy import deepcopy
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M10 = ROOT.parent
CAPS = {"baseline": 160, "proposed": 116}
RUN_REVISION = "0046e4970dce6ce75a1567ff2f0cba072468d969"
FREEZE_REVISION = "e866b10e23ebf4c359c0c7e643f92cb8a3640c37"
VERIFIER = "m10-v11-results"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    # Python equality alone treats True and 1 as equal.
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError(f"Nonfinite JSON value: {value}")


def decode(data):
    return json.loads(data, object_pairs_hook=unique_object, parse_constant=invalid_constant)


class Checks:
    def __init__(self):
        self.failures = []

    def require(self, condition, location, message, *, kind="integrity"):
        if not condition:
            self.failures.append({"kind": kind, "location": location, "message": message})
        return bool(condition)

    def equal(self, actual, expected, location, message):
        return self.require(canonical(actual) == canonical(expected), location, message)

    def failed(self, location, error):
        self.require(False, location, f"{type(error).__name__}: {error}")


def manifests(checks):
    counts = {"historical": 0, "v11": 0}
    folders = [M10, *(M10 / f"v{n}" for n in range(2, 11))]
    paths = [folder / name for folder in folders for name in ("sha256.json", "results/sha256.json")]
    paths.append(ROOT / "sha256.json")
    current = {}
    for path in paths:
        group = "v11" if path == ROOT / "sha256.json" else "historical"
        try:
            manifest = decode(path.read_bytes())
            if path == ROOT / "sha256.json":
                current = manifest
            for name, expected in manifest.items():
                counts[group] += 1
                try:
                    target = (path.parent / name).resolve()
                    if not checks.require(
                        target.is_relative_to(M10), str(path), "Manifest path escapes M10"
                    ):
                        continue
                    checks.equal(
                        digest(target.read_bytes()), expected, str(target), "SHA256 mismatch"
                    )
                except (OSError, ValueError, TypeError) as error:
                    checks.failed(str(path) + "/" + name, error)
        except (OSError, ValueError, TypeError, AttributeError) as error:
            checks.failed(str(path), error)
    checks.equal(counts, {"historical": 396, "v11": 67}, "manifests", "Unexpected entry counts")
    return counts, current


@contextmanager
def frozen_imports(arm, checks):
    """Keep the two frozen packages separate, including importlib prompt resources."""
    old_path = sys.path[:]
    old_modules = {k: v for k, v in sys.modules.items() if k.split(".")[0] == "meeting_notes"}
    for name in old_modules:
        del sys.modules[name]
    source = ROOT / arm
    sys.path.insert(0, str(source))
    try:
        runtime = importlib.import_module("meeting_notes.ollama")
        evidence = importlib.import_module("meeting_notes.evidence") if arm == "proposed" else None
        loaded = {
            name: str(Path(module.__file__).resolve())
            for name, module in tuple(sys.modules.items())
            if name.split(".")[0] == "meeting_notes" and getattr(module, "__file__", None)
        }
        for name, path in loaded.items():
            if not checks.require(Path(path).is_relative_to(source), name, "Nonfrozen import"):
                raise RuntimeError("Refusing replay with nonfrozen imports")
        yield runtime, evidence, loaded
    finally:
        for name in list(sys.modules):
            if name.split(".")[0] == "meeting_notes":
                del sys.modules[name]
        sys.modules.update(old_modules)
        sys.path[:] = old_path


def historical_replay(checks):
    # This script reads saved wrapper-9 evidence; historical results scripts write it.
    result = subprocess.run(
        [sys.executable, "-B", str(ROOT / "check_offline.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    if not checks.require(
        result.returncode == 0, "check_offline.py", result.stderr or "Replay failed"
    ):
        return None
    try:
        report = decode(result.stdout)
        checks.equal(report["historical_manifest_entries"], 396, "historical replay", "Entry count")
        checks.equal(report["wrapper9_replays"], 17, "historical replay", "Wrapper-9 replay count")
        return report
    except (ValueError, KeyError, TypeError) as error:
        checks.failed("historical replay", error)
        return None


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("Timestamp must include a UTC offset")
    return parsed


def run_metadata(run, manifest, settings, checks):
    checks.equal(run.get("approved_repetitions"), 1, "run", "Repetitions differ from approval")
    checks.equal(run.get("approved_cases_per_arm"), 40, "run", "Case count differs from approval")
    checks.equal(
        run.get("approved_total_request_cap"), 276, "run", "Total cap differs from approval"
    )
    checks.equal(run.get("arm_caps"), CAPS, "run", "Arm caps differ from approval")
    checks.equal(run.get("frozen_hashes"), manifest, "run", "Frozen hashes differ")
    checks.equal(
        run.get("revision"), RUN_REVISION, "run", "Run revision differs from approved base"
    )
    provenance = decode((ROOT / "provenance.json").read_bytes())
    checks.equal(
        run.get("source_revision"), provenance["implementation_commit"], "run", "Source revision"
    )
    checks.equal(run.get("freeze_revision"), FREEZE_REVISION, "run", "Freeze revision")
    for key in ("approval", "stopping_rules"):
        checks.require(
            isinstance(run.get(key), str) and bool(run[key].strip()), "run", f"Missing {key}"
        )
    checks.require(
        run.get("status") in ("complete", "completed"),
        "run",
        "Run is not complete",
        kind="completion",
    )
    before = run.get("environment_before", {})
    model = before.get("model", {})
    checks.equal(model.get("name"), settings["model"], "environment", "Model name")
    checks.equal(model.get("model"), settings["model"], "environment", "Model identity")
    model_digest = model.get("digest", "")
    checks.require(
        isinstance(model_digest, str)
        and len(model_digest) == 64
        and all(c in "0123456789abcdef" for c in model_digest),
        "environment",
        "Missing/invalid model digest",
    )
    checks.require(
        bool(before.get("ollama", {}).get("version")), "environment", "Missing Ollama version"
    )
    arms = run.get("arms", {})
    checks.equal(sorted(arms), sorted(CAPS), "run", "Missing or unexpected arm metadata")
    stable = True
    end_times = {}
    start_times = {}
    for arm, cap in CAPS.items():
        meta = arms.get(arm, {})
        where = f"run/{arm}"
        checks.equal(meta.get("max_requests"), cap, where, "Arm cap")
        checks.equal(meta.get("returncode"), 0, where, "Arm has not exited successfully")
        stable &= checks.equal(
            meta.get("environment_before"), before, where, "Pre-arm environment changed/missing"
        )
        after = meta.get("environment_after", run.get("environment_after_" + arm))
        stable &= checks.equal(after, before, where, "Post-arm environment changed/missing")
        if "environment_after_" + arm in run:
            stable &= checks.equal(
                run["environment_after_" + arm], before, where, "Post-arm environment changed"
            )
        elapsed = meta.get("elapsed_seconds")
        checks.require(
            type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0,
            where,
            "Invalid/missing wall time",
        )
        try:
            start_times[arm], end_times[arm] = (
                timestamp(meta["started_at"]),
                timestamp(meta["finished_at"]),
            )
            wall = (end_times[arm] - start_times[arm]).total_seconds()
            checks.require(wall >= 0, where, "Arm ends before it starts")
            if type(elapsed) in (int, float):
                checks.require(abs(wall - elapsed) < 5, where, "Wall time differs from timestamps")
            command = meta["command"]
            checks.require(
                isinstance(command, list) and "--run" in command, where, "Missing runner command"
            )
            for option, expected in (
                ("--freeze", "v11"),
                ("--arm", arm),
                ("--repetitions", "1"),
                ("--max-requests", str(cap)),
            ):
                checks.equal(command.count(option), 1, where, f"Repeated/missing {option}")
                checks.equal(
                    command[command.index(option) + 1], expected, where, f"Command {option}"
                )
            destination = Path(command[command.index("--output") + 1])
            # A copied snapshot can be verified elsewhere; bind the recorded filename.
            checks.equal(destination.name, f"{arm}.jsonl", where, "Command output filename")
        except (KeyError, ValueError, TypeError, IndexError) as error:
            checks.failed(where, error)
    try:
        checks.require(
            end_times["baseline"] <= start_times["proposed"],
            "run",
            "Arms overlap or run out of order",
        )
        checks.require(
            timestamp(run["started_at"]) <= start_times["baseline"],
            "run",
            "Run start is after baseline",
        )
        checks.require(
            timestamp(run["finished_at"]) >= end_times["proposed"],
            "run",
            "Run finish is before proposed",
        )
    except (KeyError, ValueError, TypeError) as error:
        checks.failed("run/timestamps", error)
    return {
        "stable": bool(stable),
        "model_digest": model_digest,
        "ollama_version": before.get("ollama", {}).get("version"),
    }


def header_checks(header, arm, manifest, settings, checks):
    expected = {
        "freeze": "v11",
        "arm": arm,
        "repetitions": 1,
        "max_requests": CAPS[arm],
        "settings": settings,
        "frozen_hashes": manifest,
    }
    checks.equal(header, expected, arm + "/header", "Header differs from frozen settings/approval")


class ReplayMismatch(RuntimeError):
    pass


def baseline_diagnostics(trace):
    return {
        "attempts": [
            {
                "stage": "summary",
                "index": index,
                "request_number": sent["request_number"],
                "sent": True,
                "selected": False,
                "correction": None,
                "status": "unreplayed",
                "error": transport_error(sent),
                "transport_error": sent.get("error"),
                "response_error": transport_error(sent) if "response" in sent else None,
                "parse_error": None,
                "warnings": [],
                "selection_reason": None,
            }
            for index, sent in enumerate(trace)
        ],
        "selected_attempt": None,
        "warnings": [],
        "fallback": False,
    }


@contextmanager
def observe_baseline(runtime, model, diagnostics, position):
    """Observe exact failures and parsed object identities without changing decisions."""
    parse = runtime.parse_summary
    figures = runtime.unsaid_numbers
    chat = model._chat
    parsed = []

    def observed_parse(reply):
        index = position() - 1
        attempt = diagnostics["attempts"][index]
        try:
            value = parse(reply)
        except runtime.SummaryError as error:
            attempt.update(status="unmappable", error=str(error), parse_error=str(error))
            raise
        attempt["status"] = "compiled"
        parsed.append((index, value))
        return value

    def observed_figures(summary, said):
        warnings = figures(summary, said)
        for index, value in parsed:
            if value is summary:
                diagnostics["attempts"][index]["warnings"] = list(warnings)
                break
        return warnings

    def observed_chat(messages):
        index = position()
        correction = (
            None
            if len(messages) == 2
            else "figures"
            if messages[-1]["content"].startswith("Nobody said these numbers:")
            else "format"
        )
        if index < len(diagnostics["attempts"]):
            diagnostics["attempts"][index]["correction"] = correction
        try:
            return chat(messages)
        except runtime.SummaryError as error:
            if position() == index:
                # The runner rejects an exhausted budget before recording a transport.
                diagnostics["attempts"].append(
                    {
                        "stage": "summary",
                        "index": index,
                        "request_number": None,
                        "sent": False,
                        "selected": False,
                        "correction": correction,
                        "status": "unsent",
                        "error": str(error),
                        "transport_error": None,
                        "response_error": None,
                        "parse_error": None,
                        "warnings": [],
                        "selection_reason": None,
                    }
                )
            else:
                attempt = diagnostics["attempts"][index]
                field = (
                    "transport_error"
                    if attempt["transport_error"] is not None
                    else "response_error"
                )
                attempt.update(status="error", error=str(error))
                attempt[field] = str(error)
            raise

    runtime.parse_summary = observed_parse
    runtime.unsaid_numbers = observed_figures
    model._chat = observed_chat
    try:
        yield parsed
    finally:
        runtime.parse_summary = parse
        runtime.unsaid_numbers = figures
        model._chat = chat


def select_baseline(diagnostics, parsed, summary):
    selected = next((index for index, value in parsed if value is summary), None)
    diagnostics["selected_attempt"] = selected
    if selected is None:
        return
    attempt = diagnostics["attempts"][selected]
    attempt["selected"] = True
    diagnostics["warnings"] = attempt["warnings"]
    later = diagnostics["attempts"][selected + 1 :]
    diagnostics["fallback"] = bool(later)
    if later:
        reason = (
            "Retained prior valid summary after correction failure"
            if later[-1]["error"] is not None
            else "Retained prior summary; correction did not reduce figure warnings"
        )
    elif any(index < selected for index, _ in parsed):
        reason = "Selected correction with fewer figure warnings"
    elif attempt["correction"] == "format":
        reason = "Selected valid format correction"
    else:
        reason = "Selected valid initial summary"
    attempt["selection_reason"] = reason
    for index, _ in parsed:
        if index != selected:
            diagnostics["attempts"][index]["selection_reason"] = (
                "Correction did not reduce figure warnings"
                if index > selected
                else "Replaced by correction with fewer figure warnings"
            )


def baseline_counts(attempts, counts):
    for attempt in attempts:
        counts["attempts"] += 1
        counts["requests"] += attempt["sent"]
        counts["unsent"] += not attempt["sent"]
        counts["corrections"] += attempt["correction"] is not None
        counts["sent_corrections"] += attempt["sent"] and attempt["correction"] is not None
        counts["errors"] += attempt["error"] is not None
        counts["transport_errors"] += attempt["transport_error"] is not None
        counts["response_errors"] += attempt["response_error"] is not None
        counts["blocked"] += attempt["parse_error"] is not None
        counts["unmappable"] += attempt["parse_error"] is not None
        counts["selected"] += attempt["selected"]
        counts["warnings"] += len(attempt["warnings"])


def replay_row(row, pair, arm, offset, runtime, evidence, settings, checks, where, baseline=None):
    """Execute only deterministic frozen code, with an in-memory saved transport."""
    trace = row["transport"]
    used = 0

    def saved_post(path, body):
        nonlocal used
        checks.equal(path, "/api/chat", where, "Unexpected endpoint")
        if offset + used >= CAPS[arm]:
            raise runtime.SummaryError("Chosen request budget exhausted")
        if used >= len(trace):
            raise ReplayMismatch("Frozen runtime requested an unrecorded exchange")
        sent = trace[used]
        used += 1
        checks.equal(
            body,
            sent["request"],
            f"{where}/transport/{used}",
            "Request differs from frozen runtime",
        )
        if "error" in sent:
            raise runtime.SummaryError(sent["error"])
        return deepcopy(sent["response"])

    metadata = pair["meeting"]
    meeting = runtime.Meeting.new(
        metadata["title"],
        datetime.fromisoformat(metadata["started_at"]),
        tuple(metadata["attendees"]),
    )
    model = runtime.OllamaSummarizer(
        settings["model"],
        settings["num_ctx"],
        saved_post,
        metadata["my_name"],
        think=settings["think"],
    )
    summary = None
    error = None
    if arm == "baseline" and baseline is None:
        baseline = baseline_diagnostics(trace)
    observer = (
        observe_baseline(runtime, model, baseline, lambda: used)
        if arm == "baseline"
        else nullcontext([])
    )
    with observer as parsed:
        try:
            if arm == "proposed":
                summary = model.summarize(
                    meeting, pair["transcript"], handwritten_text=pair["handwritten_text"]
                )
            else:
                summary = model.summarize(meeting, pair["transcript"])
        except runtime.SummaryError as failure:
            error = str(failure)
    if arm == "baseline":
        select_baseline(baseline, parsed, summary)
        checks.require(
            summary is None or baseline["selected_attempt"] is not None,
            where,
            "Baseline result has no observed parser selection",
        )
    checks.equal(
        used, len(trace), where, "Recorded transport contains calls unused by frozen runtime"
    )
    checks.equal(row.get("error"), error, where, "Saved error differs from frozen runtime")
    checks.equal(
        row.get("summary"),
        summary.model_dump() if summary is not None else None,
        where,
        "Saved summary differs from frozen selection",
    )
    if arm == "baseline":
        checks.require("audit" not in row, where, "Baseline unexpectedly contains an audit")
        return None
    audit = model.audit.model_dump()
    checks.equal(
        row.get("audit"),
        audit,
        where,
        "Full audit differs from replay, including failed/unsent attempts",
    )
    if "summary" not in row:
        return None
    generation = evidence.Generation.model_validate(
        {
            "version": 10,
            "summary": row["summary"],
            "audit": row["audit"],
            "evidence": {
                "transcript": pair["transcript"],
                "context": evidence.meeting_context(meeting),
                "handwritten_original": pair["handwritten_text"],
                "handwritten_text": pair["handwritten_text"],
            },
        }
    )
    roundtrip = evidence.Generation.model_validate_json(generation.model_dump_json())
    checks.equal(
        roundtrip.model_dump(), generation.model_dump(), where, "Wrapper-10 roundtrip differs"
    )
    checks.equal(generation.summary.model_dump(), row["summary"], where, "Wrapper summary differs")
    checks.equal(generation.audit.model_dump(), row["audit"], where, "Wrapper audit differs")
    selected = row["audit"]["selected"]
    warnings = row["audit"]["attempts"][selected]["warnings"]
    checks.equal(
        roundtrip.audit.attempts[selected].warnings, warnings, where, "Roundtrip warnings differ"
    )
    return {
        "case": row["case"],
        "repetition": row["repetition"],
        "wrapper_version": 10,
        "summary_matches": True,
        "audit_matches": True,
        "warnings": warnings,
        "evidence": generation.evidence.model_dump(),
    }


def stage_counts():
    return {
        "attempts": 0,
        "requests": 0,
        "corrections": 0,
        "sent_corrections": 0,
        "unsent": 0,
        "errors": 0,
        "transport_errors": 0,
        "response_errors": 0,
        "blocked": 0,
        "unmappable": 0,
        "selected": 0,
        "warnings": 0,
        "server_seconds": [],
    }


def latency(counts, response, checks, where):
    duration = (response or {}).get("total_duration")
    if duration is not None and checks.require(
        type(duration) is int and duration >= 0, where, "Invalid server duration"
    ):
        counts["server_seconds"].append(duration / 1e9)


def transport_error(sent):
    if "error" in sent:
        return sent["error"]
    response = sent.get("response") or {}
    if response.get("done_reason") == "length":
        return "Model ran out of context"
    message = response.get("message")
    if not isinstance(message, dict) or "content" not in message:
        return "Ollama reply had no message"
    return None


def attempt_report(attempt, stage, index, selected, sent, reason):
    error = attempt.get("error")
    blocking = attempt.get("blocking", [])
    state = (
        "unsent"
        if not sent
        else "error"
        if error
        else "unmappable"
        if any(e.startswith(("Invalid draft:", "Invalid comparison:")) for e in blocking)
        else "blocked"
        if blocking
        else "compiled"
    )
    return {
        "stage": stage,
        "index": index,
        "selected": index == selected,
        "sent": sent,
        "unsent_reason": reason,
        "status": state,
        "error": error,
        "blocking": blocking,
        "warnings": attempt.get("warnings", []),
        "selection_errors": attempt.get("selection_errors", []),
    }


def proposed_attempts(row, pair, stages, schemas, request, offset, checks, where):
    audit = row.get("audit", {})
    reports = []
    transport_index = 0
    has_notes = bool(pair["handwritten_text"].strip())
    for stage, field in (("comparison", "comparison_attempts"), ("summary", "attempts")):
        attempts = audit.get(field, [])
        counts = stages.setdefault(stage, stage_counts())
        checks.require(len(attempts) <= 2, where, f"{stage} exceeds two attempts")
        if stage == "comparison" and not has_notes:
            checks.equal(attempts, [], where, "Comparison attempted without notes")
        selected = audit.get("comparison_selected" if stage == "comparison" else "selected")
        checks.require(
            selected is None or type(selected) is int and 0 <= selected < len(attempts),
            where,
            f"Invalid {stage} selection",
        )
        for index, attempt in enumerate(attempts):
            location = f"{where}/{stage}/{index}"
            body = attempt["request"]
            counts["attempts"] += 1
            counts["corrections"] += index > 0
            counts["selected"] += index == selected
            counts["warnings"] += len(attempt["warnings"])
            counts["blocked"] += bool(attempt["blocking"])
            counts["errors"] += attempt["error"] is not None
            counts["unmappable"] += any(
                e.startswith(("Invalid draft:", "Invalid comparison:")) for e in attempt["blocking"]
            )
            checks.equal(
                body["format"],
                schemas[pair["id"]][stage],
                location,
                "Per-case request schema differs",
            )
            estimate, context = request.request_budget(body)
            try:
                request.verify_exchange(
                    body, attempt["response"], attempt["reply"], attempt["error"]
                )
            except ValueError as error:
                checks.failed(location, error)
            reason = (
                "context"
                if estimate > context
                else "budget"
                if attempt["error"] == "Chosen request budget exhausted"
                else None
            )
            sent = reason is None
            if reason == "budget":
                checks.equal(
                    offset + transport_index,
                    CAPS["proposed"],
                    location,
                    "Unsent budget error before cap",
                )
            if sent:
                counts["requests"] += 1
                counts["sent_corrections"] += index > 0
                counts["transport_errors"] += attempt["response"] is None
                counts["response_errors"] += (
                    attempt["response"] is not None and attempt["error"] is not None
                )
                if checks.require(
                    transport_index < len(row["transport"]),
                    location,
                    "Sent audit attempt has no transport",
                ):
                    trace = row["transport"][transport_index]
                    checks.equal(
                        trace["request"], body, location, "Transport request differs from attempt"
                    )
                    checks.equal(
                        trace.get("response"),
                        attempt["response"],
                        location,
                        "Transport response differs from attempt",
                    )
                    checks.equal(
                        trace.get("error"),
                        attempt["error"] if attempt["response"] is None else None,
                        location,
                        "Transport error differs from attempt",
                    )
                transport_index += 1
                latency(counts, attempt["response"], checks, location)
            else:
                counts["unsent"] += 1
            report = attempt_report(attempt, stage, index, selected, sent, reason)
            report["estimated_tokens"] = estimate
            reports.append(report)
    checks.equal(
        transport_index, len(row["transport"]), where, "Transport contains hidden/unmapped calls"
    )
    return reports


def verify_arm(arm, data, pairs, settings, manifest, checks, run):
    stages = {}
    outcomes = []
    replays = []
    seen = []
    sent_count = 0
    if data is None:
        lines = []
    else:
        lines = data.splitlines()
    if lines:
        try:
            header_checks(decode(lines[0]), arm, manifest, settings, checks)
        except (ValueError, TypeError) as error:
            checks.failed(arm + "/header", error)
    else:
        checks.require(False, arm, "Missing JSONL header")
    schemas = decode((ROOT / "proposed/request-schemas.json").read_bytes())
    baseline_schema = decode((ROOT / "baseline/schema.json").read_bytes())
    with frozen_imports(arm, checks) as (runtime, evidence, imports):
        checks.equal(
            runtime.TIMEOUT_SECONDS, settings["timeout_seconds"], arm, "Frozen timeout differs"
        )
        request = (
            importlib.import_module("meeting_notes.request_v11") if arm == "proposed" else None
        )
        for line_number, line in enumerate(lines[1:], 2):
            where = f"{arm}/line/{line_number}"
            start_failures = len(checks.failures)
            baseline = None
            try:
                row = decode(line)
                case, repetition = row["case"], row["repetition"]
                where = f"{arm}/{case}/{repetition}"
                checks.require(
                    type(repetition) is int and repetition == 1, where, "Unexpected repetition"
                )
                checks.require(case in pairs, where, "Unknown case")
                checks.require((case, repetition) not in seen, where, "Duplicate slot")
                seen.append((case, repetition))
                allowed = {
                    "case",
                    "repetition",
                    "summary",
                    "error",
                    "audit",
                    "transport",
                    "requests_so_far",
                }
                checks.require(not set(row) - allowed, where, "Unexpected row fields")
                checks.require(
                    ("summary" in row) != ("error" in row),
                    where,
                    "Slot needs exactly one summary/error",
                )
                if "error" in row:
                    checks.require(
                        isinstance(row["error"], str) and bool(row["error"]),
                        where,
                        "Invalid row error",
                    )
                trace = row["transport"]
                offset = sent_count
                checks.require(isinstance(trace, list), where, "Transport must be a list")
                for index, sent in enumerate(trace):
                    sent_count += 1
                    location = f"{where}/transport/{index}"
                    checks.equal(
                        sent.get("request_number"),
                        sent_count,
                        location,
                        "Noncontiguous request numbering",
                    )
                    checks.require(
                        set(sent)
                        in (
                            {"request", "request_number", "response"},
                            {"request", "request_number", "error"},
                        ),
                        location,
                        "Transport requires exactly a response or raw error",
                    )
                    body = sent["request"]
                    checks.equal(
                        set(body) == {"model", "messages", "stream", "think", "format", "options"},
                        True,
                        location,
                        "Unexpected request fields",
                    )
                    checks.equal(
                        body.get("model"), settings["model"], location, "Request model differs"
                    )
                    checks.equal(
                        body.get("options"),
                        {"num_ctx": settings["num_ctx"], "temperature": settings["temperature"]},
                        location,
                        "Request options differ",
                    )
                    checks.equal(body.get("think"), settings["think"], location, "Thinking differs")
                    checks.equal(body.get("stream"), False, location, "Streaming differs")
                    response = sent.get("response")
                    checks.require(
                        response is None or isinstance(response, dict),
                        location,
                        "Response must be an object",
                    )
                    if response and "model" in response:
                        checks.equal(
                            response["model"], settings["model"], location, "Response model differs"
                        )
                    if arm == "baseline":
                        counts = stages.setdefault("summary", stage_counts())
                        checks.equal(
                            body["format"], baseline_schema, location, "Baseline schema differs"
                        )
                        estimate = (len(json.dumps(body, ensure_ascii=False)) + 2) // 3 + 4096
                        checks.require(
                            estimate <= settings["num_ctx"],
                            location,
                            "Complete sent baseline request exceeds context",
                        )
                        latency(counts, response, checks, location)
                checks.equal(
                    row.get("requests_so_far"), sent_count, where, "Cumulative requests differ"
                )
                if case not in pairs:
                    continue
                pair = pairs[case]
                cap = 4 if arm == "baseline" or pair["handwritten_text"].strip() else 2
                checks.require(len(trace) <= cap, where, "Per-slot request ceiling exceeded")
                baseline = baseline_diagnostics(trace) if arm == "baseline" else None
                attempts = (
                    proposed_attempts(row, pair, stages, schemas, request, offset, checks, where)
                    if arm == "proposed"
                    else baseline["attempts"]
                )
                replay = None
                try:
                    replay = replay_row(
                        row, pair, arm, offset, runtime, evidence, settings, checks, where, baseline
                    )
                except Exception as error:
                    checks.failed(where + "/replay", error)
                audit = row.get("audit", {})
                selected = audit.get("selected")
                warnings = audit["attempts"][selected]["warnings"] if selected is not None else []
                if baseline is not None:
                    selected = baseline["selected_attempt"]
                    warnings = baseline["warnings"]
                    baseline_counts(attempts, stages.setdefault("summary", stage_counts()))
                summary = row.get("summary", {})
                raw_errors = sum(
                    a["error"] is not None and a.get("parse_error") is None for a in attempts
                )
                valid = len(checks.failures) == start_failures
                if replay is not None:
                    replay["verified"] = valid
                    replays.append(replay)
                complete = "summary" in row and "error" not in row and valid
                checks.require(
                    complete,
                    where,
                    "Slot lacks a valid published selection or replay",
                    kind="completion",
                )
                outcomes.append(
                    {
                        "case": case,
                        "repetition": repetition,
                        "status": "complete"
                        if complete
                        else "published_with_error"
                        if "summary" in row
                        else "blocked",
                        "published": "summary" in row,
                        "evidence_valid": valid,
                        "requests": len(trace),
                        "raw_errors": raw_errors,
                        "selected_attempt": selected,
                        **(
                            {
                                "parse_errors": sum(a["parse_error"] is not None for a in attempts),
                                "fallback": baseline["fallback"],
                            }
                            if baseline is not None
                            else {}
                        ),
                        "comparison_selected": audit.get("comparison_selected"),
                        "failed_comparison": arm == "proposed"
                        and bool(pair["handwritten_text"].strip())
                        and audit.get("comparison_selected") is None,
                        "warnings": warnings,
                        "attempts": attempts,
                        "error": row.get("error"),
                        "conflicts": len(summary.get("conflicts", [])),
                        "review_items": sum(
                            bool(a.get("review")) for a in summary.get("action_items", [])
                        ),
                        "assigned_due_values": sum(
                            a.get("due") is not None for a in summary.get("action_items", [])
                        ),
                    }
                )
            except Exception as error:
                checks.failed(where, error)
                outcomes.append(
                    {
                        "location": where,
                        "status": "unverifiable",
                        "published": False,
                        "evidence_valid": False,
                    }
                )
                if arm == "baseline":
                    outcomes[-1].update(
                        baseline if baseline is not None else baseline_diagnostics([])
                    )
    expected = [(case, 1) for case in pairs]
    checks.equal(seen, expected, arm, "Exact case/repetition order and coverage differ")
    for case, repetition in expected:
        if (case, repetition) not in seen:
            outcomes.append(
                {
                    "case": case,
                    "repetition": repetition,
                    "status": "missing",
                    "published": False,
                    "requests": 0,
                }
            )
            if arm == "baseline":
                outcomes[-1].update(baseline_diagnostics([]))
            checks.require(
                False, f"{arm}/{case}/{repetition}", "Missing agreed slot", kind="completion"
            )
    checks.require(sent_count <= CAPS[arm], arm, "Arm request cap exceeded")
    for counts in stages.values():
        values = counts.pop("server_seconds")
        counts.update(
            measured_server_replies=len(values),
            server_seconds_total=sum(values),
            server_seconds_median=statistics.median(values) if values else None,
            server_seconds_max=max(values) if values else None,
        )
    return (
        {
            "recorded_slots": len(seen),
            "expected_slots": 40,
            "outcome_counts": dict(Counter(o["status"] for o in outcomes)),
            "requests": sent_count,
            "request_cap": CAPS[arm],
            "elapsed_seconds": run.get("arms", {}).get(arm, {}).get("elapsed_seconds"),
            "stages": stages,
            "outcomes": outcomes,
            "output_sha256": digest(data) if data is not None else None,
        },
        replays,
        imports,
    )


def verify(results):
    checks = Checks()
    counts, manifest = manifests(checks)
    report = {
        "verifier": VERIFIER,
        "results_dir": str(results),
        "manifest_entries": counts,
        "approved_repetitions": 1,
        "approved_total_request_cap": 276,
        "arms": {},
        "quality": {
            "status": "not_assessed",
            "reason": (
                "Requires semantic scoring against frozen rubric/expected.json. "
                "IDs, valid schemas and faithful replay do not establish quality."
            ),
        },
        "latency_basis": (
            "Arm wall times and raw response total_duration; failed requests may have no server "
            "duration. Frozen runner has no per-request client wall timer."
        ),
        "failures": checks.failures,
    }
    replays = []
    snapshots = {}
    # Never execute frozen code if its integrity cannot be established.
    if not checks.failures:
        settings = decode((ROOT / "settings.json").read_bytes())
        checks.equal(
            {key: settings.get(key) for key in ("repetitions", "request_budget")},
            {"repetitions": None, "request_budget": None},
            "settings",
            "Frozen approval-null settings changed",
        )
        pairs = {pair["id"]: pair for pair in decode((ROOT / "pairs.json").read_bytes())}
        checks.equal(len(pairs), 40, "pairs", "Expected 40 cases")
        checks.equal(
            sum(bool(p["handwritten_text"].strip()) for p in pairs.values()),
            18,
            "pairs",
            "Expected 18 cases with notes",
        )
        report["historical_replay"] = historical_replay(checks)
        for name in ("run.json", "baseline.jsonl", "proposed.jsonl"):
            try:
                snapshots[name] = (results / name).read_bytes()
            except OSError as error:
                checks.failed(name, error)
                snapshots[name] = None
        run = {}
        try:
            run = decode(snapshots["run.json"]) if snapshots["run.json"] is not None else {}
            report["environment"] = run_metadata(run, manifest, settings, checks)
        except Exception as error:
            checks.failed("run.json", error)
        for arm in CAPS:
            try:
                report["arms"][arm], replay, loaded = verify_arm(
                    arm, snapshots[arm + ".jsonl"], pairs, settings, manifest, checks, run
                )
                replays.extend(replay)
                report.setdefault("frozen_imports", {})[arm] = loaded
            except Exception as error:
                checks.failed(arm, error)
        for name, before in snapshots.items():
            try:
                after = (results / name).read_bytes()
            except OSError:
                after = None
            checks.require(
                before == after,
                name,
                "Input changed during verification; verify again after the run finishes",
            )
        report["input_sha256"] = {
            name: digest(data) if data is not None else None for name, data in snapshots.items()
        }
    report["requests_used"] = sum(a["requests"] for a in report["arms"].values())
    checks.require(report["requests_used"] <= 276, "total", "Total request cap exceeded")
    report["unused_requests"] = 276 - report["requests_used"]
    report["expected_slots"] = 80
    report["recorded_slots"] = sum(a["recorded_slots"] for a in report["arms"].values())
    report["outcome_counts"] = dict(
        Counter(o["status"] for a in report["arms"].values() for o in a["outcomes"])
    )
    report["published_summary_replays"] = sum(r["verified"] for r in replays)
    report["published_proposed_summaries"] = sum(
        o["published"] for o in report["arms"].get("proposed", {}).get("outcomes", [])
    )
    checks.equal(
        report["published_summary_replays"],
        report["published_proposed_summaries"],
        "replays",
        "Every published proposed summary must have a verified wrapper-10 replay",
    )
    report["evidence_integrity"] = (
        "failed" if any(f["kind"] == "integrity" for f in checks.failures) else "verified"
    )
    report["completion"] = "failed" if checks.failures else "complete"
    return report, replays


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=ROOT / "results")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="new directory for completion.json and replay.jsonl; otherwise stdout only",
    )
    args = parser.parse_args()
    output = args.output_dir.resolve() if args.output_dir else None
    if output:
        if output.exists():
            parser.error(
                "--output-dir must be a new directory; existing evidence is never replaced"
            )
        if output.is_relative_to(M10) and not output.is_relative_to(ROOT / "results"):
            parser.error("Derived output cannot be placed in frozen/historical directories")
    sys.dont_write_bytecode = True
    report, replays = verify(args.results_dir.resolve())
    if output:
        output.mkdir(parents=True, exist_ok=False)
        with (output / "completion.json").open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
        with (output / "replay.jsonl").open("x", encoding="utf-8") as stream:
            stream.writelines(
                json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n" for row in replays
            )
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if report["completion"] == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
