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

    transcribe = commands.add_parser("transcribe", help="re-run transcription for a meeting")
    transcribe.add_argument("meeting_id")

    render = commands.add_parser("render", help="re-write a meeting's transcript into the vault")
    render.add_argument("meeting_id")
    return parser


def _record(store: MeetingStore, title: str | None, recorder: Recorder) -> MeetingDir:
    meeting_dir = store.create(Meeting.new(title, datetime.now().astimezone()))
    stop = threading.Event()

    def on_interrupt(signum: int, frame: FrameType | None) -> None:
        stop.set()

    previous = signal.signal(signal.SIGINT, on_interrupt)
    try:
        print(f"Recording {meeting_dir.id}. Press Ctrl-C to stop.")
        recorder.record(meeting_dir.audio(pipeline.CHANNEL), stop)
    finally:
        signal.signal(signal.SIGINT, previous)
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
            meeting_dir = _record(store, args.title, make_recorder())
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
