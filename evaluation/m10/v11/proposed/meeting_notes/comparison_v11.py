"""V11 relations and code-resolved claim coverage, without inferring identity.

Dimension strings are literal extractions (subject may be a short semantic label).
None means absent; a None field listed in unresolved means extraction is unresolved.
Populated dimensions don't prove correct splitting, qualifier attribution or entailment.
"""

import re
from typing import Any, Literal, get_args

from pydantic import Field

from meeting_notes.grounding import Record
from meeting_notes.spans_v11 import (
    Anchor,
    Snapshot,
    Source,
    Span,
    formatting_gap,
    source_errors,
    span,
)
from meeting_notes.spans_v11 import (
    resolve as resolve_anchor,
)

Dimension = Literal["subject", "quantity", "unit", "period", "scope", "status"]


class Meaning(Record):
    subject: str | None
    quantity: str | None
    unit: str | None
    period: str | None
    scope: str | None
    status: str | None
    unresolved: list[Dimension]


class Account(Anchor):
    kind: Literal["fact", "commitment", "context", "request"]
    meaning: Meaning


class Claim(Record):
    note: Account
    transcript: list[Account]
    outcome: Literal["consistent", "additional", "conflicting", "related-distinct", "uncertain"]
    reason: str = Field(min_length=1)


class Comparison(Record):
    claims: list[Claim]


class ResolvedAccount(Record):
    span: Span
    kind: Literal["fact", "commitment", "context", "request"]
    meaning: Meaning


class ResolvedClaim(Record):
    id: str
    note: ResolvedAccount
    transcript: list[ResolvedAccount]
    outcome: Literal["consistent", "additional", "conflicting", "related-distinct", "uncertain"]
    reason: str


class Resolution(Record):
    claims: list[ResolvedClaim]
    gaps: list[Span]
    errors: list[str]


def request_schema(sources: list[Source]) -> dict[str, Any]:
    if not sources or len({s.id for s in sources}) != len(sources):
        raise ValueError("Unique source IDs are required")
    schema = Comparison.model_json_schema()
    schema["$defs"]["Account"]["properties"]["source_id"] = {
        "type": "string",
        "enum": [s.id for s in sources],
    }
    return schema


def _meaning_errors(account: Account) -> list[str]:
    errors: list[str] = []
    meaning = account.meaning
    if len(set(meaning.unresolved)) != len(meaning.unresolved):
        errors.append("Duplicate unresolved dimension")
    for name in get_args(Dimension):
        value: str | None = getattr(meaning, name)
        if value is not None and (
            not value.strip() or value.strip().casefold() in ("null", "none")
        ):
            errors.append(f"Blank/literal-null dimension {name}")
        if name in meaning.unresolved and value is not None:
            errors.append(f"Unresolved dimension {name} must have null value")
        if value is not None and name != "subject" and value not in account.quote:
            errors.append(f"Dimension {name} must be extracted literally from its account")
    # This narrow presence diagnostic doesn't extract or invent a value or unit.
    # Embedded model identifiers aren't quantities; explicitly extracted periods
    # account for their own digits. Other ambiguities can be marked unresolved.
    periods: list[tuple[int, int]] = []
    if meaning.period:
        periods = [
            (m.start(), m.end()) for m in re.finditer(re.escape(meaning.period), account.quote)
        ]
    numeric = any(
        not any(start <= m.start() and m.end() <= end for start, end in periods)
        for m in re.finditer(r"(?<![\w-])\d+(?:[.,]\d+)*(?![\w])", account.quote)
    )
    for name, present in (
        ("quantity", numeric),
        (
            "unit",
            bool(re.search(r"[$€£%]|\b(?:dollars?|cents?|seats?|hours?)\b", account.quote, re.I)),
        ),
    ):
        if present and getattr(meaning, name) is None and name not in meaning.unresolved:
            errors.append(f"Explicit {name} needs extraction or unresolved status")
    return errors


def epistemic_review(left: Meaning, right: Meaning) -> bool:
    """Only overt tentative/estimate versus confirmed/approval markers need review.

    Literal wording/case inequality proves nothing. These two narrow marker groups
    diagnose an unresolved epistemic relation, not factual agreement or conflict.
    Unrecognized status phrases remain a semantic evaluation concern.
    """

    def group(value: str | None) -> str | None:
        if value and re.search(r"\b(?:estimate[ds]?|tentative|proposed|proposal)\b", value, re.I):
            return "tentative"
        if value and re.search(r"\b(?:confirmed|approved|approval|final)\b", value, re.I):
            return "confirmed"
        return None

    a, b = group(left.status), group(right.status)
    return a is not None and b is not None and a != b


def resolve(comparison: Comparison, sources: list[Source]) -> Resolution:
    """Resolve ordered exact anchors and retain every gap; errors fail compilation closed."""
    errors = source_errors(Snapshot(sources=sources))
    result: list[ResolvedClaim] = []
    gaps: list[Span] = []
    positions = {s.id: index for index, s in enumerate(sources)}
    last_order = (-1, -1)
    ends: dict[str, int] = {}
    counts: dict[str, int] = {}
    for claim in comparison.claims:
        note: ResolvedAccount | None = None
        transcript: list[ResolvedAccount] = []
        for account, kind in [
            (claim.note, "notes"),
            *[(a, "transcript") for a in claim.transcript],
        ]:
            errors.extend(f"{account.source_id}: {e}" for e in _meaning_errors(account))
            try:
                selected = resolve_anchor(account, sources, kind)
                resolved = ResolvedAccount(
                    span=selected, kind=account.kind, meaning=account.meaning
                )
                if kind == "notes":
                    note = resolved
                else:
                    transcript.append(resolved)
            except ValueError as error:
                errors.append(str(error))
        if (
            claim.outcome in ("consistent", "conflicting", "related-distinct")
            and not claim.transcript
        ):
            errors.append(f"{claim.outcome} requires transcript accounts: {claim.note.source_id}")
        if claim.outcome == "additional" and claim.transcript:
            errors.append(f"Additional claim must be unmatched: {claim.note.source_id}")
        if claim.outcome == "conflicting" and any(
            a.kind in ("request", "context") for a in [claim.note, *claim.transcript]
        ):
            errors.append(
                f"Nonfactual account cannot assert factual conflict: {claim.note.source_id}"
            )
        if not claim.reason.strip():
            errors.append(f"Blank relation reason: {claim.note.source_id}")
        if claim.outcome in ("consistent", "conflicting"):
            if any(a.meaning.unresolved for a in [claim.note, *claim.transcript]):
                errors.append("Unresolved extraction requires an uncertain relation")
            if any(epistemic_review(a.meaning, claim.note.meaning) for a in claim.transcript):
                errors.append(
                    "Overt tentative/confirmed relation requires uncertain/related review"
                )
        refs = [(a.span.source_id, a.span.start, a.span.end) for a in transcript]
        if len(refs) != len(set(refs)):
            errors.append(f"Duplicate transcript comparison account: {claim.note.source_id}")
        for index, (source_id, start, end) in enumerate(refs):
            for other_id, other_start, other_end in refs[:index]:
                if source_id == other_id and start < other_end and other_start < end:
                    errors.append(f"Overlapping transcript comparison accounts: {source_id}")
        if note is None:
            continue
        selected = note.span
        source = next(s for s in sources if s.id == selected.source_id)
        order = (positions[source.id], selected.start)
        if order <= last_order:
            errors.append(f"Reversed or duplicate claim order: {source.id}")
        last_order = order
        previous = ends.get(source.id, 0)
        if selected.start < previous:
            errors.append(f"Duplicate or overlapping claim span: {source.id}")
        elif selected.start > previous:
            gap = span(source, previous, selected.start)
            gaps.append(gap)
            if not formatting_gap(gap.text, between=source.id in ends):
                errors.append(f"Uncovered semantic text: {source.id} [{gap.start}:{gap.end}]")
        ends[source.id] = max(previous, selected.end)
        counts[source.id] = counts.get(source.id, 0) + 1
        result.append(
            ResolvedClaim(
                id=f"{source.id}.C{counts[source.id]}",
                note=note,
                transcript=transcript,
                outcome=claim.outcome,
                reason=claim.reason,
            )
        )
    for source in sources:
        if source.source != "notes":
            continue
        previous = ends.get(source.id, 0)
        if previous < len(source.text):
            gap = span(source, previous, len(source.text))
            gaps.append(gap)
            if not formatting_gap(gap.text):
                errors.append(f"Uncovered semantic text: {source.id} [{gap.start}:{gap.end}]")
    gaps.sort(key=lambda gap: (positions[gap.source_id], gap.start))
    return Resolution(claims=result, gaps=gaps, errors=errors)


def validate(comparison: Comparison, sources: list[Source]) -> list[str]:
    return resolve(comparison, sources).errors


def claim_ids(comparison: Comparison, sources: list[Source]) -> list[str]:
    resolution = resolve(comparison, sources)
    if resolution.errors:
        raise ValueError("; ".join(resolution.errors))
    return [c.id for c in resolution.claims]
