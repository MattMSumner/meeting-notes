"""Compile direct references without asking the model to rewrite commitments."""

import re

from meeting_notes.contract_v4 import Draft
from meeting_notes.figures import unsaid_numbers
from meeting_notes.grounding import Checked, Passage
from meeting_notes.summary import ActionItem, Conflict, Summary


class Source(Passage):
    start: int
    end: int
    turn: int


def passages(transcript: str, notes: str) -> list[Source]:
    result: list[Source] = []
    for kind, text, prefix in (("transcript", transcript, "T"), ("notes", notes, "N")):
        offset = 0
        index = 0
        for turn, line in enumerate(text.splitlines(keepends=True)):
            speaker = None
            content = line.rstrip("\r\n")
            base = offset
            match = re.match(r"\[\d+:\d\d:\d\d\] ([^:]+): ", content)
            if kind == "transcript" and match:
                speaker = match[1]
                base += match.end()
                content = content[match.end() :]
            cuts = [0]
            for boundary in re.finditer(r"(?<=[.!?;])\s+", content):
                preceding = content[: boundary.start()].split()[-1]
                if re.fullmatch(
                    r"(?:[A-Za-z]\.)+|(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|etc)\.", preceding, re.I
                ):
                    continue
                cuts.append(boundary.end())
            cuts.append(len(content))
            for a, b in zip(cuts, cuts[1:], strict=False):
                piece = content[a:b].rstrip()
                if not piece.strip():
                    continue
                index += 1
                result.append(
                    Source(
                        id=f"{prefix}{index}",
                        source="transcript" if kind == "transcript" else "notes",
                        text=piece,
                        speaker=speaker,
                        start=base + a,
                        end=base + a + len(piece),
                        turn=turn,
                    )
                )
            offset += len(line)
    return result


_DATE = re.compile(
    r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|today|tomorrow|tonight|week|month|year|January|February|March|April|May|June|July|August|September|October|November|December)\b|\b\d{1,4}[-/]\d{1,2}",
    re.I,
)


TIMING_PATTERN = _DATE


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
    for identifier in dict.fromkeys(t.commitment for t in draft.action_items):
        group = [t for t in draft.action_items if t.commitment == identifier]
        primary = resolve([identifier], "transcript")
        related_ids = list(dict.fromkeys(i for t in group for i in t.timing_context))
        related = resolve(related_ids, "transcript")
        task_sources.update([identifier, *related_ids])
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
        proposals = {t.timing for t in group if t.timing}
        timing = next(iter(proposals)) if len(proposals) == 1 else None
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
                *[f"Other spoken timing: {s.text}" for s in related],
            ]
            if identifier in disputed:
                review.append("This source is disputed; see Conflicts.")
        actions.append(ActionItem(owner=owner, task=text, due=due, review=review))

    def section(name: str, kind: str) -> list[str]:
        output: list[str] = []
        for item in getattr(draft, name):
            evidence = resolve(item.sources, kind)
            if set(item.sources) & task_sources:
                continue
            if set(item.sources) & disputed:
                if (
                    name in ("overview", "key_points")
                    and "Sources disagree; see Conflicts." not in output
                ):
                    output.append("Sources disagree; see Conflicts.")
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
