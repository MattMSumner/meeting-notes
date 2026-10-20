from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from meeting_notes.meeting import Meeting
from meeting_notes.store import MeetingNotFound, MeetingStore
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


def test_refuses_to_overwrite_an_existing_meeting(tmp_path: Path):
    store = MeetingStore(tmp_path)
    store.create(Meeting.new("Sync", STARTED))

    with pytest.raises(FileExistsError):
        store.create(Meeting.new("Sync", STARTED))


def test_unknown_meeting_id(tmp_path: Path):
    with pytest.raises(MeetingNotFound):
        MeetingStore(tmp_path).get("2026-10-20-1405-nope")
