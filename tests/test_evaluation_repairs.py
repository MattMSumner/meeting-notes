"""Replay observed omissions and conflict grouping without contacting a model."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from meeting_notes.compiler import passages, validate
from meeting_notes.contract import Action, Dispute, Draft, SupportedText
from meeting_notes.meeting import Meeting
from meeting_notes.ollama import OllamaSummarizer

ROOT = Path(__file__).resolve().parents[1] / "evaluation/m10/v8"


@pytest.mark.parametrize("case", ["empty", "status_conflict"])
def test_observed_failure_requires_correction_and_preserves_unrelated_commitments(case: str):
    pair = next(p for p in json.loads((ROOT / "pairs.json").read_text()) if p["id"] == case)
    row = next(
        json.loads(s)
        for s in (ROOT / "results/proposed.jsonl").read_text().splitlines()[1:]
        if json.loads(s)["case"] == case
    )
    reply = row["audit"]["attempts"][row["audit"]["selected"]]["reply"]
    value = Draft.model_validate_json(reply)
    sources = passages(pair["transcript"], pair["handwritten_text"])
    checked = validate(value, sources)
    assert checked.summary is None
    corrected = value.model_copy(deep=True)
    if case == "empty":
        assert any("omitted agreement T4" in b for b in checked.blocking)
        corrected.decisions = [SupportedText(text="Release Friday.", sources=["T4"])]
    else:
        assert any("groups commitments" in b for b in checked.blocking)
        corrected.conflicts[0].transcript = ["T1"]
    responses_list = [reply, corrected.model_dump_json()]
    if case == "status_conflict":
        from comparison_helpers import account

        from meeting_notes.comparison import Claim, Comparison

        comparison = Comparison(
            claims=[
                Claim(
                    note=account("N1", sources[-1].text),
                    transcript=[account("T1", sources[0].text)],
                    outcome="conflicting",
                    reason="Different readiness accounts.",
                )
            ]
        )
        corrected.conflicts = []
        corrected.key_points = [
            item
            for item in corrected.key_points
            if all(ref.startswith("T") for ref in item.sources)
        ]
        responses_list = [comparison.model_dump_json(), reply, corrected.model_dump_json()]
    responses = iter(responses_list)
    requests: list[dict[str, Any]] = []

    def post(path: str, body: dict[str, Any]) -> dict[str, Any]:
        requests.append(body)
        return {"message": {"content": next(responses)}}

    engine = OllamaSummarizer("fake", 32768, post, "Sam")
    result = engine.summarize(
        Meeting.new("Synthetic", datetime(2026, 1, 1)),
        pair["transcript"],
        handwritten_text=pair["handwritten_text"],
    )
    assert len(requests) == (2 if case == "empty" else 3) and engine.audit.selected == 1
    if case == "empty":
        assert result.decisions == ["Release Friday."]
        assert len(result.action_items) == 2
    else:
        assert result.conflicts[0].transcript == "I think the staging environment is ready."
        assert result.action_items[0].task == "I will verify the health checks."
        assert not result.action_items[0].review


def test_genuinely_disputed_commitment_can_have_its_own_conflict():
    value = Draft(
        overview=[],
        key_points=[],
        decisions=[],
        action_items=[Action(original_commitment_id="T1", timing=None)],
        timing_updates=[],
        notes_context=[],
        conflicts=[Dispute(topic="Task", transcript=["T1"], notes=["N1"])],
    )
    checked = validate(
        value,
        passages("[00:00:00] Sam: I will check the invoice.", "The invoice check was cancelled."),
    )
    assert checked.summary is not None
    assert checked.summary.action_items[0].review


@pytest.mark.parametrize("section", ["overview", "key_points", "decisions"])
def test_flat_id_vocabulary_does_not_allow_notes_in_spoken_sections(section: str):
    value = Draft(
        overview=[],
        key_points=[],
        decisions=[],
        action_items=[],
        timing_updates=[],
        notes_context=[],
        conflicts=[],
    )
    setattr(value, section, [SupportedText(text="Launch approved.", sources=["N1"])])
    checked = validate(value, passages("[00:00:00] Sam: We discussed launch.", "Launch approved."))
    assert checked.summary is None
    assert "Invalid transcript source: N1" in checked.blocking
