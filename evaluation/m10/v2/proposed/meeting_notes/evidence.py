"""Saved model inputs, separate from the model's output schema."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

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

    version: Literal[1] = 1
    summary: Summary
    evidence: Evidence


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
