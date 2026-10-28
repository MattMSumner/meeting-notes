import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from meeting_notes.meeting import Meeting
from meeting_notes.store import ChannelCapture, MeetingDir, MeetingNotFound, MeetingStore
from meeting_notes.summary import Detail, Summary, SummaryError
from meeting_notes.transcript import Segment

STARTED = datetime(2026, 10, 20, 14, 5, tzinfo=timezone(timedelta(hours=-4)))


def test_round_trips_a_meeting(tmp_path: Path):
    store = MeetingStore(tmp_path)
    meeting = Meeting.new("Weekly Sync", STARTED)

    created = store.create(meeting)

    assert created.path == tmp_path / "2026-10-20-1405-weekly-sync"
    assert store.get(created.id).load_meeting() == meeting


def test_round_trips_segments_per_channel(tmp_path: Path):
    meeting_dir = MeetingStore(tmp_path).create(Meeting.new("Sync", STARTED))
    segments = [Segment(0.0, 1.5, "Hello."), Segment(2.0, 3.25, "Shall we start?")]

    meeting_dir.save_segments("me", segments)

    assert meeting_dir.load_segments("me") == segments
    assert meeting_dir.segments_file("me").name == "segments.me.json"


def test_audio_path_per_channel(tmp_path: Path):
    meeting_dir = MeetingStore(tmp_path).create(Meeting.new("Sync", STARTED))

    assert meeting_dir.audio("me") == meeting_dir.path / "me.wav"


def test_a_second_meeting_with_the_same_title_in_the_same_minute_gets_a_number(tmp_path: Path):
    store = MeetingStore(tmp_path)
    first = store.create(Meeting.new("Untitled", STARTED))

    second = store.create(Meeting.new("Untitled", STARTED))
    third = store.create(Meeting.new("Untitled", STARTED))

    assert first.load_meeting().title == "Untitled"
    assert second.load_meeting().title == "Untitled 2"
    assert third.load_meeting().title == "Untitled 3"
    # So their notes don't overwrite each other in the vault either.
    assert len({m.load_meeting().note_stem for m in (first, second, third)}) == 3


def test_unknown_meeting_id(tmp_path: Path):
    with pytest.raises(MeetingNotFound):
        MeetingStore(tmp_path).get("2026-10-20-1405-nope")


def test_reads_channel_captures_from_capture_json(tmp_path: Path):
    meeting_dir = MeetingStore(tmp_path).create(Meeting.new("Sync", STARTED))
    manifest = {
        "started_at": "2026-10-20T18:05:00Z",
        "sample_rate": 16000,
        "channels": {
            "me": {
                "file": "me.wav",
                "offset_seconds": 0.002,
                "duration_seconds": 30,
                "all_zero": False,
            },
            "them": {
                "file": "them.wav",
                "offset_seconds": 0.027,
                "duration_seconds": 30,
                "all_zero": True,
            },
        },
    }
    (meeting_dir.path / "capture.json").write_text(json.dumps(manifest))

    captures = meeting_dir.captures()

    assert captures == {
        "me": ChannelCapture(offset=0.002, all_zero=False),
        "them": ChannelCapture(offset=0.027, all_zero=True),
    }
    assert captures["me"].has_audio
    assert not captures["them"].has_audio


def test_channel_without_audio_has_no_offset(tmp_path: Path):
    meeting_dir = MeetingStore(tmp_path).create(Meeting.new("Sync", STARTED))
    (meeting_dir.path / "capture.json").write_text(
        '{"channels": {"them": {"file": "them.wav", "duration_seconds": 0, "all_zero": false}}}'
    )

    assert meeting_dir.captures() == {"them": ChannelCapture(offset=None, all_zero=False)}
    assert not meeting_dir.captures()["them"].has_audio


def test_meetings_recorded_before_notes_capture_are_mic_only(tmp_path: Path):
    meeting_dir = MeetingStore(tmp_path).create(Meeting.new("Sync", STARTED))
    assert meeting_dir.captures() == {}

    meeting_dir.audio("me").write_bytes(b"audio")

    assert meeting_dir.captures() == {"me": ChannelCapture(offset=0.0, all_zero=False)}


def test_recording_that_crashed_before_capture_json_keeps_both_channels(tmp_path: Path):
    meeting_dir = MeetingStore(tmp_path).create(Meeting.new("Sync", STARTED))
    meeting_dir.audio("me").write_bytes(b"audio")
    meeting_dir.audio("them").write_bytes(b"audio")

    assert not meeting_dir.has_manifest
    assert meeting_dir.captures() == {
        "me": ChannelCapture(offset=0.0, all_zero=False),
        "them": ChannelCapture(offset=0.0, all_zero=False),
    }


def test_write_unless_edited_overwrites_its_own_output(tmp_path: Path):
    meeting_dir = MeetingDir(tmp_path / "meeting")
    meeting_dir.path.mkdir()
    note = tmp_path / "vault" / "note.md"

    assert meeting_dir.write_unless_edited({note: "first"}) == []
    assert meeting_dir.write_unless_edited({note: "second"}) == []
    assert note.read_text() == "second"


def test_write_unless_edited_keeps_edits_made_in_the_vault(tmp_path: Path):
    meeting_dir = MeetingDir(tmp_path / "meeting")
    meeting_dir.path.mkdir()
    note = tmp_path / "vault" / "note.md"
    transcript = tmp_path / "vault" / "transcripts" / "note.md"  # same name, other folder
    meeting_dir.write_unless_edited({note: "generated", transcript: "generated"})
    note.write_text("generated, then edited")

    skipped = meeting_dir.write_unless_edited({note: "regenerated", transcript: "regenerated"})

    assert skipped == [note]
    assert note.read_text() == "generated, then edited"
    assert transcript.read_text() == "regenerated"
    # Once moved away, it's written again.
    note.unlink()
    assert meeting_dir.write_unless_edited({note: "regenerated"}) == []


def test_an_unreadable_summary_is_a_summary_error(tmp_path: Path):
    meeting_dir = MeetingDir(tmp_path)
    meeting_dir.summary_file.write_text('{"overview": "cut off mid-wri')

    with pytest.raises(SummaryError, match="summary.json couldn't be read"):
        meeting_dir.load_summary()


def test_loads_legacy_summaries_without_rewriting_them_and_round_trips_details(tmp_path: Path):
    directory = MeetingDir(tmp_path)
    original = '{"overview":"Pricing.","key_points":[],"decisions":[],"action_items":[]}'
    directory.summary_file.write_text(original)

    summary = directory.load_summary()

    assert isinstance(summary, Summary)
    assert summary.details == []
    assert directory.summary_file.read_text() == original
    summary.details = [Detail(speaker="Sam", subject="Build budget", quote="Seventy is doable.")]
    directory.save_summary(summary)
    assert directory.load_summary() == summary


def test_reads_draft_figures_as_details_without_rewriting_the_file(tmp_path: Path):
    directory = MeetingDir(tmp_path)
    original = json.dumps(
        {
            "overview": "Pricing.",
            "key_points": ["The proposal is under review."],
            "decisions": [],
            "action_items": [],
            "figures": [{"speaker": "Them", "subject": "Budget", "quote": "Seventy is doable."}],
        }
    )
    directory.summary_file.write_text(original)

    summary = directory.load_summary()

    assert summary is not None
    assert summary.details == [Detail(speaker="Them", subject="Budget", quote="Seventy is doable.")]
    assert summary.key_points == ["The proposal is under review."]
    assert directory.summary_file.read_text() == original
    directory.save_summary(summary)
    saved = json.loads(directory.summary_file.read_text())
    assert "figures" not in saved
    assert saved["details"][0]["quote"] == "Seventy is doable."


def test_source_details_round_trip_without_generated_topic_labels(tmp_path: Path):
    directory = MeetingDir(tmp_path)
    summary = Summary(
        overview="Pricing.",
        decisions=[],
        action_items=[],
        details=[Detail(speaker="Them", start=0, quote="Seventy is doable.")],
    )

    directory.save_summary(summary)

    assert directory.load_summary() == summary
    assert summary.details[0].subject is None


def test_attendees_round_trip_and_older_meetings_have_none(tmp_path: Path):
    store = MeetingStore(tmp_path)
    meeting_dir = store.create(Meeting.new("Sync", STARTED, ("Alex Doe",)))
    assert meeting_dir.load_meeting().attendees == ("Alex Doe",)

    older = tmp_path / "2026-10-20-0900-old"
    older.mkdir()
    (older / "meeting.json").write_text(
        '{"title": "Old", "started_at": "2026-10-20T09:00:00-04:00"}'
    )
    assert MeetingDir(older).load_meeting().attendees == ()
