"""Command-line entry point: `notes`."""

import argparse
import signal
import sys
import threading
from collections.abc import Callable, Sequence
from datetime import datetime
from types import FrameType

from meeting_notes import pipeline
from meeting_notes.config import Config
from meeting_notes.meeting import Meeting
from meeting_notes.recorder import CaptureError, CaptureNotInstalled, CaptureRecorder, Recorder
from meeting_notes.store import MeetingDir, MeetingNotFound, MeetingStore
from meeting_notes.transcript import Transcriber


def _default_transcriber(config: Config) -> Transcriber:
    from meeting_notes.parakeet import ParakeetTranscriber

    return ParakeetTranscriber(config.model)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="notes", description="Local-first meeting notetaker.")
    commands = parser.add_subparsers(dest="command", required=True)

    record = commands.add_parser(
        "record", help="record the mic and system audio until Ctrl-C, then transcribe"
    )
    record.add_argument("--title", help="meeting title (default: Untitled)")
    record.add_argument(
        "--duration", type=float, metavar="SECONDS", help="stop automatically after SECONDS"
    )

    transcribe = commands.add_parser("transcribe", help="re-run transcription for a meeting")
    transcribe.add_argument("meeting_id")

    render = commands.add_parser("render", help="re-write a meeting's transcript into the vault")
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


def main(
    argv: Sequence[str] | None = None,
    *,
    config: Config | None = None,
    make_transcriber: Callable[[Config], Transcriber] = _default_transcriber,
    make_recorder: Callable[[Config], Recorder] = lambda config: CaptureRecorder(config.capture),
) -> int:
    args = _parser().parse_args(argv)
    config = config or Config.from_env()
    store = MeetingStore(config.data_dir)

    if args.command == "check":
        try:
            return CaptureRecorder(config.capture).check()
        except CaptureNotInstalled as error:
            print(error, file=sys.stderr)
            return 1

    if args.command == "record":
        meeting_dir = store.create(Meeting.new(args.title, datetime.now().astimezone()))
        try:
            _record(meeting_dir, args.duration, make_recorder(config))
        except CaptureNotInstalled as error:
            print(error, file=sys.stderr)
            return 1
        except CaptureError as error:
            # Whatever was recorded is still worth transcribing.
            print(f"Recording ended with an error: {error}", file=sys.stderr)
            if not meeting_dir.captures():
                print("No audio was saved.", file=sys.stderr)
                return 1
            print(
                f"Transcribing what was saved. To retry later: notes transcribe {meeting_dir.id}",
                file=sys.stderr,
            )
    else:
        try:
            meeting_dir = store.get(args.meeting_id)
        except MeetingNotFound as error:
            print(f"No meeting with id {error}", file=sys.stderr)
            return 1

    if args.command in ("record", "transcribe"):
        print("Transcribing...", flush=True)
        pipeline.transcribe(meeting_dir, make_transcriber(config))

    path = pipeline.render(meeting_dir, config)
    print(f"Transcript: {path}")
    return 0
