"""What's running in the background: recordings, and notes being written after them.

Each running meeting has a session.json in its folder naming the process doing the work
and what it's doing. The process removes it when it finishes. One left behind by a process
that's gone (a crash, a reboot) marks an orphaned meeting that `notes stop` recovers."""

import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from meeting_notes.store import MeetingDir, MeetingStore


class Phase(StrEnum):
    RECORDING = "recording"
    PROCESSING = "processing"
    """Transcribing, summarizing and writing the note."""


@dataclass(frozen=True)
class Session:
    pid: int
    process_started: str
    """When the process started, as `ps` reports it. A pid alone can be reused after a
    reboot; the pair can't."""
    phase: Phase
    started_at: datetime


class Processes(Protocol):
    def started(self, pid: int) -> str | None:
        """When the process started, or None if it isn't running."""
        ...

    def interrupt(self, pid: int) -> None:
        """Asks the process to stop, as Ctrl-C would."""
        ...

    def spawn(self, args: list[str], log: Path) -> int:
        """Runs `notes <args>` in the background, detached from us. Returns its pid."""
        ...

    def stop_capture(self, out_dir: Path) -> None:
        """Stops a notes-capture left recording into out_dir by a crashed `notes`."""
        ...


def session_file(meeting_dir: MeetingDir) -> Path:
    return meeting_dir.path / "session.json"


def read(meeting_dir: MeetingDir) -> Session | None:
    try:
        text = session_file(meeting_dir).read_text()
    except FileNotFoundError:  # including removed by its process just now
        return None
    try:
        data = json.loads(text)
        return Session(
            pid=int(data["pid"]),
            process_started=str(data["process_started"]),
            phase=Phase(data["phase"]),
            started_at=datetime.fromisoformat(data["started_at"]),
        )
    except (ValueError, KeyError, TypeError):
        # Half-written by a crash. Treat it as orphaned so it gets recovered.
        return Session(0, "", Phase.RECORDING, datetime.now().astimezone())


def write(meeting_dir: MeetingDir, session: Session) -> None:
    payload = {
        "pid": session.pid,
        "process_started": session.process_started,
        "phase": session.phase.value,
        "started_at": session.started_at.isoformat(),
    }
    # Written whole then renamed, so a reader never sees half a file. The temp name is per
    # process: `notes start` and the recording it launches write the same session.
    tmp = meeting_dir.path / f".session.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(payload, indent=2) + "\n")
    tmp.replace(session_file(meeting_dir))


def clear(meeting_dir: MeetingDir, pid: int) -> None:
    """Removes the session, if it's still the one belonging to pid."""
    session = read(meeting_dir)
    if session is not None and session.pid == pid:
        session_file(meeting_dir).unlink(missing_ok=True)


def stop_request_file(meeting_dir: MeetingDir) -> Path:
    """Asks a recording to stop. Unlike a signal, it can't arrive too early to be handled:
    a recording started a moment ago reads it once it's ready."""
    return meeting_dir.path / "stop-requested"


@contextmanager
def lock(store: MeetingStore) -> Generator[None]:
    """Lets one `start` or `stop` run at a time, so two at once (a double press in
    Spotlight) can't both start a recording or both recover the same orphan."""
    store.root.mkdir(parents=True, exist_ok=True)
    with (store.root / ".lock").open("w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def is_running(session: Session, processes: Processes) -> bool:
    return session.pid > 0 and processes.started(session.pid) == session.process_started


@dataclass(frozen=True)
class Active:
    meeting_dir: MeetingDir
    session: Session
    running: bool
    """False if the process is gone without finishing: the meeting is orphaned."""


def find(store: MeetingStore, processes: Processes) -> list[Active]:
    """Every meeting with a session, oldest first."""
    found: list[Active] = []
    for meeting_dir in store.all():
        session = read(meeting_dir)
        if session is not None:
            found.append(Active(meeting_dir, session, is_running(session, processes)))
    return found


class SystemProcesses:
    def started(self, pid: int) -> str | None:
        # ps formats the time in the caller's locale and time zone, which differ between a
        # shortcut and a terminal (and change when travelling). Fixed, so they compare.
        result = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            capture_output=True,
            text=True,
            env={**os.environ, "LC_ALL": "C", "TZ": "UTC"},
        )
        return result.stdout.strip() or None

    def interrupt(self, pid: int) -> None:
        try:
            os.kill(pid, signal.SIGINT)
        except ProcessLookupError:
            pass

    def spawn(self, args: list[str], log: Path) -> int:
        with log.open("a") as out:
            process = subprocess.Popen(
                [sys.executable, "-m", "meeting_notes", *args],
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=out,
                # Its own session: it outlives whatever started it (a shortcut, a terminal).
                start_new_session=True,
                # Ctrl-C (which `notes stop` sends) is ignored until the job sets up its own
                # handling. Otherwise a stop during Python's startup kills it outright.
                preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_IGN),
            )
        return process.pid

    def stop_capture(self, out_dir: Path) -> None:
        pattern = f"notes-capture record --out {re.escape(str(out_dir))}$"
        subprocess.run(["pkill", "-INT", "-f", pattern])
        for _ in range(150):  # notes-capture finishes its files within a few seconds
            if subprocess.run(["pgrep", "-f", pattern], capture_output=True).returncode != 0:
                return
            time.sleep(0.2)
        subprocess.run(["pkill", "-KILL", "-f", pattern])
