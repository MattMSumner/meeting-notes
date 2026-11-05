"""Local generation diagnostics, kept outside the model-facing summary schema."""

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from meeting_notes.compiler import Source
from meeting_notes.grounding import Passage


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


@runtime_checkable
class AuditedSummarizer(Protocol):
    @property
    def audit(self) -> Audit | CurrentAudit | ReferenceAudit: ...
