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

from meeting_notes.commitments import action_item, action_turn_ids, verify_commitments
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


def check_timing_roles(summary: Summary) -> None:
    assert summary.decisions == [], "Promises are not separate agreements"
    assert len(summary.action_items) == 5, "Expected five independent communication tasks"
    for person, work, due in (
        ("Morgan", "pilot", None),
        ("Lee", "audit", "wednesday"),
        ("Casey", "rota", None),
        ("Jordan", "patch", None),
        ("Taylor", "campaign", "monday"),
    ):
        [item] = [item for item in summary.action_items if person.lower() in item.task.lower()]
        assert item.owner == "Sam" and work in item.task.lower()
        assert any(
            verb in item.task.lower()
            for verb in ("talk", "contact", "ask", "speak", "discuss", "message")
        )
        if due is None:
            assert item.due is None, "Related timing became a communication deadline"
        else:
            assert due in (item.due or "").lower(), "Lost the explicit communication deadline"


def check_accepted_requests(summary: Summary) -> None:
    assert summary.decisions == []
    assert len(summary.action_items) == 2
    for work, due in (("checklist", "thursday"), ("guide", "planning")):
        [item] = [item for item in summary.action_items if work in item.task.lower()]
        assert item.owner == "Riley"
        assert due in (item.due or "").lower()
        if work == "guide":
            assert "rollback" in item.task.lower(), "Lost the requested scope of the review"


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
    if case == "timing_roles":
        return [("timing_roles", lambda: check_timing_roles(summary))]
    if case == "accepted_requests":
        return [("accepted_requests", lambda: check_accepted_requests(summary))]
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
            action_item(item).model_dump() for item in evidence.action_items
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
                assert item.kind == "accepted_request"
                assert "t9" in item.request_turn_ids, "Missing original request"
                assert "t10" in item.commitment_turn_ids, "Missing acceptance"
                assert item.action_timing is not None and item.action_timing.turn_id == "t10"
            elif "finance" in text or "billing" in text:
                assert "t11" in item.commitment_turn_ids
                assert item.kind == "promise" and item.action_timing is None
                if "billing" in text:
                    back = "tuesday" if case == "golden" else "thursday"
                    assert any(
                        timing.turn_id == "t11" and back in timing.value.lower()
                        for timing in item.related_timing
                    ), "Missing related work timing"
            else:
                assert "t13" in item.commitment_turn_ids
                assert item.action_timing is not None and item.action_timing.turn_id == "t13"
    elif case == "numbers":
        for item in evidence.action_items:
            assert item.kind == "accepted_request"
            assert "t11" in item.request_turn_ids and "t12" in item.commitment_turn_ids
            assert item.action_timing is not None and item.action_timing.turn_id == "t12"
    elif case == "conditional_commitments":
        for item in evidence.action_items:
            publish = "publish" in item.task.lower()
            assert ("t1" if publish else "t2") in item.commitment_turn_ids
            assert item.kind == ("promise" if publish else "reported_commitment")
    elif case == "timing_roles":
        for person, source, day in (
            ("morgan", "t1", "thursday"),
            ("lee", "t2", "friday"),
            ("casey", "t3", "monday"),
            ("jordan", "t4", "tuesday"),
            ("taylor", "t5", None),
        ):
            [item] = [item for item in evidence.action_items if person in item.task.lower()]
            assert item.kind == "promise" and source in item.commitment_turn_ids
            if day is None:
                assert item.related_timing == []
            else:
                assert any(
                    t.turn_id == source and day in t.value.lower() for t in item.related_timing
                )
            assert (item.action_timing is not None) == (person in ("lee", "taylor"))
            if item.action_timing is not None:
                assert item.action_timing.turn_id == source
    elif case == "accepted_requests":
        for work, request, acceptance in (("checklist", "t1", "t2"), ("guide", "t3", "t6")):
            [item] = [item for item in evidence.action_items if work in item.task.lower()]
            assert item.kind == "accepted_request"
            assert request in item.request_turn_ids and acceptance in item.commitment_turn_ids
            assert item.action_timing is not None and item.action_timing.turn_id == acceptance
            if work == "guide":
                assert "t5" in action_turn_ids(item), "Missing the review's requested scope"


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
