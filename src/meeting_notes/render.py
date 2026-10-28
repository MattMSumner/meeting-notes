"""Markdown output for the Obsidian vault."""

import json
from collections.abc import Sequence

from meeting_notes.meeting import Meeting
from meeting_notes.merge import Line
from meeting_notes.summary import ActionItem, Summary


def timestamp(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def _yaml_string(value: str) -> str:
    # A JSON string is a valid YAML string, and handles quotes and colons in titles.
    return json.dumps(value, ensure_ascii=False)


def _frontmatter(meeting: Meeting, tags: str) -> list[str]:
    attendees = (
        [f"attendees: [{', '.join(_yaml_string(name) for name in meeting.attendees)}]"]
        if meeting.attendees
        else []
    )
    return [
        "---",
        f"date: {meeting.started_at:%Y-%m-%d}",
        f'time: "{meeting.started_at:%H:%M}"',
        f"title: {_yaml_string(meeting.title)}",
        *attendees,
        f"tags: [{tags}]",
        "source: meeting-notes",
        "---",
        "",
    ]


def _callouts(warnings: Sequence[str]) -> list[str]:
    out: list[str] = []
    for warning in warnings:
        out += [f"> [!warning] {warning}", ""]
    return out


def _line_text(line: Line) -> str:
    parts: list[str] = []
    position = 0
    for aside in line.asides:
        parts.append(line.text[position : aside.position])
        parts.append(f" *([{timestamp(aside.start)}] {aside.speaker}: {aside.text})*")
        position = aside.position
    parts.append(line.text[position:])
    return "".join(parts)


def render_transcript(meeting: Meeting, lines: Sequence[Line], warnings: Sequence[str] = ()) -> str:
    out = [
        *_frontmatter(meeting, "meeting, transcript"),
        f"# {meeting.title}: transcript",
        "",
        f"Note: [[{meeting.note_stem}]]",
        "",
        *_callouts(warnings),
    ]
    if not lines:
        out.append("_No speech was detected._")
    speaker = None
    for line in lines:
        # A paragraph continuing the same speaker's turn doesn't repeat their name.
        who = "" if line.speaker == speaker else f" {line.speaker}:"
        speaker = line.speaker
        out += [f"**[{timestamp(line.start)}]{who}** {_line_text(line)}", ""]
    return "\n".join(out).rstrip() + "\n"


def _action_item(item: ActionItem) -> str:
    text = f"**{item.owner}**: {item.task}" if item.owner else item.task
    return f"- [ ] {text}" + (f" (due {item.due})" if item.due else "")


def _bullets(items: Sequence[str]) -> list[str]:
    return [f"- {item}" for item in items] or ["_None._"]


def render_note(
    meeting: Meeting,
    summary: Summary | None,
    meeting_id: str,
    has_speech: bool = True,
    warnings: Sequence[str] = (),
) -> str:
    """The meeting's note: summary, decisions and action items, linking to the transcript."""
    out = [*_frontmatter(meeting, "meeting"), f"# {meeting.title}", "", *_callouts(warnings)]
    if summary is None:
        if has_speech:
            out += [
                f"> [!note] No summary yet. To write one: `notes summarize {meeting_id}`",
                "",
            ]
        else:
            out += ["_No speech was detected._", ""]
    else:
        out += ["## Summary", "", summary.overview, ""]
        if summary.key_points:
            out += [*_bullets(summary.key_points), ""]
        if summary.details:
            out += ["## Details", ""]
            # A correction can repeat an already-valid detail; show it only once.
            details = dict.fromkeys(
                (detail.speaker, detail.subject, " ".join(detail.quote.split()))
                for detail in summary.details
            )
            out += [
                f"- **{speaker} — {subject}:** “{quote}”" for speaker, subject, quote in details
            ]
            out.append("")
        out += ["## Decisions", "", *_bullets(summary.decisions), ""]
        actions = [_action_item(item) for item in summary.action_items] or ["_None._"]
        out += ["## Action items", "", *actions, ""]
    out.append(f"Transcript: [[{meeting.transcript_stem}]]")
    return "\n".join(out) + "\n"
