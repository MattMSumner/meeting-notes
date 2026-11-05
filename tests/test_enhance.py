"""Explicit enhancement uses frozen evidence and never edits original writing."""

import json
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest
from test_cli import SUMMARY, FakeRecorder, FakeSummarizer, FakeTranscriber, write_capture
from test_start_stop import FakeDesktop, FakeProcesses

from meeting_notes import pipeline, session
from meeting_notes.cli import main
from meeting_notes.config import Config
from meeting_notes.evidence import Generation, snapshot
from meeting_notes.figures import evidence_issues
from meeting_notes.macos import DesktopError
from meeting_notes.meeting import Meeting
from meeting_notes.session import Phase, Session
from meeting_notes.store import MeetingDir, MeetingStore
from meeting_notes.summary import Conflict, Summary, SummaryError
from meeting_notes.transcript import Segment


class Desktop(FakeDesktop):
    def __init__(self) -> None:
        super().__init__(None)
        self.choices: list[tuple[str, str]] = []
        self.opened: list[Path] = []
        self.on_choose: Callable[[], None] = lambda: None
        self.fail_open = False

    def choose_meeting(self, choices: list[tuple[str, str]]) -> str | None:
        self.choices = choices
        self.on_choose()
        return self.answer

    def open_note(self, path: Path) -> None:
        if self.fail_open:
            raise DesktopError("unavailable")
        self.opened.append(path)


class Harness:
    def __init__(self, root: Path) -> None:
        self.config = Config(
            data_dir=root / "data", notes_dir=root / "vault", model="fake", my_name="Sam"
        )
        self.processes = FakeProcesses()
        self.desktop = Desktop()
        self.summarizer = FakeSummarizer()
        self.factories = 0
        self.transcriber = FakeTranscriber({"me": [Segment(0, 1, "Ship Friday for 120 dollars.")]})

    def make_summary(self, config: Config) -> FakeSummarizer:
        self.factories += 1
        return self.summarizer

    def run(self, *args: str) -> int:
        return main(
            args,
            config=self.config,
            processes=self.processes,
            desktop=self.desktop,
            make_summarizer=self.make_summary,
            make_transcriber=lambda _: self.transcriber,
            make_recorder=lambda _: FakeRecorder(),
        )

    def ready(self, minute: int = 0) -> MeetingDir:
        directory = MeetingStore(self.config.data_dir).create(
            Meeting.new("Synthetic", datetime(2026, 10, 20, 12, minute).astimezone())
        )
        write_capture(directory.path)
        pipeline.transcribe(directory, self.transcriber)
        return directory


@pytest.fixture
def h(tmp_path: Path) -> Harness:
    return Harness(tmp_path)


def test_record_recovery_and_retranscribe_never_construct_a_summarizer(h: Harness):
    assert h.run("record") == 0
    directory = MeetingStore(h.config.data_dir).all()[0]
    assert h.run("transcribe", directory.id, "--background") == 0
    assert h.factories == 0
    assert not directory.summary_file.exists()
    assert (
        "Ready to enhance"
        in (h.config.notes_dir / f"{directory.load_meeting().note_stem}.md").read_text()
    )


@pytest.mark.parametrize("command", ["enhance", "summarize"])
def test_snapshots_survive_edits_during_inference_and_deletion(h: Harness, command: str):
    directory = h.ready()
    path = h.config.notes_dir / "writing.md"
    path.parent.mkdir()
    original = b"Personal context: 456 dollars.\r\nKeep this.\r\n"
    path.write_bytes(original)
    directory.save_handwritten_path(path)

    class Editing(FakeSummarizer):
        def summarize(
            self, meeting: Meeting, transcript: str, *, handwritten_text: str = ""
        ) -> Summary:
            path.write_text("Later edits")
            return SUMMARY.model_copy(update={"notes_context": ["Personal context: 456 dollars."]})

    h.summarizer = Editing()
    assert h.run(command, directory.id) == 0
    saved = directory.load_generation()
    assert isinstance(saved, Generation)
    assert saved.evidence.handwritten_original.encode() == original
    assert saved.evidence.handwritten_text.encode() == original
    assert "Sam:" in saved.evidence.transcript
    assert saved.evidence.context.startswith("Meeting: Synthetic")
    path.unlink()
    before = directory.summary_file.read_bytes()
    assert h.run("render", directory.id) == 0
    assert directory.summary_file.read_bytes() == before
    note = (h.config.notes_dir / f"{directory.load_meeting().note_stem}.md").read_text()
    assert "## From your notes" in note and "Check number" not in note
    assert h.run("enhance", directory.id) == 1
    assert directory.summary_file.read_bytes() == before


@pytest.mark.parametrize("content", [b"", b" \r\n", None])
def test_empty_or_untouched_template_notes_have_empty_effective_input(
    h: Harness, content: bytes | None
):
    directory = h.ready()
    meeting = directory.load_meeting()
    path = h.config.notes_dir / "writing.md"
    path.parent.mkdir()
    if content is None:
        content = (
            f"# {meeting.title}\r\n\r\nAvailable after processing: "
            f"[[{meeting.note_stem}|Summary]] · [[{meeting.transcript_stem}|Transcript]]\r\n\r\n"
        ).encode()
    path.write_bytes(content)
    directory.save_handwritten_path(path)
    assert h.run("enhance", directory.id) == 0
    assert h.summarizer.notes == [""]
    assert path.read_bytes() == content


def test_removes_only_exact_generated_lines(h: Harness):
    directory = h.ready()
    path = directory.path / "writing.md"
    original = "# Changed title\r\nAvailable after processing: my link\r\n# Synthetic\r\nText\r\n"
    path.write_bytes(original.encode())
    directory.save_handwritten_path(path)
    evidence = snapshot(directory.load_meeting(), "spoken")
    assert evidence.handwritten_original == original
    assert evidence.handwritten_text == original.replace("# Synthetic\r\n", "")


@pytest.mark.parametrize("mode", ["missing", "invalid", "unreadable"])
def test_bad_handwritten_file_fails_before_inference(
    h: Harness, mode: str, monkeypatch: pytest.MonkeyPatch
):
    directory = h.ready()
    path = directory.path / "writing.md"
    directory.save_handwritten_path(path)
    if mode == "invalid":
        path.write_bytes(b"\xff")
    if mode == "unreadable":
        original = Path.read_bytes

        def read(self: Path) -> bytes:
            if self == path:
                raise PermissionError("synthetic denial")
            return original(self)

        monkeypatch.setattr(Path, "read_bytes", read)
    assert h.run("enhance", directory.id) == 1
    assert h.summarizer.transcripts == []
    assert not directory.summary_file.exists()


def test_failed_generation_and_atomic_replace_preserve_previous_result(
    h: Harness, monkeypatch: pytest.MonkeyPatch
):
    directory = h.ready()
    assert h.run("enhance", directory.id) == 0
    before = directory.summary_file.read_bytes()
    h.summarizer = FakeSummarizer("down")
    assert h.run("enhance", directory.id) == 1
    assert directory.summary_file.read_bytes() == before
    h.summarizer = FakeSummarizer()
    replace = Path.replace

    def fail(self: Path, target: str | Path) -> Path:
        if self.name == ".summary.tmp":
            raise OSError("synthetic disk failure")
        return replace(self, target)

    monkeypatch.setattr(Path, "replace", fail)
    assert h.run("enhance", directory.id) == 1
    assert directory.summary_file.read_bytes() == before
    assert not (directory.path / ".summary.tmp").exists()


def test_reenhancement_refreshes_snapshot_and_transcribe_clears_it(h: Harness):
    directory = h.ready()
    path = directory.path / "writing.md"
    path.write_bytes(b"First\r\n")
    directory.save_handwritten_path(path)
    assert h.run("enhance", directory.id) == 0
    path.write_bytes(b"Second\r\n")
    assert h.run("enhance", directory.id) == 0
    saved = directory.load_generation()
    assert isinstance(saved, Generation) and saved.evidence.handwritten_original == "Second\r\n"
    note = h.config.notes_dir / f"{directory.load_meeting().note_stem}.md"
    note.write_text("User edited summary")
    h.factories = 0
    assert h.run("transcribe", directory.id) == 0
    assert h.factories == 0 and directory.load_generation() is None
    assert note.read_text() == "User edited summary"
    assert path.read_bytes() == b"Second\r\n"


@pytest.mark.parametrize(
    "data",
    [
        {"version": 2, "summary": {}},
        {"evidence": {}},
        {"version": 1, "summary": SUMMARY.model_dump()},
    ],
)
def test_malformed_wrapper_cannot_fall_back_to_live_inputs(h: Harness, data: dict[str, object]):
    directory = h.ready()
    directory.summary_file.write_text(json.dumps(data))
    with pytest.raises(SummaryError):
        directory.load_generation()
    assert h.run("render", directory.id) == 0
    assert (
        "couldn't be read"
        in (h.config.notes_dir / f"{directory.load_meeting().note_stem}.md").read_text()
    )


def test_legacy_summary_renders_without_handwritten_file(h: Harness):
    directory = h.ready()
    directory.save_summary(SUMMARY)
    directory.save_handwritten_path(directory.path / "missing.md")
    assert h.run("render", directory.id) == 0
    assert directory.load_summary() == SUMMARY


def test_chooser_orders_ready_meetings_and_cancel_does_nothing(h: Harness):
    older, newer = h.ready(), h.ready(1)
    newer.save_summary(SUMMARY)
    incomplete = h.ready(2)
    incomplete.segments_file("them").unlink()
    active = h.ready(3)
    session.write(active, Session(9999, "gone", Phase.PROCESSING, datetime.now().astimezone()))
    silent = h.ready(4)
    silent.save_segments("me", [])
    before = sorted(str(p) for p in h.config.data_dir.rglob("*"))
    assert h.run("enhance", "--choose") == 0
    assert [identifier for identifier, _ in h.desktop.choices] == [newer.id, older.id]
    assert h.processes.spawned == []
    assert sorted(str(p) for p in h.config.data_dir.rglob("*")) == before
    assert h.factories == 0


def test_chooser_empty_and_revalidates_after_dialog(h: Harness):
    assert h.run("enhance", "--choose") == 0
    assert "No meetings are ready" in h.desktop.notifications[0]
    directory = h.ready()
    h.desktop.answer = directory.id
    h.desktop.on_choose = lambda: directory.segments_file("me").unlink()
    assert h.run("enhance", "--choose") == 1
    assert h.processes.spawned == []


def test_chooser_claims_detached_job_without_snapshot(h: Harness):
    directory = h.ready()
    h.desktop.answer = directory.id
    assert h.run("enhance", "--choose") == 0
    assert h.processes.spawned == [["enhance", directory.id, "--background"]]
    current = session.read(directory)
    assert current and current.phase == Phase.ENHANCING
    assert not directory.summary_file.exists()
    assert h.factories == 0


@pytest.mark.parametrize("command", ["enhance", "transcribe", "render"])
def test_processing_lock_rejects_concurrent_commands(h: Harness, command: str):
    directory = h.ready()
    with session.processing_lock(directory):
        assert h.run(command, directory.id) == 1
    assert h.factories == 0


def test_enhancement_crash_reports_explicit_retry_without_transcribing(h: Harness):
    directory = h.ready()
    session.write(directory, Session(9999, "gone", Phase.ENHANCING, datetime.now().astimezone()))
    assert h.run("stop") == 0
    assert h.processes.spawned == [] and h.processes.stopped_captures == []
    assert f"notes enhance {directory.id}" in h.desktop.notifications[0]
    assert h.factories == 0
    assert h.run("enhance", directory.id) == 0


@pytest.mark.parametrize("protected,fail_open", [(False, False), (True, False), (False, True)])
def test_spotlight_completion_opens_only_new_published_summary(
    h: Harness, protected: bool, fail_open: bool
):
    directory = h.ready()
    note = h.config.notes_dir / f"{directory.load_meeting().note_stem}.md"
    if protected:
        note.parent.mkdir()
        note.write_text("Edited")
    h.desktop.fail_open = fail_open
    session.write(
        directory, Session(os.getpid(), "us", Phase.ENHANCING, datetime.now().astimezone())
    )
    assert h.run("enhance", directory.id, "--background") == 0
    assert directory.load_summary() == SUMMARY
    assert session.read(directory) is None
    assert h.desktop.opened == ([] if protected or fail_open else [note])
    if protected:
        assert note.read_text() == "Edited"
        assert "saved internally" in h.desktop.notifications[0]
    if fail_open:
        assert "couldn't open" in h.desktop.notifications[-1]


def test_no_speech_refuses_enhancement_without_summarizer(h: Harness):
    directory = h.ready()
    directory.save_segments("me", [])
    assert h.run("enhance", directory.id) == 1
    assert h.factories == 0


def test_source_specific_number_checks_cover_conflicts_and_metadata():
    summary = Summary(
        overview="Budget 500",
        key_points=["In 2026"],
        decisions=[],
        action_items=[],
        notes_context=["Budget 120", "Unknown 777"],
        conflicts=[Conflict(topic="Budget", transcript="500", handwritten="120")],
    )
    issues = evidence_issues(summary, "120", "500", "2026")
    assert len(issues) == 6
    assert sum("only in the other source" in issue for issue in issues) == 4
    assert sum("only in meeting metadata" in issue for issue in issues) == 1
    assert sum("neither source" in issue for issue in issues) == 1


def test_global_lock_is_free_during_dialog_and_inference(h: Harness):
    import fcntl

    directory = h.ready()
    lock = h.config.data_dir / ".lock"

    def assert_free() -> None:
        with lock.open("a") as file:
            fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(file, fcntl.LOCK_UN)

    h.desktop.on_choose = assert_free
    assert h.run("enhance", "--choose") == 0

    class Checking(FakeSummarizer):
        def summarize(
            self, meeting: Meeting, transcript: str, *, handwritten_text: str = ""
        ) -> Summary:
            assert_free()
            return SUMMARY

    h.summarizer = Checking()
    assert h.run("enhance", directory.id) == 0


def test_notification_failure_does_not_discard_success(h: Harness):
    directory = h.ready()

    class BrokenDesktop(Desktop):
        def notify(self, message: str) -> None:
            raise DesktopError("notification unavailable")

    h.desktop = BrokenDesktop()
    assert h.run("enhance", directory.id, "--background") == 0
    assert directory.load_summary() == SUMMARY
    assert len(h.desktop.opened) == 1


def test_explicit_retry_of_crashed_enhancement_does_not_transcribe(h: Harness):
    directory = h.ready()
    session.write(directory, Session(9999, "gone", Phase.ENHANCING, datetime.now().astimezone()))
    h.transcriber.calls.clear()
    assert h.run("enhance", directory.id) == 0
    assert h.transcriber.calls == []


def test_conflicts_render_both_accounts_and_empty_sections_are_omitted(h: Harness):
    directory = h.ready()
    directory.save_summary(
        SUMMARY.model_copy(
            update={
                "conflicts": [Conflict(topic="Timing", transcript="June", handwritten="July")],
                "notes_context": ["Check access"],
            }
        )
    )
    assert h.run("render", directory.id) == 0
    path = h.config.notes_dir / f"{directory.load_meeting().note_stem}.md"
    body = path.read_text()
    assert "## From your notes" in body and "## Conflicts" in body
    assert "Transcript: June Handwritten notes: July" in body
    directory.save_summary(SUMMARY)
    assert h.run("render", directory.id) == 0
    assert "## Conflicts" not in path.read_text()
    assert "## From your notes" not in path.read_text()


@pytest.mark.parametrize("freeze", ["v1", "v2", "v3"])
def test_frozen_evaluation_materials_match_manifest_without_inference(freeze: str):
    import hashlib

    root = Path(__file__).resolve().parents[1] / "evaluation" / "m10"
    if freeze != "v1":
        root /= freeze
    manifest: dict[str, str] = json.loads((root / "sha256.json").read_text())
    for name, expected in manifest.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
    pairs: list[dict[str, object]] = json.loads((root / "pairs.json").read_text())
    assert {pair["id"] for pair in pairs[:5]} == {
        "empty",
        "sparse",
        "additional",
        "conflicting",
        "ambiguous_dates",
    }


def test_full_deadline_and_dispute_qualification_survive_saved_render(h: Harness):
    from legacy_ollama import OllamaSummarizer
    from test_ollama import FakeOllama

    directory = h.ready()
    directory.save_segments(
        "me",
        [
            Segment(
                0,
                5,
                "The estimate is 80 thousand. I will verify it Tuesday, "
                "or Thursday if approval slips.",
            )
        ],
    )
    path = directory.path / "writing.md"
    path.write_text("Estimate: 95 thousand.\n")
    directory.save_handwritten_path(path)
    from meeting_notes.grounding import Claim, Dispute, Draft, Span, Task

    spoken = Span(passage="T1", quote="The estimate is 80 thousand.")
    written = Span(passage="N1", quote="Estimate: 95 thousand.")
    commitment = Span(
        passage="T2", quote="I will verify it Tuesday, or Thursday if approval slips."
    )
    reply = Draft(
        claims=[
            Claim(id="spoken", text="Estimate 80 thousand", evidence=[spoken]),
            Claim(id="written", text="Estimate 95 thousand", evidence=[written]),
            Claim(id="task", text="Verify it", evidence=[commitment]),
        ],
        overview=["spoken"],
        key_points=["spoken"],
        decisions=[],
        notes_context=["written"],
        action_items=[
            Task(
                claim="task",
                owner="Sam",
                owner_evidence=None,
                commitment=commitment,
                timing=Span(passage="T2", quote="Tuesday, or Thursday if approval slips"),
                timing_link=[],
            )
        ],
        conflicts=[Dispute(topic="Estimate", transcript_claim="spoken", notes_claim="written")],
    )
    api = FakeOllama(reply.model_dump_json())
    model = OllamaSummarizer("qwen3:30b", 32768, api, "Sam")
    pipeline.summarize(directory, pipeline.conversation(directory), model, "Sam")
    path.unlink()
    assert h.run("render", directory.id) == 0
    saved = directory.load_summary()
    assert saved is not None
    assert saved.action_items[0].due == "Tuesday, or Thursday if approval slips"
    body = (h.config.notes_dir / f"{directory.load_meeting().note_stem}.md").read_text()
    assert "(due Tuesday, or Thursday if approval slips)" in body
    core, conflict = body.split("## Conflicts")
    assert "80 thousand" not in core and "95 thousand" not in core
    assert (
        "Transcript: The estimate is 80 thousand. Handwritten notes: Estimate: 95 thousand."
        in conflict
    )
    assert "Check number" not in body
    assert len(api.requests) == 1


def test_failed_grounding_saves_diagnostics_and_preserves_previous_result(h: Harness):
    from legacy_ollama import OllamaSummarizer
    from test_ollama import FakeOllama, reply

    directory = h.ready()
    directory.save_summary(SUMMARY)
    before = directory.summary_file.read_bytes()
    model = OllamaSummarizer(
        "fake", 32768, FakeOllama(reply(quote="absent"), reply(passage="absent")), "Sam"
    )
    with pytest.raises(SummaryError, match="evidence validation"):
        pipeline.summarize(directory, pipeline.conversation(directory), model, "Sam")
    assert directory.summary_file.read_bytes() == before
    [attempt] = list((directory.path / "attempts").glob("*.json"))
    data = json.loads(attempt.read_text())
    assert data["audit"]["selected"] is None
    assert len(data["audit"]["attempts"]) == 2
    assert data["evidence"]["transcript"].startswith("[00:00:00] Sam:")
    assert all(a["blocking"] and a["reply"] for a in data["audit"]["attempts"])


def test_audited_warnings_survive_render_and_source_deletion(h: Harness):
    from legacy_ollama import OllamaSummarizer
    from test_ollama import FakeOllama, reply

    directory = h.ready()
    bad_number = reply("Cost 777 dollars", "Ship Friday for 120 dollars.")
    model = OllamaSummarizer("fake", 32768, FakeOllama(bad_number, "not json"), "Sam")
    pipeline.summarize(directory, pipeline.conversation(directory), model, "Sam")
    saved = directory.load_generation()
    assert isinstance(saved, Generation) and saved.version == 2 and saved.audit is not None
    assert saved.audit.selected == 0
    assert h.run("render", directory.id) == 0
    note = h.config.notes_dir / f"{directory.load_meeting().note_stem}.md"
    assert "numbers absent from cited evidence: 777" in note.read_text()
    # The selected draft cannot be swapped for a different stored summary.
    data = json.loads(directory.summary_file.read_text())
    data["summary"]["overview"] = "Silently changed"
    directory.summary_file.write_text(json.dumps(data))
    with pytest.raises(SummaryError, match="does not match"):
        directory.load_generation()


@pytest.mark.parametrize("change", ["missing", "index", "passages", "blocked"])
def test_malformed_v2_audit_never_falls_back_to_live_inputs(h: Harness, change: str):
    from legacy_ollama import OllamaSummarizer
    from test_ollama import FakeOllama, reply

    directory = h.ready()
    model = OllamaSummarizer(
        "fake", 32768, FakeOllama(reply("Spoken commitment", "Ship Friday for 120 dollars.")), "Sam"
    )
    pipeline.summarize(directory, pipeline.conversation(directory), model, "Sam")
    data = json.loads(directory.summary_file.read_text())
    if change == "missing":
        del data["audit"]
    elif change == "index":
        data["audit"]["selected"] = -1
    elif change == "passages":
        data["audit"]["passages"][0]["text"] = "changed"
    else:
        data["audit"]["attempts"][0]["blocking"] = ["unresolved error"]
    directory.summary_file.write_text(json.dumps(data))
    with pytest.raises(SummaryError):
        directory.load_generation()


def test_failed_audit_save_prevents_publication_and_preserves_old_generation(
    h: Harness,
    monkeypatch: pytest.MonkeyPatch,
):
    from legacy_ollama import OllamaSummarizer
    from test_ollama import FakeOllama, reply

    directory = h.ready()
    directory.save_summary(SUMMARY)
    before = directory.summary_file.read_bytes()
    original = Path.replace

    def fail(self: Path, target: str | Path) -> Path:
        if self.parent.name == "attempts":
            raise OSError("synthetic audit save failure")
        return original(self, target)

    monkeypatch.setattr(Path, "replace", fail)
    model = OllamaSummarizer(
        "fake", 32768, FakeOllama(reply("Spoken", "Ship Friday for 120 dollars.")), "Sam"
    )
    with pytest.raises(OSError, match="audit save failure"):
        pipeline.summarize(directory, pipeline.conversation(directory), model, "Sam")
    assert directory.summary_file.read_bytes() == before
    assert list((directory.path / "attempts").iterdir()) == []


def test_current_generation_is_saved_with_v3_and_survives_source_deletion(h: Harness):
    from test_ollama import FakeOllama

    from meeting_notes.contract import Draft, SupportedText
    from meeting_notes.ollama import OllamaSummarizer

    directory = h.ready()
    original = directory.path / "synthetic-notes.md"
    original.write_bytes(b"Synthetic context.\r\n")
    directory.save_handwritten_path(original)
    value = Draft(
        overview=[SupportedText(text="Spoken context.", sources=["T1"])],
        key_points=[],
        decisions=[],
        action_items=[],
        notes_context=[],
        conflicts=[],
    )
    model = OllamaSummarizer("fake", 32768, FakeOllama(value.model_dump_json()), "Sam")
    pipeline.summarize(directory, pipeline.conversation(directory), model, "Sam")
    saved = directory.load_generation()
    assert isinstance(saved, Generation) and saved.version == 3
    path = directory.load_meeting().handwritten_path
    assert path is not None
    path.unlink()
    assert h.run("render", directory.id) == 0
    assert directory.load_generation() == saved
