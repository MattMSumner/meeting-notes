"""A meeting's summary and the interface any summarization backend implements."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

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


class Figure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speaker: str = Field(
        min_length=1, description="The exact transcript speaker label, not an inferred name"
    )
    subject: str = Field(
        min_length=1, description="A neutral name for what is measured, without interpreting stance"
    )
    quote: str = Field(
        min_length=1,
        description="Complete sentence(s) copied verbatim, including scope and qualifications; "
        "never just the number",
    )

    @field_validator("speaker", "subject", "quote")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class Figures(BaseModel):
    model_config = ConfigDict(extra="forbid")

    figures: list[Figure]


class Narrative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overview: str = Field(description="Two or three sentences: what the meeting was about")
    key_points: list[str]
    decisions: list[str]
    action_items: list[ActionItem]


class Summary(Narrative):
    # Older saved summaries have no evidence section. New extractions must supply it.
    figures: list[Figure] = Field(default_factory=list[Figure])


def parse_response[T: BaseModel](text: str, model: type[T]) -> T:
    """Validates a model reply, raising SummaryError with a readable reason."""
    try:
        return model.model_validate_json(text)
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in e['loc']) or 'reply'}: {e['msg']}"
            for e in error.errors()
        )
        raise SummaryError(
            f"The summary wasn't valid JSON in the expected shape ({problems})"
        ) from None


def parse_summary(text: str) -> Summary:
    return parse_response(text, Summary)


class Summarizer(Protocol):
    def summarize(self, meeting: Meeting, transcript: str) -> Summary: ...
