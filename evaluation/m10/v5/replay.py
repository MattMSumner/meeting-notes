#!/usr/bin/env python3
"""Replay V4 responses through the repaired contract without inference or semantic repair."""

import argparse
import hashlib
import json
from pathlib import Path

from meeting_notes.compiler import Source, passages, validate
from meeting_notes.contract import Action, Dispute, Draft, SupportedText, Timing
from meeting_notes.contract_v4 import Draft as PriorDraft
from meeting_notes.evidence import meeting_context
from meeting_notes.meeting import Meeting


def adapt(reply: str, sources: list[Source]) -> Draft:
    prior = PriorDraft.model_validate_json(reply)
    by_id = {s.id: s for s in sources}
    actions = []
    for task in prior.action_items:
        timing = None
        if task.timing is not None:
            primary = by_id.get(task.commitment)
            if primary and primary.source == "transcript" and primary.text.count(task.timing) == 1:
                matches = [primary]
            else:
                matches = [
                    s
                    for s in sources
                    if s.source == "transcript" and s.text.count(task.timing) == 1
                ]
            if len(matches) != 1:
                raise ValueError(
                    "Timing quote has no unambiguous exact source; no mapping invented"
                )
            timing = Timing(source_id=matches[0].id, quote=task.timing)
        actions.append(
            Action(commitment_id=task.commitment, timing=timing, timing_context=task.timing_context)
        )
    return Draft(
        overview=[SupportedText.model_validate(s.model_dump()) for s in prior.overview],
        key_points=[SupportedText.model_validate(s.model_dump()) for s in prior.key_points],
        decisions=[SupportedText.model_validate(s.model_dump()) for s in prior.decisions],
        notes_context=[SupportedText.model_validate(s.model_dump()) for s in prior.notes_context],
        conflicts=[Dispute.model_validate(s.model_dump()) for s in prior.conflicts],
        action_items=actions,
    )


def main() -> None:
    from datetime import datetime

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "evaluation/m10/v4"
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
