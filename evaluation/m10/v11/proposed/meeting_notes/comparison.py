"""Cross-source claim comparison; references and text coverage are mechanical checks."""

from typing import Any, Literal

from pydantic import Field

from meeting_notes.compiler import Source
from meeting_notes.grounding import Record


class Meaning(Record):
    subject: str = Field(min_length=1)
    quantity: str | None
    unit: str | None
    period: str | None
    scope: str | None
    status: str = Field(min_length=1, description="Preserve estimate/proposal/approval/uncertainty")


class Account(Record):
    source_id: str
    quote: str = Field(min_length=1)
    kind: Literal["fact", "commitment", "context", "request"]
    meaning: Meaning


class Claim(Record):
    note: Account
    transcript: list[Account]
    outcome: Literal["consistent", "additional", "conflicting", "uncertain"]
    reason: str = Field(min_length=1)


class Comparison(Record):
    claims: list[Claim]


def request_schema(sources: list[Source]) -> dict[str, Any]:
    schema = Comparison.model_json_schema()
    schema["$defs"]["Account"]["properties"]["source_id"] = {
        "type": "string",
        "enum": [s.id for s in sources],
    }
    return schema


def validate(comparison: Comparison, sources: list[Source]) -> list[str]:
    """Require a nonoverlapping partition of every note passage, not semantic completeness."""
    lookup = {s.id: s for s in sources}
    errors: list[str] = []
    covered: dict[str, str] = {}
    for claim in comparison.claims:
        for account, kind in [
            (claim.note, "notes"),
            *[(a, "transcript") for a in claim.transcript],
        ]:
            source = lookup.get(account.source_id)
            if source is None or source.source != kind:
                errors.append(f"Invalid {kind} comparison source: {account.source_id}")
            elif account.quote not in source.text:
                errors.append(f"Comparison quote absent from {account.source_id}")
        identifier = claim.note.source_id
        covered[identifier] = covered.get(identifier, "") + claim.note.quote
        refs = [(a.source_id, a.quote) for a in claim.transcript]
        if len(refs) != len(set(refs)):
            errors.append(f"Duplicate transcript comparison account for {identifier}")
        if claim.outcome in ("consistent", "conflicting") and not claim.transcript:
            errors.append(f"{claim.outcome} requires transcript accounts: {identifier}")
        if claim.outcome == "additional" and claim.transcript:
            errors.append(f"Additional claim must be unmatched: {identifier}")
        if claim.note.kind in ("request", "context") and claim.outcome == "conflicting":
            errors.append(f"Nonfactual note cannot assert a factual conflict: {identifier}")
    for source in sources:
        if source.source == "notes" and covered.get(source.id, "") != source.text:
            errors.append(f"Incomplete or duplicated claim coverage: {source.id}")
    return errors


def claim_ids(comparison: Comparison) -> list[str]:
    counts: dict[str, int] = {}
    result: list[str] = []
    for claim in comparison.claims:
        identifier = claim.note.source_id
        counts[identifier] = counts.get(identifier, 0) + 1
        result.append(f"{identifier}.C{counts[identifier]}")
    return result
