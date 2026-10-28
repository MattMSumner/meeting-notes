"""Two-pass summaries against local Ollama. Only synthetic transcripts belong here.

    uv run pytest -m integration tests/test_ollama_integration.py

Run several times before trusting a prompt change; model results can vary between runs.
"""

import re
from datetime import datetime
from pathlib import Path

import pytest

from meeting_notes.config import Config
from meeting_notes.figures import numbers, verify_details
from meeting_notes.meeting import Meeting
from meeting_notes.ollama import OllamaSummarizer, http_post
from meeting_notes.summary import Summary

pytestmark = pytest.mark.integration
GOLDEN = Path(__file__).parent / "fixtures" / "golden_transcript.txt"
NUMBERS = Path(__file__).parent / "fixtures" / "numbers_transcript.txt"
AVAILABILITY = Path(__file__).parent / "fixtures" / "availability_transcript.txt"


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


def check_golden(
    summary: Summary, person: str = "Dan", absent: str = "Monday", back: str = "Tuesday"
) -> None:
    assert (
        "billing"
        in " ".join(
            [summary.overview, *(detail.subject + " " + detail.quote for detail in summary.details)]
        ).lower()
    )
    assert any("write" in decision.lower() for decision in summary.decisions)
    [priya] = [item for item in summary.action_items if item.owner == "Priya"]
    assert "plan" in priya.task.lower() and "thursday" in (priya.due or "").lower()
    mine = " ".join(item.task.lower() for item in summary.action_items if item.owner == "Sam")
    assert person.lower() in mine and "finance" in mine
    assert any(
        item.owner == "Sam"
        and "planning" in item.task.lower()
        and any(word in item.task.lower() for word in ("rotation", "on-call", "on call"))
        for item in summary.action_items
    ), "Dropped the commitment to raise the on-call rotation at planning"
    assert "Sam" in summary.overview
    # An absence must not become a return or the day of a commitment.
    prose = " ".join(prose_sentences(summary)).lower()
    assert not re.search(rf"\b(?:return(?:s|ing)?|back)\s+(?:on\s+)?{absent.lower()}\b", prose), (
        f"Turned an absence on {absent} into a return on {absent}"
    )
    for item in summary.action_items:
        if person.lower() in item.task.lower():
            assert absent.lower() not in f"{item.task} {item.due}".lower()
            if item.due:
                assert back.lower() in item.due.lower()


def prose_sentences(summary: Summary) -> list[str]:
    return [
        summary.overview,
        *summary.key_points,
        *summary.decisions,
        *(f"{item.owner} {item.task} {item.due or ''}" for item in summary.action_items),
    ]


def check_overview(summary: Summary) -> None:
    assert not list(numbers(summary.overview)), "Detailed quantities belong in source quotes"
    assert not re.search(
        r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        summary.overview.lower(),
    ), "Detailed dates belong in source quotes"


def test_summarizes_the_golden_transcript(golden_summary: Summary):
    check_golden(golden_summary)
    check_overview(golden_summary)
    verify_details(golden_summary.details, GOLDEN.read_text())


def check_availability(summary: Summary, absent: str, back: str) -> None:
    assert any(
        detail.speaker == "Them" and f"out on {absent}" in detail.quote
        for detail in summary.details
    ), "Dropped the availability constraint"
    assert any(
        detail.speaker == "Sam" and f"on {back} when he's back" in detail.quote
        for detail in summary.details
    ), "Dropped the intended start and return context"


def test_quotes_availability_with_its_context(golden_summary: Summary):
    check_availability(golden_summary, "Monday", "Tuesday")


def test_preserves_availability_when_people_and_days_change():
    summary = summarize_fixture(
        AVAILABILITY, Meeting.new("Lighthouse migration", datetime(2026, 10, 20, 10, 0))
    )
    check_golden(summary, "Alex", "Wednesday", "Thursday")
    check_overview(summary)
    verify_details(summary.details, AVAILABILITY.read_text())
    check_availability(summary, "Wednesday", "Thursday")


def check_said_numbers(summary: Summary) -> None:
    sentences = prose_sentences(summary)
    # Nobody priced the retainer. Its price cannot be calculated from total minus build.
    assert not any(has_amount(sentence, 30) for sentence in sentences)
    for sentence in sentences:
        lowered = sentence.lower()
        if has_amount(sentence, 80) and any(
            word in lowered for word in ("total", "all in", "all-in")
        ):
            assert has_amount(sentence, 120)


def has_amount(sentence: str, amount: int) -> bool:
    return any(value in (amount, amount * 1000) for _, value in numbers(sentence))


def test_uses_only_numbers_someone_said(numbers_summary: Summary):
    check_said_numbers(numbers_summary)


def check_number_positions(summary: Summary) -> None:
    # Details carry coverage. Any amount repeated in prose still needs its qualifications.
    sentences = prose_sentences(summary)
    for sentence in sentences:
        if has_amount(sentence, 70):
            lowered = sentence.lower()
            assert not any(word in lowered for word in ("max", "at most", "limit")), sentence
        if has_amount(sentence, 100):
            assert "probably" in sentence.lower(), f"Lost the budget qualification: {sentence}"
    for speaker, amounts in (("Sam", (120, 80)), ("Nadia", (40, 100, 70))):
        for amount in amounts:
            for sentence in sentences:
                if has_amount(sentence, amount):
                    assert speaker in sentence, f"Missing attribution of {amount} to {speaker}"


def test_preserves_the_meaning_of_any_amount_repeated_in_prose(numbers_summary: Summary):
    check_overview(numbers_summary)
    check_number_positions(numbers_summary)


def check_pricing_commitments(summary: Summary) -> None:
    assert "Sam" in summary.overview
    [follow_up] = summary.action_items
    assert follow_up.owner == "Nadia"
    assert "procurement" in follow_up.task.lower()
    assert "this week" in (follow_up.due or "").lower()


def test_keeps_the_pricing_follow_up_with_its_owner(numbers_summary: Summary):
    check_pricing_commitments(numbers_summary)


def check_quoted_details(summary: Summary) -> None:
    verify_details(summary.details, NUMBERS.read_text())
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
            detail.speaker == speaker
            and all(fragment in " ".join(detail.quote.lower().split()) for fragment in fragments)
            for detail in summary.details
        ), f"Missing qualified quote by {speaker}: {fragments}"


def test_quotes_both_sides_details_with_their_scope_and_qualifications(numbers_summary: Summary):
    check_quoted_details(numbers_summary)
