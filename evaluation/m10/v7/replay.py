#!/usr/bin/env python3
"""Replay V6 responses through the repaired contract without inference or semantic repair."""

import argparse
import hashlib
import json
from pathlib import Path

from meeting_notes.compiler import Source, passages, validate
from meeting_notes.contract import Draft
from meeting_notes.evidence import meeting_context
from meeting_notes.meeting import Meeting


def adapt(reply: str, sources: list[Source]) -> Draft:
    return Draft.model_validate_json(reply)


def main() -> None:
    from datetime import datetime

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "evaluation/m10/v6"
    for manifest_path in [root / "sha256.json", root / "results/sha256.json"]:
        for name, digest in json.loads(manifest_path.read_text()).items():
            if hashlib.sha256((manifest_path.parent / name).read_bytes()).hexdigest() != digest:
                parser.error(f"Input changed: {name}")
    pairs = {p["id"]: p for p in json.loads((root / "pairs.json").read_text())}
    results = [json.loads(s) for s in (root / "results/proposed.jsonl").read_text().splitlines()][
        1:
    ]
    with args.output.open("x") as output:
        for result in results:
            pair = pairs[result["case"]]
            sources = passages(pair["transcript"], pair["handwritten_text"])
            metadata = pair["meeting"]
            meeting = Meeting.new(
                metadata["title"],
                datetime.fromisoformat(metadata["started_at"]),
                tuple(metadata["attendees"]),
            )
            for index, attempt in enumerate(result["audit"]["attempts"]):
                row = {
                    "case": result["case"],
                    "attempt": index,
                    "original_blocking": attempt["blocking"],
                }
                try:
                    draft = adapt(attempt["reply"], sources)
                    checked = validate(draft, sources, meeting_context(meeting))
                    row.update(
                        draft=draft.model_dump(),
                        summary=checked.summary.model_dump() if checked.summary else None,
                        blocking=checked.blocking,
                        warnings=checked.warnings,
                    )
                except ValueError as error:
                    row["adapter_error"] = str(error)
                output.write(json.dumps(row) + "\n")


if __name__ == "__main__":
    main()
