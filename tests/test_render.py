from datetime import datetime

import pytest

from meeting_notes.meeting import Meeting
from meeting_notes.merge import Aside, Line
from meeting_notes.render import render_note, render_transcript, timestamp
from meeting_notes.summary import ActionItem, Figure, Summary

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
        "Note: [[2026-10-20_Weekly Sync_1405]]\n"
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


SUMMARY = Summary(
    overview="Planned the release.",
    key_points=["Tests pass.", "Docs need a pass."],
    decisions=["Ship on Friday."],
    action_items=[
        ActionItem(owner="Me", task="Tag the release", due="Friday"),
        ActionItem(owner=None, task="Update the docs", due=None),
    ],
)


def test_renders_the_note_with_summary_decisions_and_action_items():
    assert render_note(MEETING, SUMMARY, "id") == (
        "---\n"
        "date: 2026-10-20\n"
        'time: "14:05"\n'
        'title: "Weekly Sync"\n'
        "tags: [meeting]\n"
        "source: meeting-notes\n"
        "---\n"
        "\n"
        "# Weekly Sync\n"
        "\n"
        "## Summary\n"
        "\n"
        "Planned the release.\n"
        "\n"
        "- Tests pass.\n"
        "- Docs need a pass.\n"
        "\n"
        "## Decisions\n"
        "\n"
        "- Ship on Friday.\n"
        "\n"
        "## Action items\n"
        "\n"
        "- [ ] **Me**: Tag the release (due Friday)\n"
        "- [ ] Update the docs\n"
        "\n"
        "Transcript: [[2026-10-20_Weekly Sync_1405_transcript]]\n"
    )


def test_note_says_none_for_empty_sections():
    empty = Summary(overview="Catch-up.", key_points=[], decisions=[], action_items=[])

    note = render_note(MEETING, empty, "id")

    assert "## Decisions\n\n_None._\n" in note
    assert "## Action items\n\n_None._\n" in note
    assert "## Figures" not in note


def test_renders_verified_figures_between_the_summary_and_decisions():
    summary = SUMMARY.model_copy(
        update={
            "figures": [
                Figure(
                    speaker="Them",
                    subject="Build budget",
                    quote="Seventy for the build is definitely doable.",
                ),
            ]
        }
    )

    note = render_note(MEETING, summary, "id")

    assert (
        "## Figures\n\n- **Them — Build budget:** “Seventy for the build is definitely doable.”\n\n"
        in note
    )
    assert note.index("## Summary") < note.index("## Figures") < note.index("## Decisions")


def test_shows_duplicate_figures_once_without_losing_distinct_subjects():
    quote = "There's no travel budget, and we pay on net ninety terms."
    travel = Figure(speaker="Them", subject="Travel budget", quote=quote)
    terms = Figure(speaker="Them", subject="Payment terms", quote=quote)
    summary = SUMMARY.model_copy(update={"figures": [travel, travel, terms]})

    note = render_note(MEETING, summary, "id")

    assert note.count("**Them — Travel budget:**") == 1
    assert note.count("**Them — Payment terms:**") == 1
    assert len(summary.figures) == 3


def test_note_without_a_summary_says_how_to_write_one():
    note = render_note(MEETING, None, "2026-10-20-1405-weekly-sync")

    assert "`notes summarize 2026-10-20-1405-weekly-sync`" in note
    assert "Transcript: [[" in note


def test_note_carries_the_recording_warnings():
    assert "> [!warning] Them was silent." in render_note(
        MEETING, SUMMARY, "id", True, ["Them was silent."]
    )


def test_a_paragraph_continuing_a_turn_does_not_repeat_the_speaker():
    lines = [Line(0.0, "Me", "First."), Line(40.0, "Me", "Second."), Line(50.0, "Them", "Yes.")]

    assert render_transcript(MEETING, lines).endswith(
        "**[00:00:00] Me:** First.\n\n**[00:00:40]** Second.\n\n**[00:00:50] Them:** Yes.\n"
    )


def test_renders_asides_inline_with_their_own_speaker_and_time():
    lines = [
        Line(
            0.0,
            "Me",
            "First. Second. Third.",
            (
                Aside(6, 1.0, "Them", "Yeah."),
                Aside(14, 21.0, "Them", "Okay."),
            ),
        ),
        Line(40.0, "Me", "Fourth.", (Aside(7, 42.0, "Them", "Right."),)),
        Line(50.0, "Them", "Next point."),
    ]

    assert render_transcript(MEETING, lines).endswith(
        "**[00:00:00] Me:** First. *([00:00:01] Them: Yeah.)* "
        "Second. *([00:00:21] Them: Okay.)* Third.\n\n"
        "**[00:00:40]** Fourth. *([00:00:42] Them: Right.)*\n\n"
        "**[00:00:50] Them:** Next point.\n"
    )
