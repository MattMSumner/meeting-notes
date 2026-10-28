"""A meeting's summary and the interface any summarization backend implements."""

from typing import Protocol

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError, field_validator

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


class Detail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speaker: str = Field(
        min_length=1, description="The exact transcript speaker label, not an inferred name"
    )
    subject: str = Field(
        min_length=1,
        description="A neutral topic label, without interpreting stance or availability",
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


class Details(BaseModel):
    model_config = ConfigDict(extra="forbid")

    details: list[Detail]


class Narrative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overview: str = Field(
        description="Two or three short sentences naming participants, topics and outcomes; "
        "no amounts, dates or availability details (these are quoted separately)"
    )
    decisions: list[str]
    action_items: list[ActionItem]


class Summary(Narrative):
    # Kept for notes saved before detailed facts were rendered as source quotes.
    key_points: list[str] = Field(default_factory=list[str])
    # Older saved summaries have no evidence section. New extractions must supply it.
    details: list[Detail] = Field(
        default_factory=list[Detail], validation_alias=AliasChoices("details", "figures")
    )


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
