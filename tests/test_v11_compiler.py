import json

import pytest
from test_v11_comparison import account, additional

from meeting_notes.comparison_v11 import Claim, Comparison
from meeting_notes.compiler_v11 import Evidence, correction_errors, replay, validate
from meeting_notes.contract_v11 import Action, Draft, SupportedText, TimingUpdate, request_schema
from meeting_notes.spans_v11 import Anchor, Source, snapshot


def action(source: Source, timing: str | None = None) -> Action:
    return Action(
        original_commitment_id=source.id,
        undertaking=Anchor(source_id=source.id, quote=source.text),
        context=[],
        basis="explicit",
        disposition="committed",
        timing=Anchor(source_id=source.id, quote=timing) if timing else None,
    )


def draft(*actions: Action) -> Draft:
    return Draft(
        overview=[], key_points=[], decisions=[], action_items=list(actions), timing_updates=[]
    )


def test_summary_schema_has_only_flat_transcript_ids_and_no_generated_notes_or_conflicts() -> None:
    schema = request_schema(["T1", "T2"], ["N1"])
    assert set(schema["properties"]) == {
        "overview",
        "key_points",
        "decisions",
        "action_items",
        "timing_updates",
    }
    assert schema["$defs"]["SourceID"]["enum"] == ["T1", "T2"]
    assert "N1" not in json.dumps(schema)
    for owner, field in [
        ("Anchor", "source_id"),
        ("Action", "original_commitment_id"),
        ("TimingUpdate", "original_commitment_id"),
    ]:
        assert schema["$defs"][owner]["properties"][field] == {"$ref": "#/$defs/SourceID"}
    with pytest.raises(ValueError):
        request_schema([])
    with pytest.raises(ValueError):
        request_schema(["T1"], ["T1"])


def test_task_owner_and_complete_timing_suffix_are_assembled_from_sources() -> None:
    saved = snapshot("[0:00:01] Mira: I will send the invoice by next Friday if approval arrives.")
    response = draft(action(saved.sources[0], "Friday"))
    result = validate(response, saved, Comparison(claims=[]))
    assert not result.blocking
    assert result.summary
    assert result.summary.action_items[0].model_dump() == {
        "owner": "Mira",
        "task": saved.sources[0].text,
        "due": "by next Friday if approval arrives",
        "review": [],
    }


@pytest.mark.parametrize(
    ("text", "timing"),
    [
        ("If approval does not arrive, I will send the invoice by Friday.", "Friday"),
        ("Unless approval arrives, I will send the invoice by Friday.", "Friday"),
        ("I will send the invoice Friday and check rollback.", "Friday"),
        ("I will send the invoice Friday and review the logs Monday.", "Monday"),
        ("I will send the invoice Friday or Monday if approval arrives.", "Monday"),
        ("I will send the invoice after approval.", "after approval"),
    ],
)
def test_conditional_coordinated_and_multidate_boundaries_keep_timing_review(
    text: str, timing: str
) -> None:
    saved = snapshot(f"[0:00:01] Mira: {text}")
    result = validate(draft(action(saved.sources[0], timing)), saved, Comparison(claims=[]))
    assert not result.blocking
    assert result.summary
    selected = result.summary.action_items[0]
    assert selected.task == text
    assert selected.due is None
    assert selected.review


def test_not_before_is_timing_qualifier_rather_than_negated_task() -> None:
    saved = snapshot("[0:00:01] Mira: I will send the invoice not before Friday.")
    result = validate(draft(action(saved.sources[0], "Friday")), saved, Comparison(claims=[]))
    assert result.summary
    assert result.summary.action_items[0].due == "not before Friday"


def test_uncertain_candidates_stay_attributed_review_outside_checklist() -> None:
    saved = snapshot("[0:00:01] Mira: I will send the invoice.")
    response = draft(action(saved.sources[0]))
    response.action_items[0].disposition = "uncertain"
    result = validate(response, saved, Comparison(claims=[]))
    assert result.summary and not result.summary.action_items
    assert "Mira" in result.warnings[0] and saved.sources[0].text in result.warnings[0]
    assert result.evidence.commitments[0].disposition == "uncertain"


def test_fact_as_action_blocks_even_with_kind_like_claim_and_valid_source() -> None:
    saved = snapshot("[0:00:01] Mira: Service costs 275 dollars.", "Service costs 440 dollars.")
    response = Comparison(
        claims=[
            Claim(
                note=account("N1", saved.sources[1].text, quantity="440", unit="dollars"),
                transcript=[account("T1", saved.sources[0].text, quantity="275", unit="dollars")],
                outcome="conflicting",
                reason="Same service, differing costs.",
            )
        ]
    )
    response.claims[0].transcript[0].kind = "commitment"
    result = validate(draft(action(saved.sources[0])), saved, response)
    assert result.summary is None
    assert any("Noncommitment T1" in e for e in result.blocking)
    assert result.evidence.commitments[0].disposition == "rejected"


@pytest.mark.parametrize(
    "field", ["overview", "undertaking", "context", "timing", "update", "original"]
)
def test_every_spoken_field_rejects_note_ids_at_runtime(field: str) -> None:
    saved = snapshot(
        "[0:00:01] Mira: I will send the invoice by Friday.", "I will send the invoice by Friday."
    )
    response = draft(action(saved.sources[0], "Friday"))
    note = saved.sources[1]
    if field == "overview":
        response.overview = [SupportedText(text=note.text, sources=[note.id])]
    elif field == "undertaking":
        response.action_items[0].undertaking.source_id = note.id
    elif field == "context":
        response.action_items[0].context = [Anchor(source_id=note.id, quote=note.text)]
    elif field == "timing":
        response.action_items[0].timing = Anchor(source_id=note.id, quote="Friday")
    elif field == "original":
        response.action_items[0].original_commitment_id = note.id
    else:
        response.timing_updates = [
            TimingUpdate(
                original_commitment_id="T1", evidence=[Anchor(source_id=note.id, quote="Friday")]
            )
        ]
    result = validate(response, saved, additional(account(note.id, note.text)))
    assert result.summary is None
    assert any("Invalid transcript source: N1" in e for e in result.blocking)


def test_spoken_prose_with_valid_transcript_id_cannot_copy_wrong_source() -> None:
    saved = snapshot("[0:00:01] Mira: The queue is green.", "The archive is read only.")
    response = draft()
    response.overview = [SupportedText(text=saved.sources[1].text, sources=["T1"])]
    result = validate(response, saved, additional(account("N1", saved.sources[1].text)))
    assert result.summary is None
    assert any("verbatim notes prose" in e for e in result.blocking)
    response.overview[0].text = "According to the notes, the archive is read only."
    assert any(
        "written-source prose" in e
        for e in validate(
            response, saved, additional(account("N1", saved.sources[1].text))
        ).blocking
    )


def test_wrong_quotes_and_uncited_numbers_are_checked_before_disputed_prose_is_removed() -> None:
    saved = snapshot("[0:00:01] Mira: Service costs 275 dollars.", "Service costs 440 dollars.")
    comparison = Comparison(
        claims=[
            Claim(
                note=account("N1", saved.sources[1].text, quantity="440", unit="dollars"),
                transcript=[account("T1", saved.sources[0].text, quantity="275", unit="dollars")],
                outcome="conflicting",
                reason="Same service.",
            )
        ]
    )
    response = draft()
    response.overview = [
        SupportedText(text="Mira said “Service costs 999 dollars.”", sources=["T1"])
    ]
    result = validate(response, saved, comparison)
    assert result.summary is None
    assert any("quotation absent" in e for e in result.blocking)
    assert any("999 absent" in warning for warning in result.warnings)
    response.overview[0].text = "Service costs 330 dollars."
    result = validate(response, saved, comparison, "Budget 330 dollars")
    assert result.summary
    assert any("only in metadata" in warning for warning in result.warnings)


def test_independent_agreement_and_task_survive_factual_conflict_in_mixed_prose() -> None:
    saved = snapshot(
        "[0:00:01] Mira: Service costs 275 dollars. I will send the invoice by Friday.\n"
        "[0:00:02] Ravi: Agreed, release Friday.",
        "Service costs 440 dollars.",
    )
    response = draft(action(saved.sources[1], "Friday"))
    response.overview = [
        SupportedText(text="Service costs 275 dollars and release Friday.", sources=["T1", "T3"])
    ]
    response.decisions = [SupportedText(text="Release Friday.", sources=["T3"])]
    comparison = Comparison(
        claims=[
            Claim(
                note=account("N1", saved.sources[-1].text, quantity="440", unit="dollars"),
                transcript=[account("T1", saved.sources[0].text, quantity="275", unit="dollars")],
                outcome="conflicting",
                reason="Same service.",
            )
        ]
    )
    result = validate(response, saved, comparison)
    assert not result.blocking
    assert result.summary
    assert result.summary.conflicts[0].transcript == saved.sources[0].text
    assert result.summary.action_items[0].task == saved.sources[1].text
    assert result.summary.action_items[0].due == "by Friday"
    assert result.summary.decisions == ["Release Friday."]
    assert saved.sources[2].text in result.summary.overview


@pytest.mark.parametrize("outcome", ["related-distinct", "uncertain"])
def test_related_and_uncertain_accounts_remain_visible_with_independent_task(outcome: str) -> None:
    saved = snapshot(
        "[0:00:01] Mira: The confirmed Regional cost is 275 dollars. I will send the invoice.",
        "The tentative Global cost is 440 dollars.",
    )
    comparison = Comparison(
        claims=[
            Claim(
                note=account(
                    "N1",
                    saved.sources[-1].text,
                    quantity="440",
                    unit="dollars",
                    scope="Global",
                    status="tentative",
                ),
                transcript=[
                    account(
                        "T1",
                        saved.sources[0].text,
                        quantity="275",
                        unit="dollars",
                        scope="Regional",
                        status="confirmed",
                    )
                ],
                outcome="related-distinct" if outcome == "related-distinct" else "uncertain",
                reason="Scope differs; epistemic relation unresolved.",
            )
        ]
    )
    result = validate(draft(action(saved.sources[1])), saved, comparison)
    assert result.summary and not result.summary.conflicts
    assert len(result.summary.action_items) == 1
    assert any("Comparison review required" in warning for warning in result.warnings)


def test_invalid_comparison_blocks_publication_of_independent_task() -> None:
    saved = snapshot("[0:00:01] Mira: I will send the invoice.", "Important uncovered note")
    result = validate(draft(action(saved.sources[0])), saved, Comparison(claims=[]))
    assert result.summary is None and result.blocking


def test_later_timing_is_review_and_evidence_keeps_its_original_target() -> None:
    saved = snapshot("[0:00:01] Mira: I will send the invoice.\n[0:00:02] Ravi: By Monday.")
    response = draft(action(saved.sources[0]))
    response.timing_updates = [
        TimingUpdate(
            original_commitment_id="T1", evidence=[Anchor(source_id="T2", quote="By Monday")]
        )
    ]
    result = validate(response, saved, Comparison(claims=[]))
    assert result.summary
    selected = result.summary.action_items[0]
    assert selected.due is None and "By Monday" in " ".join(selected.review)
    assert result.evidence.timing_updates[0].original_commitment_id == "T1"


def test_missing_commitment_and_independent_agreement_are_blocking_omissions() -> None:
    saved = snapshot(
        "[0:00:01] Mira: I will send the invoice.\n[0:00:02] Ravi: Agreed, release Friday."
    )
    result = validate(draft(), saved, Comparison(claims=[]))
    assert any("omitted commitment" in error for error in result.blocking)
    assert any("omitted agreement" in error for error in result.blocking)


def test_correction_protects_real_tasks_timing_and_agreements_without_protecting_fact_actions() -> (
    None
):
    saved = snapshot(
        "[0:00:01] Mira: Service costs 275 dollars. I will send the invoice by Friday.\n"
        "[0:00:02] Ravi: Agreed, release Friday."
    )
    first = draft(action(saved.sources[0]), action(saved.sources[1], "Friday"))
    first.decisions = [SupportedText(text="Release Friday.", sources=["T3"])]
    previous = validate(first, saved, Comparison(claims=[]))
    assert previous.summary is None
    corrected = first.model_copy(deep=True)
    corrected.action_items = corrected.action_items[1:]
    current = validate(corrected, saved, Comparison(claims=[]))
    assert current.summary
    assert not correction_errors(previous, current)
    corrected.action_items[0].disposition = "uncertain"
    corrected.decisions = []
    dropped = validate(corrected, saved, Comparison(claims=[]))
    errors = correction_errors(previous, dropped)
    assert any("lost admissible commitment" in error for error in errors)
    assert any("lost independent agreement" in error for error in errors)
    assert not any("lost admissible commitment/timing: T1" in error for error in errors)


def test_full_snapshot_and_resolution_roundtrip_and_recompute_without_original_files() -> None:
    saved = snapshot(
        "\n[0:00:01] Mira: I will send the invoice by Friday.\n\n",
        "\n Heading: archive is green, and guide is pending  \n",
    )
    comparison = additional(
        account("N1", "Heading"),
        account("N1", "archive is green"),
        account("N1", "guide is pending"),
    )
    response = draft(action(saved.sources[0], "Friday"))
    result = validate(response, saved, comparison, "Synthetic review")
    assert result.summary
    restored = Evidence.model_validate_json(result.evidence.model_dump_json())
    assert replay(restored) == result
    assert restored.snapshot == saved
    restored.resolution.gaps[0].text = "changed"
    assert replay(restored).summary is None
    assert any("differs from recomputation" in error for error in replay(restored).blocking)


def test_source_snapshot_mismatch_and_duplicate_ids_are_rejected() -> None:
    saved = snapshot("[0:00:01] Mira: I will send the invoice.")
    response = draft(action(saved.sources[0]))
    saved.transcript = "changed"
    assert validate(response, saved, Comparison(claims=[])).summary is None
    saved.sources.append(saved.sources[0])
    assert any(
        "Source IDs must be unique" in error
        for error in validate(response, saved, Comparison(claims=[])).blocking
    )


def test_snapshot_recomputation_detects_omitted_sources_and_altered_speaker() -> None:
    saved = snapshot("[0:00:01] Mira: I will send the invoice.", "Important written context")
    response = draft(action(saved.sources[0]))
    saved.sources = saved.sources[:1]
    result = validate(response, saved, Comparison(claims=[]))
    assert result.summary is None
    assert any("complete effective snapshot" in error for error in result.blocking)
    saved = snapshot("[0:00:01] Mira: I will send the invoice.")
    saved.sources[0].speaker = "Ravi"
    assert validate(response, saved, Comparison(claims=[])).summary is None
