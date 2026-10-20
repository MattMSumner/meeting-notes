"""OllamaSummarizer against a fake Ollama API."""

import json
from datetime import datetime
from typing import Any

import pytest

from meeting_notes.meeting import Meeting
from meeting_notes.ollama import OllamaError, OllamaSummarizer, default_prompt
from meeting_notes.summary import SummaryError

MEETING = Meeting.new("Weekly Sync", datetime(2026, 10, 20, 14, 5))
GOOD = json.dumps(
    {"overview": "Planned the release.", "key_points": [], "decisions": [], "action_items": []}
)


class FakeOllama:
    """Replies to /api/chat with each canned message content in turn."""

    def __init__(self, *replies: str, prompt_eval_count: int = 1000, done_reason: str = "stop"):
        self.replies = list(replies)
        self.prompt_eval_count = prompt_eval_count
        self.done_reason = done_reason
        self.requests: list[dict[str, Any]] = []

    def __call__(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        assert path == "/api/chat"
        self.requests.append(body)
        return {
            "message": {"role": "assistant", "content": self.replies.pop(0)},
            "done_reason": self.done_reason,
            "prompt_eval_count": self.prompt_eval_count,
            "eval_count": 200,
        }


def summarizer(ollama: FakeOllama, num_ctx: int = 32768) -> OllamaSummarizer:
    return OllamaSummarizer("qwen3:30b", num_ctx, ollama, "Sam", prompt="Summarize for {name}.")


def test_sends_the_transcript_with_an_explicit_context_size_and_schema():
    ollama = FakeOllama(GOOD)

    summary = summarizer(ollama).summarize(MEETING, "[00:00:00] Me: Hi.")

    assert summary.overview == "Planned the release."
    [request] = ollama.requests
    assert request["model"] == "qwen3:30b"
    assert request["options"]["num_ctx"] == 32768
    assert request["stream"] is False
    assert request["think"] is True
    assert request["format"]["required"] == ["overview", "key_points", "decisions", "action_items"]
    system, user = request["messages"]
    assert system == {"role": "system", "content": "Summarize for Sam."}
    assert "Meeting: Weekly Sync" in user["content"]
    assert user["content"].endswith("[00:00:00] Me: Hi.")


def test_retries_once_after_a_malformed_reply_saying_what_was_wrong():
    ollama = FakeOllama("not json", GOOD)

    summary = summarizer(ollama).summarize(MEETING, "transcript")

    assert summary.overview == "Planned the release."
    retry = ollama.requests[1]["messages"]
    assert retry[2] == {"role": "assistant", "content": "not json"}
    assert "Invalid JSON" in retry[3]["content"]


def test_gives_a_readable_error_after_two_malformed_replies():
    ollama = FakeOllama("not json", "still not json")

    with pytest.raises(SummaryError, match="wasn't valid JSON"):
        summarizer(ollama).summarize(MEETING, "transcript")
    assert len(ollama.requests) == 2


def test_refuses_a_transcript_too_long_for_the_context_without_sending_it():
    ollama = FakeOllama(GOOD)

    with pytest.raises(OllamaError, match="MEETING_NOTES_NUM_CTX to at least"):
        summarizer(ollama, num_ctx=8192).summarize(MEETING, "word " * 4000)
    assert ollama.requests == []


def test_fails_when_the_reply_was_cut_off():
    ollama = FakeOllama(GOOD, done_reason="length")

    with pytest.raises(OllamaError, match="ran out of context"):
        summarizer(ollama).summarize(MEETING, "transcript")


def test_a_reply_without_a_message_is_a_readable_error():
    def post(path: str, body: dict[str, Any]) -> dict[str, Any]:
        return {"error": "something odd"}

    with pytest.raises(OllamaError, match="no message"):
        OllamaSummarizer("m", 32768, post, "Sam", prompt="p").summarize(MEETING, "transcript")


def test_the_default_prompt_ships_with_the_package():
    assert '"action_items"' in default_prompt()
    assert "{name}" in default_prompt()
