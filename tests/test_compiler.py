import json
from datetime import datetime

import pytest

from meeting_notes.compiler import passages, validate
from meeting_notes.contract import Action, Dispute, Draft, SupportedText, Timing, TimingUpdate
from meeting_notes.evidence import Evidence, Generation
from meeting_notes.meeting import Meeting
from meeting_notes.ollama import OllamaSummarizer


def draft(timing: str | None = None, context: list[str] | None = None) -> Draft:
    return Draft(
        overview=[],
        key_points=[],
        decisions=[],
        notes_context=[],
        conflicts=[],
        timing_updates=[TimingUpdate(original_commitment_id="T1", source_ids=context)]
        if context
        else [],
        action_items=[
            Action(
                original_commitment_id="T1",
                timing=Timing(source_id="T1", quote=timing) if timing else None,
            )
        ],
    )


@pytest.mark.parametrize("timing", ["Friday", "Friday."])
def test_task_wording_does_not_block_a_correct_due(timing: str):
    checked = validate(draft(timing), passages("[00:00:00] Sam: I will send the draft Friday.", ""))
    assert checked.summary is not None
    item = checked.summary.action_items[0]
    assert item.task == "I will send the draft"
    assert item.due == "Friday"
    assert item.owner == "Sam"
    assert not item.review


def test_condition_is_expanded_from_source():
    checked = validate(
        draft("Friday"),
        passages("[00:00:00] Sam: I will send it Friday, or Monday if review slips.", ""),
    )
    assert checked.summary is not None
    assert checked.summary.action_items[0].due == "Friday, or Monday if review slips"


@pytest.mark.parametrize(
    "text,timing",
    [
        ("Next Tuesday, I will send the draft.", "Next Tuesday"),
        ("I will send the draft Friday and check rollback.", "Friday"),
        ("I will review Friday logs.", "Friday"),
        ("I will send the draft.", "invented Friday"),
    ],
)
def test_ambiguous_timing_publishes_review(text: str, timing: str):
    checked = validate(draft(timing), passages("[00:00:00] Sam: " + text, ""))
    assert checked.summary is not None
    item = checked.summary.action_items[0]
    assert item.due is None and item.review
    assert item.task == text
    assert all("invented Friday" not in entry for entry in item.review)


def test_revision_prevents_assigning_original_due_and_suppresses_prose():
    value = draft("Friday", ["T2"])
    value.overview = [SupportedText(text="Friday is confirmed.", sources=["T1"])]
    checked = validate(
        value,
        passages("[00:00:00] Sam: I will send the draft Friday. Actually, Monday instead.", ""),
    )
    assert checked.summary is not None
    assert "Friday" not in checked.summary.overview
    item = checked.summary.action_items[0]
    assert item.due is None
    assert any("Monday" in entry for entry in item.review)


def test_note_sentences_and_source_offsets_preserve_original():
    notes = "Estimate: 150 thousand dollars. Delivery: July.\r\nDr. Smith agrees."
    sources = passages("", notes)
    assert len(sources) == 3
    assert all(notes[s.start : s.end] == s.text for s in sources)
    assert sources[-1].text == "Dr. Smith agrees."


def test_conflicts_preserve_hedges_and_separate_note_facts():
    value = draft()
    value.action_items = []
    value.conflicts = [Dispute(topic="Delivery", transcript=["T1"], notes=["N2"])]
    value.notes_context = [SupportedText(text="Estimate 150 thousand dollars.", sources=["N1"])]
    result = validate(
        value,
        passages(
            "[00:00:00] Sam: I think delivery is in June.",
            "Estimate: 150 thousand dollars. Delivery: July.",
        ),
    )
    assert result.summary is not None
    assert result.summary.conflicts[0].transcript.startswith("I think")
    assert result.summary.notes_context


def test_unknown_reference_blocks_and_third_person_does_not_assign_speaker():
    value = draft()
    result = validate(value, passages("[00:00:00] Sam: Alex will send the draft.", ""))
    assert result.summary is not None and result.summary.action_items[0].owner is None
    value.action_items[0].original_commitment_id = "N1"
    assert validate(value, passages("", "Send the draft.")).summary is None


def test_current_model_and_wrapper_reproduce_review_without_live_sources():
    value = draft("Friday", ["T2"])
    calls: list[dict[str, object]] = []

    def post(path: str, body: dict[str, object]) -> dict[str, object]:
        calls.append(body)
        return {"message": {"content": value.model_dump_json()}}

    model = OllamaSummarizer("fake", 32768, post, "Sam")
    meeting = Meeting.new("Synthetic", datetime.fromisoformat("2026-10-20T14:00:00-04:00"), ())
    transcript = "[00:00:00] Sam: I will send the draft Friday. Actually Monday instead."
    summary = model.summarize(meeting, transcript)
    assert len(calls) == 1
    from meeting_notes.evidence import meeting_context

    saved = Generation(
        version=9,
        summary=summary,
        evidence=Evidence(
            transcript=transcript,
            context=meeting_context(meeting),
            handwritten_original="",
            handwritten_text="",
        ),
        audit=model.audit,
    )
    assert Generation.model_validate_json(saved.model_dump_json()) == saved
    data = json.loads(saved.model_dump_json())
    data["summary"]["action_items"][0]["due"] = "Friday"
    with pytest.raises(ValueError, match="does not match"):
        Generation.model_validate(data)


@pytest.mark.parametrize(
    "introduction", ["Alex here.", "I am Alex.", "I'm Alex.", "My name is Alex."]
)
def test_identity_stays_in_its_turn(introduction: str):
    value = draft()
    value.action_items[0].original_commitment_id = "T2"
    result = validate(
        value, passages("[00:00:00] Them: " + introduction + " I will check rollback.", "")
    )
    assert result.summary is not None
    assert result.summary.action_items[0].owner == "Alex"
    result = validate(
        value, passages("[00:00:00] Them: Alex here.\n[00:00:02] Them: I will check rollback.", "")
    )
    assert result.summary is not None and result.summary.action_items[0].owner == "Them"


def test_duplicate_proposals_become_review_and_keep_one_checkbox():
    value = draft("Friday")
    value.action_items.append(
        Action(original_commitment_id="T1", timing=Timing(source_id="T1", quote="Monday"))
    )
    result = validate(
        value, passages("[00:00:00] Sam: I will send it Friday, or Monday if needed.", "")
    )
    assert result.summary is not None
    assert len(result.summary.action_items) == 1
    assert result.summary.action_items[0].due is None
    assert result.summary.action_items[0].review


def test_relative_modifier_is_not_left_on_task():
    result = validate(draft("Friday"), passages("[00:00:00] Sam: I will send it next Friday.", ""))
    assert result.summary is not None
    assert result.summary.action_items[0].task == "I will send it"
    assert result.summary.action_items[0].due == "next Friday"


def test_semantic_selection_is_not_proven_by_reference_integrity():
    # A quoted tentative statement still needs semantic evaluation. The compiler
    # cannot certify that model-selected actions are genuine commitments.
    result = validate(draft(), passages("[00:00:00] Sam: Maybe I could check rollback.", ""))
    assert result.summary is not None
    assert result.summary.action_items[0].owner is None
    assert result.summary.action_items[0].task.startswith("Maybe")


def test_unknown_reference_gets_one_correction_and_context_is_checked_before_send():
    from meeting_notes.summary import SummaryError

    value = draft("Friday")
    invalid = value.model_copy(deep=True)
    invalid.action_items[0].original_commitment_id = "missing"
    replies = iter([invalid.model_dump_json(), value.model_dump_json()])
    requests: list[dict[str, object]] = []

    def post(path: str, body: dict[str, object]) -> dict[str, object]:
        requests.append(body)
        return {"message": {"content": next(replies)}}

    meeting = Meeting.new("Synthetic", datetime.fromisoformat("2026-10-20T14:00:00-04:00"), ())
    model = OllamaSummarizer("fake", 32768, post, "Sam")
    result = model.summarize(meeting, "[00:00:00] Sam: I will send the draft Friday.")
    assert result.action_items[0].due == "Friday"
    assert len(requests) == 2 and model.audit.selected == 1
    assert "claims" not in json.dumps(requests[0]["format"])
    too_small = OllamaSummarizer("fake", 1, post, "Sam")
    with pytest.raises(SummaryError, match="too long"):
        too_small.summarize(meeting, "[00:00:00] Sam: I will send the draft Friday.")
    assert len(requests) == 2


def test_review_render_qualifies_old_deadline_before_showing_it():
    from meeting_notes.render import render_note

    value = draft("Friday", ["T2"])
    result = validate(
        value,
        passages("[00:00:00] Sam: I will send the draft Friday. Actually Monday instead.", ""),
    )
    assert result.summary is not None
    meeting = Meeting.new("Synthetic", datetime.fromisoformat("2026-10-20T14:00:00-04:00"), ())
    note = render_note(meeting, result.summary, "synthetic")
    assert note.index("Review required") < note.index("Friday")
    assert "(due Friday)" not in note
    assert "Monday" in note


def test_numeric_correction_cannot_remove_a_publishable_commitment():
    first = draft("Friday")
    first.overview = [SupportedText(text="Cost 777 dollars.", sources=["T2"])]
    correction = first.model_copy(deep=True)
    correction.action_items = []
    correction.overview[0].text = "Cost 80 dollars."
    replies = iter([first.model_dump_json(), correction.model_dump_json()])

    def post(path: str, body: dict[str, object]) -> dict[str, object]:
        return {"message": {"content": next(replies)}}

    meeting = Meeting.new("Synthetic", datetime.fromisoformat("2026-10-20T14:00:00-04:00"), ())
    model = OllamaSummarizer("fake", 32768, post, "Sam")
    result = model.summarize(
        meeting, "[00:00:00] Sam: I will send the draft Friday. Cost 80 dollars."
    )
    assert len(result.action_items) == 1
    assert model.audit.selected == 0


def test_self_context_is_redundant_even_without_a_deadline():
    value = draft("Friday", ["T1"])
    sources = passages("[00:00:00] Sam: I will send it Friday.", "")
    result = validate(value, sources)
    assert result.summary is not None
    assert result.summary.action_items[0].due == "Friday"
    assert not result.summary.action_items[0].review
    value = draft(None, ["T1"])
    result = validate(value, passages("[00:00:00] Sam: I will check rollback.", ""))
    assert result.summary is not None
    assert not result.summary.action_items[0].review


def test_timing_source_preserves_later_answer_even_with_question_context():
    value = draft(None, ["T2", "T3"])
    result = validate(
        value,
        passages(
            "[00:00:00] Sam: I will check rollback.\n"
            "[00:00:02] Them: When?\n[00:00:04] Sam: Friday.",
            "",
        ),
    )
    assert result.summary is not None
    action = result.summary.action_items[0]
    assert action.due is None
    assert any("Friday" in line for line in action.review)
    assert any("association unverified" in line for line in action.review)


def test_suppression_preserves_source_timing_when_proposal_points_to_wrong_statement():
    value = draft("Friday.", ["T2"])
    value.overview = [SupportedText(text="Rollback on Friday.", sources=["T1", "T3"])]
    result = validate(
        value,
        passages(
            "[00:00:00] Sam: I will check rollback.\n"
            "[00:00:02] Them: When?\n[00:00:04] Sam: Friday.",
            "",
        ),
    )
    assert result.summary is not None
    assert result.summary.overview.startswith("Sam: “Friday.”")
    assert result.summary.action_items[0].due is None
    assert not any("Friday" in line for line in result.summary.action_items[0].review)


def test_valid_other_task_reference_cannot_supply_a_due_value():
    value = draft()
    value.action_items[0].timing = Timing(source_id="T2", quote="Friday")
    sources = passages("[00:00:00] Sam: I will check rollback. I will send the draft Friday.", "")
    result = validate(value, sources)
    assert result.summary is None
    assert any("Possible omitted commitment T2" in issue for issue in result.blocking)
    value.action_items.append(Action(original_commitment_id="T2", timing=None))
    result = validate(value, sources)
    assert result.summary is not None
    assert result.summary.action_items[0].due is None
    assert any("association unverified" in line for line in result.summary.action_items[0].review)


@pytest.mark.parametrize("bad_id", ["missing", "N2"])
def test_known_conflict_cannot_hide_unknown_or_unrelated_wrong_source(bad_id: str):
    value = draft()
    value.action_items = []
    value.conflicts = [Dispute(topic="Support", transcript=["T1"], notes=["N1"])]
    value.key_points = [SupportedText(text="Sources disagree.", sources=["T1", "N1", bad_id])]
    result = validate(
        value,
        passages(
            "[00:00:00] Sam: Support costs 120 dollars.",
            "Support costs 150 dollars. Unrelated 777 dollars.",
        ),
    )
    assert result.summary is None
    assert any(bad_id in issue for issue in result.blocking)


def test_known_conflict_neutralizes_redundant_cross_source_prose():
    value = draft()
    value.action_items = []
    value.conflicts = [Dispute(topic="Support", transcript=["T1"], notes=["N1"])]
    value.key_points = [
        SupportedText(text="Support is definitely 150 dollars.", sources=["T1", "N1"]),
        SupportedText(text="Monitoring costs 80 dollars.", sources=["T2"]),
    ]
    result = validate(
        value,
        passages(
            "[00:00:00] Sam: Support costs 120 dollars. Monitoring costs 80 dollars.",
            "Support costs 150 dollars.",
        ),
    )
    assert result.summary is not None
    assert result.summary.key_points == [
        "Sources disagree; see Conflicts.",
        "Monitoring costs 80 dollars.",
    ]
    assert result.summary.conflicts[0].handwritten == "Support costs 150 dollars."


def test_unknown_timing_source_and_unrelated_notes_still_block():
    value = draft()
    sources = passages("[00:00:00] Sam: I will check rollback.", "Friday.")
    value.action_items[0].timing = Timing(source_id="N1", quote="Friday")
    assert validate(value, sources).summary is None
    value.action_items[0].timing = Timing(source_id="missing", quote="Friday")
    assert validate(value, sources).summary is None


def test_request_schema_enumerates_ids_in_each_reference_field():
    from meeting_notes.contract import request_schema

    schema = request_schema(["T1", "T2"], ["N1"])
    definitions = schema["$defs"]
    assert definitions["SourceID"]["enum"] == ["T1", "T2", "N1"]
    assert "AnySource" not in definitions
    for owner, field in [
        ("Action", "original_commitment_id"),
        ("Timing", "source_id"),
        ("TimingUpdate", "original_commitment_id"),
    ]:
        assert definitions[owner]["properties"][field] == {"$ref": "#/$defs/SourceID"}
    for owner, field in [
        ("SupportedText", "sources"),
        ("Dispute", "notes"),
        ("Dispute", "transcript"),
        ("TimingUpdate", "source_ids"),
    ]:
        assert definitions[owner]["properties"][field]["items"] == {"$ref": "#/$defs/SourceID"}
    empty = request_schema(["T1"], [])
    assert empty["properties"]["conflicts"]["maxItems"] == 0
    assert empty["properties"]["notes_context"]["maxItems"] == 0
    assert request_schema(["T9"], [])["$defs"]["SourceID"]["enum"] == ["T9"]


def test_valid_own_timing_is_not_downgraded_by_redundant_summary_reference():
    value = draft("Friday", ["T1"])
    value.overview = [SupportedText(text="Tagging and release Friday.", sources=["T1", "T2"])]
    value.decisions = [SupportedText(text="Release Friday.", sources=["T2"])]
    result = validate(
        value,
        passages("[00:00:00] Sam: I will tag the release Friday. Agreed, release Friday.", ""),
    )
    assert result.summary is not None
    assert result.summary.action_items[0].due == "Friday"
    assert not result.summary.action_items[0].review
    assert result.summary.decisions == ["Release Friday."]


@pytest.mark.parametrize(
    "freeze,version,expected",
    [("v4", 3, 9), ("v5", 4, 12), ("v6", 5, 12), ("v7", 6, 13), ("v8", 6, 11)],
)
def test_published_generations_still_validate_with_original_rules(
    freeze: str, version: int, expected: int
):
    from pathlib import Path

    from meeting_notes.evidence import meeting_context

    root = Path(__file__).resolve().parents[1] / "evaluation/m10" / freeze
    pairs = {p["id"]: p for p in json.loads((root / "pairs.json").read_text())}
    rows = [json.loads(s) for s in (root / "results/proposed.jsonl").read_text().splitlines()][1:]
    count = 0
    for row in rows:
        if "summary" not in row:
            continue
        pair = pairs[row["case"]]
        metadata = pair["meeting"]
        meeting = Meeting.new(
            metadata["title"],
            datetime.fromisoformat(metadata["started_at"]),
            tuple(metadata["attendees"]),
        )
        data = {
            "version": version,
            "summary": row["summary"],
            "audit": row["audit"],
            "evidence": {
                "transcript": pair["transcript"],
                "context": meeting_context(meeting),
                "handwritten_original": pair["handwritten_text"],
                "handwritten_text": pair["handwritten_text"],
            },
        }
        saved = Generation.model_validate(data)
        assert saved.summary.model_dump() == row["summary"]
        count += 1
    assert count == expected


def test_mixed_conflict_preserves_independent_fact_without_settling_dispute():
    value = draft()
    value.action_items = []
    value.conflicts = [Dispute(topic="Support", transcript=["T2"], notes=["N1"])]
    value.key_points = [
        SupportedText(text="Both costs are 150 dollars.", sources=["T1", "T2", "N1"])
    ]
    result = validate(
        value,
        passages(
            "[00:00:00] Sam: Monitoring costs 120 dollars. Support costs 120 dollars.",
            "Support costs 150 dollars.",
        ),
    )
    assert result.summary is not None
    assert result.summary.key_points == [
        "Sources disagree; see Conflicts.",
        "Sam: “Monitoring costs 120 dollars.”",
    ]
    assert result.summary.conflicts[0].transcript == "Support costs 120 dollars."
    assert result.summary.conflicts[0].handwritten == "Support costs 150 dollars."


def test_shared_overview_does_not_link_independent_decision_to_undated_task():
    value = draft()
    value.overview = [SupportedText(text="Rollback and release Friday.", sources=["T1", "T2"])]
    value.decisions = [SupportedText(text="Release Friday.", sources=["T2"])]
    result = validate(
        value,
        passages(
            "[00:00:00] Sam: I will check rollback. Agreed, release Friday.",
            "",
        ),
    )
    assert result.summary is not None
    assert result.summary.decisions == ["Release Friday."]
    assert "Sam: “Agreed, release Friday.”" in result.summary.overview
    action = result.summary.action_items[0]
    assert action.due is None and not action.review


@pytest.mark.parametrize("target,refs", [("T2", ["T1"]), ("T3", ["T2"]), ("T1", ["N1"])])
def test_invalid_update_relationships_block(target: str, refs: list[str]):
    value = draft()
    if target == "T2":
        value.action_items[0].original_commitment_id = target
    value.timing_updates = [TimingUpdate(original_commitment_id=target, source_ids=refs)]
    result = validate(
        value,
        passages(
            "[00:00:00] Sam: I will send the draft Friday. "
            "Actually, Monday instead. I mean the draft.",
            "Tuesday.",
        ),
    )
    assert result.summary is None and result.blocking


def test_unrelated_later_update_cannot_assign_borrowed_due():
    value = draft(None, ["T2"])
    value.action_items.append(Action(original_commitment_id="T2", timing=None))
    result = validate(
        value,
        passages(
            "[00:00:00] Sam: I will check rollback. I will send the draft Friday.",
            "",
        ),
    )
    assert result.summary is not None
    action = result.summary.action_items[0]
    assert action.task == "I will check rollback."
    assert action.due is None
    assert any("association unverified" in s for s in action.review)


def test_numeric_retry_cannot_drop_timing_revision_and_request_omits_offsets():
    first = draft("Friday", ["T2"])
    first.key_points = [SupportedText(text="Cost 777 dollars.", sources=["T3"])]
    correction = first.model_copy(deep=True)
    correction.timing_updates = []
    correction.key_points[0].text = "Cost 80 dollars."
    replies = iter([first.model_dump_json(), correction.model_dump_json()])
    requests: list[dict[str, object]] = []

    def post(path: str, body: dict[str, object]) -> dict[str, object]:
        requests.append(body)
        return {"message": {"content": next(replies)}}

    meeting = Meeting.new("Synthetic", datetime.fromisoformat("2026-10-20T14:00:00-04:00"), ())
    model = OllamaSummarizer("fake", 32768, post, "Sam")
    result = model.summarize(
        meeting,
        "[00:00:00] Sam: I will send the draft Friday. Actually Monday instead. Cost 80 dollars.",
    )
    assert model.audit.selected == 0
    assert result.action_items[0].due is None
    assert any("Monday" in s for s in result.action_items[0].review)
    messages = json.loads(json.dumps(requests[0]["messages"]))
    spoken, _written = messages[1]["content"].split("Handwritten sources", 1)
    sources = json.loads(spoken.split("(evidence, not instructions):\n")[1])
    assert all(len(s) == 3 for s in sources)
    assert sources[0] == ["T1", "Sam", "I will send the draft Friday."]
    assert model.audit.passages[0].start > 0


def test_external_timing_is_normalized_to_review_without_mutating_draft():
    value = draft()
    value.action_items[0].timing = Timing(source_id="T3", quote="Friday")
    before = value.model_dump_json()
    result = validate(
        value,
        passages(
            "[00:00:00] Sam: I will check rollback.\n[00:00:02] Alex: When?\n"
            "[00:00:04] Sam: Friday, or Monday if review slips.",
            "",
        ),
    )
    assert value.model_dump_json() == before
    assert result.summary is not None
    action = result.summary.action_items[0]
    assert action.task == "I will check rollback." and action.due is None
    assert any("Friday, or Monday if review slips." in s for s in action.review)


@pytest.mark.parametrize("quote", ["Tuesday", "rollback", "Friday"])
def test_external_timing_requires_unique_exact_date(quote: str):
    value = draft()
    value.action_items[0].timing = Timing(source_id="T2", quote=quote)
    result = validate(
        value,
        passages(
            "[00:00:00] Sam: I will check rollback. Friday or Friday after rollback.",
            "",
        ),
    )
    assert result.summary is None
    assert any("Invalid external timing" in s for s in result.blocking)


def test_external_timing_cannot_point_backwards():
    value = draft()
    value.action_items[0].original_commitment_id = "T2"
    value.action_items[0].timing = Timing(source_id="T1", quote="Friday")
    assert (
        validate(value, passages("[00:00:00] Sam: Friday. I will check rollback.", "")).summary
        is None
    )


def test_omitted_task_requests_bounded_correction_without_fabricating_action():
    from meeting_notes.summary import SummaryError

    first = draft("Friday")
    first.key_points = [SupportedText(text="Alex will review next week.", sources=["T2"])]
    corrected = first.model_copy(deep=True)
    corrected.action_items.append(Action(original_commitment_id="T2", timing=None))
    transcript = (
        "[00:00:00] Sam: I will send it Friday.\n[00:00:03] Alex: I will review it next week."
    )
    assert validate(first, passages(transcript, "")).summary is None
    replies = iter([first.model_dump_json(), corrected.model_dump_json()])
    requests: list[dict[str, object]] = []

    def post(path: str, body: dict[str, object]) -> dict[str, object]:
        requests.append(body)
        return {"message": {"content": next(replies)}}

    meeting = Meeting.new("Synthetic", datetime.fromisoformat("2026-10-20T14:00:00-04:00"), ())
    model = OllamaSummarizer("fake", 32768, post, "Sam")
    assert len(model.summarize(meeting, transcript).action_items) == 2
    assert len(requests) == 2 and model.audit.selected == 1
    assert "Possible omitted commitment T2" in json.dumps(requests[1])
    replies = iter([first.model_dump_json(), first.model_dump_json()])
    with pytest.raises(SummaryError, match="Possible omitted commitment T2"):
        model.summarize(meeting, transcript)
    assert len(requests) == 4 and model.audit.selected is None


def test_numeric_correction_cannot_drop_normalized_external_timing():
    first = draft()
    first.action_items[0].timing = Timing(source_id="T2", quote="Friday")
    first.key_points = [SupportedText(text="Cost 777 dollars.", sources=["T3"])]
    correction = first.model_copy(deep=True)
    correction.action_items[0].timing = None
    correction.key_points[0].text = "Cost 80 dollars."
    replies = iter([first.model_dump_json(), correction.model_dump_json()])

    def post(path: str, body: dict[str, object]) -> dict[str, object]:
        return {"message": {"content": next(replies)}}

    meeting = Meeting.new("Synthetic", datetime.fromisoformat("2026-10-20T14:00:00-04:00"), ())
    model = OllamaSummarizer("fake", 32768, post, "Sam")
    result = model.summarize(
        meeting,
        "[00:00:00] Sam: I will check rollback. Friday. Cost 80 dollars.",
    )
    assert model.audit.selected == 0
    assert result.action_items[0].due is None
    assert any("Friday" in s for s in result.action_items[0].review)


@pytest.mark.parametrize(
    "phrase,quote",
    [
        ("after Friday", "Friday"),
        ("not before Friday", "Friday"),
        ("not before Friday", "before Friday"),
        ("at least one week after Friday", "Friday"),
        ("at least one week after Friday", "after Friday"),
        ("at least one week after Friday", "one week after Friday"),
        ("no later than Friday", "Friday"),
        ("only on Friday", "Friday"),
        ("around next Friday", "Friday"),
        ("two weeks before Friday", "before Friday"),
    ],
)
def test_partial_timing_qualifiers_keep_full_commitment_for_review(phrase: str, quote: str):
    text = f"I will send the draft {phrase}."
    result = validate(draft(quote), passages("[00:00:00] Sam: " + text, ""))
    assert result.summary is not None
    action = result.summary.action_items[0]
    assert action.due is None
    assert action.task == text
    assert f"Original commitment: {text}" in action.review


@pytest.mark.parametrize(
    "phrase", ["after Friday", "not before Friday", "at least one week after Friday"]
)
def test_complete_timing_quote_retains_qualifiers(phrase: str):
    result = validate(
        draft(phrase), passages(f"[00:00:00] Sam: I will send the draft {phrase}.", "")
    )
    assert result.summary is not None
    action = result.summary.action_items[0]
    assert action.due == phrase
    assert action.task == "I will send the draft"
    assert not action.review


def test_saved_partial_timing_uses_its_original_validator():
    from meeting_notes.audit import Attempt, CoverageAudit, TimingAudit
    from meeting_notes.compiler_v7 import validate as original_validate

    transcript = "[00:00:00] Sam: I will send the draft after Friday."
    sources = passages(transcript, "")
    value = draft("Friday")
    old = original_validate(value, sources)
    new = validate(value, sources)
    assert old.summary is not None and new.summary is not None
    assert old.summary != new.summary
    evidence = Evidence(
        transcript=transcript, context="", handwritten_original="", handwritten_text=""
    )
    attempt = Attempt(request={}, reply=value.model_dump_json())
    saved = Generation(
        version=6,
        summary=old.summary,
        evidence=evidence,
        audit=CoverageAudit(passages=sources, attempts=[attempt], selected=0),
    )
    assert Generation.model_validate_json(saved.model_dump_json()) == saved
    current = Generation(
        version=7,
        summary=new.summary,
        evidence=evidence,
        audit=TimingAudit(passages=sources, attempts=[attempt], selected=0),
    )
    assert Generation.model_validate_json(current.model_dump_json()) == current
    with pytest.raises(ValueError, match="does not match"):
        Generation(version=7, summary=old.summary, evidence=evidence, audit=current.audit)
