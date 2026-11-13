import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from prototypes.reviewable_draft import Draft, Section
from prototypes.reviewable_draft import examples as examples


def section(draft: Draft, kind: str) -> Section:
    return next(s for s in draft.sections if s.kind == kind)


def test_all_authored_examples_keep_the_exact_frozen_inputs() -> None:
    drafts = examples.load_examples()
    pairs = cast(list[dict[str, Any]], json.loads(examples.PAIRS.read_text()))
    originals = {p["id"]: p for p in pairs}
    assert len(pairs) == 40
    assert tuple(drafts) == examples.CASES
    for name, draft in drafts.items():
        pair = originals[name]
        assert draft.snapshot.transcript == pair["transcript"]
        assert draft.snapshot.handwritten_text == pair["handwritten_text"]
        assert draft.snapshot.title == pair["meeting"]["title"]
        assert draft.snapshot.started_at == pair["meeting"]["started_at"]
        assert draft.snapshot.attendees == tuple(pair["meeting"]["attendees"])
        assert draft.snapshot.my_name == pair["meeting"]["my_name"]


def test_unavailable_comparison_keeps_the_independent_qualified_invoice_suggestion() -> None:
    draft = examples.load_examples()["multi_claim_notes"]
    actions = section(draft, "actions")
    assert section(draft, "review").state == "unavailable"
    assert section(draft, "review").items == ()
    assert [i.text for i in actions.items] == ["Sam — check the invoice not before next Friday."]
    text = examples.preview(draft)
    assert "incomplete" in text.casefold()
    assert "I will check the invoice not before next Friday." in text
    assert draft.snapshot.handwritten_text in text


def test_equivalent_prices_are_shown_as_original_accounts_without_a_conflict_claim() -> None:
    draft = examples.load_examples()["unit_equivalence"]
    assert section(draft, "review").review_sources == ("T1", "N1")
    text = examples.preview(draft)
    assert "Support costs 120 dollars." in text
    assert "Support costs 12000 cents." in text
    assert "conflict" not in text.casefold()


def test_shared_evidence_is_quoted_once_instead_of_repeated_under_each_section() -> None:
    draft = examples.load_examples()["multi_claim_notes"]
    text = examples.preview(draft)
    assert text.count(draft.snapshot.sources[0].text) == 1
    assert "## Source excerpts" in text


def test_negative_controls_do_not_gain_suggested_current_work() -> None:
    drafts = examples.load_examples()
    assert section(drafts["accepted_status_answer"], "actions").items == ()
    retracted = drafts["accepted_request_retracted"]
    assert section(retracted, "actions").items == ()
    assert section(retracted, "review").review_sources == ("T1", "T2", "T3")
    partial = drafts["partial_coordination_retracted"]
    assert section(partial, "actions").items == ()
    assert section(partial, "actions").review_sources == ("T1", "T2")
    assert "still-relevant invoice-sending work" in section(partial, "actions").notice
    replacement = drafts["cancellation_with_new_task"]
    assert [i.text for i in section(replacement, "actions").items] == ["Sam — send the invoice."]


def test_original_and_complete_later_timing_are_available_together() -> None:
    draft = examples.load_examples()["qualified_external_timing"]
    action = section(draft, "actions")
    assert action.state == "needs_review"
    assert action.review_sources == ("T1", "T2")
    text = examples.preview(draft)
    assert "I will send the invoice." in text
    assert "Not before next Friday unless finance objects." in text


def test_preview_export_never_overwrites_an_edited_directory(tmp_path: Path) -> None:
    output = tmp_path / "previews"
    examples.write_previews(output)
    edited = output / "empty.md"
    edited.write_text("Owner edits stay here.\n")
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    with pytest.raises(FileExistsError):
        examples.write_previews(output)
    assert {p.name: p.read_bytes() for p in output.iterdir()} == before


def test_exported_preview_and_input_hashes_match_the_captured_bytes(tmp_path: Path) -> None:
    output = tmp_path / "previews"
    examples.write_previews(output)
    manifest = cast(dict[str, Any], json.loads((output / "manifest.json").read_text()))
    assert manifest["kind"] == "authored_offline_rendering"
    assert manifest["model_requests"] == 0
    assert manifest["input_sha256"] == hashlib.sha256(examples.PAIRS.read_bytes()).hexdigest()
    assert manifest["fixture_sha256"] == hashlib.sha256(examples.FIXTURES.read_bytes()).hexdigest()
    assert set(manifest["previews"]) == set(examples.CASES)
    for name in examples.CASES:
        text = (output / f"{name}.md").read_bytes()
        assert hashlib.sha256(text).hexdigest() == manifest["previews"][name]["sha256"]
        assert b"No model generated this preview." in text


def test_bad_frozen_input_does_not_create_a_preview_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pair_file = tmp_path / "pairs.json"
    pair_file.write_bytes(examples.PAIRS.read_bytes() + b"\n")
    (tmp_path / "sha256.json").write_bytes((examples.PAIRS.parent / "sha256.json").read_bytes())
    monkeypatch.setattr(examples, "PAIRS", pair_file)
    output = tmp_path / "previews"
    with pytest.raises(ValueError, match="Frozen synthetic inputs changed"):
        examples.write_previews(output)
    assert not output.exists()


def test_unlabelled_responses_cannot_be_exported_as_authored_examples(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = cast(dict[str, Any], json.loads(examples.FIXTURES.read_text()))
    fixture["authored"] = False
    path = tmp_path / "responses.json"
    path.write_text(json.dumps(fixture))
    monkeypatch.setattr(examples, "FIXTURES", path)
    output = tmp_path / "previews"
    with pytest.raises(ValueError, match="explicitly identified as authored"):
        examples.write_previews(output)
    assert not output.exists()


def test_example_command_renders_a_reviewable_partial_draft_without_the_app() -> None:
    result = subprocess.run(
        [sys.executable, "-B", "-m", "prototypes.reviewable_draft", "--case", "multi_claim_notes"],
        cwd=examples.ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "No model generated this preview." in result.stdout
    assert "incomplete" in result.stdout.casefold()
    assert "Sam" in result.stdout and "not before next Friday" in result.stdout


def test_checked_in_previews_reproduce_exactly(tmp_path: Path) -> None:
    output = tmp_path / "previews"
    examples.write_previews(output)
    committed = Path(__file__).parent / "previews"
    assert {p.name for p in output.iterdir()} == {p.name for p in committed.iterdir()}
    for path in output.iterdir():
        assert path.read_bytes() == (committed / path.name).read_bytes(), path.name
