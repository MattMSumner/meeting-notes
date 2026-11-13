"""The meeting on the calendar right now, to suggest as the recording's title.

Events come from `notes-capture calendar`, which reads whatever calendars macOS syncs
(Google Calendar, added in System Settings > Internet Accounts). Choosing the meeting is
done here, so it can be tested without a calendar."""

import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

# A meeting is suggested from this long before it starts (joining a call a bit early).
EARLY_START = timedelta(minutes=5)
# How far back to look for meetings still going on.
LOOK_BACK = timedelta(hours=6)
# Reading the calendar takes well under a second. Longer means it's stuck (say, on a
# permission prompt hidden behind other windows): start without a suggestion instead.
TIMEOUT_SECONDS = 5


@dataclass(frozen=True)
class Attendee:
    name: str
    is_me: bool


@dataclass(frozen=True)
class Event:
    title: str
    start: datetime
    end: datetime
    all_day: bool = False
    cancelled: bool = False
    declined: bool = False
    attendees: tuple[Attendee, ...] = ()

    @property
    def other_attendees(self) -> list[str]:
        return [attendee.name for attendee in self.attendees if not attendee.is_me]


def parse_events(text: str) -> list[Event]:
    """Events from `notes-capture calendar` JSON."""
    return [_event(data) for data in json.loads(text)]


def _event(data: dict[str, Any]) -> Event:
    return Event(
        title=str(data.get("title", "")),
        start=datetime.fromisoformat(data["start"]),
        end=datetime.fromisoformat(data["end"]),
        all_day=bool(data.get("all_day", False)),
        cancelled=bool(data.get("cancelled", False)),
        declined=data.get("my_status") == "declined",
        attendees=tuple(
            Attendee(_attendee_name(attendee), bool(attendee.get("is_me", False)))
            for attendee in data.get("attendees", [])
        ),
    )


def _attendee_name(attendee: dict[str, Any]) -> str:
    """Their name, or failing that their email address's local part."""
    name = attendee.get("name") or ""
    email = attendee.get("email") or ""
    if name and name != email:
        return str(name)
    return str(email).split("@")[0] or "unknown"


def current_meeting(events: Sequence[Event], now: datetime) -> Event | None:
    """The meeting being recorded: one happening now or about to start, ignoring all-day,
    cancelled and declined events. Of several, the one whose start is nearest to now, so
    at 10:58 the 11:00 meeting wins over the 10:00 one that's about to end."""
    candidates = [
        event
        for event in events
        if not (event.all_day or event.cancelled or event.declined or not event.title.strip())
        and event.start - EARLY_START <= now < event.end
    ]
    return min(candidates, key=lambda event: abs(event.start - now), default=None)


class Calendar(Protocol):
    def events(self, start: datetime, end: datetime) -> list[Event]: ...


class CaptureCalendar:
    """Reads events with notes-capture. Never fails: a calendar problem just means no
    suggestion, with the reason on stderr."""

    def __init__(self, binary: Path) -> None:
        self.binary = binary

    def events(self, start: datetime, end: datetime) -> list[Event]:
        if not self.binary.is_file():
            return []
        try:
            result = subprocess.run(
                [str(self.binary), "calendar", "--from", _iso(start), "--to", _iso(end)],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            print("Couldn't read the calendar: it took too long.", file=sys.stderr)
            return []
        except OSError as error:
            print(f"Couldn't read the calendar: {error}", file=sys.stderr)
            return []
        if result.returncode != 0:
            print(f"Couldn't read the calendar: {result.stderr.strip()}", file=sys.stderr)
            return []
        try:
            return parse_events(result.stdout)
        except (ValueError, KeyError, TypeError) as error:
            print(f"Couldn't read the calendar: {error}", file=sys.stderr)
            return []


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def meeting_now(calendar: Calendar, now: datetime) -> Event | None:
    return current_meeting(calendar.events(now - LOOK_BACK, now + EARLY_START), now)
