import json
from datetime import UTC, datetime, timedelta
from typing import Any

from meeting_notes.calendar import Event, current_meeting, parse_events

NOW = datetime(2026, 10, 21, 15, 0, tzinfo=UTC)


def event(title: str, start_minutes: int, minutes: int = 30, **kwargs: Any) -> Event:
    start = NOW + timedelta(minutes=start_minutes)
    return Event(title, start, start + timedelta(minutes=minutes), **kwargs)


def test_picks_the_meeting_happening_now():
    assert current_meeting([event("Standup", -10)], NOW) == event("Standup", -10)


def test_nothing_on_the_calendar_means_no_suggestion():
    assert current_meeting([], NOW) is None
    assert current_meeting([event("Later", 60), event("Earlier", -90)], NOW) is None


def test_a_meeting_about_to_start_counts():
    assert current_meeting([event("Joined early", 4)], NOW) == event("Joined early", 4)
    assert current_meeting([event("Too early", 10)], NOW) is None


def test_back_to_back_prefers_the_one_starting_now():
    # 10:58: the 10:00 meeting hasn't ended, but the 11:00 one is what's being joined.
    meetings = [event("First", -58, minutes=60), event("Second", 2)]

    assert current_meeting(meetings, NOW) == event("Second", 2)


def test_a_meeting_that_just_ended_is_not_suggested():
    assert current_meeting([event("Over", -30, minutes=30)], NOW) is None


def test_overlapping_meetings_prefer_the_most_recent_start():
    meetings = [event("Long workshop", -120, minutes=240), event("Quick sync", -5)]

    assert current_meeting(meetings, NOW) == event("Quick sync", -5)


def test_all_day_declined_cancelled_and_untitled_events_are_ignored():
    meetings = [
        event("Birthday", -600, minutes=1440, all_day=True),
        event("Declined", -5, declined=True),
        event("Cancelled", -5, cancelled=True),
        event("  ", -5),
        event("Real", -20),
    ]

    assert current_meeting(meetings, NOW) == event("Real", -20)


def test_parses_notes_capture_output():
    output = json.dumps(
        [
            {
                "title": "Design review",
                "start": "2026-10-21T15:00:00Z",
                "end": "2026-10-21T15:30:00Z",
                "all_day": False,
                "calendar": "me@example.com",
                "cancelled": False,
                "my_status": "declined",
                "attendees": [
                    {
                        "name": "Sam",
                        "email": "sam@example.com",
                        "status": "accepted",
                        "is_me": True,
                    },
                    {
                        "name": "Alex Doe",
                        "email": "alex@example.com",
                        "status": "accepted",
                        "is_me": False,
                    },
                    # No display name: the email's local part. No email key at all is fine too.
                    {
                        "name": "jo@example.com",
                        "email": "jo@example.com",
                        "status": "pending",
                        "is_me": False,
                    },
                    {"name": "Kim", "status": "pending", "is_me": False},
                ],
            }
        ]
    )

    [parsed] = parse_events(output)

    assert parsed.title == "Design review"
    assert parsed.start == datetime(2026, 10, 21, 15, 0, tzinfo=UTC)
    assert parsed.declined
    assert parsed.other_attendees == ["Alex Doe", "jo", "Kim"]
