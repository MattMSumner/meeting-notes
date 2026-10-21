"""Command-line entry point: `notes`."""

import argparse
import os
import signal
import sys
import threading
import time
from collections.abc import Callable, Sequence
from datetime import datetime
from types import FrameType

from meeting_notes import pipeline, session
from meeting_notes.config import Config
from meeting_notes.macos import Desktop, MacDesktop
from meeting_notes.meeting import Meeting
from meeting_notes.recorder import CaptureError, CaptureNotInstalled, CaptureRecorder, Recorder
from meeting_notes.render import timestamp
from meeting_notes.session import Active, Phase, Processes, Session, SystemProcesses
from meeting_notes.store import MeetingDir, MeetingNotFound, MeetingStore
from meeting_notes.summary import Summarizer, SummaryError
from meeting_notes.transcript import Transcriber

# How long `notes stop` waits for a recording to finish writing its audio.
STOP_WAIT_SECONDS = 45


def _default_transcriber(config: Config) -> Transcriber:
    from meeting_notes.parakeet import ParakeetTranscriber

    return ParakeetTranscriber(config.model)


def _default_summarizer(config: Config) -> Summarizer:
    from meeting_notes.ollama import OllamaSummarizer, http_post

    return OllamaSummarizer(
        config.summary_model,
        config.num_ctx,
        http_post(config.ollama_url),
        config.my_name,
        think=config.summary_think,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="notes", description="Local-first meeting notetaker.")
    commands = parser.add_subparsers(dest="command", required=True)

    start = commands.add_parser(
        "start", help="start recording in the background; `notes stop` writes the note"
    )
    titles = start.add_mutually_exclusive_group()
    titles.add_argument("--title", help="meeting title (default: Untitled)")
    titles.add_argument("--ask-title", action="store_true", help="ask for the title in a dialog")

    commands.add_parser("stop", help="stop recording; the note is written in the background")
    commands.add_parser("status", help="show what's recording or being written")

    record = commands.add_parser(
        "record", help="record the mic and system audio until Ctrl-C, then transcribe and summarize"
    )
    record.add_argument("--title", help="meeting title (default: Untitled)")
    record.add_argument(
        "--duration", type=float, metavar="SECONDS", help="stop automatically after SECONDS"
    )
    # Used by `notes start`: record into a meeting it created, reporting by notification.
    record.add_argument("--meeting-id", help=argparse.SUPPRESS)
    record.add_argument("--background", action="store_true", help=argparse.SUPPRESS)

    transcribe = commands.add_parser(
        "transcribe", help="re-run transcription (and the summary) for a meeting"
    )
    transcribe.add_argument("meeting_id")
    # Used by `notes stop` to finish a recording orphaned by a crash.
    transcribe.add_argument("--background", action="store_true", help=argparse.SUPPRESS)

    summarize = commands.add_parser("summarize", help="re-run the summary for a meeting")
    summarize.add_argument("meeting_id")

    render = commands.add_parser(
        "render", help="re-write a meeting's note and transcript into the vault"
    )
    render.add_argument("meeting_id")

    commands.add_parser("check", help="check that the mic and system audio can be recorded")
    return parser


# Any of these stops the recording cleanly, then transcription runs. Ctrl-C sends SIGINT,
# but some launchers (like Claude Code's ! mode) stop commands with SIGTERM or SIGHUP.
STOP_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


def _record(meeting_dir: MeetingDir, duration: float | None, recorder: Recorder) -> None:
    stop = threading.Event()

    def on_stop_signal(signum: int, frame: FrameType | None) -> None:
        stop.set()

    previous = {sig: signal.signal(sig, on_stop_signal) for sig in STOP_SIGNALS}
    # Flushed explicitly: notes-capture writes to the same terminal, and Python buffers
    # stdout when it isn't a TTY (e.g. under Claude Code), which put our lines after its.
    timer = threading.Timer(duration, stop.set) if duration else None
    try:
        if timer:
            timer.start()
            print(
                f"Recording {meeting_dir.id} for {duration:g}s. Press Ctrl-C to stop early.",
                flush=True,
            )
        else:
            print(f"Recording {meeting_dir.id}. Press Ctrl-C to stop.", flush=True)
        recorder.record(meeting_dir.path, stop)
    finally:
        if timer:
            timer.cancel()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    print("Stopped.", flush=True)


def _title(meeting_dir: MeetingDir) -> str:
    return meeting_dir.load_meeting().title


class _Commands:
    def __init__(
        self,
        config: Config,
        make_transcriber: Callable[[Config], Transcriber],
        make_summarizer: Callable[[Config], Summarizer],
        make_recorder: Callable[[Config], Recorder],
        processes: Processes,
        desktop: Desktop,
    ) -> None:
        self.config = config
        self.store = MeetingStore(config.data_dir)
        self.make_transcriber = make_transcriber
        self.make_summarizer = make_summarizer
        self.make_recorder = make_recorder
        self.processes = processes
        self.desktop = desktop

    def _tell(self, message: str, *, error: bool = False) -> None:
        """For commands run from a shortcut: no terminal, so also a notification."""
        print(message, file=sys.stderr if error else sys.stdout, flush=True)
        self.desktop.notify(message)

    def _session(self, phase: Phase) -> Session:
        pid = os.getpid()
        started = self.processes.started(pid) or ""
        return Session(pid, started, phase, datetime.now().astimezone())

    def _recording(self) -> list[Active]:
        """Recordings in progress in other processes."""
        return [
            active
            for active in session.find(self.store, self.processes)
            if active.running
            and active.session.phase == Phase.RECORDING
            and active.session.pid != os.getpid()
        ]

    def _recover_orphans(self) -> list[Active]:
        """Finishes meetings whose process died: stops any capture still recording into them
        and writes their notes in the background."""
        orphans = [a for a in session.find(self.store, self.processes) if not a.running]
        for orphan in orphans:
            meeting_dir = orphan.meeting_dir
            self.processes.stop_capture(meeting_dir.path)
            session.session_file(meeting_dir).unlink(missing_ok=True)
            if not meeting_dir.captures():
                self._tell(f"“{_title(meeting_dir)}” stopped before any audio was saved.")
                continue
            pid = self.processes.spawn(
                ["transcribe", meeting_dir.id, "--background"], meeting_dir.path / "notes.log"
            )
            started = self.processes.started(pid) or ""
            session.write(
                meeting_dir, Session(pid, started, Phase.PROCESSING, orphan.session.started_at)
            )
            self._tell(
                f"“{_title(meeting_dir)}” stopped unexpectedly. Writing its note from what "
                "was recorded."
            )
        return orphans

    def start(self, args: argparse.Namespace) -> int:
        self._recover_orphans()
        if recording := self._recording():
            self._tell(f"Already recording “{_title(recording[0].meeting_dir)}”.", error=True)
            return 1
        title: str | None = args.title
        if args.ask_title:
            title = self.desktop.ask_text("Meeting title (leave empty for Untitled):")
            if title is None:
                return 0  # cancelled
        meeting_dir = self.store.create(Meeting.new(title, datetime.now().astimezone()))
        pid = self.processes.spawn(
            ["record", "--meeting-id", meeting_dir.id, "--background"],
            meeting_dir.path / "notes.log",
        )
        # Written here as well as by the recording itself, so a second `start` straight
        # after this one sees it.
        session.write(
            meeting_dir,
            Session(
                pid,
                self.processes.started(pid) or "",
                Phase.RECORDING,
                meeting_dir.load_meeting().started_at,
            ),
        )
        print(f"Recording {meeting_dir.id} in the background. Stop it with `notes stop`.")
        return 0

    def stop(self, args: argparse.Namespace) -> int:
        recovered = self._recover_orphans()
        recording = self._recording()
        if not recording:
            if recovered:
                return 0
            self._tell("Nothing is recording.", error=True)
            return 1
        for active in recording:
            self.processes.interrupt(active.session.pid)
        deadline = time.monotonic() + STOP_WAIT_SECONDS
        status = 0
        for active in recording:
            # The recording moves on to writing the note once its audio is saved.
            while (
                (current := session.read(active.meeting_dir)) is not None
                and current.phase == Phase.RECORDING
                and session.is_running(current, self.processes)
                and time.monotonic() < deadline
            ):
                time.sleep(0.2)
            if current is not None and current.phase == Phase.RECORDING:
                self._tell(f"“{_title(active.meeting_dir)}” didn't stop.", error=True)
                status = 1
            else:
                print(f"Stopped {active.meeting_dir.id}. The note will be ready shortly.")
        return status

    def status(self, args: argparse.Namespace) -> int:
        found = session.find(self.store, self.processes)
        if not found:
            print("Not recording.")
        now = datetime.now().astimezone()
        for active in found:
            title = _title(active.meeting_dir)
            if not active.running:
                print(f"“{title}” stopped unexpectedly. Run `notes stop` to recover it.")
            elif active.session.phase == Phase.RECORDING:
                elapsed = (now - active.session.started_at).total_seconds()
                print(f"Recording “{title}” for {timestamp(elapsed)} ({active.meeting_dir.id})")
            else:
                print(f"Writing the note for “{title}” ({active.meeting_dir.id})")
        return 0

    def record(self, args: argparse.Namespace) -> int:
        if args.meeting_id is None:
            if recording := self._recording():
                print(
                    f"Already recording {recording[0].meeting_dir.id}. Stop it with `notes stop`.",
                    file=sys.stderr,
                )
                return 1
            meeting_dir = self.store.create(Meeting.new(args.title, datetime.now().astimezone()))
        else:
            meeting_dir = self.store.get(args.meeting_id)
        title = _title(meeting_dir)
        session.write(meeting_dir, self._session(Phase.RECORDING))
        try:
            if args.background:
                self.desktop.notify(f"Recording “{title}”.")
            try:
                _record(meeting_dir, args.duration, self.make_recorder(self.config))
            except CaptureNotInstalled as error:
                self._report(str(error), args.background)
                return 1
            except CaptureError as error:
                # Whatever was recorded is still worth transcribing.
                if not meeting_dir.captures():
                    self._report(
                        f"Recording “{title}” failed ({error}). No audio was saved.",
                        args.background,
                    )
                    return 1
                self._report(
                    f"Recording “{title}” ended with an error ({error}). Writing the note from "
                    f"what was saved. To retry later: notes transcribe {meeting_dir.id}",
                    args.background,
                )
            else:
                if args.background:
                    self.desktop.notify(f"Stopped recording “{title}”. Writing the note…")
            session.write(meeting_dir, self._session(Phase.PROCESSING))
            return self._write_note(meeting_dir, transcribe=True, background=args.background)
        finally:
            session.clear(meeting_dir, os.getpid())

    def _report(self, message: str, background: bool) -> None:
        print(message, file=sys.stderr, flush=True)
        if background:
            self.desktop.notify(message)

    def _write_note(
        self, meeting_dir: MeetingDir, *, transcribe: bool, background: bool = False
    ) -> int:
        """Transcribes (if asked), summarizes and renders. Returns the exit status."""
        if transcribe:
            print("Transcribing...", flush=True)
            pipeline.transcribe(meeting_dir, self.make_transcriber(self.config))
        talk = pipeline.conversation(meeting_dir)
        title = _title(meeting_dir)
        print(f"Summarizing with {self.config.summary_model}...", flush=True)
        summary_error: SummaryError | None = None
        try:
            pipeline.summarize(
                meeting_dir, talk, self.make_summarizer(self.config), self.config.my_name
            )
        except pipeline.NotTranscribed as error:
            self._report(f"Couldn't summarize: {error}", background)
            return 1
        except SummaryError as error:
            # The transcript is still worth writing; the note says how to retry.
            summary_error = error
            print(f"Couldn't summarize: {error}", file=sys.stderr)
            print(f"To retry: notes summarize {meeting_dir.id}", file=sys.stderr)
        self._render(meeting_dir, talk)
        if background:
            self.desktop.notify(
                f"The note for “{title}” is ready."
                if summary_error is None
                else f"Wrote the transcript for “{title}”, but couldn't summarize it: "
                f"{summary_error}"
            )
        return 0 if summary_error is None else 1

    def _render(self, meeting_dir: MeetingDir, talk: pipeline.Conversation) -> None:
        rendered = pipeline.render(meeting_dir, talk, self.config)
        print(f"Note: {rendered.note}")
        print(f"Transcript: {rendered.transcript}")
        for path in rendered.skipped:
            print(
                f"Left {path.name} alone: it was edited after it was written. "
                "Move it away and run `notes render` to replace it.",
                file=sys.stderr,
            )

    def existing(self, args: argparse.Namespace) -> int:
        """transcribe, summarize and render: re-run stages for a meeting."""
        try:
            meeting_dir = self.store.get(args.meeting_id)
        except MeetingNotFound as error:
            print(f"No meeting with id {error}", file=sys.stderr)
            return 1
        if args.command == "render":
            self._render(meeting_dir, pipeline.conversation(meeting_dir))
            return 0
        background = getattr(args, "background", False)
        if background:
            session.write(meeting_dir, self._session(Phase.PROCESSING))
        try:
            return self._write_note(
                meeting_dir, transcribe=args.command == "transcribe", background=background
            )
        finally:
            if background:
                session.clear(meeting_dir, os.getpid())


def main(
    argv: Sequence[str] | None = None,
    *,
    config: Config | None = None,
    make_transcriber: Callable[[Config], Transcriber] = _default_transcriber,
    make_summarizer: Callable[[Config], Summarizer] = _default_summarizer,
    make_recorder: Callable[[Config], Recorder] = lambda config: CaptureRecorder(config.capture),
    processes: Processes | None = None,
    desktop: Desktop | None = None,
) -> int:
    args = _parser().parse_args(argv)
    config = config or Config.from_env()

    if args.command == "check":
        try:
            return CaptureRecorder(config.capture).check()
        except CaptureNotInstalled as error:
            print(error, file=sys.stderr)
            return 1

    commands = _Commands(
        config,
        make_transcriber,
        make_summarizer,
        make_recorder,
        processes or SystemProcesses(),
        desktop or MacDesktop(),
    )
    match args.command:
        case "start":
            return commands.start(args)
        case "stop":
            return commands.stop(args)
        case "status":
            return commands.status(args)
        case "record":
            return commands.record(args)
        case _:
            return commands.existing(args)
