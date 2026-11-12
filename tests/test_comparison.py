"""Bounded comparison with hand-authored claims; these tests do not score a model."""

import json
from pathlib import Path

import pytest
from comparison_helpers import account
from test_current_ollama import MEETING, Transport, model, reply

from meeting_notes.comparison import Claim, Comparison, claim_ids, validate
from meeting_notes.compiler import passages
from meeting_notes.compiler_comparison import validate as compile_draft
from meeting_notes.contract import Action, Draft, SupportedText
from meeting_notes.evidence import Evidence, Generation, meeting_context
from meeting_notes.ollama import CHARS_PER_TOKEN, REPLY_TOKENS, OllamaError
from meeting_notes.summary import SummaryError

TRANSCRIPT = (
    "[00:00:00] Sam: Monitoring costs 120 dollars. Support costs 120 dollars. "
    "I will check the invoice. Agreed, release Friday."
)
NOTES = "Support costs 150 dollars."


def conflict() -> Comparison:
    return Comparison(
        claims=[
            Claim(
                note=account("N1", NOTES),
                transcript=[account("T2", "Support costs 120 dollars.")],
                outcome="conflicting",
                reason="Different stated prices for the same support service.",
            )
        ]
    )


def summary_draft() -> Draft:
    return Draft(
        overview=[],
        key_points=[SupportedText(text="Both services cost 120 dollars.", sources=["T1", "T2"])],
        decisions=[SupportedText(text="Release Friday.", sources=["T4"])],
        action_items=[Action(original_commitment_id="T3", timing=None)],
        timing_updates=[],
        notes_context=[],
        conflicts=[],
    )


def test_shared_number_conflict_is_compiled_without_disputing_monitoring_or_commitments():
    transport = Transport(conflict().model_dump_json(), summary_draft().model_dump_json())
    engine = model(transport)
    result = engine.summarize(MEETING, TRANSCRIPT, handwritten_text=NOTES)
    assert len(transport.requests) == 2
    assert result.conflicts[0].transcript == "Support costs 120 dollars."
    assert result.conflicts[0].handwritten == NOTES
    assert "Sam: “Monitoring costs 120 dollars.”" in result.key_points
    assert "Both services cost 120 dollars." not in result.key_points
    assert result.decisions == ["Release Friday."]
    assert result.action_items[0].task == "I will check the invoice."
    assert not result.action_items[0].review
    assert engine.audit.comparison_selected == 0 and engine.audit.selected == 0
    assert transport.requests[1]["format"]["properties"]["conflicts"]["maxItems"] == 0


@pytest.mark.parametrize("outcome", ["uncertain", "consistent", "conflicting", "additional"])
def test_explicit_comparison_outcomes_control_publication_and_review(outcome: str):
    comparison = conflict()
    comparison.claims[0].outcome = outcome  # type: ignore[assignment]
    if outcome == "additional":
        comparison.claims[0].transcript = []
    transport = Transport(comparison.model_dump_json(), summary_draft().model_dump_json())
    engine = model(transport)
    result = engine.summarize(MEETING, TRANSCRIPT, handwritten_text=NOTES)
    assert len(transport.requests) == 2  # Uncertainty does not trigger a summary correction.
    assert bool(result.conflicts) == (outcome == "conflicting")
    assert bool(engine.audit.attempts[0].warnings) == (outcome == "uncertain")
    if outcome == "uncertain":
        warning = engine.audit.attempts[0].warnings[0]
        assert "review required" in warning and NOTES in warning
        assert "Support costs 120 dollars." in warning
        assert "Both services cost 120 dollars." not in result.key_points
    elif outcome in ("consistent", "additional"):
        assert result.notes_context == [NOTES]


def test_multiclaim_passage_preserves_unmatched_request_separately():
    notes = "Support costs 150 dollars, and please book a venue."
    comparison = conflict()
    comparison.claims[0].note.quote = "Support costs 150 dollars, "
    request = account("N1", "and please book a venue.")
    request.kind = "request"
    comparison.claims.append(
        Claim(note=request, transcript=[], outcome="additional", reason="Request only in notes.")
    )
    sources = passages(TRANSCRIPT, notes)
    assert not validate(comparison, sources)
    assert claim_ids(comparison) == ["N1.C1", "N1.C2"]
    result = compile_draft(summary_draft(), sources, comparison)
    assert result.summary is not None
    assert result.summary.notes_context == ["and please book a venue."]
    assert len(result.summary.action_items) == 1
    assert result.summary.conflicts[0].handwritten == "Support costs 150 dollars, "


@pytest.mark.parametrize(
    "defect",
    [
        "missing",
        "duplicate",
        "wrong_notes",
        "wrong_transcript",
        "unknown",
        "quote",
        "no_match",
        "additional_match",
        "request_conflict",
        "duplicate_account",
    ],
)
def test_invalid_coverage_and_references_block_before_generation(defect: str):
    comparison = conflict()
    claim = comparison.claims[0]
    if defect == "missing":
        comparison.claims = []
    elif defect == "duplicate":
        comparison.claims.append(claim.model_copy(deep=True))
    elif defect == "wrong_notes":
        claim.note.source_id = "T2"
    elif defect == "wrong_transcript":
        claim.transcript[0].source_id = "N1"
    elif defect == "unknown":
        claim.transcript[0].source_id = "T999"
    elif defect == "quote":
        claim.transcript[0].quote = "Invented account."
    elif defect == "no_match":
        claim.transcript = []
    elif defect == "additional_match":
        claim.outcome = "additional"
    elif defect == "request_conflict":
        claim.note.kind = "request"
    elif defect == "duplicate_account":
        claim.transcript *= 2
    transport = Transport(comparison.model_dump_json(), comparison.model_dump_json())
    engine = model(transport)
    with pytest.raises(SummaryError, match="coverage requires review"):
        engine.summarize(MEETING, TRANSCRIPT, handwritten_text=NOTES)
    assert len(transport.requests) == 2 and not engine.audit.attempts
    assert engine.audit.comparison_selected is None
    assert all(a.blocking for a in engine.audit.comparison_attempts)


def test_comparison_and_summary_have_separate_single_correction_budgets():
    transport = Transport(
        "bad comparison",
        conflict().model_dump_json(),
        "bad draft",
        summary_draft().model_dump_json(),
    )
    engine = model(transport)
    engine.summarize(MEETING, TRANSCRIPT, handwritten_text=NOTES)
    assert len(transport.requests) == 4
    assert engine.audit.comparison_selected == engine.audit.selected == 1
    for index in (1, 3):
        assert len(transport.requests[index]["messages"]) == 4
    assert "bad comparison" not in json.dumps(transport.requests[2])
    assert "Support costs 150 dollars." in json.dumps(transport.requests[2])


@pytest.mark.parametrize("stage", ["comparison", "summary"])
def test_transport_failure_has_no_hidden_retry(stage: str):
    transport = Transport(
        *([conflict().model_dump_json()] if stage == "summary" else []), OllamaError("offline")
    )
    engine = model(transport)
    with pytest.raises(SummaryError, match="offline"):
        engine.summarize(MEETING, TRANSCRIPT, handwritten_text=NOTES)
    assert len(transport.requests) == (2 if stage == "summary" else 1)
    attempts = engine.audit.attempts if stage == "summary" else engine.audit.comparison_attempts
    assert attempts[-1].error == "offline"


def test_comparison_correction_counts_complete_history_before_sending():
    transport = Transport("bad " * 25000)
    engine = model(transport)
    with pytest.raises(OllamaError, match="too long"):
        engine.summarize(MEETING, TRANSCRIPT, handwritten_text=NOTES)
    assert len(transport.requests) == 1
    assert len(engine.audit.comparison_attempts) == 2
    assert engine.audit.comparison_attempts[-1].error


def test_summary_context_counts_comparison_evidence_without_truncation():
    comparison = conflict()
    comparison.claims[0].reason = "reason " * 18000
    transport = Transport(comparison.model_dump_json())
    engine = model(transport)
    with pytest.raises(OllamaError, match="too long"):
        engine.summarize(MEETING, TRANSCRIPT, handwritten_text=NOTES)
    assert len(transport.requests) == 1
    request = engine.audit.attempts[0].request
    assert comparison.claims[0].reason in request["messages"][1]["content"]
    assert (
        len(json.dumps(request, ensure_ascii=False)) + CHARS_PER_TOKEN - 1
    ) // CHARS_PER_TOKEN + REPLY_TOKENS > 32768


def test_new_wrapper_replays_comparison_and_rejects_changed_classification():
    transport = Transport(conflict().model_dump_json(), summary_draft().model_dump_json())
    engine = model(transport)
    result = engine.summarize(MEETING, TRANSCRIPT, handwritten_text=NOTES)
    saved = Generation(
        version=9,
        summary=result,
        audit=engine.audit,
        evidence=Evidence(
            transcript=TRANSCRIPT,
            context=meeting_context(MEETING),
            handwritten_original=NOTES,
            handwritten_text=NOTES,
        ),
    )
    assert Generation.model_validate_json(saved.model_dump_json()) == saved
    changed = saved.model_copy(deep=True)
    assert changed.audit is not None
    data = json.loads(saved.model_dump_json())
    selected = json.loads(data["audit"]["comparison_attempts"][0]["reply"])
    selected["claims"][0]["outcome"] = "consistent"
    data["audit"]["comparison_attempts"][0]["reply"] = json.dumps(selected)
    with pytest.raises(ValueError, match="does not match"):
        Generation.model_validate(data)


def test_old_v9_generations_keep_original_validator():
    root = Path(__file__).resolve().parents[1] / "evaluation/m10/v9"
    pairs = {p["id"]: p for p in json.loads((root / "pairs.json").read_text())}
    for line in (root / "results/proposed.jsonl").read_text().splitlines()[1:]:
        row = json.loads(line)
        pair = pairs[row["case"]]
        context = row["audit"]["attempts"][0]["request"]["messages"][1]["content"].split(
            "\nTranscript sources"
        )[0]
        Generation.model_validate(
            {
                "version": 8,
                "summary": row["summary"],
                "audit": row["audit"],
                "evidence": {
                    "transcript": pair["transcript"],
                    "context": context,
                    "handwritten_original": pair["handwritten_text"],
                    "handwritten_text": pair["handwritten_text"],
                },
            }
        )


def test_uncertain_unmatched_note_is_visible_even_without_selected_prose():
    comparison = conflict()
    comparison.claims[0].outcome = "uncertain"
    comparison.claims[0].transcript = []
    draft = Draft.model_validate_json(reply())
    draft.overview = []
    checked = compile_draft(draft, passages("Discussion.", NOTES), comparison)
    assert checked.summary is not None
    assert "review" in checked.summary.overview
    assert "No transcript match established" in checked.warnings[0]


def test_factual_dispute_within_a_commitment_does_not_dispute_its_task():
    transcript = "[00:00:00] Sam: I will check the invoice, since support costs 120 dollars."
    comparison = conflict()
    comparison.claims[0].transcript[0] = account("T1", "support costs 120 dollars.")
    draft = summary_draft()
    draft.action_items[0].original_commitment_id = "T1"
    draft.decisions = []
    draft.key_points = []
    checked = compile_draft(draft, passages(transcript, NOTES), comparison)
    assert checked.summary is not None
    assert not checked.summary.action_items[0].review
    assert "contains unresolved account" in checked.summary.key_points[0]
    assert checked.summary.conflicts[0].transcript == "support costs 120 dollars."


def test_disputed_commitment_retains_full_timing_for_review():
    text = "I will send the draft not before next Friday."
    comparison = conflict()
    comparison.claims[0].note.quote = "Do not send the draft."
    comparison.claims[0].transcript[0] = account("T1", text)
    comparison.claims[0].transcript[0].kind = "commitment"
    draft = summary_draft()
    draft.action_items[0].original_commitment_id = "T1"
    draft.decisions = []
    draft.key_points = []
    checked = compile_draft(
        draft, passages("[00:00:00] Sam: " + text, "Do not send the draft."), comparison
    )
    assert checked.summary is not None
    action = checked.summary.action_items[0]
    assert action.task == text and action.due is None
    assert any(text in warning for warning in action.review)


@pytest.mark.parametrize(
    "response,reason",
    [
        ({"message": {"content": "{}"}, "done_reason": "length"}, "ran out of context"),
        ({"error": "missing message"}, "no message"),
    ],
)
def test_unusable_comparison_transport_response_stops_without_summary(
    response: dict[str, object], reason: str
):
    transport = Transport(response)
    engine = model(transport)
    with pytest.raises(SummaryError, match=reason):
        engine.summarize(MEETING, TRANSCRIPT, handwritten_text=NOTES)
    assert len(transport.requests) == 1 and not engine.audit.attempts
    assert engine.audit.comparison_attempts[0].response == response


def test_partial_claim_partition_cannot_drop_a_note_qualifier():
    comparison = conflict()
    comparison.claims[0].note.quote = "Support costs 150 dollars."
    sources = passages(TRANSCRIPT, "Perhaps Support costs 150 dollars.")
    assert any("coverage" in problem for problem in validate(comparison, sources))


def test_summary_correction_history_includes_complete_comparison_before_send():
    transport = Transport(conflict().model_dump_json(), "bad " * 25000)
    engine = model(transport)
    with pytest.raises(OllamaError, match="too long"):
        engine.summarize(MEETING, TRANSCRIPT, handwritten_text=NOTES)
    assert len(transport.requests) == 2
    assert len(engine.audit.attempts) == 2
    assert engine.audit.attempts[-1].error
    assert "Different stated prices" in json.dumps(engine.audit.attempts[-1].request)


def test_model_cannot_introduce_a_summary_conflict_outside_comparison():
    from meeting_notes.contract import Dispute

    value = summary_draft()
    value.conflicts = [Dispute(topic="Invented", transcript=["T1"], notes=["N1"])]
    checked = compile_draft(value, passages(TRANSCRIPT, NOTES), conflict())
    assert checked.summary is None
    assert "Summary conflicts must be empty" in checked.blocking[0]
