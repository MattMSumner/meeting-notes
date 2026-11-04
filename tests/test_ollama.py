"""OllamaSummarizer against a fake Ollama API."""

import json
from datetime import datetime
from typing import Any

import pytest

from meeting_notes.meeting import Meeting
from meeting_notes.ollama import OllamaError, OllamaSummarizer, default_prompt
from meeting_notes.summary import SummaryError

MEETING = Meeting.new("Weekly Sync", datetime(2026, 10, 20, 14, 5))


def reply(
    text: str = "Planned the release.", quote: str = "transcript", passage: str = "T1"
) -> str:
    return json.dumps(
        {
            "claims": [
                {"id": "fact", "text": text, "evidence": [{"passage": passage, "quote": quote}]}
            ],
            "overview": ["fact"],
            "key_points": [],
            "decisions": [],
            "action_items": [],
            "notes_context": [],
            "conflicts": [],
        }
    )


GOOD = reply()


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
    ollama = FakeOllama(reply(quote="Hi."))

    summary = summarizer(ollama).summarize(
        MEETING, "[00:00:00] Me: Hi.", handwritten_text="My notes"
    )

    assert summary.overview == "Planned the release."
    [request] = ollama.requests
    assert request["model"] == "qwen3:30b"
    assert request["options"]["num_ctx"] == 32768
    assert request["stream"] is False
    assert request["think"] is True
    assert "claims" in request["format"]["required"]
    system, user = request["messages"]
    assert system == {"role": "system", "content": "Summarize for Sam."}
    assert "Meeting: Weekly Sync" in user["content"]
    assert '"id": "T1", "source": "transcript", "text": "Hi."' in user["content"]
    assert '"id": "N1", "source": "notes", "text": "My notes"' in user["content"]


def test_retries_once_after_a_malformed_reply_saying_what_was_wrong():
    ollama = FakeOllama("not json", GOOD)

    summary = summarizer(ollama).summarize(MEETING, "transcript")

    assert summary.overview == "Planned the release."
    retry = ollama.requests[1]["messages"]
    assert retry[2] == {"role": "assistant", "content": "not json"}
    assert "Invalid JSON" in retry[3]["content"]


def test_gives_a_readable_error_after_two_malformed_replies():
    ollama = FakeOllama("not json", "still not json")

    with pytest.raises(SummaryError, match="failed evidence validation"):
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
    assert "action_items" in default_prompt()
    assert "{name}" in default_prompt()


def test_tells_the_model_who_else_was_invited():
    ollama = FakeOllama(GOOD)
    meeting = Meeting.new("Weekly Sync", datetime(2026, 10, 20, 14, 5), ("Alex Doe", "Kim"))

    summarizer(ollama).summarize(meeting, "transcript")

    assert "Others invited: Alex Doe, Kim\n" in ollama.requests[0]["messages"][1]["content"]


def with_key_point(point: str) -> str:
    data = json.loads(reply(point, "A hundred and twenty thousand all in, ninety for the build."))
    data["overview"] = ["fact"]
    data["key_points"] = ["fact"]
    return json.dumps(data)


TOTAL_AND_BUILD = "[00:00:15] Sam: A hundred and twenty thousand all in, ninety for the build."


def test_a_summary_with_only_numbers_that_were_said_is_kept():
    ollama = FakeOllama(with_key_point("$120,000 total, $90,000 build."))

    summarizer(ollama).summarize(MEETING, TOTAL_AND_BUILD)

    assert len(ollama.requests) == 1


def test_retries_once_naming_numbers_nobody_said():
    ollama = FakeOllama(
        with_key_point("$120,000 total: $90,000 build, $30,000 support."),
        with_key_point("$120,000 total, $90,000 build."),
    )

    summary = summarizer(ollama).summarize(MEETING, TOTAL_AND_BUILD)

    assert summary.key_points == ["$120,000 total, $90,000 build."]
    retry = ollama.requests[1]["messages"]
    assert "numbers absent from cited evidence: $30,000" in retry[3]["content"]


def test_keeps_the_first_summary_if_the_retry_is_no_better():
    first = with_key_point("$120,000 total: $90,000 build, $30,000 support.")
    ollama = FakeOllama(first, with_key_point("$120,000 total: $90,000 build, $35,000 support."))

    summary = summarizer(ollama).summarize(MEETING, TOTAL_AND_BUILD)

    assert summary.key_points == ["$120,000 total: $90,000 build, $30,000 support."]


def test_keeps_the_first_summary_if_the_retry_is_malformed():
    first = with_key_point("$120,000 total: $90,000 build, $30,000 support.")
    ollama = FakeOllama(first, "not json")

    summary = summarizer(ollama).summarize(MEETING, TOTAL_AND_BUILD)

    assert summary.key_points == ["$120,000 total: $90,000 build, $30,000 support."]


def test_combined_sources_can_exceed_context_even_when_each_fits():
    ollama = FakeOllama(GOOD)
    with pytest.raises(OllamaError, match="complete request"):
        summarizer(ollama, num_ctx=8192).summarize(
            MEETING, "spoken " * 900, handwritten_text="written " * 900
        )
    assert ollama.requests == []


def test_format_correction_checks_complete_request_before_sending():
    ollama = FakeOllama("x" * 20000, GOOD)
    with pytest.raises(OllamaError, match="complete request"):
        summarizer(ollama, num_ctx=8192).summarize(MEETING, "Spoken")
    assert len(ollama.requests) == 1


def test_number_correction_over_context_keeps_first_valid_result():
    first = with_key_point("$30,000 " + "x" * 20000)
    ollama = FakeOllama(first, GOOD)
    result = summarizer(ollama, num_ctx=8192).summarize(MEETING, TOTAL_AND_BUILD)
    assert result.key_points == [json.loads(first)["claims"][0]["text"]]
    assert len(ollama.requests) == 1


def test_wrong_source_references_are_blocking_and_can_be_corrected():
    ollama = FakeOllama(
        reply("Budget $500", "Budget $500", "N1"), reply("Budget $120", "Budget $120")
    )
    model = summarizer(ollama)
    result = model.summarize(MEETING, "Budget $120", handwritten_text="Budget $500")
    assert result.overview == "Budget $120"
    assert "requires only transcript evidence" in ollama.requests[1]["messages"][-1]["content"]
    assert model.audit.selected == 1
    assert model.audit.attempts[0].blocking


def test_all_failed_attempts_are_recorded_and_do_not_publish():
    ollama = FakeOllama(reply(quote="invented"), reply(passage="absent"))
    model = summarizer(ollama)
    with pytest.raises(SummaryError, match="evidence validation"):
        model.summarize(MEETING, "transcript")
    assert model.audit.selected is None
    assert len(model.audit.attempts) == 2
    assert all(a.blocking and a.reply for a in model.audit.attempts)
    assert len(model.audit.attempts[0].request["messages"]) == 2
    assert len(model.audit.attempts[1].request["messages"]) == 4


def test_numeric_retry_keeps_first_valid_candidate_when_correction_introduces_blocking_issue():
    first = with_key_point("$30,000 support.")
    ollama = FakeOllama(first, reply(quote="invented"))
    model = summarizer(ollama)
    result = model.summarize(MEETING, TOTAL_AND_BUILD)
    assert result.key_points == ["$30,000 support."]
    assert model.audit.selected == 0
    assert model.audit.attempts[0].warnings
    assert model.audit.attempts[1].blocking


def test_new_call_resets_audit_and_never_reuses_previous_sources():
    model = summarizer(FakeOllama(GOOD, reply(quote="another")))
    model.summarize(MEETING, "transcript")
    first = model.audit
    model.summarize(MEETING, "another")
    assert first is not model.audit
    assert model.audit.passages[0].text == "another"
    assert len(model.audit.attempts) == 1
