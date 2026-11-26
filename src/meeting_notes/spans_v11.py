"""Literal anchors and snapshots for V11; offsets count Python string characters.

Source and passage splitting are reused unchanged from wrapper 4. A Snapshot keeps
the complete effective inputs, including text between passages. Passing only Sources
is supported for pure callers, but cannot recover those inter-passage characters.
"""

import unicodedata

from pydantic import Field

from meeting_notes.compiler_v4 import Source as Source
from meeting_notes.compiler_v4 import passages as passages
from meeting_notes.grounding import Record


class Anchor(Record):
    source_id: str
    quote: str = Field(min_length=1)
    occurrence: int | None = Field(
        default=None, ge=1, description="One-based literal occurrence; required for repeated text"
    )


class Span(Record):
    source_id: str
    start: int
    end: int
    text: str
    absolute_start: int
    absolute_end: int


class Snapshot(Record):
    sources: list[Source]
    transcript: str | None = None
    notes: str | None = None


def snapshot(transcript: str, notes: str = "") -> Snapshot:
    return Snapshot(sources=passages(transcript, notes), transcript=transcript, notes=notes)


def source_errors(value: Snapshot) -> list[str]:
    errors: list[str] = []
    if value.transcript is not None and value.notes is not None:
        if passages(value.transcript, value.notes) != value.sources:
            errors.append("Source passages differ from the complete effective snapshot")
    if len({s.id for s in value.sources}) != len(value.sources):
        errors.append("Source IDs must be unique")
    previous: dict[str, int] = {}
    for source in value.sources:
        if source.start < previous.get(source.source, 0) or source.end != source.start + len(
            source.text
        ):
            errors.append(f"Invalid source offsets/order: {source.id}")
        previous[source.source] = source.end
        original = value.transcript if source.source == "transcript" else value.notes
        if original is not None and original[source.start : source.end] != source.text:
            errors.append(f"Source differs from snapshot: {source.id}")
    return errors


def span(source: Source, start: int, end: int) -> Span:
    return Span(
        source_id=source.id,
        start=start,
        end=end,
        text=source.text[start:end],
        absolute_start=source.start + start,
        absolute_end=source.start + end,
    )


def resolve(anchor: Anchor, sources: list[Source], kind: str) -> Span:
    """Raise ValueError for missing, ambiguous or wrong-kind literal evidence."""
    matches = [s for s in sources if s.id == anchor.source_id]
    if len(matches) != 1 or matches[0].source != kind:
        raise ValueError(f"Invalid {kind} source: {anchor.source_id}")
    source = matches[0]
    if not anchor.quote.strip():
        raise ValueError(f"Empty anchor: {source.id}")
    positions: list[int] = []
    offset = source.text.find(anchor.quote)
    while offset >= 0:
        positions.append(offset)
        offset = source.text.find(anchor.quote, offset + 1)
    if not positions:
        raise ValueError(f"Anchor absent from {source.id}")
    if anchor.occurrence is None and len(positions) != 1:
        raise ValueError(f"Repeated anchor requires occurrence: {source.id}")
    occurrence = anchor.occurrence or 1
    if occurrence > len(positions):
        raise ValueError(f"Anchor occurrence absent from {source.id}")
    start = positions[occurrence - 1]
    return span(source, start, start + len(anchor.quote))


def formatting_gap(text: str, *, between: bool = False) -> bool:
    """Only punctuation/whitespace, or one interior additive 'and', may be residual.

    Every character is retained even when permitted. 'But', 'or', hedges, negation,
    conditions and headings must be inside a claim. This is coverage, not entailment.
    """
    words = "".join(
        c for c in text if not c.isspace() and not unicodedata.category(c).startswith("P")
    )
    return not words or (between and words.casefold() == "and")
