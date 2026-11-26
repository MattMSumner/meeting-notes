"""Validate source references and compile a model draft into a publishable summary.

Reference integrity is mechanical. Entailment, missed conflicts and ambiguous speaker
identity still require evaluation; a real quote is not proof of the claim it accompanies.
"""

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from meeting_notes.figures import unsaid_numbers
from meeting_notes.summary import ActionItem, Conflict, Summary

_TIMING = re.compile(
    r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|today|tomorrow|"
    r"tonight|day|days|week|weeks|month|months|year|years|hour|hours|minute|minutes|"
    r"January|February|March|April|May|June|July|August|September|October|November|"
    r"December|after|before|when|once|until|by|soon|later)\b|"
    r"\b\d{1,4}[-/]\d{1,2}(?:[-/]\d{1,4})?\b|\b\d{1,2}:\d{2}\b|\b\d{1,2}\s*(?:am|pm)\b",
    re.IGNORECASE,
)


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Passage(Record):
    id: str
    source: Literal["transcript", "notes"]
    text: str
    speaker: str | None


def passages(transcript: str, notes: str) -> list[Passage]:
    """IDs are deterministic within the exact saved snapshot."""
    result: list[Passage] = []
    for source, text, prefix in (("transcript", transcript, "T"), ("notes", notes, "N")):
        index = 0
        for line in text.splitlines():
            speaker = None
            if source == "transcript":
                match = re.match(r"\[\d+:\d\d:\d\d\] ([^:]+): (.*)", line)
                if match:
                    speaker, line = match.groups()
            # Separate sentences and explicit coordinated commitments. Do not split an
            # alternative deadline at 'or', since its condition belongs to the task.
            parts = (
                re.split(
                    r"(?<=[.!?;])\s+|\s+(?:and|but)\s+(?=(?:I|we)\s+(?:will|shall)\b|I'll\b|we'll\b)",
                    line,
                    flags=re.IGNORECASE,
                )
                if source == "transcript"
                else [line]
            )
            for part in parts:
                if not part.strip():
                    continue
                index += 1
                result.append(
                    Passage(
                        id=f"{prefix}{index}",
                        source="transcript" if source == "transcript" else "notes",
                        text=part,
                        speaker=speaker,
                    )
                )
    return result


class Span(Record):
    passage: str
    quote: str = Field(min_length=1, description="Exact contiguous text from this passage")


class Claim(Record):
    id: str
    text: str
    evidence: list[Span] = Field(min_length=1)


class Task(Record):
    claim: str
    commitment: Span = Field(description="The complete single statement making this commitment")
    owner: str | None
    owner_evidence: Span | None = Field(
        description="Spoken name evidence when owner differs from speaker"
    )
    timing: Span | None = Field(
        description="Complete timing phrase within commitment, otherwise null"
    )
    timing_link: list[Span] = Field(
        description="Separate timing exchange needing review; never auto-assign"
    )


class Dispute(Record):
    topic: str
    transcript_claim: str
    notes_claim: str


class Draft(Record):
    claims: list[Claim]
    overview: list[str] = Field(description="Claim IDs, not prose")
    key_points: list[str] = Field(description="Claim IDs, not prose")
    decisions: list[str] = Field(description="Spoken agreement claim IDs")
    action_items: list[Task]
    notes_context: list[str] = Field(description="Written-only claim IDs")
    conflicts: list[Dispute]


@dataclass
class Checked:
    summary: Summary | None
    blocking: list[str]
    warnings: list[str]


def validate(draft: Draft, sources: list[Passage], context: str = "") -> Checked:
    blocking: list[str] = []
    warnings: list[str] = []
    source_map = {p.id: p for p in sources}
    claims = {c.id: c for c in draft.claims}
    if len(claims) != len(draft.claims):
        blocking.append("Claim IDs must be unique")
    if not draft.overview:
        blocking.append("Overview must reference at least one supported claim")
    ranges: dict[str, list[tuple[str, int, int]]] = {}

    def span(ref: Span, where: str) -> Passage | None:
        passage = source_map.get(ref.passage)
        if passage is None:
            blocking.append(f"{where}: unknown passage {ref.passage}")
            return None
        if not ref.quote.strip() or passage.text.count(ref.quote) != 1:
            blocking.append(f"{where}: quote must occur exactly once in {ref.passage}")
            return None
        return passage

    def claim(identifier: str, source: str | None, where: str) -> Claim | None:
        value = claims.get(identifier)
        if value is None:
            blocking.append(f"{where}: unknown claim {identifier}")
            return None
        if source and any(
            source_map.get(e.passage) is None or source_map[e.passage].source != source
            for e in value.evidence
        ):
            blocking.append(f"{where}: {identifier} requires only {source} evidence")
        return value

    for c in draft.claims:
        ranges[c.id] = []
        for ref in c.evidence:
            if p := span(ref, c.id):
                start = p.text.index(ref.quote)
                ranges[c.id].append((p.id, start, start + len(ref.quote)))
        # Narrow the old presence check to the cited spans, not the whole source.
        probe = Summary(overview=c.text, key_points=[], decisions=[], action_items=[])
        missing = unsaid_numbers(probe, "\n".join(e.quote for e in c.evidence))
        own_sources = {source_map[e.passage].source for e in c.evidence if e.passage in source_map}
        own = "\n".join(p.text for p in sources if p.source in own_sources)
        other = "\n".join(p.text for p in sources if p.source not in own_sources)
        for number in missing:
            single = Summary(overview=number, key_points=[], decisions=[], action_items=[])
            if not unsaid_numbers(single, own):
                reason = "found elsewhere in the same source"
            elif not unsaid_numbers(single, other):
                reason = "found in the other source"
            elif not unsaid_numbers(single, context):
                reason = "found only in meeting metadata"
            else:
                reason = "found in neither source nor meeting metadata"
            warnings.append(f"{c.id}: numbers absent from cited evidence: {number} ({reason})")

    def overlaps(a: str, b: str) -> bool:
        return any(
            pa == pb and sa < eb and sb < ea
            for pa, sa, ea in ranges.get(a, [])
            for pb, sb, eb in ranges.get(b, [])
        )

    disputed: set[str] = set()
    conflicts: list[Conflict] = []
    for d in draft.conflicts:
        spoken = claim(d.transcript_claim, "transcript", "conflict")
        written = claim(d.notes_claim, "notes", "conflict")
        disputed.update((d.transcript_claim, d.notes_claim))
        if spoken and written:
            for c in (spoken, written):
                for e in c.evidence:
                    p = source_map.get(e.passage)
                    if p is not None and e.quote != p.text:
                        blocking.append(
                            f"conflict: {c.id} must quote the complete source statement"
                        )
            topic = Summary(overview=d.topic, key_points=[], decisions=[], action_items=[])
            missing = unsaid_numbers(
                topic, " ".join(e.quote for c in (spoken, written) for e in c.evidence)
            )
            if missing:
                warnings.append(
                    "Conflict topic: numbers absent from its evidence: " + ", ".join(missing)
                )
            # Verbatim accounts preserve hedges the model might remove in paraphrasing.
            conflicts.append(
                Conflict(
                    topic=d.topic,
                    transcript=" ".join(e.quote for e in spoken.evidence),
                    handwritten=" ".join(e.quote for e in written.evidence),
                )
            )
    # A clone with a different claim ID cannot bypass a known conflict by citing the
    # same span. This is conservative when a quote contains unrelated facts as well.
    disputed |= {c.id for c in draft.claims if any(overlaps(c.id, d) for d in disputed)}
    neutral = "Sources disagree; see Conflicts."

    def section(ids: list[str], source: str, where: str) -> list[str]:
        result: list[str] = []
        for identifier in ids:
            c = claim(identifier, None if identifier in disputed else source, where)
            if c is None:
                continue
            if identifier in disputed:
                if where in ("overview", "key_points") and neutral not in result:
                    result.append(neutral)
            else:
                result.append(c.text)
        return result

    overview = section(draft.overview, "transcript", "overview")
    points = section(draft.key_points, "transcript", "key_points")
    decisions = section(draft.decisions, "transcript", "decisions")
    notes_context = section(draft.notes_context, "notes", "notes_context")
    if conflicts and neutral not in overview and neutral not in points:
        points.append(neutral)
    actions: list[ActionItem] = []
    for i, task in enumerate(draft.action_items):
        where = f"action_items.{i}"
        c = claim(task.claim, "transcript", where)
        commitment = span(task.commitment, where)
        if c is None or commitment is None:
            continue
        if task.claim in disputed:
            blocking.append(
                f"{where}: commitment overlaps disputed evidence; cite the separate commitment"
            )
        if commitment.source != "transcript" or task.commitment.quote != commitment.text:
            blocking.append(f"{where}: commitment must cite a complete transcript statement")
        if any(
            e.passage != commitment.id or e.quote not in task.commitment.quote for e in c.evidence
        ):
            blocking.append(f"{where}: task evidence must belong to its commitment statement")
        if c.text.rstrip(".!?").casefold() not in commitment.text.casefold():
            blocking.append(f"{where}: task wording must be an exact phrase in its commitment")
        # Multiple commitments in a single statement need human review, not a guessed
        # association between the last deadline and one of its tasks.
        if task.timing is not None and re.search(
            r"\b(?:and|but)\b", re.sub(r"^(and|but)\s+", "", commitment.text, flags=re.I), re.I
        ):
            blocking.append(
                f"{where}: coordinated commitment is ambiguous; review task/timing association"
            )
        if task.owner_evidence is not None:
            owner_source = span(task.owner_evidence, where + ".owner")
        else:
            owner_source = None
        if task.owner and task.owner != commitment.speaker:
            if not (
                owner_source
                and owner_source.source == "transcript"
                and owner_source.speaker == commitment.speaker
                and re.search(
                    rf"(?:\b(?:I am|I'm|this is|my name is)\s+{re.escape(task.owner)}\b|"
                    rf"\b{re.escape(task.owner)}\s+here\b)",
                    task.owner_evidence.quote if task.owner_evidence else "",
                    re.I,
                )
            ):
                blocking.append(f"{where}: owner needs spoken name evidence from the same speaker")
        due = None
        if task.timing is not None:
            timing_source = span(task.timing, where + ".timing")
            if timing_source is None or timing_source.id != commitment.id:
                blocking.append(
                    f"{where}: deadline must come from this task's commitment, not another passage"
                )
            else:
                start = commitment.text.index(task.timing.quote)
                task_end = commitment.text.casefold().find(c.text.rstrip(".!?").casefold()) + len(
                    c.text.rstrip(".!?")
                )
                tail = commitment.text[start + len(task.timing.quote) :]
                if start < task_end or tail.strip(" .!?;"):
                    blocking.append(
                        f"{where}: cite the complete trailing timing phrase after the task"
                    )
                # Broad condition markers intentionally flag uncertain attachment. They
                # are not a complete natural-language parser or an entailment proof.
                rest = commitment.text.replace(task.timing.quote, "", 1)
                if re.search(r"\b(or|if|unless|otherwise|depending|provided)\b", rest, re.I):
                    blocking.append(f"{where}: timing omits an alternative or condition")
                if not _TIMING.search(task.timing.quote):
                    blocking.append(f"{where}: timing phrase is not recognized; review it")
                due = task.timing.quote
        for ref in task.timing_link:
            p = span(ref, where + ".timing_link")
            if p and p.source != "transcript":
                blocking.append(f"{where}: timing exchange requires transcript evidence")
        if task.timing_link:
            if task.timing is not None:
                blocking.append(
                    f"{where}: cannot assign timing while a separate exchange needs review"
                )
            warnings.append(
                f"Deadline needs review for {c.text}. Timing evidence (association unverified): "
                + " / ".join(e.quote for e in task.timing_link)
            )
        if task.timing is None and not task.timing_link and _TIMING.search(commitment.text):
            warnings.append(
                f"Timing needs review for {c.text}: no deadline was assigned. "
                f"Source statement: {commitment.text}"
            )
        actions.append(ActionItem(owner=task.owner, task=c.text, due=due))
    summary = (
        None
        if blocking
        else Summary(
            overview=" ".join(overview),
            key_points=points,
            decisions=decisions,
            action_items=actions,
            notes_context=notes_context,
            conflicts=conflicts,
        )
    )
    return Checked(summary, list(dict.fromkeys(blocking)), list(dict.fromkeys(warnings)))
