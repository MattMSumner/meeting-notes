#!/usr/bin/env python3
"""Replay V5 responses through the repaired contract without inference or semantic repair."""

import argparse
import hashlib
import json
from pathlib import Path

from meeting_notes.compiler_v6 import Source, passages, validate
from meeting_notes.contract_v5 import Draft as PriorDraft
from meeting_notes.contract_v6 import Action, Dispute, Draft, SupportedText, Timing, TimingUpdate
from meeting_notes.evidence import meeting_context
from meeting_notes.meeting import Meeting


def adapt(reply: str, sources: list[Source]) -> Draft:
    prior = PriorDraft.model_validate_json(reply)
    actions = []
    updates = []
    for task in prior.action_items:
        refs = list(task.timing_context)
        timing = None
        if task.timing is not None:
            if task.timing.source_id == task.commitment_id:
                timing = Timing.model_validate(task.timing.model_dump())
            else:
                refs.append(task.timing.source_id)
        actions.append(Action(original_commitment_id=task.commitment_id, timing=timing))
        refs = list(dict.fromkeys(ref for ref in refs if ref != task.commitment_id))
        if refs:
            updates.append(TimingUpdate(original_commitment_id=task.commitment_id, source_ids=refs))
    return Draft(
        overview=[SupportedText.model_validate(s.model_dump()) for s in prior.overview],
        key_points=[SupportedText.model_validate(s.model_dump()) for s in prior.key_points],
        decisions=[SupportedText.model_validate(s.model_dump()) for s in prior.decisions],
        notes_context=[SupportedText.model_validate(s.model_dump()) for s in prior.notes_context],
        conflicts=[Dispute.model_validate(s.model_dump()) for s in prior.conflicts],
        action_items=actions,
        timing_updates=updates,
    )


def main() -> None:
    from datetime import datetime

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "evaluation/m10/v5"
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
