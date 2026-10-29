"""Dedicated commitments extraction; all other model tasks use fixed replies."""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from test_ollama_integration import (
    check_number_positions,
    check_pricing_commitments,
    check_said_numbers,
    check_scheduling_actions,
    check_scheduling_decisions,
    check_scheduling_timing,
)

from meeting_notes.commitments import verify_commitments
from meeting_notes.config import Config
from meeting_notes.meeting import Meeting
from meeting_notes.ollama import OllamaSummarizer, http_post
from meeting_notes.summary import Commitments, Summary, SummaryError, parse_response
from meeting_notes.turns import parse_turns

pytestmark = pytest.mark.integration
FIXTURES = Path(__file__).parent / "fixtures"
CASES = ["golden", "availability", "numbers", "no_commitments", "conditional_commitments"]


def meeting_for(case: str) -> Meeting:
    if case == "numbers":
        return Meeting.new("Scanner project pricing", datetime(2026, 10, 21, 14, 0))
    title = "Lighthouse migration" if case in ("golden", "availability") else "Commitments check"
    return Meeting.new(title, datetime(2026, 10, 20, 10, 0))


def check_no_commitments(summary: Summary) -> None:
    assert summary.decisions == [] and summary.action_items == [], "Invented an agreement or task"


def check_conditional_commitments(summary: Summary) -> None:
    assert summary.decisions == [], "Approval is still pending"
    assert len(summary.action_items) == 2, "Expected conditional publication and unassigned report"
    [publish] = [item for item in summary.action_items if "publish" in item.task.lower()]
    assert publish.owner == "Sam"
    assert "friday" in (publish.due or "").lower()
    text = publish.task.lower()
    assert "security" in text and "approv" in text
    assert any(
        word in text
        for word in ("if", "upon", "when", "once", "provided", "pending", "subject to", "after")
    ), "Dropped the condition on publishing"
    [report] = [item for item in summary.action_items if "risk" in item.task.lower()]
    assert "report" in report.task.lower()
    assert report.owner is None and report.due is None, "Guessed the report owner or deadline"


def checks_for(case: str, summary: Summary) -> list[tuple[str, Callable[[], None]]]:
    if case in ("golden", "availability"):
        person, absent = ("Dan", "Monday") if case == "golden" else ("Alex", "Wednesday")
        return [
            ("decisions", lambda: check_scheduling_decisions(summary)),
            ("actions", lambda: check_scheduling_actions(summary, person)),
            ("timing", lambda: check_scheduling_timing(summary, person, absent)),
        ]
    if case == "numbers":
        return [
            ("commitments", lambda: check_pricing_commitments(summary)),
            ("numbers", lambda: check_said_numbers(summary)),
            ("qualifications", lambda: check_number_positions(summary)),
        ]
    if case == "no_commitments":
        return [("empty", lambda: check_no_commitments(summary))]
    return [("conditions_and_ownership", lambda: check_conditional_commitments(summary))]


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


def check_references(case: str, evidence: Commitments) -> None:
    if case in ("golden", "availability"):
        for item in evidence.decisions:
            expected = "t9" if "write" in item.text.lower() else "t13"
            assert expected in item.turn_ids, "Decision lacks its source turn"
        for item in evidence.action_items:
            text = item.task.lower()
            if "cutover" in text:
                assert {"t9", "t10"} <= set(item.turn_ids), "Missing request or acceptance"
            elif "finance" in text or "billing" in text:
                assert "t11" in item.turn_ids
            else:
                assert "t13" in item.turn_ids
    elif case == "numbers":
        assert all("t12" in item.turn_ids for item in evidence.action_items)
    elif case == "conditional_commitments":
        for item in evidence.action_items:
            assert ("t1" if "publish" in item.task.lower() else "t2") in item.turn_ids


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


def test_commitments_cover_each_semantic_check(extracted: tuple[str, Summary, Commitments]):
    case, summary, _ = extracted
    failures: list[str] = []
    for name, check in checks_for(case, summary):
        try:
            check()
        except (AssertionError, ValueError) as error:
            failures.append(f"{name}: {error}")
    assert not failures, "\n".join(failures)


def test_commitments_cite_supporting_turns(extracted: tuple[str, Summary, Commitments]):
    case, _, evidence = extracted
    check_references(case, evidence)
