#!/usr/bin/env python3
"""Verify historical replay and strict old-response compatibility without inference."""

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
M10 = ROOT.parent
IMPORT_ROOT = ROOT / "proposed" if (ROOT / "proposed").exists() else ROOT.parents[2] / "src"
sys.path.insert(0, str(IMPORT_ROOT))

from meeting_notes.comparison_v11 import Comparison  # noqa: E402
from meeting_notes.comparison_v11 import validate as compare  # noqa: E402
from meeting_notes.compiler_v11 import validate as compile_draft  # noqa: E402
from meeting_notes.contract_v11 import Draft  # noqa: E402
from meeting_notes.evidence import Generation  # noqa: E402
from meeting_notes.spans_v11 import snapshot  # noqa: E402


def verify(path):
    manifest = json.loads(path.read_text())
    for name, expected in manifest.items():
        actual = hashlib.sha256((path.parent / name).read_bytes()).hexdigest()
        assert actual == expected, str(path.parent / name)
    return len(manifest)


def main():
    folders = [M10, *(M10 / f"v{number}" for number in range(2, 11))]
    verified = sum(
        verify(folder / name)
        for folder in folders
        for name in ("sha256.json", "results/sha256.json")
    )
    assert verified == 396
    if (ROOT / "sha256.json").exists():
        verify(ROOT / "sha256.json")
    pairs = {p["id"]: p for p in json.loads((M10 / "v10/pairs.json").read_text())}
    rows = [
        json.loads(line)
        for line in (M10 / "v10/results/proposed.jsonl").read_text().splitlines()[1:]
    ]
    totals = {"comparison_attempts": Counter(), "summary_attempts": Counter(), "cases": Counter()}
    outcomes = []
    replays = 0
    for row in rows:
        pair = pairs[row["case"]]
        saved = snapshot(pair["transcript"], pair["handwritten_text"])
        audit = row["audit"]
        if "summary" in row:
            selected = audit["attempts"][audit["selected"]]
            context = selected["request"]["messages"][1]["content"].split(
                "\nTranscript sources", 1
            )[0]
            generation = Generation.model_validate(
                {
                    "version": 9,
                    "summary": row["summary"],
                    "audit": audit,
                    "evidence": {
                        "transcript": pair["transcript"],
                        "context": context,
                        "handwritten_original": pair["handwritten_text"],
                        "handwritten_text": pair["handwritten_text"],
                    },
                }
            )
            assert Generation.model_validate_json(generation.model_dump_json()) == generation
            assert generation.summary.model_dump() == row["summary"]
            assert generation.audit is not None and generation.audit.model_dump() == audit
            replays += 1
        comparison = Comparison(claims=[])
        ready = not any(source.source == "notes" for source in saved.sources)
        for index, attempt in enumerate(audit["comparison_attempts"]):
            try:
                candidate = Comparison.model_validate_json(attempt["reply"])
            except ValueError:
                totals["comparison_attempts"]["unmappable"] += 1
                continue
            errors = compare(candidate, saved.sources)
            totals["comparison_attempts"]["blocked" if errors else "compiled"] += 1
            if index == audit["comparison_selected"] and not errors:
                comparison, ready = candidate, True
        status = "blocked"
        for index, attempt in enumerate(audit["attempts"]):
            try:
                draft = Draft.model_validate_json(attempt["reply"])
            except ValueError:
                totals["summary_attempts"]["unmappable"] += 1
                status = "unmappable"
                continue
            if not ready:
                totals["summary_attempts"]["blocked"] += 1
                continue
            context = attempt["request"]["messages"][1]["content"].split("\nTranscript sources", 1)[
                0
            ]
            checked = compile_draft(draft, saved, comparison, context)
            state = "compiled" if checked.summary is not None else "blocked"
            totals["summary_attempts"][state] += 1
            if index == audit["selected"]:
                status = state
        if not ready and not audit["attempts"]:
            status = "unmappable" if audit["comparison_attempts"] else "blocked"
        totals["cases"][status] += 1
        outcomes.append({"case": row["case"], "strict_v11_status": status})
    assert len(rows) == 22 and replays == 17
    print(
        json.dumps(
            {
                "historical_manifest_entries": verified,
                "wrapper9_replays": replays,
                "compatibility_kind": "Strict unchanged archived replies; no field conversion",
                "counts": {
                    name: {state: counts[state] for state in ("compiled", "blocked", "unmappable")}
                    for name, counts in totals.items()
                },
                "cases": outcomes,
                "limitations": "Schema incompatibility is not a semantic repair. Authored V11 "
                "fake responses and fresh model quality evaluation are separate evidence.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
