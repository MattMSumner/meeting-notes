import pytest

from meeting_notes.commitments import commitment_texts, verify_commitments
from meeting_notes.figures import unsaid_numbers_in
from meeting_notes.summary import Commitments, ExtractedAction, ExtractedDecision, SummaryError
from meeting_notes.turns import parse_turns

TURNS = parse_turns(
    "[00:00:00] Sam: Let's keep the release date. I'll tell support and update the plan.\n"
    "[00:00:01] Them: Agreed."
)


def test_distinct_actions_and_a_decision_can_share_source_turns():
    result = Commitments(
        decisions=[ExtractedDecision(text="Keep the release date.", turn_ids=["t1", "t2"])],
        action_items=[
            ExtractedAction(owner="Sam", task=task, due=None, turn_ids=["t1"])
            for task in ("Tell support", "Update the plan")
        ],
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
            ExtractedAction(owner="Sam", task="Tell support", due=due, turn_ids=["t1"])
            for due in (None, None, "Friday")
        ],
    )

    verify_commitments(result, TURNS)

    assert [item.turn_ids for item in result.decisions] == [["t1", "t2"]]
    assert [item.due for item in result.action_items] == [None, "Friday"]


def test_unknown_evidence_ids_are_rejected():
    result = Commitments(
        decisions=[],
        action_items=[ExtractedAction(owner=None, task="Check", due=None, turn_ids=["t99"])],
    )

    with pytest.raises(SummaryError, match="Unknown turn IDs: t99"):
        verify_commitments(result, TURNS)


def test_reference_numbers_cannot_authorize_or_trigger_number_corrections():
    result = Commitments(
        decisions=[ExtractedDecision(text="Spend 90.", turn_ids=["t90"])],
        action_items=[],
    )
    assert unsaid_numbers_in(commitment_texts(result), "Spend seventy.") == ["90"]
    result.decisions[0].text = "Spend seventy."
    assert unsaid_numbers_in(commitment_texts(result), "Spend seventy.") == []
