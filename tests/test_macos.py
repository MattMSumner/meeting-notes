import subprocess
from typing import Any

import pytest

from meeting_notes.macos import DesktopError, MacDesktop


def fake_osascript(monkeypatch: pytest.MonkeyPatch, returncode: int, stdout: str, stderr: str):
    def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, returncode, stdout, stderr)

    monkeypatch.setattr(subprocess, "run", run)


def test_ask_text_returns_the_answer(monkeypatch: pytest.MonkeyPatch):
    fake_osascript(monkeypatch, 0, "Weekly sync\n", "")

    assert MacDesktop().ask_text("Title?") == "Weekly sync"


def test_cancel_is_none(monkeypatch: pytest.MonkeyPatch):
    fake_osascript(monkeypatch, 1, "", "execution error: User canceled. (-128)\n")

    assert MacDesktop().ask_text("Title?") is None


def test_any_other_failure_is_an_error(monkeypatch: pytest.MonkeyPatch):
    fake_osascript(monkeypatch, 1, "", "execution error: Not authorized. (-1743)\n")

    with pytest.raises(DesktopError, match="Not authorized"):
        MacDesktop().ask_text("Title?")


def test_open_note_encodes_absolute_path_and_requests_new_tab(monkeypatch: pytest.MonkeyPatch):
    from pathlib import Path
    from urllib.parse import parse_qs, urlsplit

    seen: list[str] = []

    def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.extend(args)
        assert kwargs["timeout"] == 5
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    path = Path("/tmp/Café & # notes.md")
    MacDesktop().open_note(path)
    assert seen[0] == "open"
    assert parse_qs(urlsplit(seen[1]).query) == {"path": [str(path.resolve())], "paneType": ["tab"]}


def test_chooser_disambiguates_duplicate_labels_and_returns_original_id(
    monkeypatch: pytest.MonkeyPatch,
):
    def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        script = args[-1]
        assert '"1. Same"' in script and '"2. Same"' in script
        assert 'if selected is false then return ""' in script
        assert "multiple selections allowed false" in script
        return subprocess.CompletedProcess(args, 0, "2. Same\n", "")

    monkeypatch.setattr(subprocess, "run", run)
    assert MacDesktop().choose_meeting([("first-id", "Same"), ("stable-id", "Same")]) == "stable-id"


def test_chooser_cancellation_returns_none(monkeypatch: pytest.MonkeyPatch):
    fake_osascript(monkeypatch, 0, "\n", "")
    assert MacDesktop().choose_meeting([("id", "Label")]) is None


def test_chooser_failure_is_readable(monkeypatch: pytest.MonkeyPatch):
    fake_osascript(monkeypatch, 1, "", "Not authorized")
    with pytest.raises(DesktopError, match="Not authorized"):
        MacDesktop().choose_meeting([("id", "Label")])
