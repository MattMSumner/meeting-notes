"""The manual quote preview changes only the requested note sections."""

import json
import socket
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from meeting_notes.meeting import Meeting
from meeting_notes.render import render_note
from meeting_notes.summary import ActionItem, Detail, Summary, SummaryError
from meeting_notes.turns import parse_turns

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import preview_commitments
from scripts.preview_commitments import generate_previews, quote_section, replace_commitments

FIXTURES = Path(__file__).parent / "fixtures"
SELECTIONS = FIXTURES / "commitment_quote_selections.json"
FULL_CASES = ("golden", "availability", "numbers")
type Inputs = tuple[Path, Path, Path, Path, Path]


@pytest.fixture
def preview_inputs(tmp_path: Path) -> Inputs:
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    selections = tmp_path / "selections.json"
    selections.write_bytes(SELECTIONS.read_bytes())
    selected: dict[str, list[str]] = json.loads(selections.read_text())
    rows: list[dict[str, Any]] = []
    full_rows: list[dict[str, Any]] = []
    for case, ids in selected.items():
        text = (FIXTURES / f"{case}_transcript.txt").read_text()
        (fixtures / f"{case}_transcript.txt").write_text(text)
        turns = parse_turns(text)
        first = next((turn for turn in turns if turn.id in ids), turns[0])
        summary = Summary(
            overview=f"Sam discussed the synthetic {case} fixture.",
            decisions=["Keep the synthetic test policy"],
            action_items=[ActionItem(owner="Sam", task="Review the synthetic proposal", due=None)],
            details=[Detail(speaker=first.speaker, start=first.start, quote=first.text)],
        )
        rows.append({"case": case, "run": 1, "summary": summary.model_dump()})
        if case in FULL_CASES:
            full_rows.append({"case": case, "run": 1, "summary": summary.model_dump()})
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"rows": rows}))
    full = tmp_path / "full.json"
    full.write_text(json.dumps(full_rows))
    return fixtures, selections, baseline, full, tmp_path / "preview"


def test_quotes_preserve_whole_turn_words_speaker_and_time():
    transcript = (
        "[00:01:04] Sam: Could you review  the guide, including rollback?\n"
        "[00:01:11] Them: Yes — I'll finish it by Thursday.\n"
    )
    section = quote_section(transcript, ["t1", "t2"])
    assert "Sam" in section and "Them" in section
    assert "00:01:04" in section and "00:01:11" in section
    assert "Could you review the guide, including rollback?" in section
    assert "Yes — I'll finish it by Thursday." in section


def test_repeated_ids_restore_source_order_without_merging_equal_timestamps():
    transcript = (
        "[00:00:02] Sam: First independent promise.\n"
        "[00:00:02] Sam: Second independent promise.\n"
        "[00:00:09] Them: Unselected context.\n"
    )
    section = quote_section(transcript, ["t2", "t1", "t2"])
    assert section.count("First independent promise.") == 1
    assert section.count("Second independent promise.") == 1
    assert section.index("First independent promise.") < section.index(
        "Second independent promise."
    )
    assert section.count("00:00:02") == 2
    assert "Unselected context." not in section


def test_distinct_ids_with_identical_speaker_time_and_text_remain_distinct():
    transcript = "[00:00:02] Sam: I'll review it.\n[00:00:02] Sam: I'll review it.\n"
    section = quote_section(transcript, ["t2", "t1", "t2"])
    assert section.count("I'll review it.") == 2
    assert section.count("00:00:02") == 2


def test_unknown_id_fails_instead_of_silently_omitting_it():
    with pytest.raises(SummaryError, match="Unknown turn IDs"):
        quote_section("[00:00:02] Sam: I'll review the guide.\n", ["t2"])


@pytest.mark.parametrize(
    "case,required",
    [
        ("golden", {"t9", "t10", "t11", "t12", "t13"}),
        ("availability", {"t9", "t10", "t11", "t12", "t13"}),
        ("numbers", {"t10", "t11", "t12"}),
        ("conditional_commitments", {"t1", "t2", "t3"}),
        ("timing_roles", {"t1", "t2", "t3", "t4", "t5"}),
        ("accepted_requests", {"t1", "t2", "t3", "t5", "t6"}),
    ],
)
def test_manual_selections_keep_requests_acceptances_and_qualifying_context(
    case: str, required: set[str]
):
    selected: dict[str, list[str]] = json.loads(SELECTIONS.read_text())
    assert required <= set(selected[case])
    text = (FIXTURES / f"{case}_transcript.txt").read_text()
    section = quote_section(text, selected[case])
    for turn in parse_turns(text):
        if turn.id in required:
            assert turn.text in section
    # These neighboring turns resolve the subject and preserve pending approval.
    if case in ("golden", "availability"):
        assert "the on-call rotation" in section and "Let's not change it this month" in section
    if case == "conditional_commitments":
        assert "approval is still pending" in section
    if case == "accepted_requests":
        assert "The review should cover the rollback section" in section


def test_negative_control_has_no_selected_commitments():
    selected: dict[str, list[str]] = json.loads(SELECTIONS.read_text())
    assert selected["no_commitments"] == []
    text = (FIXTURES / "no_commitments_transcript.txt").read_text()
    section = quote_section(text, selected["no_commitments"])
    assert "_None selected._" in section
    assert all(turn.text not in section for turn in parse_turns(text))


def test_replacement_preserves_overview_details_frontmatter_and_transcript_link():
    text = "I'll review the rollback section by Thursday."
    meeting = Meeting.new("Synthetic preview", datetime(2026, 10, 20, 10))
    summary = Summary(
        overview="Sam and Riley discussed the guide.",
        decisions=["Use the new guide"],
        action_items=[ActionItem(owner="Sam", task="Review the rollback section", due="Thursday")],
        details=[Detail(speaker="Sam", start=2, quote=text)],
    )
    before = render_note(meeting, summary, meeting.id, warnings=["A synthetic warning"])
    section = quote_section(f"[00:00:02] Sam: {text}\n", ["t1"])
    after = replace_commitments(before, section)
    prefix = before.split("## Decisions\n", 1)[0]
    suffix = before[before.rindex("Transcript: [[") :]
    assert after.startswith(prefix)
    assert after.endswith(suffix)
    assert after[len(prefix) : -len(suffix)].rstrip() == section.rstrip()
    assert text in prefix and after.count(text) == 2
    assert "## Decisions\n" not in after and "## Action items\n" not in after
    assert "- [ ]" not in after


def test_generation_is_local_and_preserves_every_input(
    preview_inputs: Inputs, monkeypatch: pytest.MonkeyPatch
):
    def no_network(*args: Any, **kwargs: Any) -> None:
        pytest.fail("The manual preview must not call a network service or model")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    fixtures, selections, baseline, full, output = preview_inputs
    root = fixtures.parent
    before = {
        path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()
    }
    generate_previews(fixtures, selections, baseline, full, output)
    after = {
        path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()
    }
    assert all(after[name] == content for name, content in before.items())
    assert all(name.parts[0] == output.name for name in after.keys() - before.keys())
    cases: dict[str, list[str]] = json.loads(selections.read_text())
    expected = {"index.md", "report.json", *(f"{case}-comparison.md" for case in cases)}
    expected.update(
        f"{case}-full-{version}.md" for case in FULL_CASES for version in ("before", "after")
    )
    assert {path.name for path in output.iterdir()} == expected
    for case in FULL_CASES:
        before_note = (output / f"{case}-full-before.md").read_text()
        after_note = (output / f"{case}-full-after.md").read_text()
        prefix = before_note.split("## Decisions\n", 1)[0]
        assert after_note.startswith(prefix)
        assert (
            after_note[after_note.rindex("Transcript: [[") :]
            == before_note[before_note.rindex("Transcript: [[") :]
        )
        overlapping = next(
            turn
            for turn in parse_turns((fixtures / f"{case}_transcript.txt").read_text())
            if turn.id in cases[case]
        )
        assert overlapping.text in prefix and after_note.count(overlapping.text) == 2
    report = json.loads((output / "report.json").read_text())
    assert report["manual_selection"] is True
    assert report["model_calls"] == 0
    assert report["cases"]["no_commitments"]["quoted_turn_count"] == 0
    assert all(report["cases"][case]["details_overlap_count"] == 1 for case in FULL_CASES)


def test_unknown_selection_leaves_no_partial_output(preview_inputs: Inputs):
    fixtures, selections, baseline, full, output = preview_inputs
    manifest = json.loads(selections.read_text())
    manifest["accepted_requests"].append("t999")
    selections.write_text(json.dumps(manifest))
    with pytest.raises(SummaryError, match="Unknown turn IDs"):
        generate_previews(fixtures, selections, baseline, full, output)
    assert not output.exists()


def test_existing_preview_is_never_overwritten(preview_inputs: Inputs):
    *_, output = preview_inputs
    output.mkdir()
    marker = output / "reviewed.txt"
    marker.write_text("Keep this reviewed preview.")
    with pytest.raises(FileExistsError):
        generate_previews(*preview_inputs)
    assert marker.read_text() == "Keep this reviewed preview."
    assert list(output.iterdir()) == [marker]


@pytest.mark.parametrize("archive", ["baseline", "full"])
@pytest.mark.parametrize("problem", ["missing_case", "invalid_summary"])
def test_invalid_archives_fail_before_writing(preview_inputs: Inputs, archive: str, problem: str):
    _, _, baseline, full, output = preview_inputs
    path = baseline if archive == "baseline" else full
    data = json.loads(path.read_text())
    rows = data["rows"] if archive == "baseline" else data
    if problem == "missing_case":
        rows.pop()
    else:
        rows[0]["summary"] = {"overview": "Missing required decisions and actions"}
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        generate_previews(*preview_inputs)
    assert not output.exists()


@pytest.fixture
def preview_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True, capture_output=True)
    monkeypatch.setattr(preview_commitments, "REPO", tmp_path)
    return tmp_path


def test_cli_accepts_an_ignored_preview_destination(preview_repo: Path):
    (preview_repo / ".gitignore").write_text("/.local/m9-quoted-preview/\n")
    output = preview_repo / ".local/m9-quoted-preview/review"
    assert preview_commitments.check_output(output) == output.resolve()
    assert not output.exists()


def test_cli_rejects_unignored_preview_output(preview_repo: Path):
    output = preview_repo / ".local/m9-quoted-preview/review"
    with pytest.raises(ValueError, match="ignored|exclude"):
        preview_commitments.check_output(output)
    assert not output.exists()


def test_cli_rejects_output_outside_its_preview_directory_even_if_ignored(preview_repo: Path):
    (preview_repo / ".gitignore").write_text("/.local/\n")
    output = preview_repo / ".local/unrelated-output"
    with pytest.raises(ValueError):
        preview_commitments.check_output(output)
    assert not output.exists()


@pytest.mark.parametrize("escape_at_root", [False, True])
def test_cli_rejects_symlinks_escaping_the_preview_directory(
    preview_repo: Path, escape_at_root: bool
):
    (preview_repo / ".gitignore").write_text("/.local/\n")
    outside = preview_repo / "outside"
    outside.mkdir()
    base = preview_repo / ".local/m9-quoted-preview"
    link = base if escape_at_root else base / "linked"
    link.parent.mkdir(parents=True)
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        preview_commitments.check_output(link / "review")
    assert list(outside.iterdir()) == []
