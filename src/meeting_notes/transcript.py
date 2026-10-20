"""Transcribed speech and the interface any speech-to-text backend implements."""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class Segment:
    start: float
    """Seconds from the start of the recording."""
    end: float
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Segment":
        return cls(start=float(data["start"]), end=float(data["end"]), text=str(data["text"]))


class Transcriber(Protocol):
    def transcribe(self, audio: Path) -> list[Segment]: ...
