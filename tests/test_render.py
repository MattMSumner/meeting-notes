from datetime import datetime

import pytest

from meeting_notes.meeting import Meeting
from meeting_notes.render import render_transcript, timestamp
from meeting_notes.transcript import Segment

MEETING = Meeting.new("Weekly Sync", datetime(2026, 10, 20, 14, 5))


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0, "00:00:00"), (59.9, "00:00:59"), (61, "00:01:01"), (3725.4, "01:02:05")],
)
def test_timestamp(seconds: float, expected: str):
    assert timestamp(seconds) == expected


def test_renders_frontmatter_and_timestamped_lines():
    segments = [Segment(0.0, 2.0, "Morning."), Segment(65.0, 70.0, "Let's ship it.")]

    assert render_transcript(MEETING, "Me", segments) == (
        "---\n"
        "date: 2026-10-20\n"
        'time: "14:05"\n'
        'title: "Weekly Sync"\n'
        "tags: [meeting, transcript]\n"
        "source: meeting-notes\n"
        "---\n"
        "\n"
        "# Weekly Sync: transcript\n"
        "\n"
        "**[00:00:00] Me:** Morning.\n"
        "\n"
        "**[00:01:05] Me:** Let's ship it.\n"
    )


def test_quotes_titles_safely_in_yaml():
    meeting = Meeting(title="Alex's 1 1, take 2", started_at=datetime(2026, 10, 20, 9, 0))

    assert 'title: "Alex\'s 1 1, take 2"\n' in render_transcript(meeting, "Me", [])


def test_says_so_when_no_speech_was_detected():
    assert "_No speech was detected._" in render_transcript(MEETING, "Me", [])
