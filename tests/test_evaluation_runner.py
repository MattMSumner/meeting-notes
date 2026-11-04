"""Freeze selection and the pre-inference integrity guard, without any model calls."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("freeze", ["v1", "v2"])
def test_runner_checks_selected_freeze_before_creating_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    freeze: str,
):
    script = Path(__file__).resolve().parents[1] / "scripts" / "evaluate-enhancement.py"
    spec = importlib.util.spec_from_file_location("evaluation_runner", script)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    for version in ("v1", "v2"):
        folder = tmp_path if version == "v1" else tmp_path / version
        folder.mkdir(exist_ok=True)
        (folder / f"{version}_marker").write_text("changed")
        (folder / "sha256.json").write_text(json.dumps({f"{version}_marker": "wrong"}))
    output = tmp_path / "results.jsonl"
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(script),
            "--freeze",
            freeze,
            "--arm",
            "proposed",
            "--repetitions",
            "3",
            "--max-requests",
            "60",
            "--output",
            str(output),
            "--run",
        ],
    )
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2
    assert f"Frozen material changed: {freeze}_marker" in capsys.readouterr().err
    assert not output.exists()


def test_v2_keeps_pairs_baseline_and_rubric_unchanged():
    root = Path(__file__).resolve().parents[1] / "evaluation" / "m10"
    v2 = root / "v2"
    assert (v2 / "pairs.json").read_bytes() == (root / "pairs.json").read_bytes()
    for path in (root / "baseline").rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            assert path.read_bytes() == (v2 / path.relative_to(root)).read_bytes()
    original = (root / "README.md").read_text()
    rubric = original[
        original.index("## Manual scoring rubric") : original.index("## Manual Obsidian acceptance")
    ]
    assert (v2 / "rubric.md").read_text() == rubric
