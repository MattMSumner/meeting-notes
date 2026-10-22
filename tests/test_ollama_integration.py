"""The summary prompt against a real local model. Needs Ollama running with the model pulled:

    brew services start ollama && ollama pull qwen3:30b
    uv run pytest -m integration tests/test_ollama_integration.py

The transcript is made up. Real meetings never go in this repo."""

import re
from datetime import datetime
from pathlib import Path

import pytest

from meeting_notes.config import Config
from meeting_notes.meeting import Meeting
from meeting_notes.ollama import OllamaSummarizer, http_post

pytestmark = pytest.mark.integration

# Labelled as the summarizer sees it: my lines carry my name (here "Sam").
GOLDEN = Path(__file__).parent / "fixtures" / "golden_transcript.txt"


def test_summarizes_the_golden_transcript():
    config = Config.from_env()
    summarizer = OllamaSummarizer(
        config.summary_model,
        config.num_ctx,
        http_post(config.ollama_url),
        "Sam",
        think=config.summary_think,
    )

    summary = summarizer.summarize(
        Meeting.new("Lighthouse migration", datetime(2026, 10, 20, 10, 0)),
        GOLDEN.read_text(),
    )

    everything = summary.model_dump_json().lower()
    assert "billing" in everything
    # The decision: move writes over rather than add disk.
    assert any("write" in decision.lower() for decision in summary.decisions)
    [priya] = [item for item in summary.action_items if item.owner == "Priya"]
    assert "plan" in priya.task.lower() and "thursday" in (priya.due or "").lower()
    mine = " ".join(item.task.lower() for item in summary.action_items if item.owner == "Sam")
    assert "dan" in mine and "finance" in mine
    # Always by name: never "the user", "the manager", "I"...
    assert "Sam" in summary.overview


# A total, then a target for one part of it, then the other side's numbers: the model has
# merged these into one range ("aiming for $80–90K total"), worked out the part nobody priced
# (120 - 90 = "$30,000 support") and turned "definitely doable" into "the maximum".
NUMBERS = Path(__file__).parent / "fixtures" / "numbers_transcript.txt"


def summarize_numbers() -> list[str]:
    config = Config.from_env()
    summarizer = OllamaSummarizer(
        config.summary_model,
        config.num_ctx,
        http_post(config.ollama_url),
        "Sam",
        think=config.summary_think,
    )
    summary = summarizer.summarize(
        Meeting.new("Scanner project pricing", datetime(2026, 10, 21, 14, 0)),
        NUMBERS.read_text(),
    )
    sentences = [summary.overview, *summary.key_points, *summary.decisions]
    print("\n".join(sentences))
    return sentences


def test_uses_only_numbers_someone_said():
    sentences = summarize_numbers()

    # Nobody said what the retainer costs ("$30,000", "$30k", "$30-40k"; not "130" or "2030").
    assert not re.search(r"(?<![\d,])30(?!\d)", " ".join(sentences))
    for sentence in sentences:
        lowered = sentence.lower()
        # The build target isn't the total.
        if "80" in lowered and ("total" in lowered or "all in" in lowered or "all-in" in lowered):
            assert "120" in lowered


@pytest.mark.xfail(reason="qwen3:30b drops figures and firms up stances; so did qwen3:32b")
def test_reports_each_sides_numbers_in_their_own_words():
    sentences = summarize_numbers()

    everything = " ".join(sentences).lower()
    # Sam's total and build target; Nadia's too low, too high and doable.
    for number in ("120", "80", "40", "100", "70"):
        assert number in everything
    for sentence in sentences:
        # "Definitely doable" isn't a ceiling.
        if "70" in sentence:
            lowered = sentence.lower()
            assert "max" not in lowered and "at most" not in lowered and "limit" not in lowered
