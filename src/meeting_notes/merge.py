"""Interleaves each speaker's transcript into one conversation, by real time."""

from collections.abc import Sequence
from dataclasses import dataclass

from meeting_notes.transcript import Segment

# A long turn is split into paragraphs: at the first sentence end once a paragraph has run
# this long...
PARAGRAPH_SECONDS = 30.0
# ...or, for speech that comes back without punctuation, at the next pause after this.
LONGEST_PARAGRAPH_SECONDS = 60.0


@dataclass(frozen=True)
class Line:
    start: float
    """Seconds from the start of the recording."""
    speaker: str
    text: str


@dataclass(frozen=True)
class SpeakerTrack:
    speaker: str
    offset: float
    """Seconds from the start of the recording to this channel's first sample. Segment
    times are relative to the channel's own file, so this lines the channels up."""
    segments: list[Segment]


def merge(tracks: Sequence[SpeakerTrack]) -> list[Line]:
    """One line per paragraph: consecutive segments from the same speaker are joined, and
    a long turn is split into several lines.

    Segments are ordered by when they start. Ties go to the track listed first."""
    timed = sorted(
        (
            (track.offset + segment.start, order, track.speaker, segment.text)
            for order, track in enumerate(tracks)
            for segment in track.segments
        ),
        key=lambda item: (item[0], item[1]),
    )
    lines: list[Line] = []
    for start, _, speaker, text in timed:
        previous = lines[-1] if lines else None
        if previous and previous.speaker == speaker and not _paragraph_ends(previous, start):
            lines[-1] = Line(previous.start, speaker, f"{previous.text} {text}")
        else:
            lines.append(Line(start, speaker, text))
    return lines


def _paragraph_ends(paragraph: Line, next_start: float) -> bool:
    length = next_start - paragraph.start
    sentence_ended = paragraph.text.endswith((".", "?", "!"))
    return length >= LONGEST_PARAGRAPH_SECONDS or (length >= PARAGRAPH_SECONDS and sentence_ended)
