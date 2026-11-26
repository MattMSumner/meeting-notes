import hashlib
import json
from pathlib import Path

import pytest

from . import actions_examples as examples


def test_authored_actions_keep_original_inputs_and_checked_in_previews_reproduce(
    tmp_path: Path,
) -> None:
    output = tmp_path / "actions-previews"
    examples.write_previews(output)
    original = json.loads(examples.PAIRS.read_text())
    pairs = {p["id"]: p for p in original}
    results = examples.load_examples()
    assert len(original) == 40 and len(results) == 6
    for name, result in results.items():
        assert result.complete
        assert result.snapshot.transcript == pairs[name]["transcript"]
        assert result.snapshot.handwritten_text == pairs[name]["handwritten_text"]
    checked_in = Path(__file__).with_name("actions-previews")
    assert {p.name: p.read_bytes() for p in output.iterdir()} == {
        p.name: p.read_bytes() for p in checked_in.iterdir()
    }


def test_preview_provenance_is_authored_and_existing_edits_are_preserved(tmp_path: Path) -> None:
    output = tmp_path / "actions-previews"
    examples.write_previews(output)
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["kind"] == "authored_action_only_examples"
    assert manifest["model_requests"] == 0
    assert manifest["input_sha256"] == hashlib.sha256(examples.PAIRS.read_bytes()).hexdigest()
    assert manifest["fixture_sha256"] == hashlib.sha256(examples.FIXTURES.read_bytes()).hexdigest()
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest
    (output / "additional.md").write_text("Owner edits.\n")
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    with pytest.raises(FileExistsError):
        examples.write_previews(output)
    assert {p.name: p.read_bytes() for p in output.iterdir()} == before


def test_changed_input_or_unlabelled_fixture_fails_before_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pair_file = tmp_path / "pairs.json"
    pair_file.write_bytes(examples.PAIRS.read_bytes() + b"\n")
    with monkeypatch.context() as patch:
        patch.setattr(examples, "PAIRS", pair_file)
        with pytest.raises(ValueError, match="inputs changed"):
            examples.write_previews(tmp_path / "bad-input")
    fixture = json.loads(examples.FIXTURES.read_text())
    fixture["authored"] = False
    fixture_file = tmp_path / "fixture.json"
    fixture_file.write_text(json.dumps(fixture))
    monkeypatch.setattr(examples, "FIXTURES", fixture_file)
    with pytest.raises(ValueError, match="explicitly authored"):
        examples.write_previews(tmp_path / "bad-fixture")
    assert not (tmp_path / "bad-input").exists() and not (tmp_path / "bad-fixture").exists()
