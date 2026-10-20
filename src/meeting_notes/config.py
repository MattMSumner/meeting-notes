"""Where things live. Override with environment variables (tests do)."""

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DATA_DIR = Path.home() / "Library" / "Application Support" / "meeting-notes" / "meetings"
DEFAULT_NOTES_DIR = Path.home() / "development" / "notes" / "meetings"
DEFAULT_MODEL = "mlx-community/parakeet-tdt-0.6b-v2"
# Built by capture/install.sh.
DEFAULT_CAPTURE = REPO_ROOT / "capture/build/NotesCapture.app/Contents/MacOS/notes-capture"


@dataclass(frozen=True)
class Config:
    data_dir: Path
    """Audio and intermediate files, one folder per meeting. Kept out of the vault."""
    notes_dir: Path
    """The vault folder notes are written to. Transcripts go in its transcripts/ folder."""
    model: str
    capture: Path = DEFAULT_CAPTURE
    """The notes-capture binary, inside its signed NotesCapture.app."""

    @property
    def transcripts_dir(self) -> Path:
        return self.notes_dir / "transcripts"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            data_dir=Path(os.environ.get("MEETING_NOTES_DATA_DIR", DEFAULT_DATA_DIR)),
            notes_dir=Path(os.environ.get("MEETING_NOTES_NOTES_DIR", DEFAULT_NOTES_DIR)),
            model=os.environ.get("MEETING_NOTES_MODEL", DEFAULT_MODEL),
            capture=Path(os.environ.get("MEETING_NOTES_CAPTURE", DEFAULT_CAPTURE)),
        )
