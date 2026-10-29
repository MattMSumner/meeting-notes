"""A meeting's summary and the interface any summarization backend implements."""

from typing import Annotated, Protocol

from pydantic import (
    AfterValidator,
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

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
    subject: str | None = Field(
        default=None,
        min_length=1,
        description="A neutral topic label, without interpreting stance or availability",
    )
    quote: str = Field(
        min_length=1,
        description="Complete sentence(s) copied verbatim, including scope and qualifications; "
        "never just the number",
    )
    start: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @field_validator("speaker", "subject", "quote")
    @classmethod
    def not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("must not be blank")
        return value


class TurnSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_ids: list[str]


def _not_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")
    return value


NonBlank = Annotated[str, Field(min_length=1), AfterValidator(_not_blank)]


class ExtractedDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_ids: list[NonBlank] = Field(min_length=1)
    text: NonBlank = Field(
        description="The agreed choice with its explicit subject and original time scope"
    )


class ExtractedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_ids: list[NonBlank] = Field(min_length=1)
    owner: NonBlank | None = Field(
        description="Name established anywhere in the conversation, including greetings; "
        '"Them" only for an unnamed responsible speaker; null for an unknown responsible person'
    )
    due: NonBlank | None = Field(
        description="Only an explicit deadline for doing this action; "
        "dates of work being discussed are not deadlines for discussing it. "
        "Null when the action itself has no stated deadline."
    )
    task: NonBlank = Field(
        description="Self-contained action starting with a verb; "
        "resolve pronouns and keep conditions"
    )


class Commitments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decisions: list[ExtractedDecision]
    action_items: list[ExtractedAction]


class Overview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overview: NonBlank = Field(
        description="Two or three short sentences naming participants, topics and outcomes; "
        "no amounts, dates or availability details (these are quoted separately)"
    )


class Summary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overview: str
    decisions: list[str]
    action_items: list[ActionItem]
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
