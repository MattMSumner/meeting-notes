"""Markdown output for the Obsidian vault."""

import json

from meeting_notes.meeting import Meeting
from meeting_notes.transcript import Segment


def timestamp(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def _yaml_string(value: str) -> str:
    # A JSON string is a valid YAML string, and handles quotes and colons in titles.
    return json.dumps(value, ensure_ascii=False)


def render_transcript(meeting: Meeting, speaker: str, segments: list[Segment]) -> str:
    lines = [
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
    if not segments:
        lines.append("_No speech was detected._")
    for segment in segments:
        lines.append(f"**[{timestamp(segment.start)}] {speaker}:** {segment.text}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
