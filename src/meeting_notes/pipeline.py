"""The stages that turn a recorded meeting into files in the vault."""

from pathlib import Path

from meeting_notes.config import Config
from meeting_notes.merge import SpeakerTrack, merge
from meeting_notes.render import render_transcript
from meeting_notes.store import MeetingDir
from meeting_notes.transcript import Transcriber

# Channel name (file stem) -> speaker label, in the order ties are broken.
SPEAKERS = {"me": "Me", "them": "Them"}


def transcribe(meeting_dir: MeetingDir, transcriber: Transcriber) -> None:
    for channel, capture in meeting_dir.captures().items():
        if channel in SPEAKERS and capture.has_audio:
            meeting_dir.save_segments(channel, transcriber.transcribe(meeting_dir.audio(channel)))


def render(meeting_dir: MeetingDir, config: Config) -> Path:
    """Writes the transcript into the vault and returns its path."""
    meeting = meeting_dir.load_meeting()
    captures = meeting_dir.captures()
    tracks: list[SpeakerTrack] = []
    warnings: list[str] = []
    for channel, speaker in SPEAKERS.items():
        capture = captures.get(channel)
        if capture is None:
            continue
        if capture.all_zero:
            warnings.append(
                f'The "{speaker}" audio was silent (all zeros), so it wasn\'t transcribed. '
                "If this was a call, macOS probably blocked capture: run `notes check`."
            )
        elif capture.offset is not None and meeting_dir.segments_file(channel).is_file():
            tracks.append(SpeakerTrack(speaker, capture.offset, meeting_dir.load_segments(channel)))

    markdown = render_transcript(meeting, merge(tracks), warnings)
    config.transcripts_dir.mkdir(parents=True, exist_ok=True)
    path = config.transcripts_dir / f"{meeting.transcript_stem}.md"
    path.write_text(markdown)
    return path
