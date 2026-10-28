"""Two-pass summaries against local Ollama. Only synthetic transcripts belong here.

    uv run pytest -m integration tests/test_ollama_integration.py

Run several times before trusting a prompt change; model results can vary between runs.
"""

import re
from datetime import datetime
from pathlib import Path

import pytest

from meeting_notes.config import Config
from meeting_notes.figures import verify_figures
from meeting_notes.meeting import Meeting
from meeting_notes.ollama import OllamaSummarizer, http_post
from meeting_notes.summary import Summary

pytestmark = pytest.mark.integration
GOLDEN = Path(__file__).parent / "fixtures" / "golden_transcript.txt"
NUMBERS = Path(__file__).parent / "fixtures" / "numbers_transcript.txt"


def summarize_fixture(path: Path, meeting: Meeting) -> Summary:
    config = Config.from_env()
    return OllamaSummarizer(
        config.summary_model,
        config.num_ctx,
        http_post(config.ollama_url),
        "Sam",
        think=config.summary_think,
    ).summarize(meeting, path.read_text())


@pytest.fixture(scope="module")
def golden_summary() -> Summary:
    return summarize_fixture(
        GOLDEN,
        Meeting.new("Lighthouse migration", datetime(2026, 10, 20, 10, 0)),
    )


@pytest.fixture(scope="module")
def numbers_summary() -> Summary:
    # All assertions in a run inspect the same result, including any model corrections.
    return summarize_fixture(
        NUMBERS,
        Meeting.new("Scanner project pricing", datetime(2026, 10, 21, 14, 0)),
    )


def check_golden(summary: Summary) -> None:
    assert "billing" in " ".join([summary.overview, *summary.key_points]).lower()
    assert any("write" in decision.lower() for decision in summary.decisions)
    [priya] = [item for item in summary.action_items if item.owner == "Priya"]
    assert "plan" in priya.task.lower() and "thursday" in (priya.due or "").lower()
    mine = " ".join(item.task.lower() for item in summary.action_items if item.owner == "Sam")
    assert "dan" in mine and "finance" in mine
    assert "Sam" in summary.overview
    # Dan is out on Monday; quoting that correctly must not become a Monday return.
    prose = " ".join([summary.overview, *summary.key_points, *summary.decisions]).lower()
    assert not re.search(r"\b(?:return(?:s|ing)?|back)\s+(?:on\s+)?monday\b", prose), (
        "Turned an absence on Monday into a return on Monday"
    )


def test_summarizes_the_golden_transcript(golden_summary: Summary):
    check_golden(golden_summary)
    verify_figures(golden_summary.figures, GOLDEN.read_text())


def check_said_numbers(summary: Summary) -> None:
    sentences = [summary.overview, *summary.key_points, *summary.decisions]
    # Nobody priced the retainer. Its price cannot be calculated from total minus build.
    assert not re.search(r"(?<![\d,])30(?!\d)", " ".join(sentences))
    for sentence in sentences:
        lowered = sentence.lower()
        if "80" in lowered and any(word in lowered for word in ("total", "all in", "all-in")):
            assert "120" in lowered


def test_uses_only_numbers_someone_said(numbers_summary: Summary):
    check_said_numbers(numbers_summary)


def check_number_positions(summary: Summary) -> None:
    # Check prose separately: displaying the quotes must not hide poor summarization.
    sentences = [summary.overview, *summary.key_points, *summary.decisions]
    everything = " ".join(sentences).lower()
    for number in ("120", "80", "90", "40", "100", "70"):
        assert number in everything, f"Dropped {number} from the narrative"
    for sentence in sentences:
        if "70" in sentence:
            lowered = sentence.lower()
            assert not any(word in lowered for word in ("max", "at most", "limit")), sentence
        if "100" in sentence:
            assert "probably" in sentence.lower(), f"Lost the budget qualification: {sentence}"
    for speaker, amounts in (("Sam", ("120", "80")), ("Nadia", ("40", "100", "70"))):
        for amount in amounts:
            assert any(speaker in sentence and amount in sentence for sentence in sentences), (
                f"Missing attribution of {amount} to {speaker}"
            )


@pytest.mark.xfail(reason="Remove only after five successful two-pass evaluations")
def test_reports_each_sides_numbers_in_their_own_words(numbers_summary: Summary):
    check_number_positions(numbers_summary)


def check_quoted_figures(summary: Summary) -> None:
    verify_figures(summary.figures, NUMBERS.read_text())
    expected = [
        ("Sam", ("whole engagement", "all in", "thinking about a hundred and twenty thousand")),
        ("Sam", ("build itself", "eighty to ninety thousand", "aiming for")),
        ("Them", ("forty thousand", "too low")),
        ("Them", ("a hundred plus", "probably more than we can do")),
        ("Them", ("seventy for the build", "definitely doable")),
        ("Them", ("net ninety", "can't change")),
        ("Them", ("no travel budget",)),
    ]
    for speaker, fragments in expected:
        assert any(
            figure.speaker == speaker
            and all(fragment in " ".join(figure.quote.lower().split()) for fragment in fragments)
            for figure in summary.figures
        ), f"Missing qualified quote by {speaker}: {fragments}"


def test_quotes_both_sides_figures_with_their_scope_and_qualifications(numbers_summary: Summary):
    check_quoted_figures(numbers_summary)
