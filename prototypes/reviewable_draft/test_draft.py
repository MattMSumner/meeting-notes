"""Synthetic contracts for an authored draft, not a semantic quality evaluation."""

import socket
import subprocess
from collections.abc import Callable
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import NoReturn, cast

import pytest

from . import Draft, Item, Section, Snapshot, Source, render
from .model import KINDS

_SNAPSHOT = Snapshot(
    title="Synthetic planning",
    started_at="2026-11-13T09:00:00-05:00",
    attendees=("Rae", "Quinn"),
    my_name="Rae",
    transcript=(
        "[00:00:00] Rae: I will check the invoice after approval. Keep that condition.\n"
        "[00:00:08] Quinn: We can revisit the capacity estimate later."
    ),
    handwritten_text="  Ask about capacity\n\nKeep the estimates separate.\n",
)


def _draft(
    *overrides: Section,
    snapshot: Snapshot = _SNAPSHOT,
    generation_id: str = "authored-1",
) -> Draft:
    sections = {kind: Section(kind, "draft", snapshot.snapshot_id, generation_id) for kind in KINDS}
    sections.update({section.kind: section for section in overrides})
    return Draft(snapshot, generation_id, tuple(sections.values()))


def test_valid_action_survives_optional_review_failure() -> None:
    draft = _draft(
        Section(
            "actions",
            "draft",
            _SNAPSHOT.snapshot_id,
            "authored-1",
            (Item("Rae will check the invoice after approval.", ("T1",)),),
        ),
        Section(
            "review",
            "unavailable",
            _SNAPSHOT.snapshot_id,
            "authored-1",
            notice="The written capacity comparison is unavailable; inspect these passages.",
            review_sources=("T2", "N1"),
        ),
    )
    output = render(draft)
    assert "Incomplete draft" in output
    assert "Rae will check the invoice after approval" in output
    assert "Written by Rae" in output
    assert "Spoken by Quinn" in output
    assert "capacity comparison is unavailable" in output
    assert _SNAPSHOT.snapshot_id not in output
    assert "authored-1" not in output
    assert "T1" not in output and "N1" not in output


def test_rejected_section_items_cannot_publish_even_if_record_is_forged() -> None:
    section = Section(
        "review",
        "unavailable",
        _SNAPSHOT.snapshot_id,
        "authored-1",
        notice="The written comparison did not finish.",
        review_sources=("T2", "N1"),
    )
    rejected = (Item("Rejected comparison prose", ("T2", "N1")),)
    with pytest.raises(ValueError, match="unavailable"):
        replace(section, items=rejected)
    draft = _draft(section)
    object.__setattr__(section, "items", rejected)
    with pytest.raises(ValueError, match="unavailable"):
        render(draft)


def test_partial_cancellation_keeps_whole_passages_in_focused_review() -> None:
    snapshot = replace(
        _SNAPSHOT,
        transcript=(
            "[00:00:00] Rae: I will review the draft and send the invoice after approval.\n"
            "[00:00:09] Quinn: Cancel the draft review. Invoice sending still follows approval."
        ),
    )
    draft = _draft(
        Section(
            "actions",
            "needs_review",
            snapshot.snapshot_id,
            "authored-1",
            (Item("Rae will send the invoice after approval.", ("T1", "T2")),),
            notice="Inspect the cancelled review alongside the remaining invoice work.",
            review_sources=("T1", "T2"),
        ),
        snapshot=snapshot,
    )
    output = render(draft)
    assert "Needs review" in output
    assert "Incomplete draft" not in output
    assert "Rae will send the invoice after approval" in output
    assert "Context to review" in output
    assert "I will review the draft and send the invoice after approval." in output
    assert "Cancel the draft review. Invoice sending still follows approval." in output
    assert len(snapshot.sources) == 4  # Two whole turns and two written lines.


def test_passages_keep_whole_turns_and_raw_writing_gaps() -> None:
    writing = "\r\n  First written line  \r\n\r\n\tSecond written line\n\n"
    transcript = (
        "[00:00:00] Rae: First sentence. Second sentence.\n\nA continuation.\n"
        "[00:01:00] Quinn: Yes."
    )
    snapshot = replace(_SNAPSHOT, transcript=transcript, handwritten_text=writing)
    spoken, reply, first, second = snapshot.sources
    assert spoken == Source(
        "T1",
        "transcript",
        "Rae",
        "00:00:00",
        "First sentence. Second sentence.\n\nA continuation.\n",
    )
    assert reply.text == "Yes."
    assert (first.id, first.text, second.id, second.text) == (
        "N1",
        "  First written line  ",
        "N2",
        "\tSecond written line",
    )
    assert snapshot.handwritten_text == writing
    assert writing in render(_draft(snapshot=snapshot))
    with pytest.raises(FrozenInstanceError):
        first.__setattr__("text", "changed")


def test_fingerprint_includes_every_metadata_and_raw_input_field() -> None:
    alternatives = (
        replace(_SNAPSHOT, title="Another synthetic title"),
        replace(_SNAPSHOT, started_at="2026-11-14T09:00:00-05:00"),
        replace(_SNAPSHOT, attendees=("Quinn", "Rae")),
        replace(_SNAPSHOT, my_name="Quinn"),
        replace(_SNAPSHOT, transcript=_SNAPSHOT.transcript + "\n"),
        replace(_SNAPSHOT, handwritten_text=_SNAPSHOT.handwritten_text + "\n"),
    )
    assert len({snapshot.snapshot_id for snapshot in (_SNAPSHOT, *alternatives)}) == 7
    assert replace(_SNAPSHOT).snapshot_id == _SNAPSHOT.snapshot_id


def test_sections_cannot_mix_snapshots_or_generations_even_with_identical_words() -> None:
    section = Section(
        "summary", "draft", _SNAPSHOT.snapshot_id, "authored-1", (Item("Same words", ("T1",)),)
    )
    with pytest.raises(ValueError, match="snapshot"):
        _draft(section, snapshot=replace(_SNAPSHOT, title="Different context"))
    with pytest.raises(ValueError, match="generation"):
        _draft(replace(section, generation_id="authored-2"))
    with pytest.raises(ValueError, match="generation"):
        replace(_draft(section), generation_id="authored-2")


def test_draft_requires_exactly_four_distinct_section_kinds() -> None:
    draft = _draft()
    with pytest.raises(ValueError, match="each section kind"):
        replace(draft, sections=draft.sections[:-1])
    with pytest.raises(ValueError, match="distinct"):
        replace(draft, sections=(*draft.sections, draft.sections[0]))


@pytest.mark.parametrize("kind", ("summary", "decisions", "actions"))
def test_spoken_sections_reject_written_items_and_focused_context(kind: str) -> None:
    section = next(section for section in _draft().sections if section.kind == kind)
    with pytest.raises(ValueError, match="transcript"):
        _draft(replace(section, items=(Item("A written observation", ("N1",)),)))
    with pytest.raises(ValueError, match="transcript"):
        _draft(
            replace(
                section, state="needs_review", notice="Inspect the timing.", review_sources=("N1",)
            )
        )


def test_review_can_cite_both_origins_without_classifying_their_relationship() -> None:
    output = render(
        _draft(
            Section(
                "review",
                "draft",
                _SNAPSHOT.snapshot_id,
                "authored-1",
                (Item("Inspect these two passages.", ("T2", "N1")),),
            )
        )
    )
    assert "Spoken by Quinn" in output and "Written by Rae" in output
    assert "We can revisit the capacity estimate later." in output
    assert "  Ask about capacity" in output
    assert "conflict" not in output


def test_unknown_and_duplicate_references_are_rejected() -> None:
    section = _draft().sections[0]
    with pytest.raises(ValueError, match="unknown source"):
        _draft(replace(section, items=(Item("Unsupported passage", ("T999",)),)))
    with pytest.raises(ValueError, match="unknown source"):
        _draft(replace(section, review_sources=("N999",)))
    with pytest.raises(ValueError, match="repeat"):
        Item("Duplicate source", ("T1", "T1"))
    with pytest.raises(ValueError, match="repeat"):
        replace(section, review_sources=("T1", "T1"))
    with pytest.raises(ValueError, match="sources"):
        Item("No source", ())


@pytest.mark.parametrize("state", ("needs_review", "unavailable"))
def test_incomplete_analysis_requires_a_notice_and_focused_context(state: str) -> None:
    section = Section("review", "draft", _SNAPSHOT.snapshot_id, "authored-1")
    unchecked_replace = cast(Callable[..., Section], replace)
    with pytest.raises(ValueError, match="notice"):
        unchecked_replace(section, state=state, review_sources=("T2",))
    with pytest.raises(ValueError, match="sources"):
        unchecked_replace(section, state=state, notice="Inspect the capacity wording.")


def test_missing_snapshot_and_missing_writing_are_errors_but_empty_writing_is_normal() -> None:
    empty = replace(_SNAPSHOT, handwritten_text="")
    assert all(source.kind == "transcript" for source in empty.sources)
    assert "No handwritten notes." in render(_draft(snapshot=empty))
    with pytest.raises(TypeError, match="Snapshot"):
        replace(_draft(), snapshot=cast(Snapshot, None))
    with pytest.raises(TypeError, match="handwritten_text"):
        replace(_SNAPSHOT, handwritten_text=cast(str, None))
    unchecked_snapshot = cast(Callable[..., Snapshot], Snapshot)
    with pytest.raises(TypeError, match="handwritten_text"):
        unchecked_snapshot("Synthetic", "2026-11-13", (), "Rae", _SNAPSHOT.transcript)


@pytest.mark.parametrize(
    "transcript",
    (
        "not a timestamped turn",
        "[00:99:00] Rae: Bad timestamp.",
        "[00:00:00] Rae: Valid.\n[bad timestamp] Quinn: Must not disappear.",
        "[00:00:00] Rae:   ",
    ),
)
def test_malformed_transcript_cannot_silently_disappear(transcript: str) -> None:
    with pytest.raises(ValueError):
        replace(_SNAPSHOT, transcript=transcript)


def test_non_string_raw_input_is_rejected() -> None:
    with pytest.raises(TypeError, match="transcript"):
        replace(_SNAPSHOT, transcript=cast(str, ["A turn"]))
    with pytest.raises(TypeError, match="attendee"):
        replace(_SNAPSHOT, attendees=(cast(str, 7),))


def test_mutable_nesting_is_rejected_at_every_collection_boundary() -> None:
    section = _draft().sections[0]
    with pytest.raises(TypeError, match="tuple"):
        replace(_SNAPSHOT, attendees=cast(tuple[str, ...], ["Rae"]))
    with pytest.raises(TypeError, match="tuple"):
        Item("Mutable references", cast(tuple[str, ...], ["T1"]))
    with pytest.raises(TypeError, match="tuple"):
        replace(section, items=cast(tuple[Item, ...], [Item("Valid", ("T1",))]))
    with pytest.raises(TypeError, match="tuple"):
        replace(section, review_sources=cast(tuple[str, ...], ["T1"]))
    with pytest.raises(TypeError, match="tuple"):
        replace(_draft(), sections=cast(tuple[Section, ...], [section]))


def test_wrong_record_types_and_forged_mutable_nesting_cannot_render() -> None:
    with pytest.raises(TypeError, match="Item"):
        replace(_draft().sections[0], items=(cast(Item, "wrong record"),))
    with pytest.raises(TypeError, match="Section"):
        replace(_draft(), sections=(cast(Section, Item("Wrong record", ("T1",))),))
    draft = _draft()
    object.__setattr__(draft.sections[0], "review_sources", ["T1"])
    with pytest.raises(TypeError, match="tuple"):
        render(draft)
    with pytest.raises(TypeError, match="Draft"):
        render(cast(Draft, "wrong record"))


def test_model_prose_cannot_inject_markdown_html_or_checklists() -> None:
    attack = (
        "# Hidden heading\n- [x] Claim accepted\n<!-- hide --> <script>alert(1)</script> [[target]]"
    )
    snapshot = replace(_SNAPSHOT, title=attack, my_name="<b>Rae</b>")
    output = render(
        _draft(
            Section(
                "review",
                "needs_review",
                snapshot.snapshot_id,
                "authored-1",
                (Item(attack, ("T1",)),),
                notice=attack,
                review_sources=("T1",),
            ),
            snapshot=snapshot,
        )
    )
    assert "\\# Hidden heading" in output
    assert "\\- \\[x\\] Claim accepted" in output
    assert "&lt;\\!" in output and "&lt;script&gt;" in output
    assert "\\[\\[target\\]\\]" in output
    assert "<script>" not in output and "<!--" not in output
    assert "\n- [x]" not in output and "\n# Hidden heading" not in output
    assert "&lt;b&gt;Rae&lt;\\/b&gt;" in output


def test_original_sources_stay_literal_even_when_they_contain_fences_or_checklists() -> None:
    writing = "\n```\n# Literal heading\n- [x] Personal writing\n<script>literal</script>\n````\n\n"
    snapshot = replace(
        _SNAPSHOT,
        handwritten_text=writing,
        transcript="[00:00:00] <b>Rae</b>: ```\n- [ ] Quoted speech\n````",
    )
    output = render(
        _draft(
            Section(
                "actions",
                "draft",
                snapshot.snapshot_id,
                "authored-1",
                (Item("Inspect the quoted speech.", ("T1",)),),
            ),
            snapshot=snapshot,
        )
    )
    assert "Spoken by &lt;b&gt;Rae&lt;\\/b&gt;" in output
    assert "00\\:00\\:00" in output
    assert f"`````text\n{writing}`````" in output
    # Every checkbox-like line is inside a code fence, never an executable task.
    fence: str | None = None
    for line in output.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("`"):
            ticks = stripped.split("text")[0]
            if fence is None:
                fence = ticks
            elif stripped == fence:
                fence = None
        if stripped.startswith(("- [ ]", "- [x]")):
            assert fence is not None
    assert fence is None


def test_render_uses_saved_values_after_original_files_change_and_performs_no_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    notes = tmp_path / "synthetic-notes.txt"
    transcript = tmp_path / "synthetic-transcript.txt"
    notes.write_text("Saved handwritten wording.\n\n", encoding="utf-8")
    transcript.write_text(_SNAPSHOT.transcript, encoding="utf-8")
    snapshot = replace(
        _SNAPSHOT, handwritten_text=notes.read_text(), transcript=transcript.read_text()
    )
    draft = _draft(snapshot=snapshot)
    notes.write_text("Changed later.", encoding="utf-8")
    transcript.unlink()

    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("render attempted IO")

    with monkeypatch.context() as patch:
        patch.setattr("builtins.open", forbidden)
        for method in ("open", "read_text", "read_bytes", "write_text", "write_bytes"):
            patch.setattr(Path, method, forbidden)
        patch.setattr(socket, "socket", forbidden)
        patch.setattr(subprocess, "Popen", forbidden)
        first, second = render(draft), render(draft)
    assert first == second
    assert "Saved handwritten wording.\n\n" in first
    assert "Changed later" not in first
    assert "Synthetic planning" in first


def test_valid_references_do_not_establish_meaning() -> None:
    # Deliberately wrong authored meaning still passes the mechanical boundary.
    output = render(
        _draft(
            Section(
                "actions",
                "draft",
                _SNAPSHOT.snapshot_id,
                "authored-1",
                (Item("Quinn will launch a fictional rocket today.", ("T1",)),),
            )
        )
    )
    assert "fictional rocket today" in output
    assert "**AI draft — review required**" in output
    assert "Review and edit these suggestions before using them" in output
