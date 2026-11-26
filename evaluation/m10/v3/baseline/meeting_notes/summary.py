"""A meeting's summary and the interface any summarization backend implements."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from meeting_notes.meeting import Meeting


class SummaryError(Exception):
    pass


class ActionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner: str | None = Field(
        description='Who will do it: a name, "Them" if no name was given, or null if unclear'
    )
    task: str
    due: str | None = Field(description="When it's due, only if the transcript says")


class Summary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overview: str = Field(description="Two or three sentences: what the meeting was about")
    key_points: list[str]
    decisions: list[str]
    action_items: list[ActionItem]


def parse_summary(text: str) -> Summary:
    """Validates a model's JSON reply, raising SummaryError with a readable reason."""
    try:
        return Summary.model_validate_json(text)
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in e['loc']) or 'reply'}: {e['msg']}"
            for e in error.errors()
        )
        raise SummaryError(
            f"The summary wasn't valid JSON in the expected shape ({problems})"
        ) from None


class Summarizer(Protocol):
    def summarize(self, meeting: Meeting, transcript: str) -> Summary: ...
