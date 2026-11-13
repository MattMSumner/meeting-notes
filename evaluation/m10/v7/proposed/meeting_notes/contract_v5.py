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
    commitment_id: str = Field(description="Transcript source ID, never task prose or a date")
    timing: Timing | None
    timing_context: list[str] = Field(
        description="Other transcript IDs clarifying timing; omit the commitment itself"
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
    notes_context: list[SupportedText]
    conflicts: list[Dispute]


def request_schema(transcript_ids: list[str], notes_ids: list[str]) -> dict[str, Any]:
    """Restrict references to this request's sources, without certifying their meaning."""
    if not transcript_ids:
        raise ValueError("No transcript sources available")
    schema = Draft.model_json_schema()
    definitions = schema["$defs"]
    definitions["Action"]["properties"]["commitment_id"]["enum"] = transcript_ids
    definitions["Action"]["properties"]["timing_context"]["items"]["enum"] = transcript_ids
    definitions["Timing"]["properties"]["source_id"]["enum"] = transcript_ids
    definitions["SupportedText"]["properties"]["sources"]["items"]["enum"] = (
        transcript_ids + notes_ids
    )
    definitions["Dispute"]["properties"]["transcript"]["items"]["enum"] = transcript_ids
    if notes_ids:
        definitions["Dispute"]["properties"]["notes"]["items"]["enum"] = notes_ids
    else:
        # There is no valid notes reference; disable the containing arrays rather
        # than inventing a sentinel ID or emitting an invalid empty enum.
        schema["properties"]["notes_context"]["maxItems"] = 0
        schema["properties"]["conflicts"]["maxItems"] = 0
        definitions["Dispute"]["properties"]["notes"]["minItems"] = 0
        definitions["Dispute"]["properties"]["notes"]["maxItems"] = 0
    return schema
