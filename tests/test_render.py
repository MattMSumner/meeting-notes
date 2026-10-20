from datetime import datetime

import pytest

from meeting_notes.meeting import Meeting
from meeting_notes.merge import Line
from meeting_notes.render import render_transcript, timestamp

MEETING = Meeting.new("Weekly Sync", datetime(2026, 10, 20, 14, 5))


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0, "00:00:00"), (59.9, "00:00:59"), (61, "00:01:01"), (3725.4, "01:02:05")],
)
def test_timestamp(seconds: float, expected: str):
    assert timestamp(seconds) == expected


def test_renders_frontmatter_and_timestamped_lines():
    lines = [Line(0.0, "Me", "Morning."), Line(65.0, "Them", "Let's ship it.")]

    assert render_transcript(MEETING, lines) == (
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
        "**[00:01:05] Them:** Let's ship it.\n"
    )


def test_quotes_titles_safely_in_yaml():
    meeting = Meeting(title="Alex's 1 1, take 2", started_at=datetime(2026, 10, 20, 9, 0))

    assert 'title: "Alex\'s 1 1, take 2"\n' in render_transcript(meeting, [])


def test_says_so_when_no_speech_was_detected():
    assert "_No speech was detected._" in render_transcript(MEETING, [])


def test_renders_warnings_as_obsidian_callouts_before_the_transcript():
    markdown = render_transcript(MEETING, [Line(0.0, "Me", "Hello?")], ["Them was silent."])

    assert markdown.index("> [!warning] Them was silent.") < markdown.index("**[00:00:00] Me:**")
