"""notes start / stop / status, and the background jobs they run, with fake processes."""

import os
import threading
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from test_cli import FakeRecorder, FakeSummarizer, FakeTranscriber, write_capture

from meeting_notes import cli, session
from meeting_notes.cli import main
from meeting_notes.config import Config
from meeting_notes.meeting import Meeting
from meeting_notes.session import Phase, Session
from meeting_notes.store import MeetingDir, MeetingStore
from meeting_notes.transcript import Segment


class FakeProcesses:
    """Processes that exist only as entries in a dict of pid -> start time."""

    def __init__(self) -> None:
        self.running: dict[int, str] = {os.getpid(): "us"}
        self.spawned: list[list[str]] = []
        self.interrupted: list[int] = []
        self.stopped_captures: list[Path] = []
        self.on_interrupt: Callable[[int], None] = lambda pid: None
        self._next_pid = 5000

    def started(self, pid: int) -> str | None:
        return self.running.get(pid)

    def interrupt(self, pid: int) -> None:
        self.interrupted.append(pid)
        self.on_interrupt(pid)

    def spawn(self, args: list[str], log: Path) -> int:
        self._next_pid += 1
        self.running[self._next_pid] = f"started {self._next_pid}"
        self.spawned.append(args)
        return self._next_pid

    def stop_capture(self, out_dir: Path) -> None:
        self.stopped_captures.append(out_dir)


class FakeDesktop:
    def __init__(self, answer: str | None = "") -> None:
        self.answer = answer
        self.notifications: list[str] = []
        self.asked = 0

    def notify(self, message: str) -> None:
        self.notifications.append(message)

    def ask_text(self, prompt: str, default: str = "") -> str | None:
        self.asked += 1
        return self.answer


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return Config(
        data_dir=tmp_path / "data",
        notes_dir=tmp_path / "vault" / "meetings",
        model="x",
        capture=tmp_path / "no-such-binary",
        my_name="Sam",
    )


@pytest.fixture
def processes() -> FakeProcesses:
    return FakeProcesses()


@pytest.fixture
def desktop() -> FakeDesktop:
    return FakeDesktop()


def run(
    config: Config,
    processes: FakeProcesses,
    desktop: FakeDesktop,
    *argv: str,
    transcriber: FakeTranscriber | None = None,
) -> int:
    return main(
        list(argv),
        config=config,
        make_transcriber=lambda _: transcriber or FakeTranscriber(),
        make_summarizer=lambda _: FakeSummarizer(),
        make_recorder=lambda _: FakeRecorder(),
        processes=processes,
        desktop=desktop,
    )


def meeting(config: Config, title: str = "Standup", minutes_ago: int = 5) -> MeetingDir:
    started = datetime.now().astimezone() - timedelta(minutes=minutes_ago)
    return MeetingStore(config.data_dir).create(Meeting.new(title, started))


def recording_by(processes: FakeProcesses, meeting_dir: MeetingDir, pid: int = 4000) -> None:
    """Makes meeting_dir look recorded by a live process."""
    processes.running[pid] = f"started {pid}"
    session.write(
        meeting_dir,
        Session(pid, f"started {pid}", Phase.RECORDING, meeting_dir.load_meeting().started_at),
    )


def orphaned(meeting_dir: MeetingDir, phase: Phase = Phase.RECORDING) -> None:
    """Makes meeting_dir look like its process died mid-way."""
    session.write(meeting_dir, Session(4999, "gone", phase, datetime.now().astimezone()))


# start


def test_start_records_a_new_meeting_in_the_background(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    assert run(config, processes, desktop, "start", "--title", "Standup") == 0

    [meeting_dir] = MeetingStore(config.data_dir).all()
    assert meeting_dir.load_meeting().title == "Standup"
    assert processes.spawned == [["record", "--meeting-id", meeting_dir.id, "--background"]]
    current = session.read(meeting_dir)
    assert current is not None
    assert current.phase == Phase.RECORDING
    assert session.is_running(current, processes)


def test_start_can_ask_for_the_title(config: Config, processes: FakeProcesses):
    desktop = FakeDesktop(answer="Design review")

    run(config, processes, desktop, "start", "--ask-title")

    [meeting_dir] = MeetingStore(config.data_dir).all()
    assert meeting_dir.load_meeting().title == "Design review"


def test_an_empty_title_is_untitled(config: Config, processes: FakeProcesses):
    run(config, processes, FakeDesktop(answer=""), "start", "--ask-title")

    [meeting_dir] = MeetingStore(config.data_dir).all()
    assert meeting_dir.load_meeting().title == "Untitled"


def test_cancelling_the_title_dialog_starts_nothing(config: Config, processes: FakeProcesses):
    assert run(config, processes, FakeDesktop(answer=None), "start", "--ask-title") == 0

    assert MeetingStore(config.data_dir).all() == []
    assert processes.spawned == []


def test_start_while_recording_refuses_and_says_so(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    recording_by(processes, meeting(config, "Standup"))

    assert run(config, processes, desktop, "start", "--ask-title") == 1

    assert processes.spawned == []
    assert desktop.asked == 0
    assert desktop.notifications == ["Already recording “Standup”."]


def test_start_while_a_note_is_being_written_is_fine(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    earlier = meeting(config, "Earlier")
    processes.running[4000] = "started 4000"
    session.write(earlier, Session(4000, "started 4000", Phase.PROCESSING, datetime.now()))

    assert run(config, processes, desktop, "start", "--title", "Next") == 0
    assert len(processes.spawned) == 1


# stop


def test_stop_with_nothing_recording_says_so(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    assert run(config, processes, desktop, "stop") == 1

    assert desktop.notifications == ["Nothing is recording."]


def test_stop_interrupts_the_recording_and_waits_for_its_audio(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    meeting_dir = meeting(config)
    recording_by(processes, meeting_dir, pid=4000)

    def finish_recording(pid: int) -> None:
        current = session.read(meeting_dir)
        assert current is not None
        session.write(
            meeting_dir, Session(pid, current.process_started, Phase.PROCESSING, current.started_at)
        )

    processes.on_interrupt = finish_recording

    assert run(config, processes, desktop, "stop") == 0

    assert processes.interrupted == [4000]


def test_stop_reports_a_recording_that_wont_stop(
    config: Config,
    processes: FakeProcesses,
    desktop: FakeDesktop,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(cli, "STOP_WAIT_SECONDS", 0.3)
    recording_by(processes, meeting(config, "Stuck"))

    assert run(config, processes, desktop, "stop") == 1

    assert desktop.notifications == ["“Stuck” didn't stop."]


def test_stop_recovers_a_recording_whose_process_died(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    meeting_dir = meeting(config, "Crashed")
    write_capture(meeting_dir.path)
    orphaned(meeting_dir)

    assert run(config, processes, desktop, "stop") == 0

    assert processes.stopped_captures == [meeting_dir.path]
    assert processes.spawned == [["transcribe", meeting_dir.id, "--background"]]
    current = session.read(meeting_dir)
    assert current is not None and current.phase == Phase.PROCESSING
    assert session.is_running(current, processes)
    assert "“Crashed” stopped unexpectedly" in desktop.notifications[0]


def test_an_orphan_without_audio_is_cleared(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    meeting_dir = meeting(config, "Crashed")
    orphaned(meeting_dir)

    run(config, processes, desktop, "stop")

    assert processes.spawned == []
    assert session.read(meeting_dir) is None
    assert desktop.notifications[0] == "“Crashed” stopped before any audio was saved."


def test_a_reused_pid_is_not_mistaken_for_the_recording(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    # After a reboot, another process can have the recording's pid.
    meeting_dir = meeting(config)
    write_capture(meeting_dir.path)
    session.write(meeting_dir, Session(4000, "before the reboot", Phase.RECORDING, datetime.now()))
    processes.running[4000] = "after the reboot"

    run(config, processes, desktop, "stop")

    assert processes.interrupted == []
    assert processes.spawned == [["transcribe", meeting_dir.id, "--background"]]


def test_a_half_written_session_counts_as_orphaned(config: Config, processes: FakeProcesses):
    meeting_dir = meeting(config)
    session.session_file(meeting_dir).write_text('{"pid": 12')

    [active] = session.find(MeetingStore(config.data_dir), processes)

    assert not active.running


def test_start_recovers_orphans_first(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    crashed = meeting(config, "Crashed")
    write_capture(crashed.path)
    orphaned(crashed)

    assert run(config, processes, desktop, "start", "--title", "Next") == 0

    assert [args[0] for args in processes.spawned] == ["transcribe", "record"]


# status


def test_status(
    config: Config,
    processes: FakeProcesses,
    desktop: FakeDesktop,
    capsys: pytest.CaptureFixture[str],
):
    assert run(config, processes, desktop, "status") == 0
    assert capsys.readouterr().out == "Not recording.\n"

    recording_by(processes, meeting(config, "Standup", minutes_ago=12))
    orphaned(meeting(config, "Crashed", minutes_ago=60))
    run(config, processes, desktop, "status")

    out = capsys.readouterr().out
    assert "Recording “Standup” for 00:12:0" in out
    assert "“Crashed” stopped unexpectedly. Run `notes stop` to recover it." in out
    assert desktop.notifications == []


# The background jobs


def test_a_background_recording_reports_by_notification_and_cleans_up(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    meeting_dir = meeting(config, "Standup")
    phases: list[Phase | None] = []

    class CheckingTranscriber(FakeTranscriber):
        def transcribe(self, audio: Path) -> list[Segment]:
            current = session.read(meeting_dir)
            phases.append(current.phase if current else None)
            return [Segment(0.0, 1.0, "Hello.")]

    status = run(
        config,
        processes,
        desktop,
        "record",
        "--meeting-id",
        meeting_dir.id,
        "--background",
        transcriber=CheckingTranscriber(),
    )

    assert status == 0
    assert set(phases) == {Phase.PROCESSING}
    assert session.read(meeting_dir) is None
    assert desktop.notifications == [
        "Recording “Standup”.",
        "Stopped recording “Standup”. Writing the note…",
        "The note for “Standup” is ready.",
    ]


def test_a_foreground_recording_refuses_while_another_is_running(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    recording_by(processes, meeting(config, "Standup"))

    assert run(config, processes, desktop, "record") == 1
    assert len(MeetingStore(config.data_dir).all()) == 1


def test_a_recovery_job_writes_the_note_and_cleans_up(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    meeting_dir = meeting(config, "Crashed")
    write_capture(meeting_dir.path)
    transcriber = FakeTranscriber({"me": [Segment(0.0, 1.0, "Hello.")]})

    status = run(
        config,
        processes,
        desktop,
        "transcribe",
        meeting_dir.id,
        "--background",
        transcriber=transcriber,
    )

    assert status == 0
    assert session.read(meeting_dir) is None
    assert desktop.notifications == ["The note for “Crashed” is ready."]


# Review fixes


def test_a_background_job_that_fails_unexpectedly_says_so(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    meeting_dir = meeting(config, "Standup")

    class BrokenTranscriber(FakeTranscriber):
        def transcribe(self, audio: Path) -> list[Segment]:
            raise RuntimeError("out of memory")

    status = run(
        config,
        processes,
        desktop,
        "record",
        "--meeting-id",
        meeting_dir.id,
        "--background",
        transcriber=BrokenTranscriber(),
    )

    assert status == 1
    assert session.read(meeting_dir) is None
    assert "Couldn't write the note for “Standup” (out of memory)" in desktop.notifications[-1]
    assert f"notes transcribe {meeting_dir.id}" in desktop.notifications[-1]


def test_a_stop_requested_before_the_recording_is_ready_is_not_lost(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    meeting_dir = meeting(config)
    session.stop_request_file(meeting_dir).touch()
    stopped: list[bool] = []

    class WaitingRecorder:
        def record(self, directory: Path, stop: threading.Event) -> None:
            stopped.append(stop.wait(timeout=5))
            write_capture(directory)

    main(
        ["record", "--meeting-id", meeting_dir.id, "--background"],
        config=config,
        make_transcriber=lambda _: FakeTranscriber(),
        make_summarizer=lambda _: FakeSummarizer(),
        make_recorder=lambda _: WaitingRecorder(),
        processes=processes,
        desktop=desktop,
    )

    assert stopped == [True]
    assert not session.stop_request_file(meeting_dir).exists()
    assert list(meeting_dir.path.glob("*.tmp")) == []


def test_stop_asks_by_file_as_well_as_by_signal(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    meeting_dir = meeting(config)
    recording_by(processes, meeting_dir, pid=4000)
    asked: list[bool] = []

    def finish_recording(pid: int) -> None:
        asked.append(session.stop_request_file(meeting_dir).exists())
        session.write(meeting_dir, Session(pid, "started 4000", Phase.PROCESSING, datetime.now()))

    processes.on_interrupt = finish_recording

    assert run(config, processes, desktop, "stop") == 0
    assert asked == [True]


def test_a_recording_that_dies_while_stopping_is_recovered(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    meeting_dir = meeting(config, "Standup")
    write_capture(meeting_dir.path)
    recording_by(processes, meeting_dir, pid=4000)

    def die(pid: int) -> None:
        del processes.running[pid]

    processes.on_interrupt = die

    assert run(config, processes, desktop, "stop") == 0

    assert processes.spawned == [["transcribe", meeting_dir.id, "--background"]]
    assert "“Standup” stopped unexpectedly" in desktop.notifications[0]


def test_a_missing_meeting_folder_is_reported(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    status = run(config, processes, desktop, "record", "--meeting-id", "gone", "--background")

    assert status == 1
    assert desktop.notifications == ["Couldn't record: the meeting folder gone is missing."]


def test_start_waits_for_another_start_or_stop_to_finish(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    store = MeetingStore(config.data_dir)
    done = threading.Event()

    def start() -> None:
        run(config, processes, desktop, "start", "--title", "Standup")
        done.set()

    with session.lock(store):
        thread = threading.Thread(target=start)
        thread.start()
        assert not done.wait(0.3)
    assert done.wait(5)
    thread.join()
