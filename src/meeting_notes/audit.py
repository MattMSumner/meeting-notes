"""Local generation diagnostics, kept outside the model-facing summary schema."""

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from meeting_notes.comparison_v11 import Resolution
from meeting_notes.compiler import Source
from meeting_notes.compiler_v11 import Checked, correction_errors
from meeting_notes.compiler_v11 import Evidence as Compilation
from meeting_notes.grounding import Passage
from meeting_notes.spans_v11 import Snapshot, snapshot


class Attempt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request: dict[str, Any]
    reply: str | None = None
    response: dict[str, Any] | None = None
    error: str | None = None
    blocking: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Audit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validator_version: Literal["grounding-v1"] = "grounding-v1"
    passages: list[Passage] = Field(default_factory=lambda: list[Passage]())
    attempts: list[Attempt] = Field(default_factory=lambda: list[Attempt]())
    selected: int | None = None


class CurrentAudit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validator_version: Literal["grounding-v2"] = "grounding-v2"
    passages: list[Source] = Field(default_factory=lambda: list[Source]())
    attempts: list[Attempt] = Field(default_factory=lambda: list[Attempt]())
    selected: int | None = None


class ReferenceAudit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validator_version: Literal["grounding-v3"] = "grounding-v3"
    passages: list[Source] = Field(default_factory=lambda: list[Source]())
    attempts: list[Attempt] = Field(default_factory=lambda: list[Attempt]())
    selected: int | None = None


class TaskAudit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validator_version: Literal["grounding-v4"] = "grounding-v4"
    passages: list[Source] = Field(default_factory=lambda: list[Source]())
    attempts: list[Attempt] = Field(default_factory=lambda: list[Attempt]())
    selected: int | None = None


class CoverageAudit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validator_version: Literal["grounding-v5"] = "grounding-v5"
    passages: list[Source] = Field(default_factory=lambda: list[Source]())
    attempts: list[Attempt] = Field(default_factory=lambda: list[Attempt]())
    selected: int | None = None


class TimingAudit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validator_version: Literal["grounding-v6"] = "grounding-v6"
    passages: list[Source] = Field(default_factory=lambda: list[Source]())
    attempts: list[Attempt] = Field(default_factory=lambda: list[Attempt]())
    selected: int | None = None


class CompletenessAudit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validator_version: Literal["grounding-v7"] = "grounding-v7"
    passages: list[Source] = Field(default_factory=lambda: list[Source]())
    attempts: list[Attempt] = Field(default_factory=lambda: list[Attempt]())
    selected: int | None = None


class ComparisonAudit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validator_version: Literal["grounding-v8"] = "grounding-v8"
    passages: list[Source] = Field(default_factory=lambda: list[Source]())
    comparison_attempts: list[Attempt] = Field(default_factory=lambda: list[Attempt]())
    comparison_selected: int | None = None
    attempts: list[Attempt] = Field(default_factory=lambda: list[Attempt]())
    selected: int | None = None


class V11Attempt(Attempt):
    resolution: Resolution | None = None
    compilation: Compilation | None = None
    selection_errors: list[str] = Field(default_factory=list)


class V11Audit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validator_version: Literal["grounding-v9"] = "grounding-v9"
    snapshot: Snapshot = Field(default_factory=lambda: snapshot(""))
    context: str = ""
    handwritten_original: str = ""
    comparison_attempts: list[V11Attempt] = Field(default_factory=lambda: list[V11Attempt]())
    comparison_selected: int | None = None
    attempts: list[V11Attempt] = Field(default_factory=lambda: list[V11Attempt]())
    selected: int | None = None

    @property
    def passages(self) -> list[Source]:
        return self.snapshot.sources


def selection_errors(previous: Checked | None, candidate: Checked) -> list[str]:
    """Numbers borrowed from other sources cannot enter spoken prose or a fallback."""
    errors = [
        w
        for w in candidate.warnings
        if w.endswith(("(in notes)", "(elsewhere in transcript)", "(only in metadata)"))
    ]
    if previous is not None:
        errors.extend(
            e for e in correction_errors(previous, candidate) if e not in candidate.blocking
        )
    return list(dict.fromkeys(errors))


def needs_correction(warnings: list[str]) -> bool:
    return any(
        not w.startswith(("Comparison review required", "Commitment review required"))
        for w in warnings
    )


@runtime_checkable
class AuditedSummarizer(Protocol):
    @property
    def audit(
        self,
    ) -> (
        Audit
        | CurrentAudit
        | ReferenceAudit
        | TaskAudit
        | CoverageAudit
        | TimingAudit
        | CompletenessAudit
        | ComparisonAudit
        | V11Audit
    ): ...
