#!/usr/bin/env python3
"""Join completed opaque-label assessments and describe saved comparison failures."""

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    key = json.loads((ROOT / "blind-key.json").read_text())
    scores = json.loads((ROOT / "blinded-scores.json").read_text())
    joined = [{**key[row["id"]], **row} for row in scores]
    assert len(joined) == 44 and len({(s["arm"], s["case"]) for s in joined}) == 44
    (ROOT / "scores.json").write_text(json.dumps(joined, indent=2) + "\n")
    selected_outcomes = Counter()
    selected_claims = 0
    selected_comparisons = 0
    comparison_blocks = []
    summary_blocks = []
    selected_metadata_issues = []
    summaries = {}
    for line in (ROOT / "proposed.jsonl").read_text().splitlines()[1:]:
        row = json.loads(line)
        audit = row["audit"]
        selected = audit["comparison_selected"]
        if selected is not None:
            selected_comparisons += 1
            comparison = json.loads(audit["comparison_attempts"][selected]["reply"])
            for claim in comparison["claims"]:
                selected_claims += 1
                selected_outcomes[claim["outcome"]] += 1
                accounts = [claim["note"], *claim["transcript"]]
                for account in accounts:
                    meaning = account["meaning"]
                    if any(v == "null" or v == "" for v in meaning.values()):
                        selected_metadata_issues.append(
                            {
                                "case": row["case"],
                                "source": account["source_id"],
                                "meaning": meaning,
                            }
                        )
        if "summary" not in row:
            (comparison_blocks if selected is None else summary_blocks).append(row["case"])
        else:
            summaries[row["case"]] = row["summary"]
    baseline_rows = [json.loads(s) for s in (ROOT / "baseline.jsonl").read_text().splitlines()[1:]]
    old_rows = [
        json.loads(s)
        for s in (ROOT.parents[1] / "v9/results/baseline.jsonl").read_text().splitlines()[1:]
    ]
    previous = {row["case"]: row["summary"] for row in old_rows}
    report = {
        "assessment_method": (
            "Opaque arm labels scored before reading key. Source scope/output structure "
            "reveal arms; not fully blinded or independent. Same implementing agent "
            "assessed all rows."
        ),
        "scoring_conventions": (
            "Six dimensions 0–2; blocked outputs score zero in all dimensions and are "
            "separately recorded as incomplete, not as published hallucinations. "
            "Conservative unassigned timing gets partial dates credit, as in prior "
            "reports; undated-task review is polish. Numeric meaning also assesses "
            "explicit comparison dimensions, so missing quantities/units can earn partial "
            "credit even when quoted final values are correct."
        ),
        "comparison_failures": comparison_blocks,
        "summary_failures": summary_blocks,
        "selected_comparisons": selected_comparisons,
        "selected_claims": selected_claims,
        "selected_outcomes": dict(selected_outcomes),
        "selected_accounts_with_empty_or_literal_null_dimension": selected_metadata_issues,
        "proposed_critical_failure_cases": [
            s["case"] for s in joined if s["arm"] == "proposed" and s["critical_failures"]
        ],
        "baseline_critical_failure_cases": [
            s["case"] for s in joined if s["arm"] == "baseline" and s["critical_failures"]
        ],
        "spoken_commitment_missing_with_blocked_output": ["multi_claim_notes"],
        "published_invented_action_cases": ["unit_disagreement"],
        "original_13_spoken_commitments_and_independent_agreement_retained": True,
        "original_13_baseline_summaries_identical_to_v9": sum(
            r["summary"] == previous[r["case"]] for r in baseline_rows if r["case"] in previous
        ),
        "quality_result": (
            "failed: five incomplete proposed outputs and an invented action in a "
            "published output; estimate/status comparison also does not satisfy frozen "
            "uncertainty expectations"
        ),
        "manual_acceptance": (
            "Not advanced; quality gate failed. Current workflow acceptance remains pending."
        ),
        "further_inference": "None; no tuning or reruns. Unused request allowance is not reused.",
    }
    (ROOT / "assessment.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k
                not in (
                    "assessment_method",
                    "scoring_conventions",
                    "selected_accounts_with_empty_or_literal_null_dimension",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
