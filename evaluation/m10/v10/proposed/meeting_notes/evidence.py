"""Saved model inputs, separate from the model's output schema."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from meeting_notes.audit import (
    Audit,
    ComparisonAudit,
    CompletenessAudit,
    CoverageAudit,
    CurrentAudit,
    ReferenceAudit,
    TaskAudit,
    TimingAudit,
)
from meeting_notes.grounding import Draft, passages, validate
from meeting_notes.meeting import Meeting
from meeting_notes.summary import Summary, SummaryError


def meeting_context(meeting: Meeting) -> str:
    return f"Meeting: {meeting.title}\nDate: {meeting.started_at:%A %Y-%m-%d %H:%M}\n" + (
        f"Others invited: {', '.join(meeting.attendees)}\n" if meeting.attendees else ""
    )


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transcript: str
    context: str
    handwritten_original: str
    handwritten_text: str


class Generation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9] = 1
    summary: Summary
    evidence: Evidence
    audit: (
        Audit
        | CurrentAudit
        | ReferenceAudit
        | TaskAudit
        | CoverageAudit
        | CompletenessAudit
        | ComparisonAudit
        | TimingAudit
        | None
    ) = None

    @model_validator(mode="after")
    def check_audit(self) -> "Generation":
        if self.version == 1:
            if self.audit is not None:
                raise ValueError("A generation audit requires wrapper version 2")
            return self
        audit = self.audit
        if audit is None or audit.selected is None:
            raise ValueError("Version 2 requires a selected, validated attempt")
        if not 0 <= audit.selected < len(audit.attempts):
            raise ValueError("Selected attempt is out of range")
        if self.version == 9:
            from meeting_notes.comparison import Comparison
            from meeting_notes.compiler import passages as current_passages
            from meeting_notes.compiler_comparison import validate as current_validate
            from meeting_notes.contract import Draft as CurrentDraft

            if not isinstance(audit, ComparisonAudit):
                raise ValueError("Version 9 requires grounding-v8")
            if audit.passages != current_passages(
                self.evidence.transcript, self.evidence.handwritten_text
            ):
                raise ValueError("Saved passages differ from the saved evidence")
            comparison = Comparison(claims=[])
            if audit.comparison_selected is not None:
                if not 0 <= audit.comparison_selected < len(audit.comparison_attempts):
                    raise ValueError("Selected comparison is out of range")
                selected = audit.comparison_attempts[audit.comparison_selected]
                if selected.error or selected.blocking or selected.reply is None:
                    raise ValueError("Selected comparison was not publishable")
                comparison = Comparison.model_validate_json(selected.reply)
            elif audit.comparison_attempts or any(s.source == "notes" for s in audit.passages):
                raise ValueError("Comparison coverage incomplete")
            attempt = audit.attempts[audit.selected]
            if attempt.error or attempt.blocking or attempt.reply is None:
                raise ValueError("Selected attempt was not publishable")
            checked = current_validate(
                CurrentDraft.model_validate_json(attempt.reply),
                audit.passages,
                comparison,
                self.evidence.context,
            )
            if checked.summary != self.summary or checked.warnings != attempt.warnings:
                raise ValueError("Saved summary does not match its validated draft")
            return self
        if self.version == 8:
            from meeting_notes.compiler import (
                passages as current_passages,
            )
            from meeting_notes.compiler import (
                validate as current_validate,
            )
            from meeting_notes.contract import Draft as CurrentDraft

            if not isinstance(audit, CompletenessAudit):
                raise ValueError("Version 8 requires grounding-v7")
            if audit.passages != current_passages(
                self.evidence.transcript, self.evidence.handwritten_text
            ):
                raise ValueError("Saved passages differ from the saved evidence")
            attempt = audit.attempts[audit.selected]
            if attempt.error or attempt.blocking or attempt.reply is None:
                raise ValueError("Selected attempt was not publishable")
            checked = current_validate(
                CurrentDraft.model_validate_json(attempt.reply),
                audit.passages,
                self.evidence.context,
            )
            if checked.summary != self.summary or checked.warnings != attempt.warnings:
                raise ValueError("Saved summary does not match its validated draft")
            return self
        if self.version == 7:
            from meeting_notes.compiler_qualifiers import (
                passages as current_passages,
            )
            from meeting_notes.compiler_qualifiers import (
                validate as current_validate,
            )
            from meeting_notes.contract import Draft as CurrentDraft

            if not isinstance(audit, TimingAudit):
                raise ValueError("Version 7 requires grounding-v6")
            if audit.passages != current_passages(
                self.evidence.transcript, self.evidence.handwritten_text
            ):
                raise ValueError("Saved passages differ from the saved evidence")
            attempt = audit.attempts[audit.selected]
            if attempt.error or attempt.blocking or attempt.reply is None:
                raise ValueError("Selected attempt was not publishable")
            checked = current_validate(
                CurrentDraft.model_validate_json(attempt.reply),
                audit.passages,
                self.evidence.context,
            )
            if checked.summary != self.summary or checked.warnings != attempt.warnings:
                raise ValueError("Saved summary does not match its validated draft")
            return self
        if self.version == 6:
            from meeting_notes.compiler_v7 import (
                passages as current_passages,
            )
            from meeting_notes.compiler_v7 import (
                validate as current_validate,
            )
            from meeting_notes.contract import Draft as CurrentDraft

            if not isinstance(audit, CoverageAudit):
                raise ValueError("Version 6 requires grounding-v5")
            if audit.passages != current_passages(
                self.evidence.transcript, self.evidence.handwritten_text
            ):
                raise ValueError("Saved passages differ from the saved evidence")
            attempt = audit.attempts[audit.selected]
            if attempt.error or attempt.blocking or attempt.reply is None:
                raise ValueError("Selected attempt was not publishable")
            checked = current_validate(
                CurrentDraft.model_validate_json(attempt.reply),
                audit.passages,
                self.evidence.context,
            )
            if checked.summary != self.summary or checked.warnings != attempt.warnings:
                raise ValueError("Saved summary does not match its validated draft")
            return self
        if self.version == 5:
            from meeting_notes.compiler_v6 import (
                passages as current_passages,
            )
            from meeting_notes.compiler_v6 import (
                validate as current_validate,
            )
            from meeting_notes.contract_v6 import Draft as CurrentDraft

            if not isinstance(audit, TaskAudit):
                raise ValueError("Version 5 requires grounding-v4")
            if audit.passages != current_passages(
                self.evidence.transcript, self.evidence.handwritten_text
            ):
                raise ValueError("Saved passages differ from the saved evidence")
            attempt = audit.attempts[audit.selected]
            if attempt.error or attempt.blocking or attempt.reply is None:
                raise ValueError("Selected attempt was not publishable")
            checked = current_validate(
                CurrentDraft.model_validate_json(attempt.reply),
                audit.passages,
                self.evidence.context,
            )
            if checked.summary != self.summary or checked.warnings != attempt.warnings:
                raise ValueError("Saved summary does not match its validated draft")
            return self
        if self.version == 4:
            from meeting_notes.compiler_v5 import (
                passages as current_passages,
            )
            from meeting_notes.compiler_v5 import (
                validate as current_validate,
            )
            from meeting_notes.contract_v5 import Draft as CurrentDraft

            if not isinstance(audit, ReferenceAudit):
                raise ValueError("Version 4 requires grounding-v3")
            if audit.passages != current_passages(
                self.evidence.transcript, self.evidence.handwritten_text
            ):
                raise ValueError("Saved passages differ from the saved evidence")
            attempt = audit.attempts[audit.selected]
            if attempt.error or attempt.blocking or attempt.reply is None:
                raise ValueError("Selected attempt was not publishable")
            checked = current_validate(
                CurrentDraft.model_validate_json(attempt.reply),
                audit.passages,
                self.evidence.context,
            )
            if checked.summary != self.summary or checked.warnings != attempt.warnings:
                raise ValueError("Saved summary does not match its validated draft")
            return self
        if self.version == 3:
            from meeting_notes.compiler_v4 import (
                passages as current_passages,
            )
            from meeting_notes.compiler_v4 import (
                validate as current_validate,
            )
            from meeting_notes.contract_v4 import Draft as CurrentDraft

            if not isinstance(audit, CurrentAudit):
                raise ValueError("Version 3 requires grounding-v2")
            if audit.passages != current_passages(
                self.evidence.transcript, self.evidence.handwritten_text
            ):
                raise ValueError("Saved passages differ from the saved evidence")
            attempt = audit.attempts[audit.selected]
            if attempt.error or attempt.blocking or attempt.reply is None:
                raise ValueError("Selected attempt was not publishable")
            checked = current_validate(
                CurrentDraft.model_validate_json(attempt.reply),
                audit.passages,
                self.evidence.context,
            )
            if checked.summary != self.summary or checked.warnings != attempt.warnings:
                raise ValueError("Saved summary does not match its validated draft")
            return self
        if not isinstance(audit, Audit):
            raise ValueError("Version 2 requires grounding-v1")
        if audit.passages != passages(self.evidence.transcript, self.evidence.handwritten_text):
            raise ValueError("Saved passages differ from the saved evidence")
        attempt = audit.attempts[audit.selected]
        if attempt.error or attempt.blocking or attempt.reply is None:
            raise ValueError("Selected attempt was not publishable")
        checked = validate(
            Draft.model_validate_json(attempt.reply), audit.passages, self.evidence.context
        )
        if checked.summary != self.summary or checked.warnings != attempt.warnings:
            raise ValueError("Saved summary does not match its validated draft")
        return self


def snapshot(meeting: Meeting, transcript: str) -> Evidence:
    original = ""
    if meeting.handwritten_path is not None:
        try:
            # read_text translates CRLF; the original must preserve every byte.
            original = meeting.handwritten_path.read_bytes().decode("utf-8")
        except (OSError, UnicodeError) as error:
            raise SummaryError(
                f"Couldn't read handwritten notes at {meeting.handwritten_path} ({error}). "
                "Restore a readable UTF-8 file at that path, then retry enhancement."
            ) from error
    generated = {
        f"# {meeting.title}",
        f"Available after processing: [[{meeting.note_stem}|Summary]] · "
        f"[[{meeting.transcript_stem}|Transcript]]",
    }
    effective = "".join(
        line for line in original.splitlines(keepends=True) if line.rstrip("\r\n") not in generated
    )
    return Evidence(
        transcript=transcript,
        context=meeting_context(meeting),
        handwritten_original=original,
        handwritten_text=effective if effective.strip() else "",
    )
