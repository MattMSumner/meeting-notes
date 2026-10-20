"""End-to-end through the CLI, with a fake recorder and transcriber."""

import json
import os
import signal
import threading
from pathlib import Path

import pytest

from meeting_notes.cli import main
from meeting_notes.config import Config
from meeting_notes.recorder import Recorder
from meeting_notes.store import MeetingDir
from meeting_notes.transcript import Segment


def write_capture(directory: Path, them_offset: float = 0.025, them_all_zero: bool = False) -> None:
    """What notes-capture leaves behind: both channels and capture.json."""
    (directory / "me.wav").write_bytes(b"fake audio")
    (directory / "them.wav").write_bytes(b"fake audio")
    manifest = {
        "started_at": "2026-10-20T18:05:00Z",
        "sample_rate": 16000,
        "channels": {
            "me": {
                "file": "me.wav",
                "offset_seconds": 0.0,
                "duration_seconds": 30,
                "all_zero": False,
            },
            "them": {
                "file": "them.wav",
                "offset_seconds": them_offset,
                "duration_seconds": 30,
                "all_zero": them_all_zero,
            },
        },
    }
    (directory / "capture.json").write_text(json.dumps(manifest))


class FakeRecorder:
    def __init__(self, them_all_zero: bool = False) -> None:
        self.them_all_zero = them_all_zero

    def record(self, directory: Path, stop: threading.Event) -> None:
        write_capture(directory, them_all_zero=self.them_all_zero)


class WaitingRecorder:
    """Waits for the stop event like the real recorder, optionally signalling itself first."""

    def __init__(self, send_signal: signal.Signals | None = None) -> None:
        self.send_signal = send_signal
        self.stopped = False

    def record(self, directory: Path, stop: threading.Event) -> None:
        if self.send_signal:
            os.kill(os.getpid(), self.send_signal)
        self.stopped = stop.wait(timeout=5)
        write_capture(directory)


class FakeTranscriber:
    """Returns canned segments per channel (keyed by audio file stem: "me", "them")."""

    def __init__(self, segments: dict[str, list[Segment]] | None = None) -> None:
        self.segments = segments or {}
        self.calls: list[Path] = []

    def transcribe(self, audio: Path) -> list[Segment]:
        self.calls.append(audio)
        return self.segments.get(audio.stem, [])


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return Config(
        data_dir=tmp_path / "data",
        notes_dir=tmp_path / "vault" / "meetings",
        model="x",
        capture=tmp_path / "no-such-binary",
    )


def run(
    config: Config, transcriber: FakeTranscriber, *argv: str, recorder: Recorder | None = None
) -> int:
    return main(
        list(argv),
        config=config,
        make_transcriber=lambda _: transcriber,
        make_recorder=lambda _: recorder or FakeRecorder(),
    )


def only_meeting_dir(config: Config) -> MeetingDir:
    [meeting_dir] = list(config.data_dir.iterdir())
    return MeetingDir(meeting_dir)


def only_transcript(config: Config) -> str:
    [transcript] = list(config.transcripts_dir.iterdir())
    return transcript.read_text()


def test_record_transcribes_both_sides_into_one_conversation(config: Config):
    transcriber = FakeTranscriber(
        {
            "me": [Segment(0.0, 2.0, "Hi, can you hear me?"), Segment(9.0, 10.0, "Great.")],
            "them": [Segment(4.0, 6.0, "Yes, loud and clear.")],
        }
    )

    assert run(config, transcriber, "record", "--title", "Weekly Sync") == 0

    meeting_dir = only_meeting_dir(config)
    assert sorted(p.name for p in transcriber.calls) == ["me.wav", "them.wav"]
    assert meeting_dir.load_meeting().title == "Weekly Sync"
    [transcript] = list(config.transcripts_dir.iterdir())
    assert transcript.name == f"{meeting_dir.load_meeting().transcript_stem}.md"
    body = transcript.read_text()
    assert (
        "**[00:00:00] Me:** Hi, can you hear me?\n\n"
        "**[00:00:04] Them:** Yes, loud and clear.\n\n"
        "**[00:00:09] Me:** Great.\n"
    ) in body


def test_silent_system_audio_is_skipped_and_flagged(config: Config):
    transcriber = FakeTranscriber({"me": [Segment(0.0, 1.0, "Hello?")]})

    run(config, transcriber, "record", recorder=FakeRecorder(them_all_zero=True))

    assert [p.name for p in transcriber.calls] == ["me.wav"]
    body = only_transcript(config)
    assert '> [!warning] The "Them" audio was silent' in body
    assert "notes check" in body


def test_mic_only_meetings_from_m1_still_transcribe(config: Config):
    meeting_dir = config.data_dir / "2026-10-20-0848-m1-test"
    meeting_dir.mkdir(parents=True)
    (meeting_dir / "meeting.json").write_text(
        '{"title": "M1 test", "started_at": "2026-10-20T08:48:00-04:00"}'
    )
    (meeting_dir / "me.wav").write_bytes(b"fake audio")
    transcriber = FakeTranscriber({"me": [Segment(1.0, 2.0, "Old recording.")]})

    assert run(config, transcriber, "transcribe", meeting_dir.name) == 0

    assert "**[00:00:01] Me:** Old recording." in only_transcript(config)


def test_writes_nothing_in_the_vault_outside_the_meetings_folder(config: Config):
    run(config, FakeTranscriber(), "record")

    vault = config.notes_dir.parent
    written = {p.relative_to(vault) for p in vault.rglob("*") if p.is_file()}
    assert all(p.parts[0] == "meetings" for p in written)


def test_transcribe_reruns_transcription_for_an_existing_meeting(config: Config):
    run(config, FakeTranscriber({"me": [Segment(0.0, 1.0, "First take.")]}), "record")
    meeting_id = only_meeting_dir(config).id

    second = FakeTranscriber({"me": [Segment(0.0, 1.0, "Second take.")]})
    assert run(config, second, "transcribe", meeting_id) == 0

    assert "Second take." in only_transcript(config)
    assert "First take." not in only_transcript(config)


def test_render_does_not_transcribe(config: Config):
    run(config, FakeTranscriber({"me": [Segment(0.0, 1.0, "Hi.")]}), "record")
    transcriber = FakeTranscriber()

    assert run(config, transcriber, "render", only_meeting_dir(config).id) == 0

    assert transcriber.calls == []
    assert "Hi." in only_transcript(config)


def test_unknown_meeting_id_fails_cleanly(config: Config, capsys: pytest.CaptureFixture[str]):
    assert run(config, FakeTranscriber(), "transcribe", "nope") == 1

    assert "No meeting with id nope" in capsys.readouterr().err


def test_missing_capture_binary_fails_cleanly(config: Config, capsys: pytest.CaptureFixture[str]):
    code = main(["record"], config=config, make_transcriber=lambda _: FakeTranscriber())

    assert code == 1
    assert "capture/install.sh" in capsys.readouterr().err


def test_duration_stops_recording_and_still_transcribes(config: Config):
    recorder = WaitingRecorder()
    transcriber = FakeTranscriber()

    assert run(config, transcriber, "record", "--duration", "0.05", recorder=recorder) == 0

    assert recorder.stopped
    assert len(transcriber.calls) == 2


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM, signal.SIGHUP])
def test_stop_signals_end_recording_cleanly(config: Config, sig: signal.Signals):
    recorder = WaitingRecorder(send_signal=sig)
    handler_before = signal.getsignal(sig)

    assert run(config, FakeTranscriber(), "record", recorder=recorder) == 0

    assert recorder.stopped
    assert list(config.transcripts_dir.iterdir())
    assert signal.getsignal(sig) == handler_before
