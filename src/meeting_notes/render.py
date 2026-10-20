"""Markdown output for the Obsidian vault."""

import json
from collections.abc import Sequence

from meeting_notes.meeting import Meeting
from meeting_notes.merge import Line


def timestamp(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def _yaml_string(value: str) -> str:
    # A JSON string is a valid YAML string, and handles quotes and colons in titles.
    return json.dumps(value, ensure_ascii=False)


def render_transcript(meeting: Meeting, lines: Sequence[Line], warnings: Sequence[str] = ()) -> str:
    out = [
        "---",
        f"date: {meeting.started_at:%Y-%m-%d}",
        f'time: "{meeting.started_at:%H:%M}"',
        f"title: {_yaml_string(meeting.title)}",
        "tags: [meeting, transcript]",
        "source: meeting-notes",
        "---",
        "",
        f"# {meeting.title}: transcript",
        "",
    ]
    for warning in warnings:
        out += [f"> [!warning] {warning}", ""]
    if not lines:
        out.append("_No speech was detected._")
    for line in lines:
        out += [f"**[{timestamp(line.start)}] {line.speaker}:** {line.text}", ""]
    return "\n".join(out).rstrip() + "\n"
