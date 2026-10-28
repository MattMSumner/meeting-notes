"""OllamaSummarizer against a fake Ollama API."""

import json
from datetime import datetime
from typing import Any

import pytest

from meeting_notes.meeting import Meeting
from meeting_notes.ollama import (
    OllamaError,
    OllamaSummarizer,
    default_figures_prompt,
    default_prompt,
)
from meeting_notes.summary import SummaryError

MEETING = Meeting.new("Weekly Sync", datetime(2026, 10, 20, 14, 5))
GOOD = json.dumps(
    {"overview": "Planned the release.", "key_points": [], "decisions": [], "action_items": []}
)
EMPTY_FIGURES = '{"figures": []}'


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
    return OllamaSummarizer(
        "qwen3:30b",
        num_ctx,
        ollama,
        "Sam",
        prompt="Summarize for {name}.",
        figures_prompt="Extract for {name}.",
    )


def test_sends_the_transcript_with_an_explicit_context_size_and_schema():
    ollama = FakeOllama(EMPTY_FIGURES, GOOD)

    summary = summarizer(ollama).summarize(MEETING, "[00:00:00] Me: Hi.")

    assert summary.overview == "Planned the release."
    extraction, request = ollama.requests
    assert extraction["format"]["required"] == ["figures"]
    assert extraction["messages"][0]["content"] == "Extract for Sam."
    assert extraction["messages"][1]["content"].endswith("[00:00:00] Me: Hi.")
    assert request["model"] == "qwen3:30b"
    assert request["options"]["num_ctx"] == 32768
    assert request["stream"] is False
    assert request["think"] is True
    assert request["format"]["required"] == ["overview", "key_points", "decisions", "action_items"]
    system, user = request["messages"]
    assert system == {"role": "system", "content": "Summarize for Sam."}
    assert "Meeting: Weekly Sync" in user["content"]
    assert '[00:00:00] Me: Hi.\n\nVerified figures:\n{"figures":[]}' in user["content"]


def test_retries_once_after_a_malformed_reply_saying_what_was_wrong():
    ollama = FakeOllama(EMPTY_FIGURES, "not json", GOOD)

    summary = summarizer(ollama).summarize(MEETING, "transcript")

    assert summary.overview == "Planned the release."
    retry = ollama.requests[2]["messages"]
    assert retry[2] == {"role": "assistant", "content": "not json"}
    assert "Invalid JSON" in retry[3]["content"]


def test_gives_a_readable_error_after_two_malformed_replies():
    ollama = FakeOllama(EMPTY_FIGURES, "not json", "still not json")

    with pytest.raises(SummaryError, match="wasn't valid JSON"):
        summarizer(ollama).summarize(MEETING, "transcript")
    assert len(ollama.requests) == 3


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
    assert '"figures"' in default_figures_prompt()
    assert "{name}" in default_figures_prompt()


def test_tells_the_model_who_else_was_invited():
    ollama = FakeOllama(EMPTY_FIGURES, GOOD)
    meeting = Meeting.new("Weekly Sync", datetime(2026, 10, 20, 14, 5), ("Alex Doe", "Kim"))

    summarizer(ollama).summarize(meeting, "transcript")

    assert "Others invited: Alex Doe, Kim\n" in ollama.requests[0]["messages"][1]["content"]


def with_key_point(point: str) -> str:
    return json.dumps(
        {
            "overview": "Priced the project.",
            "key_points": [point],
            "decisions": [],
            "action_items": [],
        }
    )


TOTAL_AND_BUILD = "[00:00:15] Sam: A hundred and twenty thousand all in, ninety for the build."


def test_a_summary_with_only_numbers_that_were_said_is_kept():
    ollama = FakeOllama(EMPTY_FIGURES, with_key_point("$120,000 total, $90,000 build."))

    summarizer(ollama).summarize(MEETING, TOTAL_AND_BUILD)

    assert len(ollama.requests) == 2


def test_retries_once_naming_numbers_nobody_said():
    ollama = FakeOllama(
        EMPTY_FIGURES,
        with_key_point("$120,000 total: $90,000 build, $30,000 support."),
        with_key_point("$120,000 total, $90,000 build."),
    )

    summary = summarizer(ollama).summarize(MEETING, TOTAL_AND_BUILD)

    assert summary.key_points == ["$120,000 total, $90,000 build."]
    retry = ollama.requests[2]["messages"]
    assert "Nobody said these numbers: $30,000." in retry[3]["content"]


def test_keeps_the_first_summary_if_the_retry_is_no_better():
    first = with_key_point("$120,000 total: $90,000 build, $30,000 support.")
    ollama = FakeOllama(
        EMPTY_FIGURES, first, with_key_point("$120,000 total: $90,000 build, $35,000 support.")
    )

    summary = summarizer(ollama).summarize(MEETING, TOTAL_AND_BUILD)

    assert summary.key_points == ["$120,000 total: $90,000 build, $30,000 support."]


def test_keeps_the_first_summary_if_the_retry_is_malformed():
    first = with_key_point("$120,000 total: $90,000 build, $30,000 support.")
    ollama = FakeOllama(EMPTY_FIGURES, first, "not json", "still not json")

    summary = summarizer(ollama).summarize(MEETING, TOTAL_AND_BUILD)

    assert summary.key_points == ["$120,000 total: $90,000 build, $30,000 support."]


def quoted(quote: str, speaker: str = "Sam", subject: str = "Total") -> str:
    return json.dumps({"figures": [{"speaker": speaker, "subject": subject, "quote": quote}]})


EVIDENCE = quoted("A hundred and twenty thousand all in, ninety for the build.")


def test_verifies_figures_before_sending_them_to_the_writer():
    bad = quoted("$120,000 total.")
    ollama = FakeOllama(bad, EVIDENCE, GOOD)

    summary = summarizer(ollama).summarize(MEETING, TOTAL_AND_BUILD)

    assert summary.figures[0].quote == "A hundred and twenty thousand all in, ninety for the build."
    first, correction, writing = ollama.requests
    assert first["format"] == correction["format"]
    assert "Couldn't verify quoted figures" in correction["messages"][-1]["content"]
    assert "figures" not in writing["format"]["properties"]
    assert summary.figures[0].quote in writing["messages"][1]["content"]
    assert "$120,000 total." not in writing["messages"][1]["content"]


@pytest.mark.parametrize(
    "reply",
    [
        "not json",
        "{}",
        quoted("Invented."),
        quoted("A hundred and twenty thousand all in, ninety for the build.", "Them"),
    ],
)
def test_failed_extraction_never_calls_the_writer(reply: str):
    ollama = FakeOllama(reply, reply)

    with pytest.raises(SummaryError):
        summarizer(ollama).summarize(MEETING, TOTAL_AND_BUILD)

    assert len(ollama.requests) == 2
    assert all(request["format"]["required"] == ["figures"] for request in ollama.requests)


def test_an_extraction_can_be_corrected_after_a_schema_error():
    ollama = FakeOllama("{}", EMPTY_FIGURES, GOOD)

    assert summarizer(ollama).summarize(MEETING, "transcript").figures == []
    assert "figures: Field required" in ollama.requests[1]["messages"][-1]["content"]


def test_numeric_corrections_reuse_the_verified_figures():
    ollama = FakeOllama(
        EVIDENCE,
        with_key_point("$30,000 support."),
        with_key_point("$120,000 total."),
    )

    summary = summarizer(ollama).summarize(MEETING, TOTAL_AND_BUILD)

    assert summary.figures[0].quote == "A hundred and twenty thousand all in, ninety for the build."
    assert [request["format"]["required"] for request in ollama.requests].count(["figures"]) == 1
    assert summary.figures[0].quote in ollama.requests[-1]["messages"][1]["content"]


def test_the_writer_cannot_replace_verified_evidence():
    replacement = json.loads(GOOD)
    replacement["figures"] = []
    ollama = FakeOllama(EVIDENCE, json.dumps(replacement), GOOD)

    summary = summarizer(ollama).summarize(MEETING, TOTAL_AND_BUILD)

    assert len(summary.figures) == 1
    assert "figures" in ollama.requests[-1]["messages"][-1]["content"]
    assert "Extra inputs" in ollama.requests[-1]["messages"][-1]["content"]


def test_generated_figure_subjects_cannot_authorize_new_numbers():
    ollama = FakeOllama(
        quoted(
            "A hundred and twenty thousand all in, ninety for the build.",
            subject="$30,000 retainer",
        ),
        EVIDENCE,
        GOOD,
    )

    summary = summarizer(ollama).summarize(MEETING, TOTAL_AND_BUILD)

    assert (
        "subject contains numbers nobody said: $30,000"
        in ollama.requests[1]["messages"][-1]["content"]
    )
    assert summary.figures[0].subject == "Total"


def test_checks_context_again_before_a_correction_request():
    ollama = FakeOllama("x" * 20000)

    with pytest.raises(OllamaError, match="too long"):
        summarizer(ollama, num_ctx=8192).summarize(MEETING, "short transcript")

    assert len(ollama.requests) == 1


def test_checks_context_again_before_the_writing_pass():
    # Each quote is valid, but the repeated evidence would overfill the writing request.
    item = {"speaker": "Sam", "subject": "Total", "quote": "A hundred and twenty thousand."}
    ollama = FakeOllama(json.dumps({"figures": [item] * 150}))

    with pytest.raises(OllamaError, match="too long"):
        summarizer(ollama, num_ctx=8192).summarize(
            MEETING, "[00:00:00] Sam: A hundred and twenty thousand."
        )

    assert len(ollama.requests) == 1


@pytest.mark.parametrize("failure", ["network", "length"])
def test_a_failed_writing_pass_does_not_return_partial_results(failure: str):
    ollama = FakeOllama(EVIDENCE, GOOD)

    def post(path: str, body: dict[str, Any]) -> dict[str, Any]:
        reply = ollama(path, body)
        if len(ollama.requests) == 2:
            if failure == "network":
                raise OllamaError("Connection lost")
            reply["done_reason"] = "length"
        return reply

    with pytest.raises(OllamaError):
        OllamaSummarizer("m", 32768, post, "Sam").summarize(MEETING, TOTAL_AND_BUILD)
    assert len(ollama.requests) == 2
