#!/usr/bin/env python3
"""Join locked opaque-label assessments; do not change captured or frozen evidence."""

import hashlib
import json
import runpy
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIMENSIONS = (
    "commitments",
    "sources",
    "coverage",
    "comparison",
    "quantities",
    "timing_owners",
    "usefulness_completion",
)


def read(name):
    return json.loads((ROOT / name).read_text())


def write_once(name, value):
    with (ROOT / name).open("x") as output:
        output.write(json.dumps(value, indent=2) + "\n")


def main():
    lock = read("scoring-lock.json")
    assert (
        hashlib.sha256((ROOT / "blinded-scores.json").read_bytes()).hexdigest()
        == lock["scores_sha256"]
    )
    for name in ("blinded.json", "blind-key.json", "blind-preparation.json"):
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == lock["files_sha256"][name]
    preparation = read("blind-preparation.json")
    for name, expected in preparation["files_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
    scores = read("blinded-scores.json")
    key = read("blind-key.json")
    packets = read("blinded.json")
    assert len(scores) == len(key) == len(packets) == 80
    assert {s["id"] for s in scores} == set(key)
    assert {p["id"] for p in packets} == set(key)
    packets = {p["id"]: p for p in packets}
    completion = read("verification/completion.json")
    assert (
        hashlib.sha256((ROOT / "verification/completion.json").read_bytes()).hexdigest()
        == (preparation["verification_sha256"])
    )
    assert completion["evidence_integrity"] == "verified", "Resolve evidence failures first"
    assert completion["manifest_entries"] == {"historical": 396, "v11": 67}
    assert completion["historical_replay"]["wrapper9_replays"] == 17
    assert completion["recorded_slots"] == completion["expected_slots"] == 80
    for name in ("run.json", "baseline.jsonl", "proposed.jsonl"):
        assert (
            hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            == completion["input_sha256"][name]
        ), "Verifier report describes different captured inputs"
    assert preparation["run_sha256"] == completion["input_sha256"]["run.json"]
    raw = {}
    for arm in ("baseline", "proposed"):
        assert (
            preparation["captured_output_sha256"][arm] == completion["input_sha256"][arm + ".jsonl"]
        )
        for line in (ROOT / (arm + ".jsonl")).read_text().splitlines()[1:]:
            row = json.loads(line)
            slot = arm, row["case"], row["repetition"]
            assert slot not in raw
            raw[slot] = row
    assert len(raw) == 80
    assert {(i["arm"], i["case"], i["repetition"]) for i in key.values()} == set(raw)
    pairs = {p["id"]: p for p in json.loads((ROOT.parent / "pairs.json").read_text())}
    expected = {p["id"]: p for p in json.loads((ROOT.parent / "expected.json").read_text())}
    material = runpy.run_path(str(ROOT / "prepare-blind.py"))["packet_material"]
    diagnostics = {
        (arm, o["case"], o["repetition"]): o
        for arm in ("baseline", "proposed")
        for o in completion["arms"][arm]["outcomes"]
    }
    joined = []
    for score in scores:
        identity = key[score["id"]]
        row = raw[identity["arm"], identity["case"], identity["repetition"]]
        assert packets[score["id"]] == {
            "id": score["id"],
            **material(
                row,
                pairs[identity["case"]],
                expected[identity["case"]],
                identity["arm"],
                diagnostics[identity["arm"], identity["case"], identity["repetition"]],
            ),
        }, "Opaque packet differs from its captured source, attempts or selected output"
        assert type(score["complete"]) is bool
        assert score["complete"] == ("summary" in row)
        assert set(score["scores"]) == set(DIMENSIONS)
        assert all(type(value) is int and value in (0, 1, 2) for value in score["scores"].values())
        if not score["complete"]:
            assert not any(score["scores"].values())
        assert isinstance(score["observations"], list) and score["observations"]
        for failure in score["critical_failures"]:
            assert set(failure) == {"kind", "source_quote", "output_quote", "reason"}
            assert failure["kind"] and failure["reason"]
        joined.append({**identity, **score})
    arms = {}
    for arm in ("baseline", "proposed"):
        assessed = [s for s in joined if s["arm"] == arm]
        assert len(assessed) == 40
        categories = Counter(f["kind"] for s in assessed for f in s["critical_failures"])
        arms[arm] = {
            "assessed_slots": len(assessed),
            "complete": sum(s["complete"] for s in assessed),
            "incomplete_cases": [s["case"] for s in assessed if not s["complete"]],
            "critical_failure_cases": [s["case"] for s in assessed if s["critical_failures"]],
            "critical_failure_kinds": dict(categories),
            "dimension_totals_out_of_80": {
                dimension: sum(s["scores"][dimension] for s in assessed) for dimension in DIMENSIONS
            },
        }
    proposed = arms["proposed"]
    passed = (
        completion["completion"] == "complete"
        and proposed["complete"] == 40
        and not proposed["critical_failure_cases"]
    )
    assessment = {
        "method": lock["method"],
        "limitations": (
            "One repetition; all cases are development/evaluation material, none independently "
            "held out. Output structure and notes reveal arms. Agent assessment is not fully "
            "blinded measurement. Scores are descriptive, not reliability estimates."
        ),
        "arms": arms,
        "evidence_integrity": completion["evidence_integrity"],
        "completion": completion["completion"],
        "quality_pass": passed,
        "quality_result": (
            "Pass on the agreed synthetic run; current manual acceptance remains required."
            if passed
            else "Failed: incomplete/unverifiable outputs or critical semantic failures; current "
            "manual acceptance does not advance."
        ),
        "requests_used": completion["requests_used"],
        "inference_policy": (
            "No tuning, selective reruns or further inference; unused allowance is not reused."
        ),
        "built_or_merged": False,
    }
    assert not any((ROOT / name).exists() for name in ("scores.json", "assessment.json"))
    write_once("scores.json", joined)
    write_once("assessment.json", assessment)
    print(json.dumps(assessment, indent=2))


if __name__ == "__main__":
    main()
