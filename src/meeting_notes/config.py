"""Where things live. Override with environment variables (tests do)."""

import os
import pwd
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DATA_DIR = Path.home() / "Library" / "Application Support" / "meeting-notes" / "meetings"
DEFAULT_NOTES_DIR = Path.home() / "development" / "notes" / "meetings"
DEFAULT_MODEL = "mlx-community/parakeet-tdt-0.6b-v2"
# Built by capture/install.sh.
DEFAULT_CAPTURE = REPO_ROOT / "capture/build/NotesCapture.app/Contents/MacOS/notes-capture"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_SUMMARY_MODEL = "qwen3:30b"
# Tokens. An hour-long meeting is about 10-15k, plus the prompt and the reply.
DEFAULT_NUM_CTX = 32768


@dataclass(frozen=True)
class Config:
    data_dir: Path
    """Audio and intermediate files, one folder per meeting. Kept out of the vault."""
    notes_dir: Path
    """The vault folder notes are written to. Transcripts go in its transcripts/ folder."""
    model: str
    capture: Path = DEFAULT_CAPTURE
    """The notes-capture binary, inside its signed NotesCapture.app."""
    ollama_url: str = DEFAULT_OLLAMA_URL
    summary_model: str = DEFAULT_SUMMARY_MODEL
    """The Ollama model that writes the summary."""
    num_ctx: int = DEFAULT_NUM_CTX
    """The summary model's context size in tokens. Must fit the whole transcript."""
    my_name: str = "Me"
    """What the summary calls the person who recorded the meeting."""
    summary_think: bool = True
    """Let the summary model reason before answering. Slower, but noticeably more accurate
    (decisions and who owns which action item). Turn off for models that can't think."""

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
            ollama_url=os.environ.get("MEETING_NOTES_OLLAMA_URL", DEFAULT_OLLAMA_URL),
            summary_model=os.environ.get("MEETING_NOTES_SUMMARY_MODEL", DEFAULT_SUMMARY_MODEL),
            num_ctx=int(os.environ.get("MEETING_NOTES_NUM_CTX", DEFAULT_NUM_CTX)),
            my_name=os.environ.get("MEETING_NOTES_MY_NAME") or _first_name(),
            summary_think=os.environ.get("MEETING_NOTES_SUMMARY_THINK", "1") != "0",
        )


def _first_name() -> str:
    """The first name on the macOS account, e.g. "Matthew" for "Matthew Sumner"."""
    full_name = pwd.getpwuid(os.getuid()).pw_gecos
    return full_name.split()[0] if full_name.split() else "Me"
