"""CaptureRecorder against a stand-in for notes-capture: a shell script that records
until SIGINT like the real one, without needing audio hardware or permissions."""

import os
import signal
import threading
import time
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
touch "$out/ready"
while :; do sleep 0.02; done
"""


def stop_when_ready(marker: Path) -> threading.Event:
    """A stop event set once the stand-in has created `marker`, i.e. is set up.

    Stopping at a fixed delay raced the stand-in's own setup on a busy machine."""
    stop = threading.Event()

    def wait_then_stop() -> None:
        deadline = time.monotonic() + 10
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        stop.set()

    threading.Thread(target=wait_then_stop, daemon=True).start()
    return stop


@pytest.fixture
def fake_capture(tmp_path: Path) -> Path:
    binary = tmp_path / "notes-capture"
    binary.write_text(FAKE_CAPTURE)
    binary.chmod(0o755)
    return binary


def test_records_until_stopped_then_lets_capture_finish_writing(fake_capture: Path, tmp_path: Path):
    out = tmp_path / "meeting"
    out.mkdir()

    CaptureRecorder(fake_capture).record(out, stop_when_ready(out / "ready"))

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


HUNG_CAPTURE = """#!/bin/sh
# Like notes-capture's relaunch: a parent waiting on a child. Both ignore SIGINT, so
# asking them to stop times out and the recorder has to force-kill.
trap '' INT
sh -c 'trap "" INT; echo $$ > "$CHILD_PID"; while :; do sleep 0.05; done' &
wait
"""


def test_force_kill_after_timeout_reaches_the_relaunched_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    binary = tmp_path / "notes-capture"
    binary.write_text(HUNG_CAPTURE)
    binary.chmod(0o755)
    child_pid_file = tmp_path / "child.pid"
    monkeypatch.setenv("CHILD_PID", str(child_pid_file))
    monkeypatch.setattr("meeting_notes.recorder.STOP_TIMEOUT_SECONDS", 0.5)

    with pytest.raises(CaptureError):
        CaptureRecorder(binary).record(tmp_path, stop_when_ready(child_pid_file))

    child = int(child_pid_file.read_text())
    for _ in range(50):  # the kernel reaps it shortly after SIGKILL
        try:
            os.kill(child, 0)
        except ProcessLookupError:
            break
        time.sleep(0.02)
    else:
        os.kill(child, signal.SIGKILL)
        pytest.fail("the child kept running after the recorder gave up")


def test_check_without_the_binary_explains_how_to_build_it(tmp_path: Path):
    with pytest.raises(CaptureNotInstalled, match="capture/install.sh"):
        CaptureRecorder(tmp_path / "nope").check()
