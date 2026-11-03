"""notes start / stop / status, and the background jobs they run, with fake processes."""

import os
import signal
import threading
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from test_cli import FakeRecorder, FakeSummarizer, FakeTranscriber, write_capture

from meeting_notes import cli, session
from meeting_notes.calendar import Attendee, Event
from meeting_notes.cli import main
from meeting_notes.config import Config
from meeting_notes.macos import DesktopError
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

    def choose_meeting(self, choices: list[tuple[str, str]]) -> str | None:
        return self.answer

    def open_note(self, path: Path) -> None:
        pass

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
        "Recording “Standup”. Automatic stop after 3600s.",
        "Stopped recording “Standup”. Writing the note…",
        f"Ready to enhance: notes enhance {meeting_dir.id}",
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
    assert desktop.notifications == [f"Ready to enhance: notes enhance {meeting_dir.id}"]


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


# Second review


def test_ctrl_c_interrupts_transcribing_again_after_recording(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    default = signal.getsignal(signal.SIGINT)
    during: list[object] = []

    class CheckingTranscriber(FakeTranscriber):
        def transcribe(self, audio: Path) -> list[Segment]:
            during.append(signal.getsignal(signal.SIGINT))
            return []

    run(config, processes, desktop, "record", transcriber=CheckingTranscriber())

    assert during and all(handler is default for handler in during)
    assert signal.getsignal(signal.SIGINT) is default


def test_a_session_removed_while_reading_is_no_session(
    config: Config, monkeypatch: pytest.MonkeyPatch
):
    meeting_dir = meeting(config)
    orphaned(meeting_dir)

    def vanished(self: Path, *args: object, **kwargs: object) -> None:
        raise FileNotFoundError(self)

    monkeypatch.setattr(Path, "open", vanished)

    assert session.read(meeting_dir) is None


def test_process_start_times_compare_across_locales_and_time_zones(
    monkeypatch: pytest.MonkeyPatch,
):
    processes = session.SystemProcesses()
    in_terminal = processes.started(os.getpid())
    monkeypatch.setenv("LC_ALL", "de_DE.UTF-8")
    monkeypatch.setenv("TZ", "Asia/Tokyo")

    assert in_terminal is not None
    assert processes.started(os.getpid()) == in_terminal


def test_the_title_dialog_does_not_hold_up_a_stop(config: Config, processes: FakeProcesses):
    store = MeetingStore(config.data_dir)
    asked = threading.Event()

    class SlowDesktop(FakeDesktop):
        def ask_text(self, prompt: str, default: str = "") -> str | None:
            asked.set()
            return "Standup"

    with session.lock(store):  # as if a stop were running
        thread = threading.Thread(
            target=run, args=(config, processes, SlowDesktop(), "start", "--ask-title")
        )
        thread.start()
        # The dialog shows straight away; only creating the recording waits for the lock.
        assert asked.wait(2)
        assert store.all() == []
    thread.join(5)
    assert [m.load_meeting().title for m in store.all()] == ["Standup"]


def test_a_failing_title_dialog_is_reported_not_treated_as_cancel(
    config: Config, processes: FakeProcesses
):
    class BrokenDesktop(FakeDesktop):
        def ask_text(self, prompt: str, default: str = "") -> str | None:
            raise DesktopError("Not authorized to send Apple events")

    desktop = BrokenDesktop()

    assert run(config, processes, desktop, "start", "--ask-title") == 1
    assert desktop.notifications == [
        "Couldn't ask for the title (Not authorized to send Apple events)."
    ]


def test_a_crashed_note_writing_job_is_reported_once_not_rerun(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    meeting_dir = meeting(config, "Standup")
    write_capture(meeting_dir.path)
    orphaned(meeting_dir, Phase.PROCESSING)

    run(config, processes, desktop, "stop")
    run(config, processes, desktop, "stop")

    assert processes.spawned == []
    assert session.read(meeting_dir) is None
    assert desktop.notifications[0] == (
        f"Writing the note for “Standup” stopped unexpectedly. "
        f"To retry: notes transcribe {meeting_dir.id}"
    )
    assert desktop.notifications[1:] == ["Nothing is recording."]


def test_start_twice_in_a_minute_without_titles(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    assert run(config, processes, desktop, "start") == 0
    processes.running.clear()  # the first recording finished
    processes.running[os.getpid()] = "us"
    for active in session.find(MeetingStore(config.data_dir), processes):
        session.session_file(active.meeting_dir).unlink()

    assert run(config, processes, desktop, "start") == 0
    titles = [m.load_meeting().title for m in MeetingStore(config.data_dir).all()]
    assert sorted(titles) == ["Untitled", "Untitled 2"]


# Third review


def test_a_recording_that_reported_its_own_failure_is_not_recovered(
    config: Config,
    processes: FakeProcesses,
    desktop: FakeDesktop,
    monkeypatch: pytest.MonkeyPatch,
):
    meeting_dir = meeting(config, "Standup")
    write_capture(meeting_dir.path)
    recording_by(processes, meeting_dir, pid=4000)
    stale = session.read(meeting_dir)

    stale_reads: list[Session | None] = []

    def fail_on_its_own(pid: int) -> None:
        # The job reports the failure itself, clears its session and exits, just after
        # stop's next look at the session.
        session.clear(meeting_dir, pid)
        del processes.running[pid]
        stale_reads.append(stale)

    processes.on_interrupt = fail_on_its_own
    real_read = session.read

    def read(meeting_dir: MeetingDir) -> Session | None:
        return stale_reads.pop() if stale_reads else real_read(meeting_dir)

    monkeypatch.setattr(session, "read", read)

    assert run(config, processes, desktop, "stop") == 0

    assert processes.spawned == []
    assert desktop.notifications == []


def test_a_background_job_keeps_the_start_time_it_was_launched_with(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    meeting_dir = meeting(config, "Crashed", minutes_ago=40)
    write_capture(meeting_dir.path)
    began = meeting_dir.load_meeting().started_at
    # As the parent writes it when launching this process.
    session.write(meeting_dir, Session(os.getpid(), "us", Phase.PROCESSING, began))
    seen: list[datetime] = []

    class CheckingTranscriber(FakeTranscriber):
        def transcribe(self, audio: Path) -> list[Segment]:
            current = session.read(meeting_dir)
            assert current is not None
            seen.append(current.started_at)
            return []

    run(
        config,
        processes,
        desktop,
        "transcribe",
        meeting_dir.id,
        "--background",
        transcriber=CheckingTranscriber(),
    )

    assert seen and set(seen) == {began}


# Calendar titles


class FakeCalendar:
    def __init__(self, *events: Event) -> None:
        self._events = list(events)

    def events(self, start: datetime, end: datetime) -> list[Event]:
        return self._events


def standup_now() -> Event:
    now = datetime.now().astimezone()
    attendees = (Attendee("Sam", is_me=True), Attendee("Alex Doe", is_me=False))
    return Event(
        "Standup", now - timedelta(minutes=3), now + timedelta(minutes=27), attendees=attendees
    )


def run_with_calendar(
    config: Config,
    processes: FakeProcesses,
    desktop: FakeDesktop,
    calendar: FakeCalendar,
    *argv: str,
) -> int:
    return main(
        list(argv),
        config=config,
        make_transcriber=lambda _: FakeTranscriber(),
        make_summarizer=lambda _: FakeSummarizer(),
        make_recorder=lambda _: FakeRecorder(),
        processes=processes,
        desktop=desktop,
        calendar=calendar,
    )


class RecordingDesktop(FakeDesktop):
    def __init__(self, answer: str | None) -> None:
        super().__init__(answer)
        self.defaults: list[str] = []

    def ask_text(self, prompt: str, default: str = "") -> str | None:
        self.defaults.append(default)
        return self.answer


def test_the_title_dialog_is_prefilled_from_the_calendar(config: Config, processes: FakeProcesses):
    desktop = RecordingDesktop(answer="Standup")

    run_with_calendar(
        config, processes, desktop, FakeCalendar(standup_now()), "start", "--ask-title"
    )

    assert desktop.defaults == ["Standup"]
    [meeting_dir] = MeetingStore(config.data_dir).all()
    assert meeting_dir.load_meeting().title == "Standup"
    assert meeting_dir.load_meeting().attendees == ("Alex Doe",)


def test_an_edited_title_keeps_the_calendar_attendees(config: Config, processes: FakeProcesses):
    desktop = RecordingDesktop(answer="Standup (ran long)")

    run_with_calendar(
        config, processes, desktop, FakeCalendar(standup_now()), "start", "--ask-title"
    )

    [meeting_dir] = MeetingStore(config.data_dir).all()
    assert meeting_dir.load_meeting().title == "Standup (ran long)"
    assert meeting_dir.load_meeting().attendees == ("Alex Doe",)


def test_with_nothing_on_the_calendar_the_dialog_starts_empty(
    config: Config, processes: FakeProcesses
):
    desktop = RecordingDesktop(answer="")

    run_with_calendar(config, processes, desktop, FakeCalendar(), "start", "--ask-title")

    assert desktop.defaults == [""]
    [meeting_dir] = MeetingStore(config.data_dir).all()
    assert meeting_dir.load_meeting().title == "Untitled"


def test_record_without_a_title_uses_the_calendar(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    run_with_calendar(config, processes, desktop, FakeCalendar(standup_now()), "record")

    [meeting_dir] = MeetingStore(config.data_dir).all()
    assert meeting_dir.load_meeting().title == "Standup"
    note = config.notes_dir / f"{meeting_dir.load_meeting().note_stem}.md"
    assert 'attendees: ["Alex Doe"]\n' in note.read_text()


def test_clearing_the_suggested_title_drops_the_calendar_attendees(
    config: Config, processes: FakeProcesses
):
    # A cleared title means it's not the calendar's meeting (an unplanned call).
    desktop = RecordingDesktop(answer="")

    run_with_calendar(
        config, processes, desktop, FakeCalendar(standup_now()), "start", "--ask-title"
    )

    [meeting_dir] = MeetingStore(config.data_dir).all()
    assert meeting_dir.load_meeting().title == "Untitled"
    assert meeting_dir.load_meeting().attendees == ()


def test_record_reads_the_calendar_before_taking_the_lock(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    lock_was_free: list[bool] = []

    class LockCheckingCalendar(FakeCalendar):
        def events(self, start: datetime, end: datetime) -> list[Event]:
            done = threading.Event()

            def take_lock() -> None:
                with session.lock(MeetingStore(config.data_dir)):
                    done.set()

            threading.Thread(target=take_lock, daemon=True).start()
            lock_was_free.append(done.wait(1))
            return []

    run_with_calendar(config, processes, desktop, LockCheckingCalendar(), "record")

    assert lock_was_free == [True]


def test_background_recording_limit_notifies_and_cleans_session(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    from dataclasses import replace

    from test_cli import WaitingRecorder

    config = replace(config, max_recording_seconds=0.05)
    meeting_dir = meeting(config)
    recorder = WaitingRecorder()
    transcriber = FakeTranscriber({"me": [Segment(0, 1, "Synthetic speech.")]})
    summarizer = FakeSummarizer()
    assert (
        main(
            ["record", "--meeting-id", meeting_dir.id, "--background"],
            config=config,
            make_recorder=lambda _: recorder,
            make_transcriber=lambda _: transcriber,
            make_summarizer=lambda _: summarizer,
            processes=processes,
            desktop=desktop,
        )
        == 0
    )
    assert recorder.stopped and len(transcriber.calls) == 2
    assert summarizer.transcripts
    assert session.read(meeting_dir) is None
    assert any("Recording time limit reached" in message for message in desktop.notifications)
    assert desktop.notifications[-1] == "The note for “Standup” is ready."


@pytest.mark.parametrize("failure", [KeyboardInterrupt, OSError])
@pytest.mark.parametrize("corrupt", [False, True])
def test_interrupted_recovery_keeps_capture_retryable(
    config: Config, desktop: FakeDesktop, failure: type[BaseException], corrupt: bool
):
    class Interrupted(FakeProcesses):
        attempts = 0

        def stop_capture(self, out_dir: Path) -> None:
            self.attempts += 1
            current = session.read(MeetingDir(out_dir))
            assert current is not None and current.phase == Phase.STOPPING
            if self.attempts == 1:
                raise failure("shutdown interrupted")

    processes = Interrupted()
    directory = meeting(config)
    write_capture(directory.path)
    orphaned(directory)
    if corrupt:
        session.session_file(directory).write_text('{"pid":')
    previous = session.read(directory)
    with pytest.raises(failure):
        run(config, processes, desktop, "stop")
    assert session.read(directory) == previous
    assert run(config, processes, desktop, "stop") == 0
    assert processes.attempts == 2
    assert processes.spawned == [["transcribe", directory.id, "--background"]]


def test_crashed_stopping_claim_retries_shutdown(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    directory = meeting(config)
    write_capture(directory.path)
    orphaned(directory, Phase.STOPPING)
    assert run(config, processes, desktop, "stop") == 0
    assert processes.stopped_captures == [directory.path]


def test_start_is_blocked_while_capture_is_stopping(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop
):
    directory = meeting(config)
    recording_by(processes, directory)
    current = session.read(directory)
    assert current is not None
    session.write(
        directory, Session(current.pid, current.process_started, Phase.STOPPING, current.started_at)
    )
    assert run(config, processes, desktop, "start", "--title", "Second") == 1
    assert not processes.spawned
    assert len(MeetingStore(config.data_dir).all()) == 1


@pytest.mark.parametrize("payload", [b'{"pid":', b"null", b"\xff"])
def test_corrupt_session_is_stable_and_recovered_before_new_recording(
    config: Config, desktop: FakeDesktop, payload: bytes
):
    directory = meeting(config)
    write_capture(directory.path)
    session.session_file(directory).write_bytes(payload)
    assert session.read(directory) == session.read(directory)

    class CheckedProcesses(FakeProcesses):
        def stop_capture(self, out_dir: Path) -> None:
            # A concurrent start must observe the recovery claim even for corrupt JSON.
            assert run(config, self, desktop, "start", "--title", "Concurrent") == 1
            super().stop_capture(out_dir)

        def spawn(self, args: list[str], log: Path) -> int:
            assert self.stopped_captures == [directory.path]
            return super().spawn(args, log)

    processes = CheckedProcesses()
    assert run(config, processes, desktop, "stop") == 0
    assert processes.stopped_captures == [directory.path]
    assert processes.spawned == [["transcribe", directory.id, "--background"]]
    assert run(config, processes, desktop, "start", "--title", "Next") == 0
    assert processes.spawned[-1][0] == "record"


@pytest.mark.parametrize("phase", [Phase.RECORDING, Phase.STOPPING])
@pytest.mark.parametrize("damage", ["missing", "invalid", "wrong_shape"])
@pytest.mark.parametrize("audio", [False, True])
def test_damaged_metadata_cannot_prevent_capture_shutdown(
    config: Config,
    processes: FakeProcesses,
    desktop: FakeDesktop,
    phase: Phase,
    damage: str,
    audio: bool,
):
    directory = meeting(config)
    orphaned(directory, phase)
    if audio:
        write_capture(directory.path)
    path = directory.path / "meeting.json"
    if damage == "missing":
        path.unlink()
    else:
        path.write_text("{" if damage == "invalid" else "null")
    assert run(config, processes, desktop, "stop") == 0
    assert processes.stopped_captures == [directory.path]
    if audio:
        assert processes.spawned == [["transcribe", directory.id, "--background"]]
    else:
        assert session.read(directory) is None
    assert directory.id in desktop.notifications[0]


@pytest.mark.parametrize("pause_at", ["shutdown", "handoff"])
def test_concurrent_stop_waits_for_recovery_and_starts_processing_once(
    config: Config, desktop: FakeDesktop, monkeypatch: pytest.MonkeyPatch, pause_at: str
):
    directory = meeting(config)
    write_capture(directory.path)
    orphaned(directory)
    paused, release, waiting = threading.Event(), threading.Event(), threading.Event()
    results: list[int] = []
    failures: list[BaseException] = []

    def pause() -> None:
        paused.set()
        assert release.wait(5), "recovery was not released"

    class Recovering(FakeProcesses):
        def stop_capture(self, out_dir: Path) -> None:
            super().stop_capture(out_dir)
            if pause_at == "shutdown":
                pause()

        def interrupt(self, pid: int) -> None:
            super().interrupt(pid)
            raise AssertionError("second Stop signalled the recovery owner")

    processes = Recovering()
    original_captures = MeetingDir.captures

    def captures(self: MeetingDir):
        if pause_at == "handoff" and self.path == directory.path:
            pause()
        return original_captures(self)

    original_wait = cli._Commands._wait_for_stop  # pyright: ignore[reportPrivateUsage]

    def wait(self: cli._Commands, active: session.Active) -> int:  # pyright: ignore[reportPrivateUsage]
        waiting.set()
        return original_wait(self, active)

    monkeypatch.setattr(MeetingDir, "captures", captures)
    monkeypatch.setattr(cli._Commands, "_wait_for_stop", wait)  # pyright: ignore[reportPrivateUsage]

    def stop() -> None:
        try:
            results.append(run(config, processes, desktop, "stop"))
        except BaseException as error:
            failures.append(error)

    first = threading.Thread(target=stop, daemon=True)
    second = threading.Thread(target=stop, daemon=True)
    first.start()
    try:
        assert paused.wait(5)
        second.start()
        assert waiting.wait(5), failures
        assert not session.stop_request_file(directory).exists()
        assert processes.spawned == []
    finally:
        release.set()
        first.join(5)
        if second.ident is not None:
            second.join(5)
    assert not first.is_alive() and not second.is_alive()
    assert failures == []
    assert results == [0, 0]
    assert processes.interrupted == []
    assert processes.stopped_captures == [directory.path]
    assert processes.spawned == [["transcribe", directory.id, "--background"]]
    current = session.read(directory)
    assert current is not None and current.phase == Phase.PROCESSING


@pytest.mark.parametrize("phase", [Phase.RECORDING, Phase.STOPPING])
@pytest.mark.parametrize("command", ["start", "stop", "stop_after_signal"])
def test_command_rechecks_orphan_when_competing_recovery_loses_its_claim(
    config: Config,
    processes: FakeProcesses,
    desktop: FakeDesktop,
    monkeypatch: pytest.MonkeyPatch,
    phase: Phase,
    command: str,
):
    directory = meeting(config)
    orphaned(directory, phase)
    orphan = session.read(directory)
    assert orphan is not None
    if command == "stop_after_signal":
        processes.running[orphan.pid] = orphan.process_started
        if phase == Phase.RECORDING:

            def exit_on_interrupt(pid: int) -> None:
                processes.running.pop(pid)

            processes.on_interrupt = exit_on_interrupt
        else:
            original_wait = cli._Commands._wait_for_stop  # pyright: ignore[reportPrivateUsage]

            def owner_dies(self: cli._Commands, active: session.Active) -> int:  # pyright: ignore[reportPrivateUsage]
                processes.running.pop(orphan.pid)
                return original_wait(self, active)

            monkeypatch.setattr(cli._Commands, "_wait_for_stop", owner_dies)  # pyright: ignore[reportPrivateUsage]
    original_recover = cli._Commands._recover  # pyright: ignore[reportPrivateUsage]

    def recover(self: cli._Commands, active: session.Active) -> None:  # pyright: ignore[reportPrivateUsage]
        # Another command claims the snapshot before this Start can claim it.
        claim = Session(8000, "competitor", Phase.STOPPING, orphan.started_at)
        processes.running[8000] = "competitor"
        with session.lock(MeetingStore(config.data_dir)):
            session.write(directory, claim)
        original_recover(self, active)
        assert session.read(directory) == claim
        # The competing command fails before Start's final creation lock.
        with session.lock(MeetingStore(config.data_dir)):
            processes.running.pop(8000)
            session.write(directory, orphan)

    monkeypatch.setattr(cli._Commands, "_recover", recover)  # pyright: ignore[reportPrivateUsage]
    args = ["start", "--title", "Next"] if command == "start" else ["stop"]
    assert run(config, processes, desktop, *args) == 1
    assert session.read(directory) == orphan
    assert processes.spawned == []
    assert processes.stopped_captures == []
    assert len(MeetingStore(config.data_dir).all()) == 1
    assert "Run `notes stop`" in desktop.notifications[-1]


@pytest.mark.parametrize("phase", [Phase.RECORDING, Phase.STOPPING])
def test_foreground_record_does_not_bypass_unrecovered_capture(
    config: Config, processes: FakeProcesses, desktop: FakeDesktop, phase: Phase
):
    directory = meeting(config)
    orphaned(directory, phase)
    before = session.read(directory)
    assert run(config, processes, desktop, "record", "--title", "Next") == 1
    assert session.read(directory) == before
    assert len(MeetingStore(config.data_dir).all()) == 1


def test_repeated_stop_waits_through_foreground_processing_handoff(
    config: Config, desktop: FakeDesktop, monkeypatch: pytest.MonkeyPatch
):
    recording, handoff, release = threading.Event(), threading.Event(), threading.Event()
    results: list[int] = []
    failures: list[BaseException] = []
    owner_thread = threading.current_thread()
    owner_pid = os.getpid()
    processes = FakeProcesses()
    processes.running[owner_pid + 10000] = "stop commands"
    # Model separate CLI processes without sending signals to unrelated real PIDs.
    monkeypatch.setattr(
        os,
        "getpid",
        lambda: owner_pid if threading.current_thread() is owner_thread else owner_pid + 10000,
    )

    class Recorder:
        def record(self, directory: Path, stop: threading.Event) -> None:
            write_capture(directory)
            recording.set()
            assert stop.wait(5)

    def interrupt(pid: int) -> None:
        assert pid == owner_pid
        handler = signal.getsignal(signal.SIGINT)
        assert callable(handler)
        handler(signal.SIGINT, None)

    processes.on_interrupt = interrupt
    original_session = cli._Commands._session  # pyright: ignore[reportPrivateUsage]

    def next_session(self: cli._Commands, directory: MeetingDir, phase: Phase) -> Session:  # pyright: ignore[reportPrivateUsage]
        if phase == Phase.PROCESSING:
            assert signal.getsignal(signal.SIGINT) == signal.default_int_handler
            handoff.set()
            assert release.wait(5), failures
        return original_session(self, directory, phase)

    original_wait = cli._Commands._wait_for_stop  # pyright: ignore[reportPrivateUsage]

    def wait(self: cli._Commands, active: session.Active) -> int:  # pyright: ignore[reportPrivateUsage]
        if threading.current_thread().name == "second-stop":
            release.set()
        return original_wait(self, active)

    monkeypatch.setattr(cli._Commands, "_session", next_session)  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(cli._Commands, "_wait_for_stop", wait)  # pyright: ignore[reportPrivateUsage]

    def stop(ready: threading.Event) -> None:
        try:
            assert ready.wait(5)
            results.append(run(config, processes, desktop, "stop"))
        except BaseException as error:
            failures.append(error)
            release.set()

    first = threading.Thread(target=stop, args=(recording,), daemon=True)
    second = threading.Thread(target=stop, args=(handoff,), name="second-stop", daemon=True)
    transcriber = FakeTranscriber({"me": [Segment(0, 1, "Synthetic speech.")]})
    summarizer = FakeSummarizer()
    first.start()
    second.start()
    try:
        assert (
            main(
                ["record", "--title", "Synthetic"],
                config=config,
                processes=processes,
                desktop=desktop,
                make_recorder=lambda _: Recorder(),
                make_transcriber=lambda _: transcriber,
                make_summarizer=lambda _: summarizer,
            )
            == 0
        )
    finally:
        release.set()
        first.join(5)
        second.join(5)
    assert not first.is_alive() and not second.is_alive()
    assert failures == []
    assert results == [0, 0]
    assert processes.interrupted == [owner_pid]
    assert len(transcriber.calls) == 2 and len(summarizer.transcripts) == 1
    assert not session.find(MeetingStore(config.data_dir), processes)


@pytest.mark.parametrize("shutdown_fails", [False, True])
def test_stop_retains_wait_target_when_competing_owner_dies_after_liveness_check(
    config: Config, desktop: FakeDesktop, monkeypatch: pytest.MonkeyPatch, shutdown_fails: bool
):
    directory = meeting(config)
    write_capture(directory.path)
    orphaned(directory)
    initial = session.read(directory)
    assert initial is not None
    claim = Session(8000, "competitor", Phase.STOPPING, initial.started_at)

    class DyingOwner(FakeProcesses):
        def started(self, pid: int) -> str | None:
            started = super().started(pid)
            if pid == claim.pid and started is not None:
                # Return the live observation, but die before any subsequent query.
                self.running.pop(pid)
            return started

        def stop_capture(self, out_dir: Path) -> None:
            super().stop_capture(out_dir)
            if shutdown_fails:
                raise OSError("synthetic shutdown failure")

    processes = DyingOwner()
    original_recover = cli._Commands._recover  # pyright: ignore[reportPrivateUsage]
    claim_taken = False

    def recover(self: cli._Commands, active: session.Active) -> None:  # pyright: ignore[reportPrivateUsage]
        nonlocal claim_taken
        if not claim_taken:
            claim_taken = True
            with session.lock(MeetingStore(config.data_dir)):
                processes.running[claim.pid] = claim.process_started
                session.write(directory, claim)
        original_recover(self, active)

    monkeypatch.setattr(cli._Commands, "_recover", recover)  # pyright: ignore[reportPrivateUsage]
    if shutdown_fails:
        with pytest.raises(OSError, match="synthetic shutdown failure"):
            run(config, processes, desktop, "stop")
        assert session.read(directory) == claim
        assert processes.spawned == []
    else:
        assert run(config, processes, desktop, "stop") == 0
        assert processes.spawned == [["transcribe", directory.id, "--background"]]
        current = session.read(directory)
        assert current is not None and current.phase == Phase.PROCESSING
    assert processes.stopped_captures == [directory.path]
    assert processes.interrupted == []
