# pyright: reportPrivateUsage=false

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from . import work_review as review
from . import work_review_examples as examples


def inventory(path: Path) -> dict[str, bytes]:
    return {file.name: file.read_bytes() for file in path.iterdir()}


def test_seven_authored_source_mappings_preserve_complete_input_identity() -> None:
    results = examples.load_examples()
    mapping = json.loads((examples.PROPOSAL / "examples.json").read_bytes())
    pairs = {row["id"]: row for row in json.loads(examples.PAIRS.read_bytes())}
    assert len(pairs) == 40 and tuple(results) == examples.CASES
    for row in mapping["examples"]:
        result = results[row["case"]]
        assert result.state == "draft"
        assert result.snapshot_id == row["snapshot_id"] == result.snapshot.snapshot_id
        assert [list(group.refs) for group in result.groups] == row["groups"]
        if row["case"] != "authored_longer_context":
            original = pairs[row["case"]]
            assert result.snapshot.transcript == original["transcript"]
            assert result.snapshot.handwritten_text == original["handwritten_text"]
            assert result.snapshot.title == original["meeting"]["title"]
            assert result.snapshot.started_at == original["meeting"]["started_at"]
            assert result.snapshot.attendees == tuple(original["meeting"]["attendees"])
            assert result.snapshot.my_name == original["meeting"]["my_name"]
    longer = results["authored_longer_context"]
    assert len([s for s in longer.snapshot.sources if s.kind == "transcript"]) == 16
    assert [group.refs for group in longer.groups] == [("T4", "T6", "T10"), ("T11",)]
    text = examples.preview(longer)
    assert "I will not review the outline." in text
    assert "not before next Tuesday, unless the mock finance team objects." in text
    assert "next week, after the dummy approval arrives." in text
    assert "The demo room is on the second floor." not in text
    assert "Task for myself: ask the dummy venue about access." in text
    additional = examples.preview(results["additional"])
    assert "Spoken by Them" in additional and "Spoken by Alex" not in additional


def test_authored_failure_examples_are_not_repaired_or_passing_coverage() -> None:
    normal = examples.load_examples()
    failures = examples.failure_examples(normal)
    partial = failures["incomplete_longer_context"]
    assert partial.state == "incomplete"
    assert [group.refs for group in partial.groups] == [("T11",)]
    assert partial.snapshot == normal["authored_longer_context"].snapshot
    assert partial.generation_id != normal["authored_longer_context"].generation_id
    text = examples.preview(partial)
    assert "not a passing coverage example" in text
    assert "**Incomplete selection.**" in text and "Other work or context may be missing" in text
    assert "after the dummy approval arrives" in text
    assert "send the sample invoice" not in text
    unavailable = failures["unavailable_additional"]
    assert unavailable.state == "unavailable" and unavailable.groups == ()
    assert unavailable.snapshot.handwritten_text in examples.preview(unavailable)
    assert "**Passage selection unavailable.**" in examples.preview(unavailable)
    assert normal["additional"].state == "draft"


def test_previews_reproduce_byte_for_byte_with_honest_hashed_provenance(tmp_path: Path) -> None:
    output = tmp_path / "export"
    examples.write_previews(output)
    checked_in = Path(__file__).with_name("work-review-previews")
    files = inventory(output)
    assert files == inventory(checked_in)
    manifest = json.loads(files["manifest.json"])
    assert manifest["authored"] is True and manifest["model_generated"] is False
    assert manifest["model_requests"] == 0
    assert manifest["model_quality_evidence"] is False
    assert manifest["saved_effort_evidence"] is False
    assert manifest["mapping_sha256"] == examples.MAPPING_HASH
    assert manifest["input_sha256"] == hashlib.sha256(examples.PAIRS.read_bytes()).hexdigest()
    assert manifest["authored_input_sha256"] == examples.LONGER_HASH
    for name, digest in manifest["files"].items():
        assert hashlib.sha256(files[name]).hexdigest() == digest
    assert set(files) == {*manifest["files"], "manifest.json"}
    for name, data in files.items():
        if name.endswith(".md"):
            assert "Authored" in data.decode() and "No model" in data.decode()
    saved = json.loads(files["results.json"])
    assert saved["authored"] is True and saved["model_generated"] is False
    results = examples.load_examples()
    results.update(examples.failure_examples(results))
    for name, result in results.items():
        data = saved["results"][name]
        snapshot = data["snapshot"]
        restored_snapshot = review.Snapshot(
            snapshot["title"],
            snapshot["started_at"],
            tuple(snapshot["attendees"]),
            snapshot["my_name"],
            snapshot["transcript"],
            snapshot["handwritten_text"],
        )
        groups = tuple(
            review.Group(g["snapshot_id"], g["generation_id"], tuple(g["refs"]), g["binding"])
            for g in data["groups"]
        )
        restored = review.Result(
            restored_snapshot,
            data["snapshot_id"],
            data["generation_id"],
            groups,
            data["state"],
            data["binding"],
        )
        assert restored == result
        assert examples.preview(restored) == examples.preview(result)
        assert manifest["cases"][name]["snapshot_id"] == result.snapshot_id
    index = files["index.md"].decode()
    assert "six familiar" in index and "Chief-authored" in index and "not held out" in index
    assert "not passing coverage examples" in index


@pytest.mark.parametrize("existing", ["directory", "edited", "file", "symlink", "dangling"])
def test_export_refuses_existing_paths_symlinks_and_edits(tmp_path: Path, existing: str) -> None:
    output = tmp_path / "export"
    if existing in ("directory", "edited"):
        examples.write_previews(output)
        if existing == "edited":
            (output / "additional.md").write_text("Owner edit.\n")
        before = inventory(output)
    elif existing == "file":
        output.write_text("Owner file.\n")
        before = output.read_bytes()
    else:
        target = tmp_path / "target"
        if existing == "symlink":
            target.mkdir()
        output.symlink_to(target)
        before = os.readlink(output)
    with pytest.raises(FileExistsError):
        examples.write_previews(output)
    if existing in ("directory", "edited"):
        assert inventory(output) == before
    elif existing == "file":
        assert output.read_bytes() == before
    else:
        assert os.readlink(output) == before


def test_export_refuses_symlink_parents_and_does_not_create_missing_parents(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="symlinks"):
        examples.write_previews(link / "new")
    assert not (target / "new").exists()
    with pytest.raises(FileNotFoundError):
        examples.write_previews(tmp_path / "missing" / "new")
    assert not (tmp_path / "missing").exists()


@pytest.mark.parametrize("source", ["pairs", "mapping", "longer", "annex", "preview"])
def test_changed_provenance_fails_before_output_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
) -> None:
    paths = {
        "pairs": examples.PAIRS,
        "mapping": examples.PROPOSAL / "examples.json",
        "longer": examples.PROPOSAL / "authored-longer-input.json",
        "annex": examples.PROPOSAL / "sources.md",
        "preview": examples.PROPOSAL / "longer-context.md",
    }
    original = Path.read_bytes
    target = paths[source]

    def altered(path: Path) -> bytes:
        data = original(path)
        return data + b"\n" if path == target else data

    monkeypatch.setattr(Path, "read_bytes", altered)
    with pytest.raises(ValueError, match="provenance changed"):
        examples.write_previews(tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_explicit_loader_rechecks_all_longer_snapshot_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Simulate a newly pinned authored input with inconsistent redundant source metadata.
    data = json.loads((examples.PROPOSAL / "authored-longer-input.json").read_bytes())
    data["snapshot"]["authored_longer_context"]["sources"][0]["speaker"] = "Wrong speaker"
    original = examples._read

    def altered(path: Path, expected: str) -> bytes:
        if path.name == "authored-longer-input.json":
            return json.dumps(data).encode()
        return original(path, expected)

    monkeypatch.setattr(examples, "_read", altered)
    with pytest.raises(ValueError, match="Complete authored snapshot"):
        examples.write_previews(tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_import_and_pure_calls_do_not_read_fixtures_or_use_network() -> None:
    script = """
import argparse, builtins, socket
from pathlib import Path
from prototypes.reviewable_draft import generation, model, render
def forbidden(*args, **kwargs):
    raise AssertionError("Unexpected application IO")
Path.read_bytes = Path.read_text = Path.open = Path.resolve = forbidden
builtins.open = forbidden
socket.create_connection = socket.socket.connect = forbidden
from prototypes.reviewable_draft import work_review, work_review_examples
s = model.Snapshot("Synthetic", "2026-11-26", (), "Sam", "[00:00:00] Sam: I will send.", "Writing")
p = work_review.prepare(s, "host")
p.payload()
r = work_review.decode(p, '{"groups":[["T1"]]}')
assert "I will send." in work_review_examples.preview(r)
"""
    run = subprocess.run(
        [sys.executable, "-B", "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr


def test_separate_cli_prints_one_case_or_exports_new_directory(tmp_path: Path) -> None:
    command = [sys.executable, "-B", "-m", "prototypes.reviewable_draft.work_review_examples"]
    run = subprocess.run(
        [*command, "--case", "authored_longer_context"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout == examples.preview(examples.load_examples()["authored_longer_context"])
    output = tmp_path / "cli"
    exported = subprocess.run(
        [*command, "--output-dir", str(output)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert exported.returncode == 0, exported.stderr
    assert inventory(output) == inventory(Path(__file__).with_name("work-review-previews"))


def test_preview_revalidates_saved_values_without_source_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = examples.load_examples()["additional"]

    def unexpected(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Unexpected file IO")

    monkeypatch.setattr(Path, "read_bytes", unexpected)
    assert "Alex here." in examples.preview(result)
    with pytest.raises(ValueError):
        replace(result, snapshot=replace(result.snapshot, handwritten_text="Changed writing"))
