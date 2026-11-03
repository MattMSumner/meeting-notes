"""OllamaSummarizer against a fake Ollama API."""

import json
from datetime import datetime
from typing import Any

import pytest

from meeting_notes.figures import unsaid_numbers
from meeting_notes.meeting import Meeting
from meeting_notes.ollama import (
    OllamaError,
    OllamaSummarizer,
    default_commitments_prompt,
    default_details_prompt,
    default_prompt,
)
from meeting_notes.summary import SummaryError

MEETING = Meeting.new("Weekly Sync", datetime(2026, 10, 20, 14, 5))
GOOD = '{"overview":"Planned the release."}'
EMPTY_COMMITMENTS = '{"decisions":[],"action_items":[]}'
EMPTY_SELECTION = '{"turn_ids":[]}'
EVIDENCE = '{"turn_ids":["t1"]}'
TRANSCRIPT = "[00:00:00] Sam: Hi."
TOTAL_AND_BUILD = "[00:00:15] Sam: A hundred and twenty thousand all in, ninety for the build."


class FakeOllama:
    """Replies to /api/chat with each canned message content in turn."""

    def __init__(self, *replies: str, done_reason: str = "stop"):
        self.replies = list(replies)
        self.done_reason = done_reason
        self.requests: list[dict[str, Any]] = []

    def __call__(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        assert path == "/api/chat"
        self.requests.append(body)
        return {
            "message": {"role": "assistant", "content": self.replies.pop(0)},
            "done_reason": self.done_reason,
        }


def summarizer(ollama: FakeOllama, num_ctx: int = 32768) -> OllamaSummarizer:
    return OllamaSummarizer(
        "qwen3:30b",
        num_ctx,
        ollama,
        "Sam",
        prompt="Summarize for {name}.",
        details_prompt="Select for {name}.",
        commitments_prompt="Commitments for {name}.",
    )


def decision(text: str, turn_ids: tuple[str, ...] = ("t1",)) -> str:
    return json.dumps({"decisions": [{"text": text, "turn_ids": turn_ids}], "action_items": []})


def action(task: str = "Check the plan") -> str:
    return json.dumps(
        {
            "decisions": [],
            "action_items": [{"owner": "Sam", "task": task, "due": None, "turn_ids": ["t1"]}],
        }
    )


def test_sends_independent_inputs_with_explicit_context_and_schemas():
    ollama = FakeOllama(EVIDENCE, action(), GOOD)
    meeting = Meeting.new("Weekly Sync", MEETING.started_at, ("Alex Doe", "Kim"))

    summary = summarizer(ollama).summarize(meeting, TRANSCRIPT)

    selection, commitments, overview = ollama.requests
    turns = [{"id": "t1", "start": 0.0, "speaker": "Sam", "text": "Hi."}]
    assert json.loads(selection["messages"][1]["content"]) == {"turns": turns}
    assert selection["messages"][0]["content"] == "Select for Sam."
    assert commitments["messages"][0]["content"] == "Commitments for Sam."
    assert json.loads(commitments["messages"][1]["content"]) == {
        "meeting": {
            "title": "Weekly Sync",
            "date": "Tuesday 2026-10-20 14:05",
            "attendees": ["Alex Doe", "Kim"],
        },
        "turns": turns,
    }
    assert overview["messages"] == [
        {"role": "system", "content": "Summarize for Sam."},
        {
            "role": "user",
            "content": "Meeting: Weekly Sync\nDate: Tuesday 2026-10-20 14:05\n"
            "Others invited: Alex Doe, Kim\n\nTranscript:\n\n" + TRANSCRIPT,
        },
    ]
    assert [request["format"]["required"] for request in ollama.requests] == [
        ["turn_ids"],
        ["decisions", "action_items"],
        ["overview"],
    ]
    for request in ollama.requests:
        assert request["model"] == "qwen3:30b"
        assert request["options"] == {"num_ctx": 32768, "temperature": 0}
        assert request["stream"] is False and request["think"] is True
    assert summary.action_items[0].task == "Check the plan"
    assert "turn_ids" not in summary.model_dump_json()
    assert summary.key_points == []


@pytest.mark.parametrize("stage", [1, 2])
def test_retries_a_malformed_generated_section_without_repeating_other_tasks(stage: int):
    replies = [EMPTY_SELECTION, EMPTY_COMMITMENTS, GOOD]
    replies.insert(stage, "not json")
    ollama = FakeOllama(*replies)

    assert summarizer(ollama).summarize(MEETING, TRANSCRIPT).overview == "Planned the release."

    retry = ollama.requests[stage + 1]["messages"]
    assert retry[2] == {"role": "assistant", "content": "not json"}
    assert "Invalid JSON" in retry[3]["content"]
    assert len(ollama.requests) == 4


@pytest.mark.parametrize("stage", [1, 2])
def test_two_malformed_replies_stop_before_later_tasks(stage: int):
    replies = [EMPTY_SELECTION, EMPTY_COMMITMENTS][:stage] + ["not json", "still not json"]
    ollama = FakeOllama(*replies)

    with pytest.raises(SummaryError, match="wasn't valid JSON"):
        summarizer(ollama).summarize(MEETING, TRANSCRIPT)
    assert len(ollama.requests) == stage + 2


def test_refuses_a_transcript_too_long_for_the_context_without_sending_it():
    ollama = FakeOllama()
    with pytest.raises(OllamaError, match="MEETING_NOTES_NUM_CTX to at least"):
        summarizer(ollama, num_ctx=8192).summarize(MEETING, "[00:00:00] Sam: " + "word " * 4000)
    assert ollama.requests == []


@pytest.mark.parametrize("stage", [0, 1, 2])
@pytest.mark.parametrize("failure", ["network", "length"])
def test_a_failed_task_does_not_return_partial_results(stage: int, failure: str):
    ollama = FakeOllama(EMPTY_SELECTION, EMPTY_COMMITMENTS, GOOD)

    def post(path: str, body: dict[str, Any]) -> dict[str, Any]:
        reply = ollama(path, body)
        if len(ollama.requests) == stage + 1:
            if failure == "network":
                raise OllamaError("Connection lost")
            reply["done_reason"] = "length"
        return reply

    with pytest.raises(OllamaError):
        OllamaSummarizer("m", 32768, post, "Sam").summarize(MEETING, TRANSCRIPT)
    assert len(ollama.requests) == stage + 1


def test_a_reply_without_a_message_is_a_readable_error():
    def post(path: str, body: dict[str, Any]) -> dict[str, Any]:
        return {"error": "something odd"}

    with pytest.raises(OllamaError, match="no message"):
        OllamaSummarizer("m", 32768, post, "Sam", prompt="p").summarize(MEETING, TRANSCRIPT)


def test_the_prompts_ship_with_the_package():
    assert '"overview"' in default_prompt() and "{name}" in default_prompt()
    assert '"turn_ids"' in default_details_prompt()
    assert '"action_items"' in default_commitments_prompt()


def test_numbers_in_the_source_do_not_trigger_a_correction():
    ollama = FakeOllama(EMPTY_SELECTION, decision("$120,000 total, $90,000 build."), GOOD)
    summarizer(ollama).summarize(MEETING, TOTAL_AND_BUILD)
    assert len(ollama.requests) == 3


def test_number_corrections_retry_only_commitments_and_reuse_source_details():
    ollama = FakeOllama(EVIDENCE, decision("$30,000 support."), decision("$120,000 total."), GOOD)

    summary = summarizer(ollama).summarize(MEETING, TOTAL_AND_BUILD)

    assert summary.decisions == ["$120,000 total."]
    assert summary.details[0].quote in TOTAL_AND_BUILD
    retry = ollama.requests[2]
    assert retry["format"]["required"] == ["decisions", "action_items"]
    assert "Nobody said these numbers: $30,000." in retry["messages"][3]["content"]
    assert len(ollama.requests) == 4


def test_number_corrections_retry_only_the_overview():
    ollama = FakeOllama(EVIDENCE, action(), '{"overview":"$30,000 support."}', GOOD)

    summary = summarizer(ollama).summarize(MEETING, TOTAL_AND_BUILD)

    assert summary.action_items[0].task == "Check the plan"
    assert summary.overview == "Planned the release."
    assert [r["format"]["required"] for r in ollama.requests] == [
        ["turn_ids"],
        ["decisions", "action_items"],
        ["overview"],
        ["overview"],
    ]


def test_turn_ids_in_the_extraction_input_cannot_authorize_new_numbers():
    transcript = "\n".join("[00:00:00] Sam: Check the plan." for _ in range(30))
    ollama = FakeOllama(
        EMPTY_SELECTION, decision("Spend $30.", ("t30",)), decision("Check the plan."), GOOD
    )

    summary = summarizer(ollama).summarize(MEETING, transcript)

    assert summary.decisions == ["Check the plan."]
    assert "Nobody said these numbers: $30." in ollama.requests[2]["messages"][-1]["content"]


@pytest.mark.parametrize(
    "retry",
    [
        [decision("$35,000 support.")],
        ["not json", "still not json"],
        [decision("$120,000 total.", ("t99",)), decision("$120,000 total.", ("t99",))],
    ],
)
def test_keeps_valid_original_commitments_when_a_number_retry_is_no_better_or_invalid(
    retry: list[str],
):
    ollama = FakeOllama(EMPTY_SELECTION, decision("$30,000 support."), *retry, GOOD)

    summary = summarizer(ollama).summarize(MEETING, TOTAL_AND_BUILD)

    assert summary.decisions == ["$30,000 support."]
    assert unsaid_numbers(summary, TOTAL_AND_BUILD) == ["$30,000"]


def test_keeps_the_original_overview_when_its_number_retry_is_malformed():
    ollama = FakeOllama(
        EMPTY_SELECTION, EMPTY_COMMITMENTS, '{"overview":"$30,000 support."}', "bad", "still bad"
    )
    summary = summarizer(ollama).summarize(MEETING, TOTAL_AND_BUILD)
    assert summary.overview == "$30,000 support."


def test_corrects_an_unknown_selection_id_before_assembling_source_details():
    ollama = FakeOllama('{"turn_ids":["t2"]}', EVIDENCE, EMPTY_COMMITMENTS, GOOD)

    summary = summarizer(ollama).summarize(MEETING, TOTAL_AND_BUILD)

    assert summary.details[0].quote == "A hundred and twenty thousand all in, ninety for the build."
    assert summary.details[0].speaker == "Sam" and summary.details[0].start == 15
    assert summary.details[0].subject is None
    assert "Unknown turn IDs: t2" in ollama.requests[1]["messages"][-1]["content"]


def test_corrects_unknown_commitment_references_before_writing():
    ollama = FakeOllama(EMPTY_SELECTION, decision("Keep it.", ("t99",)), decision("Keep it."), GOOD)

    summary = summarizer(ollama).summarize(MEETING, TRANSCRIPT)

    assert summary.decisions == ["Keep it."]
    assert "Unknown turn IDs: t99" in ollama.requests[2]["messages"][-1]["content"]


def test_changing_earlier_outputs_cannot_change_later_inputs():
    empty = FakeOllama(EMPTY_SELECTION, EMPTY_COMMITMENTS, GOOD)
    extracted = FakeOllama(EVIDENCE, action(), GOOD)
    summarizer(empty).summarize(MEETING, TRANSCRIPT)
    summarizer(extracted).summarize(MEETING, TRANSCRIPT)
    assert empty.requests == extracted.requests


@pytest.mark.parametrize("reply", ["not json", "{}", '{"turn_ids":["t99"]}', '{"turn_ids":[1]}'])
def test_failed_selection_never_calls_later_tasks(reply: str):
    ollama = FakeOllama(reply, reply)
    with pytest.raises(SummaryError):
        summarizer(ollama).summarize(MEETING, TRANSCRIPT)
    assert len(ollama.requests) == 2
    assert all(r["format"]["required"] == ["turn_ids"] for r in ollama.requests)


@pytest.mark.parametrize(
    "reply",
    [
        "{}",
        decision("Keep it.", ("t99",)),
        '{"decisions":[{"text":"Keep it.","turn_ids":[]}],"action_items":[]}',
    ],
)
def test_failed_commitments_never_call_the_overview(reply: str):
    ollama = FakeOllama(EMPTY_SELECTION, reply, reply)
    with pytest.raises(SummaryError):
        summarizer(ollama).summarize(MEETING, TRANSCRIPT)
    assert len(ollama.requests) == 3


@pytest.mark.parametrize("field", ["details", "decisions", "action_items"])
def test_the_overview_cannot_replace_other_sections(field: str):
    replacement = json.loads(GOOD)
    replacement[field] = []
    ollama = FakeOllama(EVIDENCE, action(), json.dumps(replacement), GOOD)
    summary = summarizer(ollama).summarize(MEETING, TRANSCRIPT)
    assert len(summary.details) == 1 and len(summary.action_items) == 1
    assert "Extra inputs" in ollama.requests[-1]["messages"][-1]["content"]


@pytest.mark.parametrize("field", ["subject", "quote", "speaker", "start"])
def test_the_selector_cannot_supply_words_or_attribution(field: str):
    reply = json.loads(EVIDENCE)
    reply[field] = "Invented."
    ollama = FakeOllama(json.dumps(reply), EVIDENCE, EMPTY_COMMITMENTS, GOOD)
    summary = summarizer(ollama).summarize(MEETING, TRANSCRIPT)
    assert summary.details[0].subject is None
    assert summary.details[0].speaker == "Sam" and summary.details[0].quote == "Hi."
    assert "Extra inputs" in ollama.requests[1]["messages"][-1]["content"]


def test_checks_context_again_before_a_correction_request():
    ollama = FakeOllama("x" * 20000)
    with pytest.raises(OllamaError, match="too long"):
        summarizer(ollama, num_ctx=8192).summarize(MEETING, TRANSCRIPT)
    assert len(ollama.requests) == 1


def test_repeated_selected_ids_do_not_inflate_later_context():
    ollama = FakeOllama(json.dumps({"turn_ids": ["t1"] * 150}), EMPTY_COMMITMENTS, GOOD)
    summary = summarizer(ollama, num_ctx=8192).summarize(MEETING, TOTAL_AND_BUILD)
    assert len(summary.details) == 1 and len(ollama.requests) == 3


@pytest.mark.parametrize(("prompt_field", "sent"), [("commitments_prompt", 1), ("prompt", 2)])
def test_checks_context_before_each_generated_section(prompt_field: str, sent: int):
    ollama = FakeOllama(EMPTY_SELECTION, EMPTY_COMMITMENTS)
    with pytest.raises(OllamaError, match="too long"):
        OllamaSummarizer(
            "m",
            8192,
            ollama,
            "Sam",
            prompt="x" * 20000 if prompt_field == "prompt" else "p",
            commitments_prompt="x" * 20000 if prompt_field == "commitments_prompt" else "c",
        ).summarize(MEETING, TRANSCRIPT)
    assert len(ollama.requests) == sent
