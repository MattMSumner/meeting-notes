#!/usr/bin/env python3
"""Join locked opaque-label assessments; do not change captured or frozen evidence."""

import hashlib
import json
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
    scores = read("blinded-scores.json")
    key = read("blind-key.json")
    assert len(scores) == len(key) == 80
    assert {s["id"] for s in scores} == set(key)
    completion = read("verification/completion.json")
    raw = {}
    for arm in ("baseline", "proposed"):
        for line in (ROOT / (arm + ".jsonl")).read_text().splitlines()[1:]:
            row = json.loads(line)
            raw[arm, row["case"], row["repetition"]] = row
    joined = []
    for score in scores:
        identity = key[score["id"]]
        row = raw[identity["arm"], identity["case"], identity["repetition"]]
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
    write_once("scores.json", joined)
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
    passed = proposed["complete"] == 40 and not proposed["critical_failure_cases"]
    assessment = {
        "method": lock["method"],
        "limitations": (
            "One repetition; all cases are development/evaluation material, none independently "
            "held out. Output structure and notes reveal arms. Agent assessment is not fully "
            "blinded measurement. Scores are descriptive, not reliability estimates."
        ),
        "arms": arms,
        "quality_pass": passed,
        "quality_result": (
            "Pass on the agreed synthetic run; current manual acceptance remains required."
            if passed
            else "Failed: incomplete proposed outputs or critical semantic failures; current "
            "manual acceptance does not advance."
        ),
        "requests_used": completion["requests_used"],
        "inference_policy": (
            "No tuning, selective reruns or further inference; unused allowance is not reused."
        ),
        "built_or_merged": False,
    }
    write_once("assessment.json", assessment)
    print(json.dumps(assessment, indent=2))


if __name__ == "__main__":
    main()
