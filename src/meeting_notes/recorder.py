"""Recording, via the Swift notes-capture binary (see capture/).

notes-capture records the mic to me.wav and system audio to them.wav, and writes
capture.json with each channel's start offset. It stops cleanly on SIGINT."""

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

    def record(self, directory: Path, stop: threading.Event) -> None:
        if not self.binary.is_file():
            raise CaptureNotInstalled(self.binary)
        # stderr is inherited, so notes-capture's status and warnings reach the terminal.
        process = subprocess.Popen([str(self.binary), "record", "--out", str(directory)])
        try:
            # Ctrl-C in a terminal reaches notes-capture directly too, so it may exit on
            # its own before we ask it to.
            while not stop.wait(0.25) and process.poll() is None:
                pass
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=STOP_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        if process.returncode != 0:
            raise CaptureError(f"notes-capture exited with status {process.returncode}")

    def check(self) -> int:
        """Runs `notes-capture check`, which prints its own results. Returns its status."""
        if not self.binary.is_file():
            raise CaptureNotInstalled(self.binary)
        return subprocess.run([str(self.binary), "check"]).returncode
