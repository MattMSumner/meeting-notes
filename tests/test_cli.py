"""End-to-end through the CLI, with a fake recorder and transcriber."""

import threading
from pathlib import Path

import pytest

from meeting_notes.cli import main
from meeting_notes.config import Config
from meeting_notes.store import MeetingDir
from meeting_notes.transcript import Segment


class FakeRecorder:
    def record(self, path: Path, stop: threading.Event) -> None:
        path.write_bytes(b"fake audio")


class FakeTranscriber:
    def __init__(self, segments: list[Segment]) -> None:
        self.segments = segments
        self.calls: list[Path] = []

    def transcribe(self, audio: Path) -> list[Segment]:
        self.calls.append(audio)
        return self.segments


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return Config(data_dir=tmp_path / "data", notes_dir=tmp_path / "vault" / "meetings", model="x")


def run(config: Config, transcriber: FakeTranscriber, *argv: str) -> int:
    return main(
        list(argv),
        config=config,
        make_transcriber=lambda _: transcriber,
        make_recorder=FakeRecorder,
    )


def only_meeting_dir(config: Config) -> Path:
    [meeting_dir] = list(config.data_dir.iterdir())
    return meeting_dir


def test_record_transcribes_and_writes_transcript_to_vault(config: Config):
    transcriber = FakeTranscriber([Segment(0.0, 1.0, "Hello there.")])

    assert run(config, transcriber, "record", "--title", "Weekly Sync") == 0

    meeting_dir = MeetingDir(only_meeting_dir(config))
    assert transcriber.calls == [meeting_dir.audio("me")]
    assert meeting_dir.segments_file("me").is_file()
    meeting = meeting_dir.load_meeting()
    assert meeting.title == "Weekly Sync"
    [transcript] = list(config.transcripts_dir.iterdir())
    assert transcript.name == f"{meeting.transcript_stem}.md"
    assert "**[00:00:00] Me:** Hello there." in transcript.read_text()


def test_writes_nothing_in_the_vault_outside_the_meetings_folder(config: Config):
    run(config, FakeTranscriber([]), "record")

    vault = config.notes_dir.parent
    written = {p.relative_to(vault) for p in vault.rglob("*") if p.is_file()}
    assert all(p.parts[0] == "meetings" for p in written)


def test_transcribe_reruns_transcription_for_an_existing_meeting(config: Config):
    run(config, FakeTranscriber([Segment(0.0, 1.0, "First take.")]), "record", "--title", "Sync")
    meeting_id = only_meeting_dir(config).name

    assert (
        run(config, FakeTranscriber([Segment(0.0, 1.0, "Second take.")]), "transcribe", meeting_id)
        == 0
    )

    [transcript] = list(config.transcripts_dir.iterdir())
    assert "Second take." in transcript.read_text()
    assert "First take." not in transcript.read_text()


def test_render_does_not_transcribe(config: Config):
    run(config, FakeTranscriber([Segment(0.0, 1.0, "Hi.")]), "record")
    meeting_id = only_meeting_dir(config).name
    transcriber = FakeTranscriber([])

    assert run(config, transcriber, "render", meeting_id) == 0

    assert transcriber.calls == []


def test_unknown_meeting_id_fails_cleanly(config: Config, capsys: pytest.CaptureFixture[str]):
    assert run(config, FakeTranscriber([]), "transcribe", "nope") == 1

    assert "No meeting with id nope" in capsys.readouterr().err
