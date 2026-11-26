"""Direct source references for model drafts."""

from typing import Any

from pydantic import Field

from meeting_notes.grounding import Record


class SupportedText(Record):
    text: str
    sources: list[str] = Field(min_length=1)


class Timing(Record):
    source_id: str = Field(description="Transcript source ID containing the exact timing quote")
    quote: str = Field(min_length=1, description="Exact timing phrase from source_id")


class Action(Record):
    original_commitment_id: str = Field(
        description="Transcript ID of the original task, never a later timing correction"
    )
    timing: Timing | None


class TimingUpdate(Record):
    original_commitment_id: str = Field(
        description="ID of an existing original action being updated"
    )
    source_ids: list[str] = Field(
        min_length=1,
        description="Later transcript statements clarifying or revising that action's timing",
    )


class Dispute(Record):
    topic: str
    transcript: list[str] = Field(min_length=1)
    notes: list[str] = Field(min_length=1)


class Draft(Record):
    overview: list[SupportedText]
    key_points: list[SupportedText]
    decisions: list[SupportedText]
    action_items: list[Action]
    timing_updates: list[TimingUpdate]
    notes_context: list[SupportedText]
    conflicts: list[Dispute]


def request_schema(transcript_ids: list[str], notes_ids: list[str]) -> dict[str, Any]:
    """Restrict references to this request's sources, without certifying their meaning."""
    if not transcript_ids:
        raise ValueError("No transcript sources available")
    schema = Draft.model_json_schema()
    definitions = schema["$defs"]
    # One flat vocabulary avoids nested reference unions in the model grammar.
    # Source kind is checked by the compiler, including every correction response.
    definitions["SourceID"] = {"type": "string", "enum": transcript_ids + notes_ids}
    reference = {"$ref": "#/$defs/SourceID"}
    for owner, field in [
        ("Action", "original_commitment_id"),
        ("TimingUpdate", "original_commitment_id"),
        ("Timing", "source_id"),
    ]:
        definitions[owner]["properties"][field] = dict(reference)
    for owner, field in [
        ("TimingUpdate", "source_ids"),
        ("Dispute", "transcript"),
        ("Dispute", "notes"),
        ("SupportedText", "sources"),
    ]:
        definitions[owner]["properties"][field]["items"] = dict(reference)
    if not notes_ids:
        # There is no valid notes reference; disable the containing arrays rather
        # than inventing a sentinel ID or emitting an invalid empty enum.
        schema["properties"]["notes_context"]["maxItems"] = 0
        schema["properties"]["conflicts"]["maxItems"] = 0
        definitions["Dispute"]["properties"]["notes"]["minItems"] = 0
        definitions["Dispute"]["properties"]["notes"]["maxItems"] = 0
    return schema
