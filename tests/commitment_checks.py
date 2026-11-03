"""The same semantic checks for commitments with either evidence schema."""

import re
from collections.abc import Callable
from typing import Any

from meeting_notes.figures import numbers
from meeting_notes.summary import ActionItem, Summary


def _one(summary: Summary, matches: Callable[[str], bool]) -> ActionItem | None:
    items = [item for item in summary.action_items if matches(item.task.lower())]
    return items[0] if len(items) == 1 else None


def _text(item: ActionItem | None) -> str:
    return item.task.lower() if item is not None else ""


def _due(item: ActionItem | None, expected: str | None) -> bool:
    if item is None:
        return False
    return item.due is None if expected is None else expected in (item.due or "").lower()


def _ids(item: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for field in ("turn_ids", "commitment_turn_ids", "request_turn_ids", "context_turn_ids"):
        result.update(item.get(field, []))
    for timing in item.get("related_timing", []):
        result.add(timing["turn_id"])
    if item.get("action_timing") is not None:
        result.add(item["action_timing"]["turn_id"])
    return result


def _action_ids(item: ActionItem | None, evidence: dict[str, Any]) -> set[str]:
    if item is None:
        return set()
    # Match the saved item, so a citation on a different task cannot satisfy it.
    matches = [
        row
        for row in evidence.get("action_items", [])
        if row.get("task") == item.task and row.get("owner") == item.owner
    ]
    return _ids(matches[0]) if len(matches) == 1 else set()


def _decision_ids(text: str, evidence: dict[str, Any]) -> set[str]:
    matches = [row for row in evidence.get("decisions", []) if row.get("text") == text]
    return _ids(matches[0]) if len(matches) == 1 else set()


def _rotation(text: str) -> bool:
    return any(word in text for word in ("rotation", "on-call", "on call"))


def _scheduling(case: str, summary: Summary, evidence: dict[str, Any]) -> dict[str, bool]:
    person, absent = ("dan", "monday") if case == "golden" else ("alex", "wednesday")
    decisions = [text.lower() for text in summary.decisions]
    cutover = _one(summary, lambda text: "cutover" in text)
    billing = _one(summary, lambda text: "billing" in text)
    finance = _one(summary, lambda text: "finance" in text)
    rotation = _one(summary, _rotation)
    mine = [item for item in summary.action_items if item.owner == "Sam"]
    items = (cutover, billing, finance, rotation)
    result = {
        "decisions.count": len(decisions) == 2,
        "decisions.migration": any("write" in text for text in decisions),
        "decisions.rotation": any(_rotation(text) for text in decisions),
        "decisions.rotation_scope": any(
            _rotation(text)
            and "month" in text
            and bool(re.search(r"unchanged|defer|keep|not.{0,20}chang|no.{0,20}chang", text))
            for text in decisions
        ),
        "decisions.original_time_scope": not any(
            re.search(r"\buntil\s+(?:(?:the|next)\s+)*planning\b", text) for text in decisions
        ),
        "actions.count": len(summary.action_items) == 4,
        "actions.independent_tasks": len({item.task for item in items if item is not None}) == 4,
        "actions.sam_count": len(mine) == 3,
        "actions.cutover": cutover is not None and "plan" in _text(cutover),
        "actions.cutover_owner": cutover is not None and cutover.owner == "Priya",
        "actions.priya_count": sum(item.owner == "Priya" for item in summary.action_items) == 1,
        "actions.billing": person in _text(billing)
        and bool(
            re.search(r"\b(talk|speak|discuss|contact|coordinate|ask|check)\b", _text(billing))
        ),
        "actions.billing_owner": billing is not None and billing.owner == "Sam",
        "actions.finance": finance is not None,
        "actions.finance_owner": finance is not None and finance.owner == "Sam",
        "actions.finance_uncertainty": bool(
            re.search(r"\b(possible|potential|might|may|possibility)\b", _text(finance))
        ),
        "actions.rotation": rotation is not None,
        "actions.rotation_owner": rotation is not None and rotation.owner == "Sam",
        "timing.cutover": _due(cutover, "thursday"),
        "timing.billing": _due(billing, None),
        "timing.billing_absence": billing is not None and absent not in _text(billing),
        "timing.finance": _due(finance, None),
        "timing.rotation": rotation is not None
        and "planning" in f"{rotation.task} {rotation.due or ''}".lower(),
        "timing.rotation_deadline": _due(rotation, "planning"),
        "references.cutover_request": "t9" in _action_ids(cutover, evidence),
        "references.cutover_acceptance": "t10" in _action_ids(cutover, evidence),
        "references.billing": "t11" in _action_ids(billing, evidence),
        "references.finance": "t11" in _action_ids(finance, evidence),
        "references.rotation": "t13" in _action_ids(rotation, evidence),
        "references.decisions": bool(summary.decisions)
        and all(
            ("t9" if "write" in text.lower() else "t13") in _decision_ids(text, evidence)
            for text in summary.decisions
        ),
    }
    return result


def _has_amount(sentence: str, amount: int) -> bool:
    return any(value in (amount, amount * 1000) for _, value in numbers(sentence))


def _pricing(summary: Summary, evidence: dict[str, Any]) -> dict[str, bool]:
    item = _one(summary, lambda text: "procurement" in text)
    task = _text(item)
    sentences = [
        summary.overview,
        *summary.key_points,
        *summary.decisions,
        *(f"{action.owner} {action.task} {action.due or ''}" for action in summary.action_items),
    ]
    result = {
        "decisions.none": summary.decisions == [],
        "actions.count": len(summary.action_items) == 1,
        "actions.procurement": item is not None,
        "actions.owner": item is not None and item.owner == "Nadia",
        "actions.report_back": bool(re.search(r"\bsam\b", task))
        and bool(
            re.search(
                r"\b(?:get|report|write|come|respond|reply)\s+back\b"
                r"|\b(?:give|provide|send|share|relay|return|report|deliver)\b.{0,60}"
                r"\b(?:feedback|updates?|responses?|findings|outcomes?|results?)\b"
                r"|\b(?:update|inform|notify)\s+sam\b|\bfollow\s+up\s+with\s+sam\b",
                task,
            )
        ),
        "timing.follow_up": _due(item, "this week"),
        "references.request": "t11" in _action_ids(item, evidence),
        "references.acceptance": "t12" in _action_ids(item, evidence),
        "numbers.unsaid_retainer": not any(_has_amount(sentence, 30) for sentence in sentences),
        "numbers.total_range": all(
            _has_amount(sentence, 120)
            for sentence in sentences
            if _has_amount(sentence, 80)
            and any(word in sentence.lower() for word in ("total", "all in", "all-in"))
        ),
        "qualifications.feasible_amount": all(
            not any(word in sentence.lower() for word in ("max", "at most", "limit"))
            for sentence in sentences
            if _has_amount(sentence, 70)
        ),
        "qualifications.budget": all(
            "probably" in sentence.lower() for sentence in sentences if _has_amount(sentence, 100)
        ),
    }
    for speaker, amounts in (("Sam", (120, 80)), ("Nadia", (40, 100, 70))):
        for amount in amounts:
            result[f"numbers.attribution_{amount}"] = all(
                speaker in sentence for sentence in sentences if _has_amount(sentence, amount)
            )
    return result


def _conditional(summary: Summary, evidence: dict[str, Any]) -> dict[str, bool]:
    publish = _one(summary, lambda text: "publish" in text)
    report = _one(summary, lambda text: "risk" in text)
    task = _text(publish)
    return {
        "decisions.none": summary.decisions == [],
        "actions.count": len(summary.action_items) == 2,
        "actions.publish": publish is not None,
        "actions.publish_owner": publish is not None and publish.owner == "Sam",
        "actions.condition": "security" in task
        and "approv" in task
        and bool(re.search(r"\b(if|upon|when|once|provided|pending|subject to|after)\b", task)),
        "actions.report": report is not None and "report" in _text(report),
        "actions.unknown_owner": report is not None and report.owner is None,
        "timing.publish": _due(publish, "friday"),
        "timing.report": _due(report, None),
        "references.publish": "t1" in _action_ids(publish, evidence),
        "references.report": "t2" in _action_ids(report, evidence),
    }


def _timing(summary: Summary, evidence: dict[str, Any]) -> dict[str, bool]:
    result = {
        "decisions.none": summary.decisions == [],
        "actions.count": len(summary.action_items) == 5,
    }
    for person, work, due, source in (
        ("morgan", "pilot", None, "t1"),
        ("lee", "audit", "wednesday", "t2"),
        ("casey", "rota", None, "t3"),
        ("jordan", "patch", None, "t4"),
        ("taylor", "campaign", "monday", "t5"),
    ):
        item = _one(summary, lambda text, person=person: person in text)
        task = _text(item)
        result[f"actions.{person}"] = work in task and any(
            verb in task for verb in ("talk", "contact", "ask", "speak", "discuss", "message")
        )
        result[f"actions.{person}_owner"] = item is not None and item.owner == "Sam"
        result[f"timing.{person}"] = _due(item, due)
        result[f"references.{person}"] = source in _action_ids(item, evidence)
    return result


def _requests(summary: Summary, evidence: dict[str, Any]) -> dict[str, bool]:
    result = {
        "decisions.none": summary.decisions == [],
        "actions.count": len(summary.action_items) == 2,
    }
    for work, due, request, acceptance in (
        ("checklist", "thursday", "t1", "t2"),
        ("guide", "planning", "t3", "t6"),
    ):
        item = _one(summary, lambda text, work=work: work in text)
        result[f"actions.{work}"] = item is not None
        result[f"actions.{work}_owner"] = item is not None and item.owner == "Riley"
        result[f"timing.{work}"] = _due(item, due)
        result[f"references.{work}_request"] = request in _action_ids(item, evidence)
        result[f"references.{work}_acceptance"] = acceptance in _action_ids(item, evidence)
        if work == "guide":
            result["actions.guide_scope"] = "rollback" in _text(item)
            result["references.guide_scope"] = "t5" in _action_ids(item, evidence)
    return result


def score(case: str, summary: Summary, evidence: dict[str, Any]) -> dict[str, bool]:
    """Score each property independently; structural validation belongs to the runner."""
    if case in ("golden", "availability"):
        return _scheduling(case, summary, evidence)
    if case == "numbers":
        return _pricing(summary, evidence)
    if case == "no_commitments":
        return {
            "decisions.none": summary.decisions == [],
            "actions.none": summary.action_items == [],
        }
    if case == "conditional_commitments":
        return _conditional(summary, evidence)
    if case == "timing_roles":
        return _timing(summary, evidence)
    if case == "accepted_requests":
        return _requests(summary, evidence)
    raise ValueError(f"Unknown commitments fixture: {case}")
