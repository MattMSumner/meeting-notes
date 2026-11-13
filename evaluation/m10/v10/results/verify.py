#!/usr/bin/env python3
"""Verify and replay the saved V10 evaluation without inference."""

import hashlib
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "proposed"))
from meeting_notes.evidence import Generation, meeting_context  # noqa: E402
from meeting_notes.meeting import Meeting  # noqa: E402


def read(name):
    return json.loads((ROOT / name).read_text())


def write(name, value):
    (ROOT / "results" / name).write_text(json.dumps(value, indent=2) + "\n")


def main():
    verified = {"prior": 0, "v10": 0}
    for manifest in sorted(ROOT.parent.rglob("sha256.json")):
        if manifest.parent == ROOT / "results":
            continue
        for name, digest in json.loads(manifest.read_text()).items():
            assert hashlib.sha256((manifest.parent / name).read_bytes()).hexdigest() == digest
            verified["v10" if manifest.parent == ROOT else "prior"] += 1
    pairs = {p["id"]: p for p in read("pairs.json")}
    schemas = read("proposed/request-schemas.json")
    run = read("results/run.json")
    completion = {
        "request_cap": 162,
        "repetitions": 1,
        "manifest_entries_verified": verified,
        "arms": {},
        "model_digest": run["environment_before"]["model"]["digest"],
        "ollama_version": run["environment_before"]["ollama"]["version"],
        "environment_stable": all(
            run["environment_before"] == run["environment_after_" + arm]
            for arm in ("baseline", "proposed")
        ),
    }
    replays = []
    for arm, cap in (("baseline", 88), ("proposed", 74)):
        lines = (ROOT / "results" / (arm + ".jsonl")).read_text().splitlines()
        header, rows = json.loads(lines[0]), [json.loads(s) for s in lines[1:]]
        assert header["max_requests"] == cap and header["repetitions"] == 1
        assert header["frozen_hashes"] == read("sha256.json")
        assert len(rows) == 22 and {r["case"] for r in rows} == set(pairs)
        sent_count = 0
        stages = {}
        outcomes = []
        for row in rows:
            pair = pairs[row["case"]]
            audit = row.get("audit", {})
            selected = audit.get("selected")
            selected_attempt = audit["attempts"][selected] if selected is not None else None
            assert row["repetition"] == 1
            trace = row["transport"]
            for sent in trace:
                sent_count += 1
                assert sent["request_number"] == sent_count
            assert row["requests_so_far"] == sent_count
            warnings = selected_attempt["warnings"] if selected_attempt else []
            if arm == "proposed":
                sent_attempts = []
                for stage, field in (
                    ("comparison", "comparison_attempts"),
                    ("summary", "attempts"),
                ):
                    attempts = audit[field]
                    assert len(attempts) <= 2
                    for index, attempt in enumerate(attempts):
                        assert attempt["request"]["format"] == schemas[row["case"]][stage]
                        estimate = (
                            len(json.dumps(attempt["request"], ensure_ascii=False)) + 2
                        ) // 3 + 4096
                        if attempt["error"] == "Complete request exceeds context; not sent":
                            assert estimate > 32768
                            continue
                        assert estimate <= 32768
                        sent_attempts.append(attempt)
                        counts = stages.setdefault(
                            stage,
                            {"requests": 0, "corrections": 0, "errors": 0, "server_seconds": []},
                        )
                        counts["requests"] += 1
                        counts["corrections"] += index > 0
                        counts["errors"] += bool(attempt["error"])
                        duration = (attempt["response"] or {}).get("total_duration")
                        if duration is not None:
                            counts["server_seconds"].append(duration / 1e9)
                assert len(sent_attempts) == len(trace)
                for attempt, sent in zip(sent_attempts, trace, strict=True):
                    assert attempt["request"] == sent["request"]
                    assert attempt["response"] == sent.get("response")
                if "summary" in row:
                    metadata = pair["meeting"]
                    meeting = Meeting.new(
                        metadata["title"],
                        datetime.fromisoformat(metadata["started_at"]),
                        tuple(metadata["attendees"]),
                    )
                    generation = Generation.model_validate(
                        {
                            "version": 9,
                            "summary": row["summary"],
                            "audit": audit,
                            "evidence": {
                                "transcript": pair["transcript"],
                                "context": meeting_context(meeting),
                                "handwritten_original": pair["handwritten_text"],
                                "handwritten_text": pair["handwritten_text"],
                            },
                        }
                    )
                    assert generation.summary.model_dump() == row["summary"]
                    assert (
                        Generation.model_validate_json(generation.model_dump_json()) == generation
                    )
                    replays.append(
                        {
                            "case": row["case"],
                            "wrapper_version": 9,
                            "summary_matches": True,
                            "warnings": warnings,
                        }
                    )
            else:
                counts = stages.setdefault(
                    "summary", {"requests": 0, "corrections": 0, "errors": 0, "server_seconds": []}
                )
                assert len(trace) <= 4
                for index, sent in enumerate(trace):
                    assert sent["request"]["format"] == read("baseline/schema.json")
                    counts["requests"] += 1
                    counts["corrections"] += index > 0
                    counts["errors"] += "error" in sent
                    duration = sent.get("response", {}).get("total_duration")
                    if duration is not None:
                        counts["server_seconds"].append(duration / 1e9)
            summary = row.get("summary", {})
            outcomes.append(
                {
                    "case": row["case"],
                    "published": "summary" in row,
                    "requests": len(trace),
                    "selected_attempt": selected,
                    "comparison_selected": audit.get("comparison_selected"),
                    "warnings": warnings,
                    "conflicts": len(summary.get("conflicts", [])),
                    "review_items": sum(
                        bool(a.get("review")) for a in summary.get("action_items", [])
                    ),
                    "assigned_due_values": sum(
                        a["due"] is not None for a in summary.get("action_items", [])
                    ),
                    "error": row.get("error"),
                }
            )
        assert sent_count <= cap
        for counts in stages.values():
            values = counts.pop("server_seconds")
            counts["measured_server_replies"] = len(values)
            counts["server_seconds_total"] = sum(values)
            counts["server_seconds_median"] = statistics.median(values) if values else None
            counts["server_seconds_max"] = max(values) if values else None
        completion["arms"][arm] = {
            "completed_cases": len(rows),
            "published": sum(o["published"] for o in outcomes),
            "blocked": sum(not o["published"] for o in outcomes),
            "requests": sent_count,
            "elapsed_seconds": run["arms"][arm]["elapsed_seconds"],
            "stages": stages,
            "outcomes": outcomes,
            "output_sha256": hashlib.sha256(
                (ROOT / "results" / (arm + ".jsonl")).read_bytes()
            ).hexdigest(),
        }
    completion["requests_used"] = sum(a["requests"] for a in completion["arms"].values())
    completion["unused_requests"] = 162 - completion["requests_used"]
    completion["published_summary_replays"] = len(replays)
    completion["latency_basis"] = (
        "Arm wall time and Ollama response total_duration in seconds; server durations omit "
        "failed requests without replies. No per-request client wall timers were added "
        "to the frozen runner."
    )
    write("completion.json", completion)
    (ROOT / "results/replay.jsonl").write_text("".join(json.dumps(r) + "\n" for r in replays))
    print(
        json.dumps(
            {
                "requests_used": completion["requests_used"],
                "replays": len(replays),
                "verified": verified,
            }
        )
    )


if __name__ == "__main__":
    main()
