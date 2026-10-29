import pytest

from meeting_notes.commitments import (
    action_item,
    action_turn_ids,
    commitment_texts,
    verify_commitments,
)
from meeting_notes.figures import unsaid_numbers_in
from meeting_notes.summary import Commitments, ExtractedAction, ExtractedDecision, SummaryError
from meeting_notes.turns import parse_turns

TURNS = parse_turns(
    "[00:00:00] Sam: Let's keep the release date. "
    "I'll tell support by Friday about work starting Monday.\n"
    "[00:00:01] Them: Agreed.\n"
    "[00:00:02] Sam: Can you update the plan?\n"
    "[00:00:03] Them: Yep, I'll have it ready Thursday."
)
TIMING = {
    "turn_id": "t1",
    "quote": "I'll tell support by Friday about work starting Monday.",
    "value": "by Friday",
}
RELATED = {**TIMING, "value": "Monday"}


def action(**fields: object) -> ExtractedAction:
    return ExtractedAction.model_validate(
        {
            "kind": "promise",
            "commitment_turn_ids": ["t1"],
            "request_turn_ids": [],
            "context_turn_ids": [],
            "related_timing": [],
            "action_timing": None,
            "owner": "Sam",
            "task": "Tell support about work starting Monday",
            **fields,
        }
    )


def verify(*items: ExtractedAction) -> Commitments:
    result = Commitments(decisions=[], action_items=list(items))
    verify_commitments(result, TURNS)
    return result


def test_distinct_actions_and_a_decision_can_share_source_turns():
    result = Commitments(
        decisions=[ExtractedDecision(text="Keep the release date.", turn_ids=["t1", "t2"])],
        action_items=[action(task=task) for task in ("Tell support", "Update the plan")],
    )
    verify_commitments(result, TURNS)
    assert len(result.decisions) == 1
    assert [item.task for item in result.action_items] == ["Tell support", "Update the plan"]


def test_normalizes_repeated_ids_and_removes_only_exact_duplicate_records():
    result = Commitments(
        decisions=[
            ExtractedDecision(text="Keep the release date.", turn_ids=ids)
            for ids in (["t2", "t1", "t2"], ["t1", "t2"])
        ],
        action_items=[
            action(commitment_turn_ids=ids, related_timing=related)
            for ids, related in (
                (["t2", "t1", "t2"], [RELATED, RELATED]),
                (["t1", "t2"], [RELATED]),
            )
        ]
        + [action(action_timing=TIMING, related_timing=[RELATED])],
    )
    verify_commitments(result, TURNS)
    assert [item.turn_ids for item in result.decisions] == [["t1", "t2"]]
    assert len(result.action_items) == 2
    assert result.action_items[0].commitment_turn_ids == ["t1", "t2"]
    assert len(result.action_items[0].related_timing) == 1
    assert [action_item(item).due for item in result.action_items] == [None, "by Friday"]


def test_only_the_action_schedule_becomes_a_deadline():
    [item] = verify(action(action_timing=TIMING, related_timing=[RELATED])).action_items
    saved = action_item(item)
    assert saved.due == "by Friday" and "Monday" in saved.task
    assert set(saved.model_dump()) == {"owner", "task", "due"}
    assert action_item(action(related_timing=[RELATED])).due is None


def test_request_acceptance_context_and_timing_all_contribute_references():
    item = action(
        kind="accepted_request",
        commitment_turn_ids=["t4"],
        request_turn_ids=["t3"],
        context_turn_ids=["t2"],
        related_timing=[RELATED],
    )
    [verified] = verify(item).action_items
    assert action_turn_ids(verified) == {"t1", "t2", "t3", "t4"}
    assert verified.commitment_turn_ids == ["t4"]
    assert verified.request_turn_ids == ["t3"]
    assert verified.context_turn_ids == ["t2"]


@pytest.mark.parametrize(
    "fields",
    [
        {"commitment_turn_ids": ["t99"]},
        {"kind": "accepted_request", "request_turn_ids": ["t99"]},
        {"context_turn_ids": ["t99"]},
        {"action_timing": {**TIMING, "turn_id": "t99"}},
        {"related_timing": [{**RELATED, "turn_id": "t99"}]},
    ],
)
def test_unknown_ids_are_rejected_in_every_evidence_role(fields: dict[str, object]):
    with pytest.raises(SummaryError, match="Unknown turn IDs: t99"):
        verify(action(**fields))


@pytest.mark.parametrize("field", ["action_timing", "related_timing"])
@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"turn_id": "t2"}, "quote was not found verbatim in t2"),
        ({"quote": "I'll call support by Friday."}, "quote was not found verbatim"),
        ({"value": "by Thursday"}, "value was not found verbatim"),
        (
            {"quote": "i'll tell support by friday about work starting monday."},
            "quote was not found",
        ),
    ],
)
def test_timing_must_be_copied_from_its_exact_source(
    field: str,
    changes: dict[str, str],
    reason: str,
):
    timing = {**TIMING, **changes}
    with pytest.raises(SummaryError, match=reason):
        verify(action(**{field: [timing] if field == "related_timing" else timing}))


def test_whitespace_can_differ_without_changing_the_source_words():
    timing = {**TIMING, "quote": TIMING["quote"].replace(" ", "\n "), "value": " by\tFriday "}
    [item] = verify(action(action_timing=timing)).action_items
    assert item.action_timing is not None
    assert item.action_timing.quote == TIMING["quote"]
    assert action_item(item).due == "by Friday"


def test_validation_does_not_add_neighboring_turns():
    [item] = verify(action(commitment_turn_ids=["t4"])).action_items
    assert action_turn_ids(item) == {"t4"}


def test_internal_evidence_does_not_trigger_number_corrections():
    item = action(
        related_timing=[{"turn_id": "t90", "quote": "Work starts in 90 days.", "value": "90 days"}],
        task="Check the plan",
    )
    result = Commitments(decisions=[], action_items=[item])
    assert commitment_texts(result) == ["Check the plan "]
    assert unsaid_numbers_in(commitment_texts(result), "Check the plan.") == []


def test_number_checks_use_the_same_deadline_as_saved_actions():
    item = action(
        action_timing={"turn_id": "t1", "quote": "I'll check in 90 days.", "value": "90 days"},
        task="Check the plan",
    )
    result = Commitments(decisions=[], action_items=[item])
    assert action_item(item).due == "90 days"
    assert unsaid_numbers_in(commitment_texts(result), "Check in seventy days.") == ["90"]


def test_reference_numbers_cannot_authorize_numbers_in_decisions():
    result = Commitments(
        decisions=[ExtractedDecision(text="Spend 90.", turn_ids=["t90"])],
        action_items=[],
    )
    assert unsaid_numbers_in(commitment_texts(result), "Spend seventy.") == ["90"]
    result.decisions[0].text = "Spend seventy."
    assert unsaid_numbers_in(commitment_texts(result), "Spend seventy.") == []
