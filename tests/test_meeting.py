from datetime import datetime

import pytest

from meeting_notes.meeting import Meeting, clean_title

STARTED = datetime(2026, 10, 20, 14, 5)


def test_names_derived_from_title_and_start_time():
    meeting = Meeting.new("Weekly Sync", STARTED)

    assert meeting.id == "2026-10-20-1405-weekly-sync"
    assert meeting.note_stem == "2026-10-20_Weekly Sync_1405"
    assert meeting.transcript_stem == "2026-10-20_Weekly Sync_1405_transcript"


@pytest.mark.parametrize("title", [None, "", "   ", "///"])
def test_missing_or_unusable_title_becomes_untitled(title: str | None):
    meeting = Meeting.new(title, STARTED)

    assert meeting.title == "Untitled"
    assert meeting.id == "2026-10-20-1405-untitled"


def test_removes_characters_that_break_file_names_and_wikilinks():
    assert clean_title('1:1 Alex/Sam [draft] #team "Q4"?') == "1 1 Alex Sam draft team Q4"


def test_collapses_whitespace():
    assert clean_title("  Weekly \t  Sync \n") == "Weekly Sync"


def test_id_slug_survives_non_ascii_titles():
    meeting = Meeting.new("Café ☕ chat", STARTED)

    assert meeting.id == "2026-10-20-1405-caf-chat"
    assert meeting.note_stem == "2026-10-20_Café ☕ chat_1405"
