"""Compile direct references without asking the model to rewrite commitments."""

import re

from meeting_notes.compiler_v4 import TIMING_PATTERN as _DATE
from meeting_notes.compiler_v4 import Source as Source
from meeting_notes.compiler_v4 import passages as passages
from meeting_notes.contract_v6 import Draft
from meeting_notes.figures import unsaid_numbers
from meeting_notes.grounding import Checked
from meeting_notes.summary import ActionItem, Conflict, Summary


def validate(draft: Draft, sources: list[Source], context: str = "") -> Checked:
    lookup = {s.id: s for s in sources}
    blocking: list[str] = []
    warnings: list[str] = []

    def resolve(ids: list[str], kind: str) -> list[Source]:
        found: list[Source] = []
        for identifier in dict.fromkeys(ids):
            source = lookup.get(identifier)
            if source is None or source.source != kind:
                blocking.append(f"Invalid {kind} source: {identifier}")
            else:
                found.append(source)
        return found

    disputed: set[str] = set()
    conflicts: list[Conflict] = []
    for conflict in draft.conflicts:
        spoken = resolve(conflict.transcript, "transcript")
        written = resolve(conflict.notes, "notes")
        if len(spoken) == len(set(conflict.transcript)) and len(written) == len(
            set(conflict.notes)
        ):
            disputed.update(conflict.transcript + conflict.notes)
        conflicts.append(
            Conflict(
                topic=conflict.topic,
                transcript=" ".join(s.text for s in spoken),
                handwritten=" ".join(s.text for s in written),
            )
        )
        probe = Summary(overview=conflict.topic, key_points=[], decisions=[], action_items=[])
        for number in unsaid_numbers(probe, " ".join(s.text for s in spoken + written)):
            single = Summary(overview=number, key_points=[], decisions=[], action_items=[])
            reason = (
                "elsewhere in source material"
                if not unsaid_numbers(single, " ".join(s.text for s in sources))
                else "only in metadata"
                if not unsaid_numbers(single, context)
                else "in neither source nor metadata"
            )
            warnings.append(
                f"Conflict topic: number {number} absent from cited evidence ({reason})"
            )
    task_sources: set[str] = set()
    actions: list[ActionItem] = []
    commitments = {t.original_commitment_id for t in draft.action_items}
    updates: dict[str, list[str]] = {}
    for update in draft.timing_updates:
        target = update.original_commitment_id
        primary = resolve([target], "transcript")
        evidence = resolve(update.source_ids, "transcript")
        if target not in commitments:
            blocking.append(f"Timing update has no original action: {target}")
        for source in evidence:
            if source.id == target:
                continue
            if primary and source.start <= primary[0].start:
                blocking.append(
                    f"Timing update {source.id} must follow original commitment {target}"
                )
            updates.setdefault(target, []).append(source.id)
    for identifier in dict.fromkeys(t.original_commitment_id for t in draft.action_items):
        group = [t for t in draft.action_items if t.original_commitment_id == identifier]
        primary = resolve([identifier], "transcript")
        related = resolve(updates.get(identifier, []), "transcript")
        related.sort(key=lambda source: source.start)
        for task in group:
            if task.timing is not None:
                resolve([task.timing.source_id], "transcript")
                if task.timing.source_id != identifier:
                    blocking.append(
                        f"Initial timing must cite original commitment {identifier}; "
                        "put later evidence in timing_updates"
                    )
        task_sources.update([identifier, *(source.id for source in related)])
        if not primary:
            continue
        source = primary[0]
        text = source.text
        owner = None
        if re.search(r"\b(?:I will|I'll|I shall|I am going to|I'm going to)\b", text, re.I):
            owner = source.speaker
            introductions = [
                m[1]
                for s in sources
                if s.source == "transcript"
                and s.turn == source.turn
                and s.speaker == source.speaker
                for m in re.finditer(r"(?:^|\s)([A-Z][\w'-]*(?: [A-Z][\w'-]*)?) here\.", s.text)
            ]
            introductions += [
                m[1]
                for s in sources
                if s.source == "transcript"
                and s.turn == source.turn
                and s.speaker == source.speaker
                for m in re.finditer(
                    r"(?i:I am|I'm|this is|my name is) "
                    r"([A-Z][\w'-]*(?: [A-Z][\w'-]*)?)(?=[.!?,]|$)",
                    s.text,
                )
            ]
            if owner == "Them" and len(set(introductions)) == 1:
                owner = introductions[0]
        proposals = {(t.timing.source_id, t.timing.quote) for t in group if t.timing}
        proposal = next(iter(proposals)) if len(proposals) == 1 else None
        timing = proposal[1] if proposal and proposal[0] == identifier else None
        due = None
        review: list[str] = []
        if timing and text.count(timing) == 1 and _DATE.search(timing):
            start = text.index(timing)
            tail = text[start + len(timing) :].strip(" .!?;")
            modifier = re.search(
                r"(?:\b(?:by|on|at)\s+)?\b(?:next|this|following|coming)\s+$|\b(?:by|on|at)\s+$",
                text[:start],
                re.I,
            )
            if modifier:
                start = modifier.start()
            before = text[:start]
            if (
                before.strip()
                and owner is not None
                and not related
                and identifier not in disputed
                and not re.search(r"\b(and|but|whether)\b", text, re.I)
                and not re.search(r"\b(or|if|unless|provided|depending)\b", before, re.I)
                and (
                    not tail
                    or re.match(r"^(?:,\s*)?(or|if|unless|provided|depending)\b", tail, re.I)
                )
            ):
                due = text[start:].rstrip(".!?;")
                text = before.rstrip(" ,;")
        if due is None and (
            proposals or related or _DATE.search(source.text) or identifier in disputed
        ):
            review = [
                "Timing is unassigned; review the source evidence.",
                f"Original commitment: {source.text}",
                *[f"Other spoken timing (association unverified): {s.text}" for s in related],
            ]
            if identifier in disputed:
                review.append("This source is disputed; see Conflicts.")
        actions.append(ActionItem(owner=owner, task=text, due=due, review=review))

    def section(name: str, kind: str) -> list[str]:
        output: list[str] = []
        quoted: set[str] = set()
        for item in getattr(draft, name):
            evidence: list[Source] = []
            for ref in dict.fromkeys(item.sources):
                candidate = lookup.get(ref)
                if candidate is None or (candidate.source != kind and ref not in disputed):
                    blocking.append(f"Invalid {kind} source: {ref}")
                else:
                    evidence.append(candidate)
            removed = set(item.sources) & (task_sources | disputed)
            if removed:
                if set(item.sources) & disputed and name in ("overview", "key_points"):
                    neutral = "Sources disagree; see Conflicts."
                    if neutral not in output:
                        output.append(neutral)
                # The model may combine independent facts in one prose item. Keep
                # unaffected source text instead of guessing which prose clause remains.
                for source in evidence:
                    if source.id not in removed and source.id not in quoted:
                        label = source.speaker or (
                            "Handwritten notes" if kind == "notes" else "Transcript"
                        )
                        output.append(f"{label}: “{source.text}”")
                        quoted.add(source.id)
                continue
            probe = Summary(overview=item.text, key_points=[], decisions=[], action_items=[])
            for number in unsaid_numbers(probe, "\n".join(s.text for s in evidence)):
                single = Summary(overview=number, key_points=[], decisions=[], action_items=[])
                own = "\n".join(s.text for s in sources if s.source == kind)
                other = "\n".join(s.text for s in sources if s.source != kind)
                reason = (
                    "elsewhere in the same source"
                    if not unsaid_numbers(single, own)
                    else "in the other source"
                    if not unsaid_numbers(single, other)
                    else "only in metadata"
                    if not unsaid_numbers(single, context)
                    else "in neither source nor metadata"
                )
                warnings.append(f"{name}: number {number} absent from cited evidence ({reason})")
            output.append(item.text)
        return output

    overview = section("overview", "transcript")
    points = section("key_points", "transcript")
    decisions = section("decisions", "transcript")
    notes = section("notes_context", "notes")
    if actions:
        overview.append("See Action items for spoken commitments and timing.")
    if conflicts and not any("see Conflicts" in s for s in overview + points):
        points.append("Sources disagree; see Conflicts.")
    if not any((overview, points, decisions, notes, conflicts, actions)):
        blocking.append("No supported content was generated")
    if not overview:
        overview = ["See the supported items below."]
    summary = (
        None
        if blocking
        else Summary(
            overview=" ".join(overview),
            key_points=points,
            decisions=decisions,
            action_items=actions,
            notes_context=notes,
            conflicts=conflicts,
        )
    )
    return Checked(summary, blocking, warnings)
