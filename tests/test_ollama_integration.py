"""The summary prompt against a real local model. Needs Ollama running with the model pulled:

    brew services start ollama && ollama pull qwen3:30b
    uv run pytest -m integration tests/test_ollama_integration.py

The transcript is made up. Real meetings never go in this repo."""

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
