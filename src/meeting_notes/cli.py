"""Command-line entry point: `notes`."""

import argparse
import math
import os
import signal
import sys
import threading
import time
import traceback
from collections.abc import Callable, Sequence
from datetime import datetime
from types import FrameType

from meeting_notes import pipeline, session
from meeting_notes.calendar import Calendar, CaptureCalendar, Event, meeting_now
from meeting_notes.config import Config
from meeting_notes.macos import Desktop, DesktopError, MacDesktop
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


def _positive_seconds(value: str) -> float:
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("duration must be positive and finite")
    return seconds


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
        "--duration",
        type=_positive_seconds,
        metavar="SECONDS",
        help="stop after SECONDS, up to the configured recording cap",
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


class _StopSignals:
    """While recording, Ctrl-C (and SIGTERM/SIGHUP) stop the recording rather than the
    program. `end()` puts the usual handling back as soon as recording stops, so they
    interrupt transcribing as normal; leaving the `with` block ends it in any case."""

    def __enter__(self) -> "_StopSignals":
        self.stop = threading.Event()

        def on_stop_signal(signum: int, frame: FrameType | None) -> None:
            self.stop.set()

        self._previous = {sig: signal.signal(sig, on_stop_signal) for sig in STOP_SIGNALS}
        return self

    def end(self) -> None:
        for sig, handler in self._previous.items():
            signal.signal(sig, handler)
        self._previous = {}

    def __exit__(self, *exc_info: object) -> None:
        self.end()


def _record(
    meeting_dir: MeetingDir,
    duration: float,
    recorder: Recorder,
    stop: threading.Event,
) -> bool:
    stop_file = session.stop_request_file(meeting_dir)

    def watch_for_stop_request() -> None:
        while not stop.is_set():
            if stop_file.exists():
                stop.set()
            stop.wait(0.25)

    watcher = threading.Thread(target=watch_for_stop_request, daemon=True)
    watcher.start()
    # Flushed explicitly: notes-capture writes to the same terminal, and Python buffers
    # stdout when it isn't a TTY (e.g. under Claude Code), which put our lines after its.
    limit_reached = threading.Event()

    def stop_at_limit() -> None:
        if not stop.is_set():
            limit_reached.set()
            stop.set()

    timer = threading.Timer(duration, stop_at_limit)
    try:
        timer.start()
        print(
            f"Recording {meeting_dir.id}; automatic stop after {duration:g}s. "
            "Press Ctrl-C to stop early.",
            flush=True,
        )
        recorder.record(meeting_dir.path, stop)
    finally:
        stop.set()  # ends the watcher and prevents a late timeout report
        timer.cancel()
        timer.join()
    print("Stopped.", flush=True)
    return limit_reached.is_set()


def _title(meeting_dir: MeetingDir) -> str:
    try:
        return meeting_dir.load_meeting().title
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        # Notifications must not prevent capture shutdown when metadata is damaged.
        return meeting_dir.id


class _Commands:
    def __init__(
        self,
        config: Config,
        make_transcriber: Callable[[Config], Transcriber],
        make_summarizer: Callable[[Config], Summarizer],
        make_recorder: Callable[[Config], Recorder],
        processes: Processes,
        desktop: Desktop,
        calendar: Calendar,
    ) -> None:
        self.config = config
        self.calendar = calendar
        self.store = MeetingStore(config.data_dir)
        self.make_transcriber = make_transcriber
        self.make_summarizer = make_summarizer
        self.make_recorder = make_recorder
        self.processes = processes
        self.desktop = desktop

    def _say(self, message: str, *, notify: bool, error: bool = False) -> None:
        """Prints a message, and when there's no terminal to read it (a shortcut, a
        background job) also shows it as a notification."""
        print(message, file=sys.stderr if error else sys.stdout, flush=True)
        if notify:
            try:
                self.desktop.notify(message)
            except (OSError, DesktopError) as failure:
                print(f"Couldn't show notification ({failure}).", file=sys.stderr)

    def _session(self, meeting_dir: MeetingDir, phase: Phase) -> Session:
        """This process's session for meeting_dir. Keeps the start time of the session the
        parent wrote when it launched us (for a recovered meeting, when it began)."""
        pid = os.getpid()
        existing = session.read(meeting_dir)
        started_at = (
            existing.started_at
            if existing is not None and existing.pid == pid
            else datetime.now().astimezone()
        )
        return Session(pid, self.processes.started(pid) or "", phase, started_at)

    def _spawn_job(
        self, meeting_dir: MeetingDir, args: list[str], phase: Phase, started_at: datetime
    ) -> None:
        """Runs `notes <args>` in the background for meeting_dir, recording its session
        straight away so the next `start`, `stop` or `status` sees it."""
        pid = self.processes.spawn(args, meeting_dir.path / "notes.log")
        started = self.processes.started(pid) or ""
        session.write(meeting_dir, Session(pid, started, phase, started_at))

    def _unfinished_recordings(self) -> list[Active]:
        """Capture is unresolved even when the owning process has died."""
        return [
            active
            for active in session.find(self.store, self.processes)
            if active.session.phase in (Phase.RECORDING, Phase.STOPPING)
        ]

    def _recording(self) -> list[Active]:
        """Recordings in progress in other processes."""
        return [
            active
            for active in self._unfinished_recordings()
            if active.running
            and (active.session.pid != os.getpid() or active.session.phase == Phase.STOPPING)
        ]

    def _recover(self, orphan: Active) -> None:
        """Deals with a meeting whose process died. A recording cut off: stops any capture
        still recording into it and writes its note in the background."""
        meeting_dir = orphan.meeting_dir
        # Claim before stopping orphaned capture, which can take seconds. Other commands
        # see a live recovery session while the global lock stays free.
        capture_pending = orphan.session.phase in (Phase.RECORDING, Phase.STOPPING)
        with session.lock(self.store):
            if session.read(meeting_dir) != orphan.session:
                return
            claim = self._session(
                meeting_dir, Phase.STOPPING if capture_pending else orphan.session.phase
            )
            session.write(meeting_dir, claim)
        try:
            title = _title(meeting_dir)
            if orphan.session.phase == Phase.PROCESSING:
                self._say(
                    f"Writing the note for “{title}” stopped unexpectedly. "
                    f"To retry: notes transcribe {meeting_dir.id}",
                    notify=True,
                    error=True,
                )
                return
            self.processes.stop_capture(meeting_dir.path)
            capture_pending = False
            session.stop_request_file(meeting_dir).unlink(missing_ok=True)
            if not meeting_dir.captures():
                self._say(f"“{title}” stopped before any audio was saved.", notify=True)
                return
            with session.lock(self.store):
                self._spawn_job(
                    meeting_dir,
                    ["transcribe", meeting_dir.id, "--background"],
                    Phase.PROCESSING,
                    orphan.session.started_at,
                )
            self._say(
                f"“{title}” stopped unexpectedly. Writing its note from what was recorded.",
                notify=True,
            )
        finally:
            with session.lock(self.store):
                if session.read(meeting_dir) == claim:
                    if capture_pending:
                        # Leave a retryable orphan if shutdown was interrupted, including
                        # Ctrl-C. A hard crash leaves STOPPING, which is also recoverable.
                        session.write(meeting_dir, orphan.session)
                    else:
                        session.clear(meeting_dir, os.getpid())

    def _recover_orphans(self) -> list[Active]:
        orphans = [a for a in session.find(self.store, self.processes) if not a.running]
        for orphan in orphans:
            self._recover(orphan)
        return orphans

    def _new_meeting(self, title: str | None, event: Event | None) -> Meeting:
        """A meeting starting now. With no title given it takes the calendar event's title,
        and it gets the event's attendees, also when retitled. A cleared title means "not
        that meeting" (an unplanned call), so then it gets neither."""
        now = datetime.now().astimezone()
        if event is None or (title is not None and not title.strip()):
            return Meeting.new(title, now)
        return Meeting.new(
            event.title if title is None else title, now, tuple(event.other_attendees)
        )

    def _calendar_event(self) -> Event | None:
        return meeting_now(self.calendar, datetime.now().astimezone())

    def start(self, args: argparse.Namespace) -> int:
        if self._already_recording():
            return 1
        title: str | None = args.title
        event = self._calendar_event()
        if args.ask_title:
            # Before taking the lock: the dialog can stay open indefinitely, and a Stop
            # shouldn't wait on it.
            try:
                title = self.desktop.ask_text(
                    "Meeting title (leave empty for Untitled):",
                    default=event.title if event else "",
                )
            except DesktopError as error:
                self._say(f"Couldn't ask for the title ({error}).", notify=True, error=True)
                return 1
            if title is None:
                return 0  # cancelled
        self._recover_orphans()
        with session.lock(self.store):
            if self._already_recording(include_orphans=True):  # revalidate after recovery
                return 1
            meeting_dir = self.store.create(self._new_meeting(title, event))
            self._spawn_job(
                meeting_dir,
                ["record", "--meeting-id", meeting_dir.id, "--background"],
                Phase.RECORDING,
                meeting_dir.load_meeting().started_at,
            )
        print(
            f"Recording {meeting_dir.id} in the background; automatic stop after "
            f"{self.config.max_recording_seconds:g}s. Stop early with `notes stop`."
        )
        return 0

    def _already_recording(self, *, include_orphans: bool = False) -> bool:
        recording = self._unfinished_recordings() if include_orphans else self._recording()
        if recording:
            title = _title(recording[0].meeting_dir)
            message = (
                f"Already recording “{title}”."
                if recording[0].running
                else f"Unfinished recording “{title}”. Run `notes stop` to recover it."
            )
            self._say(message, notify=True, error=True)
            return True
        return False

    def stop(self, args: argparse.Namespace) -> int:
        recovered = self._recover_orphans()
        with session.lock(self.store):
            # An observed orphan is not proof that this command recovered it: a
            # competing claimant may have failed and restored it in the meantime.
            # Process death can happen while the lock is held. Keep owners from
            # this snapshot as wait targets rather than dropping them in a rescan.
            unfinished = self._unfinished_recordings()
            unresolved = [a for a in unfinished if not a.running]
            if unresolved:
                self._say(
                    f"Unfinished recording “{_title(unresolved[0].meeting_dir)}”. "
                    "Run `notes stop` to recover it.",
                    notify=True,
                    error=True,
                )
                return 1
            recording = [
                a
                for a in unfinished
                if a.session.pid != os.getpid() or a.session.phase == Phase.STOPPING
            ]
            if not recording:
                if recovered:
                    return 0
                self._say("Nothing is recording.", notify=True, error=True)
                return 1
            for active in recording:
                # A recovery owner is already stopping capture. Interrupting it can
                # discard the pending handoff to transcription.
                if active.session.phase == Phase.STOPPING:
                    continue
                session.stop_request_file(active.meeting_dir).touch()
                self.processes.interrupt(active.session.pid)
        return max(self._wait_for_stop(active) for active in recording)

    def _wait_for_stop(self, active: Active) -> int:
        """Waits for a recording to save its audio, which it shows by moving on to writing
        the note. Returns the exit status."""
        meeting_dir = active.meeting_dir
        deadline = time.monotonic() + STOP_WAIT_SECONDS
        while (
            (current := session.read(meeting_dir)) is not None
            and current.phase in (Phase.RECORDING, Phase.STOPPING)
            and session.is_running(current, self.processes)
            and time.monotonic() < deadline
        ):
            time.sleep(0.2)
        if current is None or current.phase not in (Phase.RECORDING, Phase.STOPPING):
            # If it failed instead, the job itself says so by notification.
            print(f"Stopped {meeting_dir.id}.")
            return 0
        if not session.is_running(current, self.processes):
            # Claiming can lose to another recovery command. Only the resulting
            # state, not an attempted recovery, establishes that stopping finished.
            self._recover(Active(meeting_dir, current, running=False))
            remaining = session.read(meeting_dir)
            if remaining is None or remaining.phase not in (Phase.RECORDING, Phase.STOPPING):
                print(f"Stopped {meeting_dir.id}.")
                return 0
            self._say(
                f"Unfinished recording “{_title(meeting_dir)}”. Run `notes stop` to recover it.",
                notify=True,
                error=True,
            )
            return 1
        self._say(f"“{_title(meeting_dir)}” didn't stop.", notify=True, error=True)
        return 1

    def status(self, args: argparse.Namespace) -> int:
        found = session.find(self.store, self.processes)
        if not found:
            print("Not recording.")
        now = datetime.now().astimezone()
        for active in found:
            title = _title(active.meeting_dir)
            if not active.running:
                print(f"“{title}” stopped unexpectedly. Run `notes stop` to recover it.")
            elif active.session.phase == Phase.STOPPING:
                print(f"Stopping “{title}” ({active.meeting_dir.id})")
            elif active.session.phase == Phase.RECORDING:
                elapsed = (now - active.session.started_at).total_seconds()
                print(f"Recording “{title}” for {timestamp(elapsed)} ({active.meeting_dir.id})")
            else:
                print(f"Writing the note for “{title}” ({active.meeting_dir.id})")
        return 0

    def record(self, args: argparse.Namespace) -> int:
        # First, so a stop that arrives while we're getting ready isn't lost.
        with _StopSignals() as signals:
            if args.meeting_id is None:
                # Outside the lock: reading the calendar can wait on a permission prompt.
                event = self._calendar_event()
                with session.lock(self.store):
                    if recording := self._unfinished_recordings():
                        print(
                            f"Already recording {recording[0].meeting_dir.id}. "
                            "Stop it with `notes stop`.",
                            file=sys.stderr,
                        )
                        return 1
                    meeting_dir = self.store.create(self._new_meeting(args.title, event))
                    session.write(meeting_dir, self._session(meeting_dir, Phase.RECORDING))
            else:
                try:
                    meeting_dir = self.store.get(args.meeting_id)
                except MeetingNotFound:
                    self._say(
                        f"Couldn't record: the meeting folder {args.meeting_id} is missing.",
                        notify=args.background,
                        error=True,
                    )
                    return 1
                session.write(meeting_dir, self._session(meeting_dir, Phase.RECORDING))
            try:
                return self._record_then_write_note(meeting_dir, args, signals)
            except Exception as error:
                if not args.background:
                    raise
                self._background_failed(meeting_dir, error)
                return 1
            finally:
                session.clear(meeting_dir, os.getpid())
                session.stop_request_file(meeting_dir).unlink(missing_ok=True)

    def _prepare_handwritten(self, meeting_dir: MeetingDir, background: bool) -> None:
        def warn(message: str) -> None:
            print(message, file=sys.stderr, flush=True)
            if background:
                try:
                    self.desktop.notify(message)
                except (OSError, DesktopError):
                    pass  # Notification failure must not prevent capture either.

        meeting = meeting_dir.load_meeting()
        path = meeting.handwritten_path
        try:
            if path is None:
                folder = self.config.notes_dir.expanduser().resolve()
                folder.mkdir(parents=True, exist_ok=True)
                number = 1
                while True:
                    suffix = "" if number == 1 else f"_{number}"
                    path = folder / f"{meeting.note_stem}{suffix}_handwritten.md"
                    try:
                        with path.open("x", encoding="utf-8") as note:
                            note.write(
                                f"# {meeting.title}\n\nAvailable after processing: "
                                f"[[{meeting.note_stem}|Summary]] · "
                                f"[[{meeting.transcript_stem}|Transcript]]\n\n"
                            )
                        break
                    except FileExistsError:
                        number += 1
                try:
                    meeting_dir.save_handwritten_path(path)
                except OSError as error:
                    warn(f"Couldn't associate handwritten note {path} ({error}).")
            elif not path.is_file():
                warn(f"Handwritten note is missing: {path}. Recording will continue.")
                return
        except OSError as error:
            warn(f"Couldn't create handwritten note ({error}). Recording will continue.")
            return
        print(f"Handwritten notes: {path}", flush=True)
        try:
            self.desktop.open_note(path)
        except (DesktopError, OSError) as error:
            warn(f"Couldn't open handwritten note {path} ({error}). Recording will continue.")

    def _record_then_write_note(
        self, meeting_dir: MeetingDir, args: argparse.Namespace, signals: _StopSignals
    ) -> int:
        title = _title(meeting_dir)
        background: bool = args.background
        self._prepare_handwritten(meeting_dir, background)
        duration = (
            min(args.duration, self.config.max_recording_seconds)
            if args.duration is not None
            else self.config.max_recording_seconds
        )
        if background:
            self.desktop.notify(f"Recording “{title}”. Automatic stop after {duration:g}s.")
        try:
            try:
                limit_reached = _record(
                    meeting_dir, duration, self.make_recorder(self.config), signals.stop
                )
            finally:
                # Stop sends signals while holding this same lock. Publish the
                # handoff before restoring SIGINT, so later Stops only wait.
                with session.lock(self.store):
                    session.write(meeting_dir, self._session(meeting_dir, Phase.STOPPING))
                    signals.end()
        except CaptureNotInstalled as error:
            self._say(str(error), notify=background, error=True)
            return 1
        except CaptureError as error:
            # Whatever was recorded is still worth transcribing.
            if not meeting_dir.captures():
                self._say(
                    f"Recording “{title}” failed ({error}). No audio was saved.",
                    notify=background,
                    error=True,
                )
                return 1
            self._say(
                f"Recording “{title}” ended with an error ({error}). Writing the note from "
                f"what was saved. To retry later: notes transcribe {meeting_dir.id}",
                notify=background,
                error=True,
            )
        else:
            if limit_reached:
                self._say(
                    f"Recording time limit reached ({duration:g}s). Stopped “{title}”; "
                    "writing the note…",
                    notify=background,
                )
            elif background:
                self.desktop.notify(f"Stopped recording “{title}”. Writing the note…")
        session.write(meeting_dir, self._session(meeting_dir, Phase.PROCESSING))
        return self._write_note(meeting_dir, transcribe=True, background=background)

    def _background_failed(self, meeting_dir: MeetingDir, error: Exception) -> None:
        """A background job failed unexpectedly. Its log gets the details; the user, who has
        no terminal, gets a notification saying where they are and how to retry."""
        traceback.print_exc()
        self._say(
            f"Couldn't write the note for “{_title(meeting_dir)}” ({error}). Details are in "
            f"notes.log in its folder. To retry: notes transcribe {meeting_dir.id}",
            notify=True,
            error=True,
        )

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
        try:
            pipeline.summarize(
                meeting_dir, talk, self.make_summarizer(self.config), self.config.my_name
            )
        except pipeline.NotTranscribed as error:
            self._say(f"Couldn't summarize: {error}", notify=background, error=True)
            return 1
        except SummaryError as error:
            # The transcript is still worth writing; the note says how to retry.
            self._render(meeting_dir, talk)
            self._say(
                f"Wrote the transcript for “{title}”, but couldn't summarize it ({error}). "
                f"To retry: notes summarize {meeting_dir.id}",
                notify=background,
                error=True,
            )
            return 1
        self._render(meeting_dir, talk)
        if background:
            self.desktop.notify(f"The note for “{title}” is ready.")
        return 0

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
        background: bool = getattr(args, "background", False)
        if background:
            session.write(meeting_dir, self._session(meeting_dir, Phase.PROCESSING))
        try:
            return self._write_note(
                meeting_dir, transcribe=args.command == "transcribe", background=background
            )
        except Exception as error:
            if not background:
                raise
            self._background_failed(meeting_dir, error)
            return 1
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
    calendar: Calendar | None = None,
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
        calendar or CaptureCalendar(config.capture),
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
