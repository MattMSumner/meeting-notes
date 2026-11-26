"""V11 transcript-only draft. Comparison owns all written context and conflicts."""

from typing import Any, Literal

from pydantic import Field

from meeting_notes.grounding import Record
from meeting_notes.spans_v11 import Anchor


class SupportedText(Record):
    text: str = Field(min_length=1)
    sources: list[str] = Field(min_length=1)


class Action(Record):
    original_commitment_id: str
    undertaking: Anchor
    context: list[Anchor]
    basis: Literal["explicit", "third-person", "accepted-request", "implied", "coordinated"]
    disposition: Literal["committed", "uncertain"]
    timing: Anchor | None


class TimingUpdate(Record):
    original_commitment_id: str
    evidence: list[Anchor] = Field(min_length=1)


class Draft(Record):
    overview: list[SupportedText]
    key_points: list[SupportedText]
    decisions: list[SupportedText]
    action_items: list[Action]
    timing_updates: list[TimingUpdate]


def request_schema(transcript_ids: list[str], notes_ids: list[str] | None = None) -> dict[str, Any]:
    """Flat T vocabulary in every field; notes_ids is accepted only for call compatibility."""
    if not transcript_ids or len(set(transcript_ids)) != len(transcript_ids):
        raise ValueError("Unique transcript source IDs are required")
    if notes_ids and set(transcript_ids) & set(notes_ids):
        raise ValueError("Transcript and notes IDs must be disjoint")
    schema = Draft.model_json_schema()
    definitions = schema["$defs"]
    definitions["SourceID"] = {"type": "string", "enum": transcript_ids}
    reference = {"$ref": "#/$defs/SourceID"}
    for owner, field in (
        ("Anchor", "source_id"),
        ("Action", "original_commitment_id"),
        ("TimingUpdate", "original_commitment_id"),
    ):
        definitions[owner]["properties"][field] = dict(reference)
    definitions["SupportedText"]["properties"]["sources"]["items"] = dict(reference)
    return schema
