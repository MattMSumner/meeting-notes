"""Regression checks for the synthetic evaluation's scoring rules."""

from copy import deepcopy
from typing import Any

import pytest
from commitment_checks import score

from meeting_notes.summary import ActionItem, Summary


def sample(case: str) -> tuple[Summary, dict[str, Any]]:
    decisions: list[tuple[str, list[str]]] = []
    actions: list[tuple[str, str | None, str | None, list[str]]]
    if case in ("golden", "availability"):
        person = "Dan" if case == "golden" else "Alex"
        decisions = [
            ("Move writes over and not buy more disk", ["t9"]),
            ("Keep the on-call rotation unchanged this month", ["t13"]),
        ]
        actions = [
            ("Write up the cutover plan", "Priya", "by Thursday", ["t9", "t10"]),
            (f"Talk to {person} about starting billing", "Sam", None, ["t11"]),
            ("Notify finance about a possible invoice freeze", "Sam", None, ["t11"]),
            ("Bring up the on-call rotation at planning", "Sam", "at planning", ["t13"]),
        ]
    elif case == "numbers":
        actions = [
            ("Talk to procurement and get back to Sam", "Nadia", "this week", ["t11", "t12"])
        ]
    elif case == "conditional_commitments":
        actions = [
            ("Publish the update if security approves it", "Sam", "Friday", ["t1"]),
            ("Send the risk report", None, None, ["t2"]),
        ]
    elif case == "timing_roles":
        actions = [
            ("Talk to Morgan about launching the pilot Thursday", "Sam", None, ["t1"]),
            ("Contact Lee about the audit starting Friday", "Sam", "Wednesday", ["t2"]),
            ("Ask Casey about the support rota", "Sam", None, ["t3"]),
            ("Message Jordan about deploying the patch Tuesday", "Sam", None, ["t4"]),
            ("Speak to Taylor about launching the renewal campaign", "Sam", "Monday", ["t5"]),
        ]
    elif case == "accepted_requests":
        actions = [
            ("Draft the release checklist", "Riley", "Thursday", ["t1", "t2"]),
            (
                "Review the deployment guide's rollback section",
                "Riley",
                "at planning",
                ["t3", "t5", "t6"],
            ),
        ]
    elif case == "no_commitments":
        actions = []
    else:
        raise ValueError(case)
    summary = Summary(
        overview="Sam discussed the meeting.",
        decisions=[text for text, _ in decisions],
        action_items=[
            ActionItem(task=task, owner=owner, due=due) for task, owner, due, _ in actions
        ],
    )
    evidence: dict[str, Any] = {
        "decisions": [{"text": text, "turn_ids": ids} for text, ids in decisions],
        "action_items": [
            {"task": task, "owner": owner, "due": due, "turn_ids": ids}
            for task, owner, due, ids in actions
        ],
    }
    return summary, evidence


def with_role_arrays(evidence: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(evidence)
    for item in result["action_items"]:
        ids = item.pop("turn_ids")
        item["commitment_turn_ids"] = ids[-1:]
        item["request_turn_ids"] = ids[:1] if len(ids) > 1 else []
        item["context_turn_ids"] = ids[1:-1]
    return result


@pytest.mark.parametrize(
    "case",
    [
        "golden",
        "availability",
        "numbers",
        "no_commitments",
        "conditional_commitments",
        "timing_roles",
        "accepted_requests",
    ],
)
def test_complete_commitments_pass_with_either_reference_schema(case: str):
    summary, evidence = sample(case)
    old = score(case, summary, evidence)
    new = score(case, summary, with_role_arrays(evidence))
    assert old == new
    assert old and all(old.values()), [name for name, passed in old.items() if not passed]


def test_invented_decision_does_not_hide_action_condition_owner_or_timing():
    summary, evidence = sample("conditional_commitments")
    summary.decisions = ["Publish the release"]
    summary.action_items[0].task = "Publish the update"
    summary.action_items[1].owner = "Sam"
    summary.action_items[0].due = None
    result = score("conditional_commitments", summary, evidence)
    assert not result["decisions.none"]
    assert not result["actions.condition"]
    assert not result["actions.unknown_owner"]
    assert not result["timing.publish"]
    assert result["actions.count"] and result["actions.report"] and result["timing.report"]


@pytest.mark.parametrize("role_arrays", [False, True])
def test_request_and_acceptance_are_independent_requirements(role_arrays: bool):
    summary, evidence = sample("accepted_requests")
    evidence["action_items"][1]["turn_ids"].remove("t3")
    if role_arrays:
        evidence = with_role_arrays(evidence)
    result = score("accepted_requests", summary, evidence)
    assert not result["references.guide_request"]
    assert result["references.guide_acceptance"]
    assert result["references.guide_scope"]
    assert result["timing.guide"]


def test_requested_scope_needs_its_source_even_when_task_names_it():
    summary, evidence = sample("accepted_requests")
    evidence["action_items"][1]["turn_ids"].remove("t5")
    result = score("accepted_requests", summary, evidence)
    assert result["actions.guide_scope"]
    assert not result["references.guide_scope"]


def test_citation_on_another_task_does_not_supply_missing_acceptance():
    summary, evidence = sample("accepted_requests")
    evidence["action_items"][0]["turn_ids"].remove("t2")
    evidence["action_items"][1]["turn_ids"].append("t2")
    result = score("accepted_requests", summary, evidence)
    assert not result["references.checklist_acceptance"]


def test_pricing_requires_the_original_request_as_well_as_the_reply():
    summary, evidence = sample("numbers")
    evidence["action_items"][0]["turn_ids"] = ["t12"]
    result = score("numbers", summary, evidence)
    assert not result["references.request"]
    assert result["references.acceptance"] and result["actions.report_back"]


@pytest.mark.parametrize(
    "task,expected",
    [
        ("Talk to procurement and get back to Sam", True),
        ("Discuss pricing with procurement and provide feedback to Sam", True),
        ("Discuss the proposal with procurement and update Sam", True),
        ("Talk to procurement about Sam's proposal", False),
        ("Talk to procurement and report back to Riley", False),
    ],
)
def test_pricing_requires_report_back_to_the_requester(task: str, expected: bool):
    summary, evidence = sample("numbers")
    summary.action_items[0].task = task
    assert score("numbers", summary, evidence)["actions.report_back"] is expected


def test_merged_promises_are_not_independent_actions_even_with_four_items():
    summary, evidence = sample("golden")
    summary.action_items[1].task += " and notify finance about a possible invoice freeze"
    summary.action_items[2] = ActionItem(owner="Sam", task="Send an unrelated email", due=None)
    result = score("golden", summary, evidence)
    assert result["actions.count"]
    assert not result["actions.independent_tasks"]


def test_a_related_work_date_is_not_an_action_deadline():
    summary, evidence = sample("timing_roles")
    summary.decisions = ["Launch the pilot"]
    summary.action_items[0].due = "Thursday"
    summary.action_items[1].due = None
    result = score("timing_roles", summary, evidence)
    assert not result["decisions.none"]
    assert not result["timing.morgan"]
    assert not result["timing.lee"]
    assert result["timing.taylor"]


def test_absence_in_task_is_detected_even_when_due_is_empty():
    summary, evidence = sample("availability")
    summary.action_items[1].task = "Talk to Alex on Wednesday about starting billing"
    result = score("availability", summary, evidence)
    assert result["timing.billing"]
    assert not result["timing.billing_absence"]


def test_rotation_timing_must_survive_in_the_saved_deadline():
    summary, evidence = sample("golden")
    summary.action_items[3].due = None
    result = score("golden", summary, evidence)
    assert result["timing.rotation"]
    assert not result["timing.rotation_deadline"]


def test_pricing_number_failures_are_independent():
    summary, evidence = sample("numbers")
    summary.decisions = [
        "The retainer is thirty thousand",
        "Nadia set a maximum of seventy thousand for the build",
        "Nadia said a hundred thousand is too much",
        "The total is eighty thousand",
    ]
    result = score("numbers", summary, evidence)
    assert not result["decisions.none"]
    assert not result["numbers.unsaid_retainer"]
    assert not result["qualifications.feasible_amount"]
    assert not result["qualifications.budget"]
    assert not result["numbers.total_range"]
    assert not result["numbers.attribution_80"]
    assert result["actions.report_back"]


def test_missing_actions_fail_their_ownership_timing_and_reference_checks():
    summary, evidence = sample("accepted_requests")
    summary.action_items = []
    result = score("accepted_requests", summary, evidence)
    assert not result["actions.checklist"]
    assert not result["actions.checklist_owner"]
    assert not result["timing.checklist"]
    assert not result["references.checklist_request"]


def test_unknown_fixture_is_an_error():
    summary, evidence = sample("no_commitments")
    with pytest.raises(ValueError, match="Unknown commitments fixture"):
        score("typo", summary, evidence)
