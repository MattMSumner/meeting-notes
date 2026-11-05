import json
from datetime import datetime

import pytest

from meeting_notes.compiler import passages, validate
from meeting_notes.contract import Action, Dispute, Draft, SupportedText
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
        action_items=[Action(commitment="T1", timing=timing, timing_context=context or [])],
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
    value.action_items[0].commitment = "N1"
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
        version=3,
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
    value.action_items[0].commitment = "T2"
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
    value.action_items.append(Action(commitment="T1", timing="Monday", timing_context=[]))
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
    invalid.action_items[0].commitment = "missing"
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
