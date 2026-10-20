"""One folder per meeting holding its audio and each pipeline stage's output.

Each stage reads the previous stage's files and writes its own, so any stage can be
re-run on its own (for example after changing the transcription model)."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from meeting_notes.meeting import Meeting
from meeting_notes.summary import Summary, SummaryError
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

    @property
    def has_manifest(self) -> bool:
        """Whether notes-capture finished cleanly and wrote capture.json."""
        return (self.path / "capture.json").is_file()

    def captures(self) -> dict[str, ChannelCapture]:
        """What each channel captured, from capture.json.

        Without capture.json (a meeting from M1, which recorded only me.wav, or a recording
        that crashed before finishing), every channel file present is used, assumed to
        start with the recording."""
        if not self.has_manifest:
            return {
                channel: ChannelCapture(offset=0.0, all_zero=False)
                for channel in ("me", "them")
                if self.audio(channel).is_file()
            }
        manifest = self.path / "capture.json"
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

    @property
    def summary_file(self) -> Path:
        return self.path / "summary.json"

    def save_summary(self, summary: Summary) -> None:
        self.summary_file.write_text(summary.model_dump_json(indent=2) + "\n")

    def load_summary(self) -> Summary | None:
        """The saved summary, or None if there isn't one. Raises SummaryError if it's unreadable."""
        if not self.summary_file.is_file():
            return None
        try:
            return Summary.model_validate_json(self.summary_file.read_text())
        except ValueError as error:  # pydantic's ValidationError is a ValueError
            raise SummaryError(f"summary.json couldn't be read ({error})") from None

    def clear_summary(self) -> None:
        """Removes the summary, e.g. because the transcript it summarized has changed."""
        self.summary_file.unlink(missing_ok=True)

    def write_unless_edited(self, files: dict[Path, str]) -> list[Path]:
        """Writes generated files into the vault, except any edited since we last wrote them.

        Notes get edited in Obsidian (ticked action items, corrected names), and re-running a
        stage shouldn't silently throw that away. Returns the files left alone."""
        written_file = self.path / "written.json"
        written: dict[str, str] = (
            json.loads(written_file.read_text()) if written_file.is_file() else {}
        )
        skipped: list[Path] = []
        for path, content in files.items():
            if path.is_file():
                current = _sha256(path.read_text())
                if current != _sha256(content) and current != written.get(str(path)):
                    skipped.append(path)
                    continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            written[str(path)] = _sha256(content)
        written_file.write_text(json.dumps(written, indent=2) + "\n")
        return skipped


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


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
