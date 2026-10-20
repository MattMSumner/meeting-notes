"""CaptureRecorder against a stand-in for notes-capture: a shell script that records
until SIGINT like the real one, without needing audio hardware or permissions."""

import threading
from pathlib import Path

import pytest

from meeting_notes.recorder import CaptureError, CaptureNotInstalled, CaptureRecorder

FAKE_CAPTURE = """#!/bin/sh
# Usage like notes-capture: record --out DIR | check
case "$1" in
  check) echo "checked" > "$CHECK_MARKER"; exit "${CHECK_STATUS:-0}" ;;
esac
out="$3"
echo "audio" > "$out/me.wav"
trap 'echo "{}" > "$out/capture.json"; exit 0' INT
while :; do sleep 0.02; done
"""


@pytest.fixture
def fake_capture(tmp_path: Path) -> Path:
    binary = tmp_path / "notes-capture"
    binary.write_text(FAKE_CAPTURE)
    binary.chmod(0o755)
    return binary


def test_records_until_stopped_then_lets_capture_finish_writing(fake_capture: Path, tmp_path: Path):
    out = tmp_path / "meeting"
    out.mkdir()
    stop = threading.Event()
    threading.Timer(0.3, stop.set).start()

    CaptureRecorder(fake_capture).record(out, stop)

    assert (out / "me.wav").is_file()
    # Written by the SIGINT handler, so the recorder waited for a clean shutdown.
    assert (out / "capture.json").is_file()


def test_capture_exiting_cleanly_on_its_own_is_fine(tmp_path: Path):
    # Ctrl-C in a terminal reaches notes-capture directly, so it can exit first.
    binary = tmp_path / "notes-capture"
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o755)

    CaptureRecorder(binary).record(tmp_path, threading.Event())


def test_capture_failing_raises(tmp_path: Path):
    binary = tmp_path / "notes-capture"
    binary.write_text("#!/bin/sh\nexit 3\n")
    binary.chmod(0o755)

    with pytest.raises(CaptureError, match="status 3"):
        CaptureRecorder(binary).record(tmp_path, threading.Event())


def test_missing_binary_explains_how_to_build_it(tmp_path: Path):
    with pytest.raises(CaptureNotInstalled, match="capture/install.sh"):
        CaptureRecorder(tmp_path / "nope").record(tmp_path, threading.Event())


@pytest.mark.parametrize("status", [0, 1])
def test_check_runs_capture_check_and_returns_its_status(
    fake_capture: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: int
):
    marker = tmp_path / "checked"
    monkeypatch.setenv("CHECK_MARKER", str(marker))
    monkeypatch.setenv("CHECK_STATUS", str(status))

    assert CaptureRecorder(fake_capture).check() == status
    assert marker.is_file()
