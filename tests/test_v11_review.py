"""Synthetic regressions from the independent V11 core review; no inference."""

import pytest

from meeting_notes.commitments_v11 import check
from meeting_notes.comparison_v11 import Comparison
from meeting_notes.compiler_v11 import Evidence, correction_errors, replay, validate
from meeting_notes.contract_v11 import Action, Draft, SupportedText, TimingUpdate
from meeting_notes.spans_v11 import Anchor, Source, resolve, snapshot


def action(source: Source, request: Source | None = None) -> Action:
    return Action(
        original_commitment_id=source.id,
        undertaking=Anchor(source_id=source.id, quote=source.text),
        context=[Anchor(source_id=request.id, quote=request.text)] if request else [],
        basis="accepted-request" if request else "explicit",
        disposition="committed",
        timing=None,
    )


def draft(*actions: Action) -> Draft:
    return Draft(
        overview=[], key_points=[], decisions=[], action_items=list(actions), timing_updates=[]
    )


@pytest.mark.parametrize(
    ("request_text", "admitted"),
    [
        ("Will you be away Friday?", False),
        ("Could you be ready Friday?", False),
        ("Can you see the invoice?", False),
        ("Would you like to send the invoice?", False),
        ("Will you have sent the invoice by Friday?", False),
        ("Could you not send the invoice?", False),
        ("For example, could you send the invoice?", False),
        ("Could you send the invoice?", True),
        ("Will you review the draft?", True),
        ("Can you please check the logs?", True),
        ("Please send the invoice.", True),
    ],
)
def test_acceptance_requires_a_source_task_request(request_text: str, admitted: bool) -> None:
    saved = snapshot(f"[0:00:01] Mira: {request_text}\n[0:00:02] Ravi: Yes.")
    response = draft(action(saved.sources[1], saved.sources[0]))
    result = validate(response, saved, Comparison(claims=[]))
    assert result.summary and not result.blocking
    candidate = result.evidence.commitments[0]
    assert (candidate.disposition == "admissible") == admitted
    assert bool(result.summary.action_items) == admitted
    assert candidate.context[0].text == request_text
    if admitted:
        assert result.summary.action_items[0].owner == "Ravi"
        assert result.summary.action_items[0].task == f"Request: {request_text} Acceptance: Yes."
    else:
        assert candidate.disposition == "uncertain"
        assert request_text in " ".join(result.warnings)
        assert "Yes." in " ".join(result.warnings)


@pytest.mark.parametrize("context", ["partial", "later", "notes", "absent"])
def test_acceptance_cannot_use_invalid_or_incomplete_request_context(context: str) -> None:
    saved = snapshot(
        "[0:00:01] Mira: Could you send the invoice if approval arrives?\n"
        "[0:00:02] Ravi: Yes.\n[0:00:03] Mira: Could you send the invoice?",
        "Could you send the invoice?",
    )
    accepted = action(saved.sources[1], saved.sources[0])
    if context == "partial":
        accepted.context[0].quote = "Could you send the invoice"
    elif context == "later":
        accepted.context = [Anchor(source_id="T3", quote=saved.sources[2].text)]
    else:
        accepted.context[0].source_id = "N1" if context == "notes" else "T99"
    candidate = check(accepted, saved.sources)
    assert candidate.disposition != "admissible"


@pytest.mark.parametrize(
    ("later", "speaker", "retracted"),
    [
        ("I will not send the invoice.", "Ravi", True),
        ("I won't send an invoice.", "Ravi", True),
        ("I will not send the invoice by Friday.", "Ravi", True),
        ("I will not send the report.", "Ravi", False),
        ("I will not review the invoice.", "Ravi", False),
        ("Mira will not send the invoice.", "Ravi", False),
        ("I will not send the invoice.", "Mira", False),
        ("If I cannot send the invoice, I will ask for help.", "Ravi", False),
    ],
)
def test_accepted_request_retraction_uses_requested_task_and_accepting_speaker(
    later: str, speaker: str, retracted: bool
) -> None:
    saved = snapshot(
        "[0:00:01] Mira: Could you send the invoice?\n[0:00:02] Ravi: Yes.\n"
        f"[0:00:03] {speaker}: {later}"
    )
    candidate = check(action(saved.sources[1], saved.sources[0]), saved.sources)
    assert (candidate.disposition == "rejected") == retracted
    assert bool(candidate.retractions) == retracted
    if retracted:
        assert candidate.retractions[0].text == later


def test_correction_can_drop_retracted_acceptance_but_must_keep_independent_task() -> None:
    saved = snapshot(
        "[0:00:01] Mira: Could you send the invoice?\n[0:00:02] Ravi: Yes.\n"
        "[0:00:03] Ravi: I will not send the invoice. I will review the draft."
    )
    accepted = action(saved.sources[1], saved.sources[0])
    independent = action(saved.sources[3])
    previous = validate(draft(accepted, independent), saved, Comparison(claims=[]))
    assert previous.summary is None
    assert previous.evidence.commitments[0].disposition == "rejected"
    current = validate(draft(independent), saved, Comparison(claims=[]))
    assert current.summary and len(current.summary.action_items) == 1
    assert correction_errors(previous, current) == []
    removed = draft()
    removed.overview = [SupportedText(text="The invoice was retracted.", sources=["T3"])]
    errors = correction_errors(previous, validate(removed, saved, Comparison(claims=[])))
    assert any("lost admissible commitment/timing: T4" in error for error in errors)
    assert not any("lost admissible commitment/timing: T2" in error for error in errors)


def test_cancellation_prefix_preserves_the_following_independent_undertaking() -> None:
    saved = snapshot(
        "[0:00:01] Mira: I will review the draft. Scratch that, I will send the invoice."
    )
    previous = validate(draft(*(action(s) for s in saved.sources)), saved, Comparison(claims=[]))
    assert previous.evidence.commitments[0].disposition == "rejected"
    assert previous.evidence.commitments[1].disposition == "admissible"
    current = validate(draft(action(saved.sources[1])), saved, Comparison(claims=[]))
    assert current.summary
    assert current.summary.action_items[0].task == saved.sources[1].text
    assert correction_errors(previous, current) == []
    omitted = validate(draft(), saved, Comparison(claims=[]))
    assert any("omitted commitment: T2" in error for error in omitted.blocking)
    assert any(
        "lost admissible commitment/timing: T2" in e for e in correction_errors(current, omitted)
    )


@pytest.mark.parametrize("selected", [True, False])
@pytest.mark.parametrize(
    "retraction",
    ["I will not review the draft.", "I will not send the invoice."],
)
def test_partial_cancellation_retains_full_review_even_when_model_omits_it(
    selected: bool, retraction: str
) -> None:
    saved = snapshot(
        "[0:00:01] Mira: I will review the draft and send the invoice.\n"
        f"[0:00:02] Mira: {retraction}"
    )
    response = draft(action(saved.sources[0])) if selected else draft()
    result = validate(response, saved, Comparison(claims=[]))
    assert result.summary and not result.summary.action_items and not result.blocking
    assert saved.sources[0].text in " ".join(result.warnings)
    assert retraction in " ".join(result.warnings)
    candidate = result.evidence.commitments[0]
    assert candidate.disposition == "uncertain"
    assert candidate.undertaking and candidate.undertaking.text == saved.sources[0].text
    assert candidate.retractions[0].text == retraction
    restored = Evidence.model_validate_json(result.evidence.model_dump_json())
    assert replay(restored) == result


@pytest.mark.parametrize("selected", [True, False])
def test_partial_cancellation_of_accepted_coordination_cannot_disappear(selected: bool) -> None:
    saved = snapshot(
        "[0:00:01] Mira: Could you review the draft and send the invoice?\n"
        "[0:00:02] Ravi: Yes.\n[0:00:03] Ravi: I will not send the invoice."
    )
    response = draft(action(saved.sources[1], saved.sources[0])) if selected else draft()
    result = validate(response, saved, Comparison(claims=[]))
    assert result.summary and not result.summary.action_items
    assert saved.sources[0].text in " ".join(result.warnings)
    assert saved.sources[2].text in " ".join(result.warnings)
    assert result.evidence.commitments[0].disposition == "uncertain"


def test_correction_omitting_partial_cancellation_keeps_its_review_evidence() -> None:
    saved = snapshot(
        "[0:00:01] Mira: I will review the draft and I will send the invoice.\n"
        "[0:00:02] Mira: I will not send the invoice."
    )
    previous = validate(draft(action(saved.sources[0])), saved, Comparison(claims=[]))
    current = validate(draft(), saved, Comparison(claims=[]))
    assert previous.summary and current.summary
    assert not current.summary.action_items
    assert current.warnings == previous.warnings
    assert current.evidence.commitments == previous.evidence.commitments
    assert correction_errors(previous, current) == []


def test_within_source_cancellation_retains_full_review_without_rewriting_tasks() -> None:
    saved = snapshot(
        "[0:00:01] Mira: I will review the draft, scratch that, I will send the invoice."
    )
    result = validate(draft(), saved, Comparison(claims=[]))
    assert result.summary and not result.summary.action_items
    assert saved.sources[0].text in " ".join(result.warnings)
    assert result.evidence.commitments[0].disposition == "uncertain"


@pytest.mark.parametrize(
    "retraction",
    ["I will not review the draft and send the invoice.", "Scratch that."],
)
def test_whole_coordination_cancellation_can_be_removed_by_correction(retraction: str) -> None:
    saved = snapshot(
        "[0:00:01] Mira: I will review the draft and send the invoice.\n"
        f"[0:00:02] Mira: {retraction}\n[0:00:03] Ravi: The room is ready."
    )
    previous = validate(draft(action(saved.sources[0])), saved, Comparison(claims=[]))
    assert previous.evidence.commitments[0].disposition == "rejected"
    response = draft()
    response.overview = [SupportedText(text="The room is ready.", sources=["T3"])]
    current = validate(response, saved, Comparison(claims=[]))
    assert current.summary and not current.summary.action_items
    assert correction_errors(previous, current) == []


@pytest.mark.parametrize(
    ("later", "speaker"),
    [
        ("I will not review the logs.", "Mira"),
        ("I will not send the report.", "Mira"),
        ("I will not review the draft.", "Ravi"),
        ("Ravi will not review the draft.", "Mira"),
    ],
)
def test_unrelated_retraction_does_not_demote_a_coordination(later: str, speaker: str) -> None:
    saved = snapshot(
        "[0:00:01] Mira: I will review the draft and send the invoice.\n"
        f"[0:00:02] {speaker}: {later}"
    )
    result = validate(draft(action(saved.sources[0])), saved, Comparison(claims=[]))
    assert result.summary and len(result.summary.action_items) == 1
    assert not result.evidence.commitments[0].retractions


@pytest.mark.parametrize("route", ["action", "update"])
def test_external_timing_review_keeps_selected_span_and_complete_source(route: str) -> None:
    saved = snapshot(
        "[0:00:01] Mira: I will send the invoice.\n"
        "[0:00:02] Ravi: Not before next Friday unless finance objects."
    )
    response = draft(action(saved.sources[0]))
    anchor = Anchor(source_id="T2", quote="Friday")
    if route == "action":
        response.action_items[0].timing = anchor
    else:
        response.timing_updates = [TimingUpdate(original_commitment_id="T1", evidence=[anchor])]
    result = validate(response, saved, Comparison(claims=[]))
    assert result.summary
    item = result.summary.action_items[0]
    assert item.due is None
    assert saved.sources[1].text in " ".join(item.review)
    evidence = result.evidence
    selected = (
        evidence.commitments[0].timing if route == "action" else evidence.timing_updates[0].span
    )
    assert selected and selected.text == "Friday"
    assert selected.start == saved.sources[1].text.index("Friday")
    assert selected.end == selected.start + len("Friday")
    complete = next(s for s in evidence.snapshot.sources if s.id == selected.source_id)
    assert complete.text == "Not before next Friday unless finance objects."
    restored = Evidence.model_validate_json(evidence.model_dump_json())
    assert replay(restored) == result
    restored.snapshot.sources[1].text = "Friday"
    assert replay(restored).summary is None


@pytest.mark.parametrize(
    "timing",
    [
        "around Friday",
        "no sooner than Friday",
        "shortly after Friday",
        "very shortly after Friday",
        "well after Friday",
        "a bit before Friday",
        "late Friday",
        "at the earliest Friday",
        "on or after Friday",
    ],
)
def test_qualified_timing_is_never_published_as_an_unqualified_due(timing: str) -> None:
    saved = snapshot(f"[0:00:01] Mira: I will send the invoice {timing}.")
    response = draft(action(saved.sources[0]))
    response.action_items[0].timing = Anchor(source_id="T1", quote="Friday")
    result = validate(response, saved, Comparison(claims=[]))
    assert result.summary
    item = result.summary.action_items[0]
    assert item.task == saved.sources[0].text
    assert item.due == timing or (
        item.due is None and saved.sources[0].text in " ".join(item.review)
    )
    assert result.evidence.commitments[0].timing
    assert result.evidence.commitments[0].timing.text == "Friday"


@pytest.mark.parametrize(
    "timing", ["by Friday", "by next Friday if approval arrives", "not before Friday", "on Friday"]
)
def test_ordinary_timing_assignment_still_works(timing: str) -> None:
    saved = snapshot(f"[0:00:01] Mira: I will send the invoice {timing}.")
    response = draft(action(saved.sources[0]))
    response.action_items[0].timing = Anchor(source_id="T1", quote="Friday")
    result = validate(response, saved, Comparison(claims=[]))
    assert result.summary
    assert result.summary.action_items[0].due == timing
    assert not result.summary.action_items[0].review


def test_correction_cannot_drop_external_timing_to_remove_its_review() -> None:
    saved = snapshot(
        "[0:00:01] Mira: I will send the invoice.\n"
        "[0:00:02] Ravi: Not before next Friday unless finance objects."
    )
    response = draft(action(saved.sources[0]))
    response.timing_updates = [
        TimingUpdate(original_commitment_id="T1", evidence=[Anchor(source_id="T2", quote="Friday")])
    ]
    previous = validate(response, saved, Comparison(claims=[]))
    current = validate(draft(action(saved.sources[0])), saved, Comparison(claims=[]))
    assert previous.summary and current.summary
    assert "Correction lost timing evidence: T2" in correction_errors(previous, current)


@pytest.mark.parametrize(
    ("original", "retraction", "cancelled"),
    [
        (
            "I will review the draft and Ravi will send the invoice.",
            "Ravi will not send the invoice.",
            True,
        ),
        (
            "I will review the draft and Ravi will send the invoice.",
            "I will not review the draft.",
            True,
        ),
        (
            "Ravi will review the draft and Dana will send the invoice.",
            "Dana will not send the invoice.",
            True,
        ),
        (
            "Ravi will review the draft and Dana will send the invoice.",
            "Ravi will not review the draft.",
            True,
        ),
        (
            "Ravi will review the draft and Dana will send the invoice "
            "and Noor will test the release.",
            "Noor will not test the release.",
            True,
        ),
        (
            "I will review the draft and send the invoice and Ravi will test the release.",
            "I will not send the invoice.",
            True,
        ),
        (
            "I will review the draft and I will send the invoice.",
            "I will not send the invoice.",
            True,
        ),
        (
            "Ravi will review the draft and Ravi will send the invoice.",
            "Ravi will not send the invoice.",
            True,
        ),
        (
            "Mira will review the draft and Ravi will send the invoice.",
            "I will not review the draft.",
            True,
        ),
        (
            "We will review the draft and Ravi will send the invoice.",
            "We will not review the draft.",
            True,
        ),
        (
            "We will review the draft and Ravi will send the invoice.",
            "I will not review the draft.",
            False,
        ),
        (
            "I will review the draft and Ravi will send the invoice.",
            "Ravi will not review the draft.",
            False,
        ),
        (
            "I will review the draft and Ravi will send the invoice.",
            "I will not send the invoice.",
            False,
        ),
        (
            "I will review the draft and Ravi will send the invoice.",
            "Ravi will not send the report.",
            False,
        ),
        (
            "I will review the draft and Ravi will send the invoice.",
            "Dana will not send the invoice.",
            False,
        ),
        (
            "Ravi will review the draft and Dana will send the invoice.",
            "Dana will not review the draft.",
            False,
        ),
    ],
)
def test_coordination_retractions_match_each_explicit_actor_and_task(
    original: str, retraction: str, cancelled: bool
) -> None:
    saved = snapshot(
        f"[0:00:01] Mira: {original}\n[0:00:02] Mira: {retraction}\n"
        "[0:00:03] Mira: I will check the logs."
    )
    response = draft(action(saved.sources[0]), action(saved.sources[2]))
    result = validate(response, saved, Comparison(claims=[]))
    assert result.summary and not result.blocking
    candidate = result.evidence.commitments[0]
    assert candidate.disposition == ("uncertain" if cancelled else "admissible")
    assert bool(candidate.retractions) == cancelled
    tasks = [item.task for item in result.summary.action_items]
    assert saved.sources[2].text in tasks
    assert (original in tasks) != cancelled
    if cancelled:
        assert original in " ".join(result.warnings)
        assert retraction in " ".join(result.warnings)
        assert candidate.undertaking and candidate.undertaking.text == original
        assert candidate.retractions[0].text == retraction


@pytest.mark.parametrize(
    ("original", "owner"),
    [
        ("I will review the draft and Ravi will send the invoice.", None),
        ("Ravi will review the draft and Dana will send the invoice.", None),
        ("I will review the draft and I will send the invoice.", "Mira"),
        ("Ravi will review the draft and Ravi will send the invoice.", "Ravi"),
    ],
)
def test_coordination_owner_is_not_assigned_wholly_to_its_first_actor(
    original: str, owner: str | None
) -> None:
    saved = snapshot(f"[0:00:01] Mira: {original}")
    result = validate(draft(action(saved.sources[0])), saved, Comparison(claims=[]))
    assert result.summary
    assert result.summary.action_items[0].owner == owner
    assert result.summary.action_items[0].task == original


def test_whole_repeated_actor_coordination_can_still_be_retracted() -> None:
    saved = snapshot(
        "[0:00:01] Mira: Ravi will review the draft and Ravi will send the invoice.\n"
        "[0:00:02] Mira: Ravi will not review the draft and send the invoice.\n"
        "[0:00:03] Mira: I will check the logs."
    )
    previous = validate(
        draft(action(saved.sources[0]), action(saved.sources[2])), saved, Comparison(claims=[])
    )
    assert previous.evidence.commitments[0].disposition == "rejected"
    current = validate(draft(action(saved.sources[2])), saved, Comparison(claims=[]))
    assert current.summary and len(current.summary.action_items) == 1
    assert correction_errors(previous, current) == []


@pytest.mark.parametrize("supplied", ["full", "empty", "partial"])
@pytest.mark.parametrize("selected", [True, False])
def test_acceptance_partial_cancellation_review_does_not_depend_on_supplied_context(
    supplied: str, selected: bool
) -> None:
    saved = snapshot(
        "[0:00:01] Mira: Could you review the draft and send the invoice?\n"
        "[0:00:02] Ravi: Yes.\n[0:00:03] Ravi: I will not send the invoice.\n"
        "[0:00:04] Ravi: I will check the logs."
    )
    accepted = action(saved.sources[1], saved.sources[0])
    if supplied == "empty":
        accepted.context = []
    elif supplied == "partial":
        accepted.context[0].quote = "review the draft"
    response = (
        draft(accepted, action(saved.sources[3])) if selected else draft(action(saved.sources[3]))
    )
    before = response.model_dump_json()
    result = validate(response, saved, Comparison(claims=[]))
    assert result.summary and not result.blocking
    assert [item.task for item in result.summary.action_items] == [saved.sources[3].text]
    warnings = " ".join(result.warnings)
    for source in saved.sources[:3]:
        assert source.text in warnings
    candidate = next(c for c in result.evidence.commitments if c.source_id == "T2")
    assert candidate.disposition == "uncertain"
    assert candidate.undertaking == resolve(accepted.undertaking, saved.sources, "transcript")
    assert candidate.retractions[0].text == saved.sources[2].text
    assert any(s.text == saved.sources[0].text for s in candidate.context)
    if selected:
        for anchor in accepted.context:
            assert resolve(anchor, saved.sources, "transcript") in candidate.context
    assert response.model_dump_json() == before
    restored = Evidence.model_validate_json(result.evidence.model_dump_json())
    assert restored.draft == response
    assert replay(restored) == result
    restored.commitments = [c for c in restored.commitments if c.source_id != "T2"]
    assert replay(restored).summary is None


@pytest.mark.parametrize("supplied", ["empty", "partial"])
def test_automatic_request_discovery_never_promotes_an_unsupported_acceptance(
    supplied: str,
) -> None:
    saved = snapshot(
        "[0:00:01] Mira: Could you review the draft and send the invoice?\n[0:00:02] Ravi: Yes."
    )
    accepted = action(saved.sources[1])
    if supplied == "partial":
        accepted.context = [Anchor(source_id="T1", quote="review the draft")]
    result = validate(draft(accepted), saved, Comparison(claims=[]))
    assert result.summary and not result.summary.action_items
    assert result.evidence.commitments[0].disposition == "uncertain"


@pytest.mark.parametrize("supplied", ["empty", "partial", "omitted"])
def test_correction_cannot_suppress_acceptance_cancellation_review(supplied: str) -> None:
    saved = snapshot(
        "[0:00:01] Mira: Could you review the draft and send the invoice?\n"
        "[0:00:02] Ravi: Yes.\n[0:00:03] Ravi: I will not send the invoice.\n"
        "[0:00:04] Ravi: I will check the logs."
    )
    accepted = action(saved.sources[1], saved.sources[0])
    independent = action(saved.sources[3])
    previous = validate(draft(accepted, independent), saved, Comparison(claims=[]))
    accepted.context = (
        [] if supplied == "empty" else [Anchor(source_id="T1", quote="send the invoice")]
    )
    response = draft(independent) if supplied == "omitted" else draft(accepted, independent)
    current = validate(response, saved, Comparison(claims=[]))
    assert previous.summary and current.summary
    assert [item.task for item in current.summary.action_items] == [saved.sources[3].text]
    assert correction_errors(previous, current) == []
    for source in saved.sources[:3]:
        assert source.text in " ".join(current.warnings)


def test_correction_omitting_mixed_actor_cancellation_keeps_review_and_independent_work() -> None:
    saved = snapshot(
        "[0:00:01] Mira: I will review the draft and Ravi will send the invoice.\n"
        "[0:00:02] Mira: Ravi will not send the invoice.\n"
        "[0:00:03] Mira: I will check the logs."
    )
    previous = validate(
        draft(action(saved.sources[0]), action(saved.sources[2])), saved, Comparison(claims=[])
    )
    current = validate(draft(action(saved.sources[2])), saved, Comparison(claims=[]))
    assert current.summary and previous.summary
    assert [item.task for item in current.summary.action_items] == [saved.sources[2].text]
    assert current.warnings == previous.warnings
    assert correction_errors(previous, current) == []
    dropped = validate(draft(), saved, Comparison(claims=[]))
    assert any(
        "lost admissible commitment/timing: T3" in e for e in correction_errors(current, dropped)
    )


@pytest.mark.parametrize(
    "original", ["I will review.", "I will review and Ravi will send the invoice."]
)
def test_nonadjacent_bare_verb_does_not_establish_retraction(original: str) -> None:
    saved = snapshot(
        f"[0:00:01] Mira: {original}\n[0:00:02] Ravi: The room is ready.\n"
        "[0:00:03] Mira: I will not review."
    )
    candidate = check(action(saved.sources[0]), saved.sources)
    assert candidate.disposition == "admissible"
    assert not candidate.retractions
