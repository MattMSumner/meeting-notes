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
