"""Freeze selection and the pre-inference integrity guard, without any model calls."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("freeze", ["v1", "v2", "v3", "v4", "v5", "v6"])
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
    for version in ("v1", "v2", "v3", "v4", "v5", "v6"):
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


def test_runner_preserves_each_reply_and_validation_failure_without_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from typing import Any

    from meeting_notes.contract import Draft, SupportedText

    good = Draft(
        overview=[SupportedText(text="transcript", sources=["T1"])],
        key_points=[],
        decisions=[],
        action_items=[],
        timing_updates=[],
        notes_context=[],
        conflicts=[],
    ).model_dump_json()

    from meeting_notes import ollama

    script = Path(__file__).resolve().parents[1] / "scripts" / "evaluate-enhancement.py"
    spec = importlib.util.spec_from_file_location("evaluation_runner", script)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    (tmp_path / "sha256.json").write_text("{}")
    (tmp_path / "settings.json").write_text(
        json.dumps({"model": "fake", "num_ctx": 32768, "think": True})
    )
    (tmp_path / "pairs.json").write_text(
        json.dumps(
            [
                {
                    "id": "synthetic",
                    "meeting": {
                        "title": "Synthetic",
                        "started_at": "2026-11-04T12:00:00-05:00",
                        "attendees": [],
                        "my_name": "Sam",
                    },
                    "transcript": "transcript",
                    "handwritten_text": "",
                }
            ]
        )
    )
    replies = iter(["not json", good])

    def fake_post(path: str, body: dict[str, Any]) -> dict[str, Any]:
        return {"message": {"content": next(replies)}}

    def fake_http_post(base_url: str) -> ollama.Post:
        return fake_post

    monkeypatch.setattr(ollama, "http_post", fake_http_post)
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    output = tmp_path / "results.jsonl"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(script),
            "--arm",
            "proposed",
            "--repetitions",
            "1",
            "--max-requests",
            "2",
            "--output",
            str(output),
            "--run",
        ],
    )
    runner.main()
    result = json.loads(output.read_text().splitlines()[1])
    assert result["requests_so_far"] == 2
    assert len(result["transport"][0]["request"]["messages"]) == 2
    assert len(result["transport"][1]["request"]["messages"]) == 4
    assert result["transport"][0]["response"]["message"]["content"] == "not json"
    assert result["audit"]["attempts"][0]["blocking"]
    assert result["audit"]["selected"] == 1


def test_v3_preserves_regressions_and_adds_eight_boundary_cases():
    root = Path(__file__).resolve().parents[1] / "evaluation" / "m10"
    original = json.loads((root / "pairs.json").read_text())
    revised = json.loads((root / "v3/pairs.json").read_text())
    assert revised[:5] == original
    assert len(revised) == 13
    assert len({pair["id"] for pair in revised}) == 13
    assert (root / "v3/rubric.md").read_bytes() == (root / "v2/rubric.md").read_bytes()
    for path in (root / "baseline").rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            assert path.read_bytes() == (root / "v3" / path.relative_to(root)).read_bytes()
