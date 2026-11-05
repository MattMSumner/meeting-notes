"""The replay is deterministic, exclusive and cannot invoke inference."""

import importlib.util
import json
import socket
import sys
from pathlib import Path
from typing import Any

import pytest


def test_replay_preserves_invalid_references_and_never_connects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    script = Path(__file__).resolve().parents[1] / "scripts/replay-v6-enhancement.py"
    spec = importlib.util.spec_from_file_location("replay_v6", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Replay must never contact a model")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    output = tmp_path / "results.jsonl"
    monkeypatch.setattr(sys, "argv", [str(script), "--output", str(output)])
    module.main()
    rows = [json.loads(s) for s in output.read_text().splitlines()]
    assert len(rows) == 15
    assert sum(bool(r.get("summary")) for r in rows) == 13
    assert sum("adapter_error" in r for r in rows) == 0
    later = next(r for r in rows if r["case"] == "later_timing")
    assert any("Friday" in text for text in later["summary"]["action_items"][0]["review"])
    additional = next(r for r in rows if r["case"] == "additional")
    assert additional["summary"] is None
    assert any("Possible omitted commitment T3" in issue for issue in additional["blocking"])
    later = [r for r in rows if r["case"] == "later_timing"]
    assert len(later) == 2
    for row in later:
        action = row["summary"]["action_items"][0]
        assert action["due"] is None
        assert action["task"] == "I will check rollback."
        assert any("Friday" in text for text in action["review"])
    original = output.read_bytes()
    with pytest.raises(FileExistsError):
        module.main()
    assert output.read_bytes() == original
