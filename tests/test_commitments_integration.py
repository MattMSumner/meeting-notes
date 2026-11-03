"""Dedicated commitments extraction; all other model tasks use fixed replies."""

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from commitment_checks import score

from meeting_notes.commitments import verify_commitments
from meeting_notes.config import Config
from meeting_notes.meeting import Meeting
from meeting_notes.ollama import OllamaSummarizer, http_post
from meeting_notes.summary import Commitments, Summary, SummaryError, parse_response
from meeting_notes.turns import parse_turns

pytestmark = pytest.mark.integration
FIXTURES = Path(__file__).parent / "fixtures"
CASES = [
    "golden",
    "availability",
    "numbers",
    "no_commitments",
    "conditional_commitments",
    "timing_roles",
    "accepted_requests",
]


def meeting_for(case: str) -> Meeting:
    if case == "numbers":
        return Meeting.new("Scanner project pricing", datetime(2026, 10, 21, 14, 0))
    title = "Lighthouse migration" if case in ("golden", "availability") else "Commitments check"
    return Meeting.new(title, datetime(2026, 10, 20, 10, 0))


def accepted_evidence(replies: list[str], summary: Summary, transcript: str) -> Commitments:
    """Find the validated response actually used, including a retained first attempt."""
    for reply in reversed(replies):
        try:
            evidence = parse_response(reply, Commitments)
            verify_commitments(evidence, parse_turns(transcript))
        except SummaryError:
            continue
        if [item.text for item in evidence.decisions] == summary.decisions and [
            item.model_dump(exclude={"turn_ids"}) for item in evidence.action_items
        ] == [item.model_dump() for item in summary.action_items]:
            return evidence
    raise AssertionError("No validated source references match the assembled commitments")


@pytest.fixture(scope="module", params=CASES)
def extracted(request: pytest.FixtureRequest) -> tuple[str, Summary, Commitments]:
    case: str = request.param
    config = Config.from_env()
    real_post = http_post(config.ollama_url)
    replies: list[str] = []

    def post(path: str, body: dict[str, Any]) -> dict[str, Any]:
        properties = body["format"]["properties"]
        if "decisions" in properties:
            response = real_post(path, body)
            replies.append(response["message"]["content"])
            return response
        content = '{"turn_ids":[]}' if "turn_ids" in properties else '{"overview":"Sam met."}'
        return {"message": {"content": content}, "done_reason": "stop"}

    transcript = (FIXTURES / f"{case}_transcript.txt").read_text()
    summary = OllamaSummarizer(
        config.summary_model, config.num_ctx, post, "Sam", think=config.summary_think
    ).summarize(meeting_for(case), transcript)
    return case, summary, accepted_evidence(replies, summary, transcript)


@pytest.mark.parametrize(
    "category", ["decisions", "actions", "timing", "references", "numbers", "qualifications"]
)
def test_commitments_preserve_meaning_and_support(
    extracted: tuple[str, Summary, Commitments], category: str
):
    case, summary, evidence = extracted
    metrics = score(case, summary, evidence.model_dump())
    failures = [
        name for name, passed in metrics.items() if name.startswith(f"{category}.") and not passed
    ]
    assert not failures, "\n".join(failures)
