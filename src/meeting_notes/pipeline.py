"""The stages that turn a recorded meeting into files in the vault."""

from pathlib import Path

from meeting_notes.config import Config
from meeting_notes.render import render_transcript
from meeting_notes.store import MeetingDir
from meeting_notes.transcript import Transcriber

# M1 records only the mic. M2 adds the "them" channel from the system audio tap.
CHANNEL = "me"
SPEAKER = "Me"


def transcribe(meeting_dir: MeetingDir, transcriber: Transcriber) -> None:
    segments = transcriber.transcribe(meeting_dir.audio(CHANNEL))
    meeting_dir.save_segments(CHANNEL, segments)


def render(meeting_dir: MeetingDir, config: Config) -> Path:
    """Writes the transcript into the vault and returns its path."""
    meeting = meeting_dir.load_meeting()
    markdown = render_transcript(meeting, SPEAKER, meeting_dir.load_segments(CHANNEL))
    config.transcripts_dir.mkdir(parents=True, exist_ok=True)
    path = config.transcripts_dir / f"{meeting.transcript_stem}.md"
    path.write_text(markdown)
    return path
