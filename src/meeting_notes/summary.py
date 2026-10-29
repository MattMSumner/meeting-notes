"""A meeting's summary and the interface any summarization backend implements."""

from typing import Annotated, Literal, Protocol, Self

from pydantic import (
    AfterValidator,
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
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


class TimingEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_id: NonBlank
    quote: NonBlank = Field(
        description="Verbatim source clause identifying the event being timed, not just a date"
    )
    value: NonBlank = Field(
        description="The time phrase copied from that quote, without calculation"
    )


class ExtractedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    commitment_turn_ids: list[NonBlank] = Field(min_length=1)
    request_turn_ids: list[NonBlank] = Field(
        description="The original request for an accepted_request; empty for other kinds"
    )
    context_turn_ids: list[NonBlank]
    kind: Literal["promise", "accepted_request", "reported_commitment"] = Field(
        description="Use accepted_request when request_turn_ids is nonempty, "
        "even for 'I'll' replies"
    )
    owner: NonBlank | None = Field(
        description="Name established anywhere in the conversation, including greetings; "
        '"Them" only for an unnamed responsible speaker; null for an unknown responsible person'
    )
    task: NonBlank = Field(
        description="Self-contained action starting with a verb; "
        "resolve pronouns and keep conditions"
    )
    related_timing: list[TimingEvidence] = Field(
        description="Dates for other activities discussed in task or someone's availability; "
        "exclude the schedule for executing task's main verb"
    )
    action_timing: TimingEvidence | None = Field(
        description="Explicit schedule for executing task's main verb; otherwise null. "
        "Timing of an activity being discussed does not schedule discussing it."
    )

    @model_validator(mode="after")
    def check_request(self) -> Self:
        if self.kind == "accepted_request" and not self.request_turn_ids:
            raise ValueError(
                "accepted_request needs request_turn_ids as well as acceptance evidence"
            )
        if self.kind != "accepted_request" and self.request_turn_ids:
            raise ValueError(
                "An item with request_turn_ids must have kind accepted_request; "
                "retain the original request and its acceptance"
            )
        return self


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
