"""Recovery must confirm helper exit before allowing its session to be cleared."""

import subprocess
from pathlib import Path

import pytest

from meeting_notes.session import SystemProcesses


def no_sleep(seconds: float) -> None:
    pass


def test_recovery_waits_for_exit_after_force_kill(monkeypatch: pytest.MonkeyPatch):
    calls: list[list[str]] = []
    checks = 0

    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        nonlocal checks
        calls.append(args)
        if args[0] == "pgrep":
            checks += 1
            return subprocess.CompletedProcess(args, 1 if checks == 152 else 0)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr("meeting_notes.session.subprocess.run", run)
    monkeypatch.setattr("meeting_notes.session.time.sleep", no_sleep)
    SystemProcesses().stop_capture(Path("/synthetic recording"))
    assert any(args[:2] == ["pkill", "-KILL"] for args in calls)
    assert checks == 152


@pytest.mark.parametrize("pgrep_code", [0, 2])
def test_failed_shutdown_or_process_check_cannot_report_success(
    monkeypatch: pytest.MonkeyPatch, pgrep_code: int
):
    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(args, pgrep_code if args[0] == "pgrep" else 1)

    monkeypatch.setattr("meeting_notes.session.subprocess.run", run)
    monkeypatch.setattr("meeting_notes.session.time.sleep", no_sleep)
    with pytest.raises(OSError):
        SystemProcesses().stop_capture(Path("/synthetic recording"))
