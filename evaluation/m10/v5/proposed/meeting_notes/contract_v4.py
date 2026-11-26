"""Direct source references for model drafts."""

from pydantic import Field

from meeting_notes.grounding import Record


class SupportedText(Record):
    text: str
    sources: list[str] = Field(min_length=1)


class Action(Record):
    commitment: str
    timing: str | None
    timing_context: list[str]


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
