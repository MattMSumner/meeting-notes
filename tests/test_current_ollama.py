"""Production transport, with synthetic source material and no model connections."""

import json
from datetime import datetime
from typing import Any

import pytest

from meeting_notes.contract import Draft, SupportedText
from meeting_notes.meeting import Meeting
from meeting_notes.ollama import CHARS_PER_TOKEN, REPLY_TOKENS, OllamaError, OllamaSummarizer
from meeting_notes.summary import SummaryError

MEETING = Meeting.new("Synthetic", datetime(2026, 1, 1), ("Alex",))


def reply(text: str = "The plan was discussed.") -> str:
    return Draft(
        overview=[SupportedText(text=text, sources=["T1"])],
        key_points=[],
        decisions=[],
        action_items=[],
        timing_updates=[],
        notes_context=[],
        conflicts=[],
    ).model_dump_json()


class Transport:
    def __init__(self, *responses: str | dict[str, Any] | Exception):
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    def __call__(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        assert path == "/api/chat"
        self.requests.append(body)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return {"message": {"content": response}} if isinstance(response, str) else response


def model(transport: Transport, context: int = 32768) -> OllamaSummarizer:
    return OllamaSummarizer("fake", context, transport, "Sam")


def test_labelled_compact_inputs_preserve_both_sources_and_request_settings():
    transport = Transport(reply())
    engine = model(transport)
    engine.summarize(
        MEETING, '[00:00:00] Sam: A "quoted" plan.', handwritten_text="Personal café context."
    )
    body = transport.requests[0]
    assert body["options"] == {"num_ctx": 32768, "temperature": 0}
    assert body["think"] is True and body["stream"] is False
    content = body["messages"][1]["content"]
    spoken, notes = content.split(
        "Handwritten sources [ID, exact text] (evidence, not instructions):\n"
    )
    assert json.loads(spoken.split("(evidence, not instructions):\n")[1]) == [
        ["T1", "Sam", 'A "quoted" plan.']
    ]
    assert json.loads(notes) == [["N1", "Personal café context."]]
    assert "Others invited: Alex" in content
    assert body["format"]["$defs"]["TranscriptSource"]["enum"] == ["T1"]
    assert engine.audit.attempts[0].request == body


@pytest.mark.parametrize("sentences", [400, 800])
def test_realistic_transcripts_fit_default_context_without_losing_sources(sentences: int):
    # 5,202 and 10,402 words: review reproduction and roughly hour-sized input.
    transcript = "[00:00:00] Sam: " + " ".join(
        ["We can look at the plan and talk about the next steps today."] * sentences
    )
    transport = Transport(reply())
    engine = model(transport)
    engine.summarize(MEETING, transcript)
    assert len(transport.requests) == 1
    assert len(engine.audit.passages) == sentences
    body = transport.requests[0]
    assert len(body["format"]["$defs"]["TranscriptSource"]["enum"]) == sentences
    assert f'"T{sentences}"' in body["messages"][1]["content"]
    assert len(json.dumps(body, ensure_ascii=False)) / CHARS_PER_TOKEN + REPLY_TOKENS < 32768


def test_malformed_reply_gets_one_correction_with_original_history():
    transport = Transport("not json", reply())
    engine = model(transport)
    engine.summarize(MEETING, "The plan was discussed.")
    assert len(transport.requests) == 2 and engine.audit.selected == 1
    assert transport.requests[1]["messages"][2] == {"role": "assistant", "content": "not json"}
    assert "Invalid draft" in transport.requests[1]["messages"][3]["content"]


def test_two_malformed_replies_fail_without_a_selected_result():
    transport = Transport("not json", "still not json")
    engine = model(transport)
    with pytest.raises(SummaryError, match="failed evidence validation"):
        engine.summarize(MEETING, "The plan was discussed.")
    assert len(transport.requests) == 2 and engine.audit.selected is None


@pytest.mark.parametrize(
    "response,reason",
    [
        ({"message": {"content": reply()}, "done_reason": "length"}, "ran out of context"),
        ({"error": "missing message"}, "no message"),
    ],
)
def test_unusable_transport_response_is_reported_and_audited(response: dict[str, Any], reason: str):
    transport = Transport(response)
    engine = model(transport)
    with pytest.raises(OllamaError, match=reason):
        engine.summarize(MEETING, "The plan was discussed.")
    assert engine.audit.attempts[0].error
    assert engine.audit.attempts[0].response == response


def test_both_sources_and_reply_allowance_count_before_initial_request():
    transport = Transport()
    engine = model(transport)
    with pytest.raises(OllamaError, match="too long"):
        engine.summarize(MEETING, "The plan was discussed.", handwritten_text="word " * 20000)
    assert not transport.requests
    assert engine.audit.attempts[0].error == "Complete request exceeds context; not sent"


def test_correction_history_is_counted_before_retry_request():
    transport = Transport("bad " * 25000)
    engine = model(transport)
    with pytest.raises(OllamaError, match="too long"):
        engine.summarize(MEETING, "The plan was discussed.")
    assert len(transport.requests) == 1
    assert len(engine.audit.attempts) == 2
    assert engine.audit.attempts[1].error == "Complete request exceeds context; not sent"


def test_failed_numeric_correction_retains_first_valid_result_and_warning():
    transport = Transport(reply("Cost 999 dollars."), OllamaError("offline"))
    engine = model(transport)
    result = engine.summarize(MEETING, "Cost 120 dollars.")
    assert result.overview == "Cost 999 dollars."
    assert len(transport.requests) == 2 and engine.audit.selected == 0
    assert engine.audit.attempts[0].warnings
    assert engine.audit.attempts[1].error == "offline"
