"""Authored V11 candidates; unchanged V10 replies are tested separately below."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from meeting_notes.commitments_v11 import check
from meeting_notes.comparison_v11 import Comparison
from meeting_notes.compiler_v11 import validate
from meeting_notes.contract_v11 import Action, Draft
from meeting_notes.spans_v11 import Anchor, Source, snapshot


def candidate(source: Source, *, uncertain: bool = False) -> Action:
    return Action(
        original_commitment_id=source.id,
        undertaking=Anchor(source_id=source.id, quote=source.text),
        context=[],
        basis="explicit",
        disposition="uncertain" if uncertain else "committed",
        timing=None,
    )


@pytest.mark.parametrize(
    "text",
    [
        "The service costs 275 dollars.",
        "The draft is ready.",
        "I already reviewed the draft.",
        "I will be away Friday.",
        "The price will increase next week.",
        "Could I review the draft?",
        "Maybe we should review the draft.",
        "I will not review the draft.",
        "I won't send the invoice.",
        "I am not committing to send the invoice.",
        "I did not say I will send the invoice.",
        "Example: I will send the invoice.",
        "The phrase is 'I will send the invoice.'",
        'For example, "I will send the invoice."',
        "The quoted example is “I will send the invoice.”",
    ],
)
def test_known_noncommitment_forms_cannot_be_admitted(text: str) -> None:
    sources = snapshot(f"[0:00:01] Mira: {text}").sources
    result = check(candidate(sources[0]), sources)
    assert result.disposition == "rejected"
    assert result.reasons


@pytest.mark.parametrize(
    ("text", "owner"),
    [
        ("I will send the invoice.", "Mira"),
        ("I'll compile the report.", "Mira"),
        ("Ravi will review the draft.", "Ravi"),
        ("Ravi has agreed to review the draft.", "Ravi"),
        ("Leave the invoice to me.", "Mira"),
        ("Leave the invoice with me.", "Mira"),
        ("The invoice is on me.", "Mira"),
        ("I will send the invoice and review the draft.", "Mira"),
        ("I will send the invoice and Ravi will review the draft.", None),
        ("If approval arrives, I will send the invoice.", "Mira"),
        ("If approval does not arrive, I will send the reminder.", "Mira"),
        ("Unless approval arrives, I will send the reminder.", "Mira"),
        ("Unless approval does not arrive, I will send the reminder.", "Mira"),
        ("I will send the invoice unless approval does not arrive.", "Mira"),
    ],
)
def test_recognized_undertakings_keep_complete_conditions(text: str, owner: str | None) -> None:
    sources = snapshot(f"[0:00:01] Mira: {text}").sources
    result = check(candidate(sources[0]), sources)
    assert result.disposition == "admissible", result.reasons
    assert result.task == text
    assert result.owner == owner


def test_declared_basis_and_disposition_do_not_prove_a_commitment() -> None:
    sources = snapshot("[0:00:01] Mira: The deployment is green.").sources
    action = candidate(sources[0])
    action.basis = "third-person"
    result = check(action, sources)
    assert result.disposition != "admissible"


def test_unrecognized_and_model_uncertain_candidates_remain_review() -> None:
    for text, uncertain in [
        ("I can help with the report.", False),
        ("I will send the invoice.", True),
    ]:
        sources = snapshot(f"[0:00:01] Mira: {text}").sources
        assert check(candidate(sources[0], uncertain=uncertain), sources).disposition == "uncertain"


@pytest.mark.parametrize(
    ("later", "speaker", "retracted"),
    [
        ("Scratch that.", "Mira", True),
        ("That was just an example.", "Mira", True),
        ("I am not committing to that.", "Mira", True),
        ("I will not review the Friday draft.", "Mira", True),
        ("I will not review the Friday logs.", "Mira", False),
        ("I will not send the Friday draft.", "Mira", False),
        ("I will not review the Friday draft.", "Ravi", False),
        ("Scratch that.", "Ravi", False),
        ("For example, the logs include warnings.", "Mira", False),
        ("If I cannot review the Friday draft, I will ask for help.", "Mira", False),
    ],
)
def test_retractions_require_same_speaker_and_same_task(
    later: str,
    speaker: str,
    retracted: bool,
) -> None:
    sources = snapshot(
        f"[0:00:01] Mira: I will review the Friday draft.\n[0:00:02] {speaker}: {later}"
    ).sources
    result = check(candidate(sources[0]), sources)
    assert (result.disposition == "rejected") == retracted
    assert bool(result.retractions) == retracted


def test_retraction_can_follow_intervening_speaker_without_canceling_unrelated_task() -> None:
    sources = snapshot(
        "[0:00:01] Mira: I will review the draft. I will send the invoice.\n"
        "[0:00:02] Ravi: The room is ready.\n"
        "[0:00:03] Mira: I won't review the draft."
    ).sources
    assert check(candidate(sources[0]), sources).disposition == "rejected"
    assert check(candidate(sources[1]), sources).disposition == "admissible"


@pytest.mark.parametrize(("actor", "retracted"), [("Ravi", True), ("I", False)])
def test_third_person_retraction_cannot_cancel_another_actors_task(
    actor: str, retracted: bool
) -> None:
    sources = snapshot(
        "[0:00:01] Mira: Ravi will send the invoice.\n"
        f"[0:00:02] Mira: {actor} will not send the invoice."
    ).sources
    result = check(candidate(sources[0]), sources)
    assert (result.disposition == "rejected") == retracted


def test_accepted_request_requires_exact_prior_context() -> None:
    sources = snapshot("[0:00:01] Ravi: Could you send the invoice?\n[0:00:02] Mira: Yes.").sources
    action = candidate(sources[1])
    action.basis = "accepted-request"
    assert check(action, sources).disposition == "uncertain"
    action.context = [Anchor(source_id=sources[0].id, quote=sources[0].text)]
    result = check(action, sources)
    assert result.disposition == "admissible"
    assert result.owner == "Mira"
    assert result.task == f"Request: {sources[0].text} Acceptance: {sources[1].text}"


@pytest.mark.parametrize(
    "introduction", ["Alex here.", "I am Alex.", "I'm Alex.", "This is Alex.", "My name is Alex."]
)
def test_owner_uses_unique_same_turn_same_speaker_introduction(introduction: str) -> None:
    sources = snapshot(f"[00:00:00] Them: {introduction} I will check rollback.").sources
    action = candidate(sources[1])
    action.context = [Anchor(source_id="T1", quote=sources[0].text)]
    result = check(action, sources)
    assert result.disposition == "admissible"
    assert result.owner == "Alex"
    assert result.owner_evidence[0].source_id == "T1"
    response = Draft(
        overview=[], key_points=[], decisions=[], action_items=[action], timing_updates=[]
    )
    compiled = validate(response, sources, Comparison(claims=[]))
    assert compiled.summary
    assert compiled.summary.action_items[0].owner == "Alex"


@pytest.mark.parametrize(
    "text",
    [
        "[00:00:00] Them: Alex here. This is Ravi. I will check rollback.",
        "[00:00:00] Them: Alex here.\n[00:00:01] Them: I will check rollback.",
        "[00:00:00] Mira: Alex here.\n[00:00:01] Them: I will check rollback.",
    ],
)
def test_ambiguous_or_other_turn_introductions_do_not_assign_owner(text: str) -> None:
    sources = snapshot(text).sources
    assert check(candidate(sources[-1]), sources).owner == "Them"


def test_undertaking_cannot_drop_negation_or_conditions() -> None:
    sources = snapshot("[0:00:01] Mira: Unless approval arrives, I will send the invoice.").sources
    action = candidate(sources[0])
    action.undertaking.quote = "I will send the invoice"
    result = check(action, sources)
    assert result.disposition == "rejected"
    assert any("qualifiers" in reason for reason in result.reasons)


def test_authored_new_contract_rejects_saved_factual_action_selection() -> None:
    path = Path(__file__).parents[1] / "evaluation/m10/v10/results/proposed.jsonl"
    row = next(
        json.loads(line)
        for line in path.read_text().splitlines()
        if json.loads(line).get("case") == "unit_disagreement"
    )
    sources = [Source.model_validate(value) for value in row["audit"]["passages"]]
    original = next(s for s in sources if s.id == "T1")
    # Authored NEW-contract evidence deliberately claims this exact fact is committed.
    action = candidate(original)
    assert action.disposition == "committed" and action.basis == "explicit"
    assert action.undertaking.quote == original.text
    result = check(action, sources)
    assert result.disposition == "rejected"
    assert "Descriptive fact" in " ".join(result.reasons)
    authored = Draft(
        overview=[], key_points=[], decisions=[], action_items=[action], timing_updates=[]
    )
    compiled = validate(authored, [original], Comparison(claims=[]))
    assert compiled.summary is None
    assert any("Noncommitment T1" in error for error in compiled.blocking)


def test_unchanged_old_reply_is_unmappable_separately_from_admissibility() -> None:
    path = Path(__file__).parents[1] / "evaluation/m10/v10/results/proposed.jsonl"
    row = next(
        json.loads(line)
        for line in path.read_text().splitlines()
        if json.loads(line).get("case") == "unit_disagreement"
    )
    # This is structural replay only, not evidence that the diagnostic was repaired.
    for attempt in row["audit"]["attempts"]:
        with pytest.raises(ValidationError):
            Draft.model_validate_json(attempt["reply"])
