"""A meeting's identity: its title, when it started, and the names derived from those."""

import re
from dataclasses import dataclass
from datetime import datetime

UNTITLED = "Untitled"

# Characters that break file names or Obsidian wikilinks.
_UNSAFE_TITLE_CHARS = re.compile(r'[/\\:*?"<>|#^\[\]]')


def clean_title(title: str | None) -> str:
    """A title that is safe to use in file names and Obsidian links."""
    cleaned = _UNSAFE_TITLE_CHARS.sub(" ", title or "")
    cleaned = " ".join(cleaned.split())
    return cleaned or UNTITLED


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


@dataclass(frozen=True)
class Meeting:
    title: str
    started_at: datetime
    attendees: tuple[str, ...] = ()
    """Everyone else invited, from the calendar."""

    @classmethod
    def new(
        cls, title: str | None, started_at: datetime, attendees: tuple[str, ...] = ()
    ) -> "Meeting":
        return cls(title=clean_title(title), started_at=started_at, attendees=attendees)

    @property
    def id(self) -> str:
        """Folder name for the meeting's data, e.g. 2026-10-20-1400-weekly-sync."""
        stamp = self.started_at.strftime("%Y-%m-%d-%H%M")
        return f"{stamp}-{slugify(self.title) or 'untitled'}"

    @property
    def note_stem(self) -> str:
        """Vault file name without extension, e.g. 2026-10-20_Weekly Sync_1400.

        Matches the vault's granola-notes convention (YYYY-MM-DD_<title>_<id>)."""
        return f"{self.started_at:%Y-%m-%d}_{self.title}_{self.started_at:%H%M}"

    @property
    def transcript_stem(self) -> str:
        return f"{self.note_stem}_transcript"
