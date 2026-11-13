"""Recording, via the Swift notes-capture binary (see capture/).

notes-capture records the mic to me.wav and system audio to them.wav, and writes
capture.json with each channel's start offset. It stops cleanly on SIGINT."""

import os
import signal
import subprocess
import threading
from pathlib import Path
from typing import Protocol

# How long notes-capture gets to finish writing after being asked to stop.
STOP_TIMEOUT_SECONDS = 30


class CaptureError(Exception):
    pass


class CaptureNotInstalled(CaptureError):
    def __init__(self, binary: Path) -> None:
        super().__init__(f"notes-capture not found at {binary}. Build it with capture/install.sh.")


class Recorder(Protocol):
    def record(self, directory: Path, stop: threading.Event) -> None:
        """Records into directory until stop is set."""
        ...


class CaptureRecorder:
    def __init__(self, binary: Path) -> None:
        self.binary = binary

    def _command(self, *args: str) -> list[str]:
        if not self.binary.is_file():
            raise CaptureNotInstalled(self.binary)
        return [str(self.binary), *args]

    def record(self, directory: Path, stop: threading.Event) -> None:
        # Its own process group: notes-capture relaunches itself (see Responsibility.swift),
        # so stopping it, or killing it if it hangs, has to reach the child that holds the
        # mic too, not just the parent. It also means a terminal's Ctrl-C reaches only us;
        # we pass it on. stderr is inherited, so its status and warnings reach the terminal.
        process = subprocess.Popen(
            self._command("record", "--out", str(directory)), start_new_session=True
        )
        try:
            while not stop.wait(0.25) and process.poll() is None:
                pass
        finally:
            if process.poll() is None:
                _signal_group(process, signal.SIGINT)
                try:
                    process.wait(timeout=STOP_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    _signal_group(process, signal.SIGKILL)
                    process.wait()
        if process.returncode != 0:
            raise CaptureError(f"notes-capture exited with status {process.returncode}")

    def check(self) -> int:
        """Runs `notes-capture check`, which prints its own results. Returns its status."""
        return subprocess.run(self._command("check")).returncode


def _signal_group(process: subprocess.Popen[bytes], sig: signal.Signals) -> None:
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        pass  # already gone
