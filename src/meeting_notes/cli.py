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
from meeting_notes.recorder import Recorder
from meeting_notes.store import MeetingDir, MeetingNotFound, MeetingStore
from meeting_notes.transcript import Transcriber


def _default_transcriber(config: Config) -> Transcriber:
    from meeting_notes.parakeet import ParakeetTranscriber

    return ParakeetTranscriber(config.model)


def _default_recorder() -> Recorder:
    from meeting_notes.recorder import MicRecorder

    return MicRecorder()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="notes", description="Local-first meeting notetaker.")
    commands = parser.add_subparsers(dest="command", required=True)

    record = commands.add_parser("record", help="record the mic until Ctrl-C, then transcribe")
    record.add_argument("--title", help="meeting title (default: Untitled)")
    record.add_argument(
        "--duration", type=float, metavar="SECONDS", help="stop automatically after SECONDS"
    )

    transcribe = commands.add_parser("transcribe", help="re-run transcription for a meeting")
    transcribe.add_argument("meeting_id")

    render = commands.add_parser("render", help="re-write a meeting's transcript into the vault")
    render.add_argument("meeting_id")
    return parser


# Any of these stops the recording cleanly, then transcription runs. Ctrl-C sends SIGINT,
# but some launchers (like Claude Code's ! mode) stop commands with SIGTERM or SIGHUP.
STOP_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


def _record(
    store: MeetingStore, title: str | None, duration: float | None, recorder: Recorder
) -> MeetingDir:
    meeting_dir = store.create(Meeting.new(title, datetime.now().astimezone()))
    stop = threading.Event()

    def on_stop_signal(signum: int, frame: FrameType | None) -> None:
        stop.set()

    previous = {sig: signal.signal(sig, on_stop_signal) for sig in STOP_SIGNALS}
    timer = threading.Timer(duration, stop.set) if duration else None
    try:
        if timer:
            timer.start()
            print(f"Recording {meeting_dir.id} for {duration:g}s. Press Ctrl-C to stop early.")
        else:
            print(f"Recording {meeting_dir.id}. Press Ctrl-C to stop.")
        recorder.record(meeting_dir.audio(pipeline.CHANNEL), stop)
    finally:
        if timer:
            timer.cancel()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    print("Stopped.")
    return meeting_dir


def main(
    argv: Sequence[str] | None = None,
    *,
    config: Config | None = None,
    make_transcriber: Callable[[Config], Transcriber] = _default_transcriber,
    make_recorder: Callable[[], Recorder] = _default_recorder,
) -> int:
    args = _parser().parse_args(argv)
    config = config or Config.from_env()
    store = MeetingStore(config.data_dir)

    try:
        if args.command == "record":
            meeting_dir = _record(store, args.title, args.duration, make_recorder())
        else:
            meeting_dir = store.get(args.meeting_id)
    except MeetingNotFound as error:
        print(f"No meeting with id {error}", file=sys.stderr)
        return 1

    if args.command in ("record", "transcribe"):
        print("Transcribing...")
        pipeline.transcribe(meeting_dir, make_transcriber(config))

    path = pipeline.render(meeting_dir, config)
    print(f"Transcript: {path}")
    return 0
