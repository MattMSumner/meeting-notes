import pytest

from meeting_notes.grounding import Claim, Dispute, Draft, Span, Task, passages, validate


def ref(passage: str, quote: str) -> Span:
    return Span(passage=passage, quote=quote)


def draft_task(
    text: str = "Check rollback", owner: str | None = "Alex", timing: Span | None = None
) -> Draft:
    return Draft(
        claims=[Claim(id="task", text=text, evidence=[ref("T1", "I will check rollback.")])],
        overview=["task"],
        key_points=[],
        decisions=[],
        notes_context=[],
        conflicts=[],
        action_items=[
            Task(
                claim="task",
                commitment=ref("T1", "I will check rollback."),
                owner=owner,
                owner_evidence=None,
                timing=timing,
                timing_link=[],
            )
        ],
    )


def test_passage_ids_are_stable_and_keep_conditions_together():
    text = (
        "[00:00:00] Sam: I will send it Friday, or Monday if review slips. And I will check logs."
    )
    first = passages(text, "Original paragraph. Still same paragraph.\r\nNext paragraph.")
    assert first == passages(text, "Original paragraph. Still same paragraph.\r\nNext paragraph.")
    assert [p.id for p in first] == ["T1", "T2", "N1", "N2"]
    assert first[0].text.endswith("or Monday if review slips.")
    assert first[0].speaker == "Sam"
    assert first[2].text == "Original paragraph. Still same paragraph."


def test_a_deadline_from_another_task_is_blocked():
    sources = passages(
        "[00:00:00] Alex: I will check rollback.\n[00:00:05] Sam: I will tag the release Friday.",
        "",
    )
    checked = validate(draft_task(timing=ref("T2", "Friday")), sources)
    assert checked.summary is None
    assert any("not another passage" in issue for issue in checked.blocking)


def test_same_speaker_does_not_allow_cross_task_deadline():
    sources = passages("[00:00:00] Alex: I will check rollback. I will tag the release Friday.", "")
    checked = validate(draft_task(timing=ref("T2", "Friday")), sources)
    assert checked.summary is None


def test_full_condition_is_required_and_preserved():
    statement = "I will check rollback Friday, or Monday if review slips."
    draft = draft_task(timing=ref("T1", "Friday"))
    draft.claims[0].evidence = [ref("T1", statement)]
    draft.action_items[0].commitment = ref("T1", statement)
    sources = passages("[00:00:00] Alex: " + statement, "")
    assert validate(draft, sources).summary is None
    draft.action_items[0].timing = ref("T1", "Friday, or Monday if review slips")
    checked = validate(draft, sources)
    assert checked.summary is not None
    assert checked.summary.action_items[0].due == "Friday, or Monday if review slips"


def test_uncertain_later_exchange_keeps_task_and_warns_without_assigning_deadline():
    draft = draft_task()
    draft.action_items[0].timing_link = [ref("T2", "When?"), ref("T3", "Friday.")]
    checked = validate(
        draft,
        passages(
            "[00:00:00] Alex: I will check rollback.\n"
            "[00:00:01] Sam: When?\n[00:00:02] Alex: Friday.",
            "",
        ),
    )
    assert checked.summary is not None
    assert checked.summary.action_items[0].due is None
    assert checked.summary.action_items[0].task == "Check rollback"
    assert "Deadline needs review" in checked.warnings[0]


def test_two_tasks_in_one_statement_do_not_get_a_guessed_date():
    statement = "I will check rollback and tag the release Friday."
    draft = draft_task(timing=ref("T1", "Friday"))
    draft.claims[0].evidence = [ref("T1", statement)]
    draft.action_items[0].commitment = ref("T1", statement)
    checked = validate(draft, passages("[00:00:00] Alex: " + statement, ""))
    assert checked.summary is None
    assert any("coordinated commitment" in issue for issue in checked.blocking)


@pytest.mark.parametrize("reference", [ref("missing", "text"), ref("T1", "invented quote")])
def test_missing_or_fabricated_references_block_publication(reference: Span):
    draft = draft_task()
    draft.claims[0].evidence = [reference]
    assert validate(draft, passages("[00:00:00] Alex: I will check rollback.", "")).summary is None


def test_task_cannot_borrow_a_real_but_unrelated_statement():
    draft = draft_task()
    draft.claims[0].evidence = [ref("T1", "I will tag the release Friday.")]
    draft.action_items[0].commitment = draft.claims[0].evidence[0]
    checked = validate(draft, passages("[00:00:00] Alex: I will tag the release Friday.", ""))
    assert checked.summary is None
    assert any("exact phrase" in issue for issue in checked.blocking)


def test_number_elsewhere_in_same_source_is_not_support_for_this_claim():
    draft = Draft(
        claims=[
            Claim(
                id="price",
                text="Monitoring costs 120 dollars",
                evidence=[ref("T1", "Monitoring costs 80 dollars.")],
            )
        ],
        overview=["price"],
        key_points=[],
        decisions=[],
        action_items=[],
        notes_context=[],
        conflicts=[],
    )
    checked = validate(
        draft,
        passages("[00:00:00] Sam: Monitoring costs 80 dollars. Support costs 120 dollars.", ""),
    )
    assert checked.summary is not None
    assert "absent from cited evidence: 120" in checked.warnings[0]


def test_known_conflicts_control_all_sections_and_cloned_claims():
    draft = Draft(
        claims=[
            Claim(
                id="spoken",
                text="Delivery is scheduled for June.",
                evidence=[ref("T1", "I think delivery is in June.")],
            ),
            Claim(id="clone", text="June delivery confirmed.", evidence=[ref("T1", "June")]),
            Claim(id="written", text="Delivery in July.", evidence=[ref("N1", "Delivery: July.")]),
            Claim(
                id="task", text="Verify delivery", evidence=[ref("T2", "I will verify delivery.")]
            ),
        ],
        overview=["spoken"],
        key_points=["clone"],
        decisions=["spoken"],
        notes_context=["written"],
        conflicts=[Dispute(topic="Delivery", transcript_claim="spoken", notes_claim="written")],
        action_items=[
            Task(
                claim="task",
                commitment=ref("T2", "I will verify delivery."),
                owner="Sam",
                owner_evidence=None,
                timing=None,
                timing_link=[],
            )
        ],
    )
    checked = validate(
        draft,
        passages(
            "[00:00:00] Sam: I think delivery is in June. I will verify delivery.",
            "Delivery: July.",
        ),
    )
    assert checked.summary is not None
    summary = checked.summary
    assert summary.overview == "Sources disagree; see Conflicts."
    assert summary.key_points == ["Sources disagree; see Conflicts."]
    assert summary.decisions == [] and summary.notes_context == []
    assert summary.conflicts[0].transcript == "I think delivery is in June."
    assert summary.action_items[0].task == "Verify delivery"


def test_written_task_cannot_enter_spoken_actions():
    draft = draft_task()
    draft.claims[0].evidence = [ref("N1", "I will check rollback.")]
    draft.action_items[0].commitment = draft.claims[0].evidence[0]
    checked = validate(draft, passages("", "I will check rollback."))
    assert checked.summary is None


def test_quoted_name_from_other_speaker_does_not_establish_owner():
    draft = draft_task(owner="Sam")
    draft.action_items[0].owner_evidence = ref("T2", "Sam here.")
    checked = validate(
        draft, passages("[00:00:00] Alex: I will check rollback.\n[00:00:01] Sam: Sam here.", "")
    )
    assert checked.summary is None


def test_conflict_account_cannot_clip_uncertainty():
    draft = Draft(
        claims=[
            Claim(id="spoken", text="June delivery", evidence=[ref("T1", "June")]),
            Claim(id="written", text="July delivery", evidence=[ref("N1", "Delivery July.")]),
        ],
        overview=["spoken"],
        key_points=[],
        decisions=[],
        action_items=[],
        notes_context=[],
        conflicts=[Dispute(topic="Delivery", transcript_claim="spoken", notes_claim="written")],
    )
    checked = validate(
        draft, passages("[00:00:00] Sam: I think delivery is in June.", "Delivery July.")
    )
    assert checked.summary is None
    assert any("complete source statement" in issue for issue in checked.blocking)


def test_deadline_cannot_end_at_if_and_omit_the_condition():
    statement = "I will check rollback Friday, or Monday if review slips."
    draft = draft_task(timing=ref("T1", "Friday, or Monday if"))
    draft.claims[0].evidence = [ref("T1", statement)]
    draft.action_items[0].commitment = ref("T1", statement)
    checked = validate(draft, passages("[00:00:00] Alex: " + statement, ""))
    assert checked.summary is None
    assert any("complete trailing timing" in issue for issue in checked.blocking)


def test_real_citations_do_not_prove_entailment_for_free_text_claims():
    draft = Draft(
        claims=[
            Claim(
                id="fact",
                text="Release approved.",
                evidence=[ref("T1", "We have not approved the release.")],
            )
        ],
        overview=["fact"],
        key_points=[],
        decisions=[],
        action_items=[],
        notes_context=[],
        conflicts=[],
    )
    # Deliberately document the boundary: structure/presence checks cannot prove stance.
    # This must fail quality evaluation even though the citation is mechanically valid.
    checked = validate(draft, passages("[00:00:00] Sam: We have not approved the release.", ""))
    assert checked.summary is not None


def test_duplicate_claim_ids_and_unknown_section_ids_are_blocking():
    draft = draft_task()
    draft.claims.append(draft.claims[0])
    draft.overview.append("absent")
    checked = validate(draft, passages("[00:00:00] Alex: I will check rollback.", ""))
    assert checked.summary is None
    assert any("unique" in issue for issue in checked.blocking)
    assert any("unknown claim" in issue for issue in checked.blocking)


def test_a_name_mentioned_by_a_speaker_is_not_their_identity():
    draft = draft_task(owner="Sam")
    draft.action_items[0].owner_evidence = ref("T2", "Thanks Sam.")
    checked = validate(
        draft, passages("[00:00:00] Them: I will check rollback.\n[00:00:01] Them: Thanks Sam.", "")
    )
    assert checked.summary is None


def test_spoken_self_introduction_can_support_task_owner():
    draft = draft_task(owner="Alex")
    draft.action_items[0].owner_evidence = ref("T2", "Alex here.")
    checked = validate(
        draft, passages("[00:00:00] Them: I will check rollback.\n[00:00:01] Them: Alex here.", "")
    )
    assert checked.summary is not None
    assert checked.summary.action_items[0].owner == "Alex"


def test_a_bare_amount_is_not_accepted_as_a_deadline():
    statement = "I will pay 120 dollars."
    draft = draft_task(text="Pay", timing=ref("T1", "120 dollars"))
    draft.claims[0].evidence = [ref("T1", statement)]
    draft.action_items[0].commitment = ref("T1", statement)
    assert validate(draft, passages("[00:00:00] Alex: " + statement, "")).summary is None


def test_omitted_timing_with_an_obvious_date_requires_a_visible_review_warning():
    statement = "I will check rollback Friday."
    draft = draft_task()
    draft.claims[0].evidence = [ref("T1", statement)]
    draft.action_items[0].commitment = ref("T1", statement)
    checked = validate(draft, passages("[00:00:00] Alex: " + statement, ""))
    assert checked.summary is not None
    assert checked.summary.action_items[0].due is None
    assert "no deadline was assigned" in checked.warnings[0]
    assert statement in checked.warnings[0]


def test_numeric_diagnostics_distinguish_other_source_metadata_and_absent_values():
    draft = Draft(
        claims=[Claim(id="fact", text="80, 90, 2026, 777", evidence=[ref("T1", "Cost 50.")])],
        overview=["fact"],
        key_points=[],
        decisions=[],
        action_items=[],
        notes_context=[],
        conflicts=[],
    )
    checked = validate(
        draft, passages("[00:00:00] Sam: Cost 50. Other cost 80.", "Cost 90."), "Date 2026"
    )
    assert len(checked.warnings) == 4
    assert "elsewhere in the same source" in checked.warnings[0]
    assert "other source" in checked.warnings[1]
    assert "only in meeting metadata" in checked.warnings[2]
    assert "neither source" in checked.warnings[3]
