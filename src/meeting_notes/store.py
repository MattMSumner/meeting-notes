"""One folder per meeting holding its audio and each pipeline stage's output.

Each stage reads the previous stage's files and writes its own, so any stage can be
re-run on its own (for example after changing the transcription model)."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from meeting_notes.meeting import Meeting
from meeting_notes.transcript import Segment


class MeetingNotFound(Exception):
    pass


@dataclass(frozen=True)
class ChannelCapture:
    """One channel's entry in capture.json, written by notes-capture."""

    offset: float | None
    """Seconds from the start of the recording to the channel's first sample, or None if
    the channel received no audio."""
    all_zero: bool
    """Every sample was zero: for system audio, almost certainly blocked by macOS."""

    @property
    def has_audio(self) -> bool:
        return self.offset is not None and not self.all_zero


class MeetingDir:
    def __init__(self, path: Path) -> None:
        self.path = path

    @property
    def id(self) -> str:
        return self.path.name

    def audio(self, channel: str) -> Path:
        return self.path / f"{channel}.wav"

    def segments_file(self, channel: str) -> Path:
        return self.path / f"segments.{channel}.json"

    def load_meeting(self) -> Meeting:
        data = json.loads((self.path / "meeting.json").read_text())
        return Meeting(title=data["title"], started_at=datetime.fromisoformat(data["started_at"]))

    def captures(self) -> dict[str, ChannelCapture]:
        """What each channel captured, from capture.json.

        Meetings recorded before notes-capture (M1) have no capture.json, just me.wav."""
        manifest = self.path / "capture.json"
        if not manifest.is_file():
            if self.audio("me").is_file():
                return {"me": ChannelCapture(offset=0.0, all_zero=False)}
            return {}
        channels: dict[str, dict[str, Any]] = json.loads(manifest.read_text())["channels"]
        return {
            name: ChannelCapture(
                offset=None
                if data.get("offset_seconds") is None
                else float(data["offset_seconds"]),
                all_zero=bool(data.get("all_zero", False)),
            )
            for name, data in channels.items()
        }

    def save_segments(self, channel: str, segments: list[Segment]) -> None:
        payload = [s.to_dict() for s in segments]
        self.segments_file(channel).write_text(json.dumps(payload, indent=2) + "\n")

    def load_segments(self, channel: str) -> list[Segment]:
        return [Segment.from_dict(d) for d in json.loads(self.segments_file(channel).read_text())]


class MeetingStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def create(self, meeting: Meeting) -> MeetingDir:
        path = self.root / meeting.id
        path.mkdir(parents=True, exist_ok=False)
        payload = {"title": meeting.title, "started_at": meeting.started_at.isoformat()}
        (path / "meeting.json").write_text(json.dumps(payload, indent=2) + "\n")
        return MeetingDir(path)

    def get(self, meeting_id: str) -> MeetingDir:
        path = self.root / meeting_id
        if not (path / "meeting.json").is_file():
            raise MeetingNotFound(meeting_id)
        return MeetingDir(path)
