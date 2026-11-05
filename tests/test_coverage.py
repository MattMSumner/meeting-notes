import pytest

from meeting_notes.compiler import passages
from meeting_notes.coverage import uncovered_commitments


@pytest.mark.parametrize(
    "text",
    [
        "I will review it next week.",
        "I'll send the draft Friday.",
        "I am going to check recovery.",
        "I’ll test recovery.",
    ],
)
def test_explicit_task_is_flagged_only_when_missing(text: str):
    sources = passages("[00:00:00] Alex: " + text, "I will send the venue request.")
    assert [s.id for s in uncovered_commitments(sources, set())] == ["T1"]
    assert uncovered_commitments(sources, {"T1"}) == []


@pytest.mark.parametrize(
    "text",
    [
        "Maybe I will review it.",
        "I will not review it.",
        "I won't review it.",
        "If needed, I will review it.",
        "I will review it if approved.",
        "I will review it?",
        "“I will review it.”",
        "Alex said I will review it.",
        "For example, I will review it.",
        "I will be away next week.",
        "I will miss the meeting.",
        "I will review it. I am not committing to it yet.",
        "I will review it. Scratch that.",
        "This is just an example. I will review it.",
    ],
)
def test_uncertain_negated_quoted_and_non_task_speech_is_not_flagged(text: str):
    assert not uncovered_commitments(passages("[00:00:00] Sam: " + text, ""), set())


def test_other_speaker_disclaimer_does_not_erase_explicit_task():
    sources = passages(
        "[00:00:00] Sam: I will review it.\n[00:00:03] Alex: I am not committing to it yet.",
        "",
    )
    assert [s.id for s in uncovered_commitments(sources, set())] == ["T1"]


def test_diagnostic_does_not_claim_to_cover_paraphrases():
    assert not uncovered_commitments(passages("[00:00:00] Sam: Leave the review to me.", ""), set())
