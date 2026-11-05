#!/usr/bin/env python3
"""Adapt saved V3 drafts to V4 references without inference or semantic repairs."""

import argparse
import json
from pathlib import Path

from meeting_notes.compiler import passages, validate
from meeting_notes.contract import Action, Dispute, Draft, SupportedText
from meeting_notes.grounding import Draft as LegacyDraft
from meeting_notes.grounding import Span


def adapt(reply: str, transcript: str, notes: str, old_sources: list[dict]) -> Draft:
    legacy = LegacyDraft.model_validate_json(reply)
    current = passages(transcript, notes)
    offsets = {}
    positions = {"transcript": 0, "notes": 0}
    inputs = {"transcript": transcript, "notes": notes}
    for source in old_sources:
        kind = source["source"]
        start = inputs[kind].find(source["text"], positions[kind])
        if start < 0:
            raise ValueError("Cannot locate saved source")
        offsets[source["id"]] = (kind, start, source["text"])
        positions[kind] = start + len(source["text"])

    def refs(span: Span) -> list[str]:
        kind, start, text = offsets[span.passage]
        if text.count(span.quote) != 1:
            raise ValueError("Unmappable original quotation")
        a = start + text.index(span.quote)
        b = a + len(span.quote)
        found = [s.id for s in current if s.source == kind and s.start < b and a < s.end]
        if not found:
            raise ValueError("Unmappable statement")
        return found

    claims = {c.id: c for c in legacy.claims}

    def claim_refs(identifier: str) -> list[str]:
        return list(dict.fromkeys(i for e in claims[identifier].evidence for i in refs(e)))

    def section(ids: list[str]) -> list[SupportedText]:
        return [SupportedText(text=claims[i].text, sources=claim_refs(i)) for i in ids]

    actions = []
    for task in legacy.action_items:
        primary = refs(task.commitment)
        if len(primary) != 1:
            raise ValueError("Commitment maps to multiple statements")
        related = [i for span in task.timing_link for i in refs(span)]
        timing = None
        if task.timing:
            targets = refs(task.timing)
            if targets == primary:
                timing = task.timing.quote
            else:
                related.extend(targets)
        actions.append(
            Action(
                commitment=primary[0], timing=timing, timing_context=list(dict.fromkeys(related))
            )
        )
    return Draft(
        overview=section(legacy.overview),
        key_points=section(legacy.key_points),
        decisions=section(legacy.decisions),
        notes_context=section(legacy.notes_context),
        action_items=actions,
        conflicts=[
            Dispute(
                topic=c.topic,
                transcript=claim_refs(c.transcript_claim),
                notes=claim_refs(c.notes_claim),
            )
            for c in legacy.conflicts
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "evaluation/m10/v3"
    pairs = {p["id"]: p for p in json.loads((root / "pairs.json").read_text())}
    rows = [
        json.loads(line) for line in (root / "results/proposed.jsonl").read_text().splitlines()
    ][1:]
    with args.output.open("x") as output:
        for row in rows:
            pair = pairs[row["case"]]
            for index, attempt in enumerate(row["audit"]["attempts"]):
                result = {
                    "case": row["case"],
                    "attempt": index,
                    "original_blocking": attempt["blocking"],
                }
                try:
                    draft = adapt(
                        attempt["reply"],
                        pair["transcript"],
                        pair["handwritten_text"],
                        row["audit"]["passages"],
                    )
                    checked = validate(
                        draft, passages(pair["transcript"], pair["handwritten_text"])
                    )
                    result.update(
                        draft=draft.model_dump(),
                        summary=checked.summary.model_dump() if checked.summary else None,
                        blocking=checked.blocking,
                        warnings=checked.warnings,
                    )
                except (ValueError, KeyError) as error:
                    result["adapter_error"] = str(error)
                output.write(json.dumps(result) + "\n")


if __name__ == "__main__":
    main()
