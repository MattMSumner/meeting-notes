"""Source selection against local Ollama, with a fixed writer reply."""

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from meeting_notes.config import Config
from meeting_notes.figures import verify_details
from meeting_notes.meeting import Meeting
from meeting_notes.ollama import OllamaSummarizer, http_post
from meeting_notes.summary import Detail
from meeting_notes.turns import parse_turns

pytestmark = pytest.mark.integration
FIXTURES = Path(__file__).parent / "fixtures"
# Required facts, and turns with only greetings, agenda setup or acknowledgments.
CASES = [
    ("numbers", {"t3", "t5", "t6", "t8"}, {"t1", "t2", "t4", "t7", "t9", "t13"}),
    ("golden", {"t2", "t3", "t6", "t8", "t11", "t12"}, {"t1", "t14", "t15"}),
    ("availability", {"t2", "t3", "t6", "t8", "t11", "t12"}, {"t1", "t14", "t15"}),
    ("greetings", set[str](), {"t1", "t2", "t3", "t4"}),
]
WRITER_REPLY = '{"overview":"Discussed the meeting.","decisions":[],"action_items":[]}'


def check_selection(
    details: list[Detail], transcript: str, required: set[str], forbidden: set[str]
) -> None:
    verify_details(details, transcript)
    turns = parse_turns(transcript)
    ids: list[str] = []
    for detail in details:
        assert detail.start is not None and detail.subject is None
        [source] = [
            turn
            for turn in turns
            if (turn.start, turn.speaker, turn.text) == (detail.start, detail.speaker, detail.quote)
        ]
        ids.append(source.id)
    assert ids == [turn.id for turn in turns if turn.id in ids], "Repeated or reordered turns"
    assert required <= set(ids), f"Missing source turns: {sorted(required - set(ids))}"
    assert not forbidden & set(ids), f"Selected irrelevant turns: {sorted(forbidden & set(ids))}"


@pytest.mark.parametrize(("case", "required", "forbidden"), CASES)
def test_selects_complete_relevant_turns(case: str, required: set[str], forbidden: set[str]):
    config = Config.from_env()
    real_post = http_post(config.ollama_url)

    def post(path: str, body: dict[str, Any]) -> dict[str, Any]:
        if "turn_ids" in body["format"]["properties"]:
            return real_post(path, body)
        return {"message": {"content": WRITER_REPLY}, "done_reason": "stop"}

    transcript = (FIXTURES / f"{case}_transcript.txt").read_text()
    summary = OllamaSummarizer(
        config.summary_model, config.num_ctx, post, "Sam", think=config.summary_think
    ).summarize(Meeting.new("Selection check", datetime(2026, 10, 20, 10, 0)), transcript)

    check_selection(summary.details, transcript, required, forbidden)
