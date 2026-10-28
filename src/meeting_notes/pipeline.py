"""The stages that turn a recorded meeting into files in the vault."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from meeting_notes.config import Config
from meeting_notes.figures import unsaid_numbers
from meeting_notes.merge import Line, SpeakerTrack, merge
from meeting_notes.render import render_note, render_transcript, timestamp
from meeting_notes.store import MeetingDir
from meeting_notes.summary import Summarizer, SummaryError
from meeting_notes.transcript import Transcriber
from meeting_notes.wavfile import repair_wav_header

# Channel name (file stem) -> speaker label, in the order ties are broken.
SPEAKERS = {"me": "Me", "them": "Them"}


def transcribe(meeting_dir: MeetingDir, transcriber: Transcriber) -> None:
    if not meeting_dir.has_manifest:
        # The recording didn't finish cleanly, so its WAV headers may be unfinished.
        for channel in SPEAKERS:
            if meeting_dir.audio(channel).is_file():
                repair_wav_header(meeting_dir.audio(channel))
    for channel, capture in meeting_dir.captures().items():
        if channel in SPEAKERS and capture.has_audio:
            meeting_dir.save_segments(channel, transcriber.transcribe(meeting_dir.audio(channel)))
    # Summarized a transcript that no longer exists.
    meeting_dir.clear_summary()


@dataclass(frozen=True)
class Conversation:
    lines: list[Line]
    transcribed: bool
    """Every channel with audio has been transcribed."""
    warnings: list[str]
    """Problems with the recording that the reader should know about."""


def conversation(meeting_dir: MeetingDir) -> Conversation:
    """Both sides' transcribed segments, interleaved in time."""
    captures = meeting_dir.captures()
    tracks: list[SpeakerTrack] = []
    warnings: list[str] = []
    transcribed = True
    if not meeting_dir.has_manifest and "them" in captures:
        warnings.append(
            "The recording didn't finish cleanly (no capture.json), so both sides are assumed "
            "to start together. Lines may be slightly out of order."
        )
    for channel, speaker in SPEAKERS.items():
        capture = captures.get(channel)
        if capture is None:
            continue
        if capture.all_zero:
            warnings.append(
                f'The "{speaker}" audio was silent (all zeros), so it wasn\'t transcribed. '
                "If this was a call, macOS probably blocked capture: run `notes check`."
            )
        elif capture.offset is None:
            warnings.append(
                f'No "{speaker}" audio was recorded at all. If this was a call, check the '
                "notes-capture output for errors and run `notes check`."
            )
        elif meeting_dir.segments_file(channel).is_file():
            tracks.append(SpeakerTrack(speaker, capture.offset, meeting_dir.load_segments(channel)))
        else:
            transcribed = False
    return Conversation(merge(tracks), transcribed, warnings)


def transcript_text(lines: Sequence[Line], my_name: str) -> str:
    """The conversation as plain text for the summary model.

    My lines are labelled with my name, not "Me": told only "Me", the model guesses who
    that is, sometimes crediting me to someone else or calling me by a role. A turn split
    into paragraphs is one line again, so it doesn't read as several turns."""
    names = {"Me": my_name}
    turns: list[Line] = []
    for line in lines:
        if turns and turns[-1].speaker == line.speaker:
            turns[-1] = Line(turns[-1].start, line.speaker, f"{turns[-1].text} {line.text}")
        else:
            turns.append(line)
    return "\n".join(
        f"[{timestamp(turn.start)}] {names.get(turn.speaker, turn.speaker)}: {turn.text}"
        for turn in turns
    )


class NotTranscribed(SummaryError):
    pass


def summarize(
    meeting_dir: MeetingDir, talk: Conversation, summarizer: Summarizer, my_name: str
) -> None:
    """Writes summary.json. Raises SummaryError if the model fails."""
    if not talk.transcribed:
        raise NotTranscribed(
            f"It hasn't been transcribed yet: run `notes transcribe {meeting_dir.id}`"
        )
    if not talk.lines:
        meeting_dir.clear_summary()  # the note says no speech was detected
        return
    meeting_dir.save_summary(
        summarizer.summarize(meeting_dir.load_meeting(), transcript_text(talk.lines, my_name))
    )


@dataclass(frozen=True)
class Rendered:
    note: Path
    transcript: Path
    skipped: list[Path]
    """Files left alone because they were edited in the vault since they were written."""


def render(meeting_dir: MeetingDir, talk: Conversation, config: Config) -> Rendered:
    """Writes the note and the transcript into the vault."""
    meeting = meeting_dir.load_meeting()
    note = config.notes_dir / f"{meeting.note_stem}.md"
    transcript = config.transcripts_dir / f"{meeting.transcript_stem}.md"
    note_warnings = list(talk.warnings)
    try:
        summary = meeting_dir.load_summary()
    except SummaryError as error:
        summary = None
        note_warnings.append(f"{error}. To write a new one: `notes summarize {meeting_dir.id}`")
    if summary is not None:
        said = "\n".join(
            [
                meeting.title,
                f"{meeting.started_at:%Y-%m-%d %H:%M}",
                *meeting.attendees,
                *(line.text for line in talk.lines),
            ]
        )
        if unsaid := unsaid_numbers(summary, said):
            note_warnings.append(
                f"Nobody said {'this number' if len(unsaid) == 1 else 'these numbers'} in "
                f"the meeting: {', '.join(unsaid)}. The summary may have worked "
                f"{'it' if len(unsaid) == 1 else 'them'} out, so check against the transcript."
            )
    skipped = meeting_dir.write_unless_edited(
        {
            transcript: render_transcript(meeting, talk.lines, talk.warnings),
            note: render_note(meeting, summary, meeting_dir.id, bool(talk.lines), note_warnings),
        }
    )
    return Rendered(note, transcript, skipped)
