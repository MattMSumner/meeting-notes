"""End-to-end through the CLI, with a fake recorder and transcriber."""

import json
import os
import signal
import threading
from datetime import datetime
from pathlib import Path

import pytest

from meeting_notes.cli import main
from meeting_notes.config import Config
from meeting_notes.meeting import Meeting
from meeting_notes.recorder import CaptureError, Recorder
from meeting_notes.store import MeetingDir, MeetingStore
from meeting_notes.summary import ActionItem, Summary, SummaryError
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


SUMMARY = Summary(
    overview="Agreed to ship on Friday.",
    key_points=["The release is ready."],
    decisions=["Ship on Friday."],
    action_items=[ActionItem(owner="Me", task="Tag the release", due="Friday")],
)


class FakeSummarizer:
    """Returns a canned summary, or fails like Ollama being down."""

    def __init__(self, error: str | None = None) -> None:
        self.error = error
        self.transcripts: list[str] = []

    def summarize(self, meeting: Meeting, transcript: str) -> Summary:
        self.transcripts.append(transcript)
        if self.error:
            raise SummaryError(self.error)
        return SUMMARY


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return Config(
        data_dir=tmp_path / "data",
        notes_dir=tmp_path / "vault" / "meetings",
        model="x",
        capture=tmp_path / "no-such-binary",
        my_name="Sam",
    )


def run(
    config: Config,
    transcriber: FakeTranscriber,
    *argv: str,
    recorder: Recorder | None = None,
    summarizer: FakeSummarizer | None = None,
) -> int:
    return main(
        list(argv),
        config=config,
        make_transcriber=lambda _: transcriber,
        make_recorder=lambda _: recorder or FakeRecorder(),
        make_summarizer=lambda _: summarizer or FakeSummarizer(),
    )


def only_meeting_dir(config: Config) -> MeetingDir:
    [meeting_dir] = list(config.data_dir.iterdir())
    return MeetingDir(meeting_dir)


def only_transcript(config: Config) -> str:
    [transcript] = list(config.transcripts_dir.iterdir())
    return transcript.read_text()


def only_note(config: Config) -> str:
    [note] = [p for p in config.notes_dir.iterdir() if p.is_file()]
    return note.read_text()


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


class CrashingRecorder:
    """Saves audio, then fails like notes-capture dying before it writes capture.json."""

    def __init__(self, save_audio: bool = True) -> None:
        self.save_audio = save_audio

    def record(self, directory: Path, stop: threading.Event) -> None:
        if self.save_audio:
            (directory / "me.wav").write_bytes(b"fake audio")
            (directory / "them.wav").write_bytes(b"fake audio")
        raise CaptureError("notes-capture exited with status -9")


def test_a_crashed_recording_still_transcribes_both_sides(
    config: Config, capsys: pytest.CaptureFixture[str]
):
    transcriber = FakeTranscriber(
        {"me": [Segment(0.0, 1.0, "Can you hear me?")], "them": [Segment(2.0, 3.0, "Yes.")]}
    )

    assert run(config, transcriber, "record", recorder=CrashingRecorder()) == 0

    err = capsys.readouterr().err
    assert "Recording ended with an error" in err
    assert f"notes transcribe {only_meeting_dir(config).id}" in err
    body = only_transcript(config)
    assert "**[00:00:00] Me:** Can you hear me?" in body
    assert "**[00:00:02] Them:** Yes." in body
    assert "didn't finish cleanly" in body


def test_a_failed_recording_with_no_audio_fails(config: Config, capsys: pytest.CaptureFixture[str]):
    code = run(config, FakeTranscriber(), "record", recorder=CrashingRecorder(save_audio=False))

    assert code == 1
    assert "No audio was saved." in capsys.readouterr().err


def test_a_side_that_never_received_audio_is_flagged(config: Config):
    meeting_dir = config.data_dir / "2026-10-20-1100-sync"
    meeting_dir.mkdir(parents=True)
    (meeting_dir / "meeting.json").write_text(
        '{"title": "Sync", "started_at": "2026-10-20T11:00:00-04:00"}'
    )
    write_capture(meeting_dir)
    manifest = json.loads((meeting_dir / "capture.json").read_text())
    manifest["channels"]["them"]["offset_seconds"] = None
    (meeting_dir / "capture.json").write_text(json.dumps(manifest))
    transcriber = FakeTranscriber({"me": [Segment(0.0, 1.0, "Hello?")]})

    assert run(config, transcriber, "transcribe", meeting_dir.name) == 0

    assert [p.name for p in transcriber.calls] == ["me.wav"]
    assert '> [!warning] No "Them" audio was recorded at all.' in only_transcript(config)


def test_check_without_the_binary_says_so(config: Config, capsys: pytest.CaptureFixture[str]):
    assert main(["check"], config=config) == 1

    err = capsys.readouterr().err
    assert "capture/install.sh" in err
    assert "Recording" not in err


def test_record_summarizes_the_conversation_into_a_note(config: Config):
    transcriber = FakeTranscriber(
        {"me": [Segment(0.0, 2.0, "Ready to ship?")], "them": [Segment(3.0, 4.0, "Friday.")]}
    )
    summarizer = FakeSummarizer()

    assert run(config, transcriber, "record", "--title", "Release", summarizer=summarizer) == 0

    assert summarizer.transcripts == ["[00:00:00] Sam: Ready to ship?\n[00:00:03] Them: Friday."]
    meeting = only_meeting_dir(config).load_meeting()
    note = config.notes_dir / f"{meeting.note_stem}.md"
    body = note.read_text()
    assert "Agreed to ship on Friday." in body
    assert "- [ ] **Me**: Tag the release (due Friday)" in body
    assert f"Transcript: [[{meeting.transcript_stem}]]" in body
    assert f"Note: [[{meeting.note_stem}]]" in only_transcript(config)


def test_a_failed_summary_still_writes_the_transcript_and_says_how_to_retry(
    config: Config, capsys: pytest.CaptureFixture[str]
):
    transcriber = FakeTranscriber({"me": [Segment(0.0, 1.0, "Hello.")]})

    status = run(config, transcriber, "record", summarizer=FakeSummarizer("Ollama is down"))

    meeting_id = only_meeting_dir(config).id
    assert status == 1
    assert "Hello." in only_transcript(config)
    assert f"`notes summarize {meeting_id}`" in only_note(config)
    err = capsys.readouterr().err
    assert "Ollama is down" in err
    assert f"notes summarize {meeting_id}" in err


def test_summarize_reruns_only_the_summary(config: Config):
    run(
        config,
        FakeTranscriber({"me": [Segment(0.0, 1.0, "Hello.")]}),
        "record",
        summarizer=FakeSummarizer("down"),
    )
    transcriber = FakeTranscriber()

    assert run(config, transcriber, "summarize", only_meeting_dir(config).id) == 0

    assert transcriber.calls == []
    assert "Agreed to ship on Friday." in only_note(config)


def test_a_meeting_with_no_speech_is_not_summarized(config: Config):
    summarizer = FakeSummarizer()

    assert run(config, FakeTranscriber(), "record", summarizer=summarizer) == 0

    assert summarizer.transcripts == []
    assert "_No speech was detected._" in only_note(config)


def test_render_leaves_a_note_edited_in_the_vault_alone(
    config: Config, capsys: pytest.CaptureFixture[str]
):
    run(config, FakeTranscriber({"me": [Segment(0.0, 1.0, "Hello.")]}), "record")
    [note] = [p for p in config.notes_dir.iterdir() if p.is_file()]
    edited = note.read_text().replace("- [ ]", "- [x]")
    note.write_text(edited)

    assert run(config, FakeTranscriber(), "render", only_meeting_dir(config).id) == 0

    assert note.read_text() == edited
    assert f"Left {note.name} alone" in capsys.readouterr().err


def test_retranscribing_with_no_speech_drops_the_old_summary(config: Config):
    run(config, FakeTranscriber({"me": [Segment(0.0, 1.0, "Hello.")]}), "record")
    meeting_dir = only_meeting_dir(config)
    assert "Agreed to ship on Friday." in only_note(config)

    run(config, FakeTranscriber(), "transcribe", meeting_dir.id)

    assert not meeting_dir.summary_file.exists()
    assert "Agreed to ship on Friday." not in only_note(config)
    assert "_No speech was detected._" in only_note(config)


def test_a_failed_summary_after_retranscribing_does_not_show_the_old_one(config: Config):
    run(config, FakeTranscriber({"me": [Segment(0.0, 1.0, "Hello.")]}), "record")
    meeting_dir = only_meeting_dir(config)

    run(
        config,
        FakeTranscriber({"me": [Segment(0.0, 1.0, "Goodbye.")]}),
        "transcribe",
        meeting_dir.id,
        summarizer=FakeSummarizer("Ollama is down"),
    )

    assert "Agreed to ship on Friday." not in only_note(config)
    assert f"`notes summarize {meeting_dir.id}`" in only_note(config)


def test_summarize_before_transcribing_says_to_transcribe(
    config: Config, capsys: pytest.CaptureFixture[str]
):
    meeting_dir = MeetingStore(config.data_dir).create(
        Meeting.new("Crashed", datetime(2026, 10, 20, 9, 0))
    )
    write_capture(meeting_dir.path)
    summarizer = FakeSummarizer()

    assert run(config, FakeTranscriber(), "summarize", meeting_dir.id, summarizer=summarizer) == 1

    assert summarizer.transcripts == []
    assert f"notes transcribe {meeting_dir.id}" in capsys.readouterr().err


def test_an_unreadable_summary_still_renders_with_a_warning(config: Config):
    run(config, FakeTranscriber({"me": [Segment(0.0, 1.0, "Hello.")]}), "record")
    meeting_dir = only_meeting_dir(config)
    meeting_dir.summary_file.write_text("{not json")

    assert run(config, FakeTranscriber(), "render", meeting_dir.id) == 0

    note = only_note(config)
    assert "> [!warning] summary.json couldn't be read" in note
    assert f"`notes summarize {meeting_dir.id}`" in note
