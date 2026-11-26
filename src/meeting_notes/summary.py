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
    review: list[str] = Field(default_factory=list)
    due: str | None = Field(
        description="Complete spoken timing phrase, including every alternative, condition "
        "and uncertainty. Must stand on its own even if task repeats the timing. "
        "Preserve relative wording; null when no timing was spoken."
    )


class Conflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str
    transcript: str = Field(description="The spoken account, preserving uncertainty")
    handwritten: str = Field(description="The handwritten account, preserving uncertainty")


class Summary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overview: str = Field(
        description="Two or three sentences about the meeting. Describe disputed topics as "
        "unresolved and refer to Conflicts; do not repeat a disputed value as settled."
    )
    key_points: list[str] = Field(
        description="Important spoken points. For disputed topics, state that the sources "
        "disagree and refer to Conflicts instead of repeating one disputed value as fact."
    )
    decisions: list[str]
    action_items: list[ActionItem]
    notes_context: list[str] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=lambda: list[Conflict]())


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
    def summarize(
        self, meeting: Meeting, transcript: str, *, handwritten_text: str = ""
    ) -> Summary: ...
