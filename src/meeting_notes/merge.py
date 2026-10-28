"""Interleaves each speaker's transcript into one conversation, by real time."""

from collections.abc import Sequence
from dataclasses import dataclass

from meeting_notes.transcript import Segment

# A long turn is split into paragraphs: at the first sentence end once a paragraph has run
# this long...
PARAGRAPH_SECONDS = 30.0
# ...or, for speech that comes back without punctuation, before it would run past this.
LONGEST_PARAGRAPH_SECONDS = 60.0
# Closing quotes and brackets can follow a sentence's last mark: 'he said "done."'
_CLOSERS = "\"')]”’"


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
            (
                track.offset + segment.start,
                order,
                track.offset + segment.end,
                track.speaker,
                segment.text,
            )
            for order, track in enumerate(tracks)
            for segment in track.segments
        ),
        key=lambda item: (item[0], item[1]),
    )
    lines: list[Line] = []
    for start, _, end, speaker, text in timed:
        previous = lines[-1] if lines else None
        if previous and previous.speaker == speaker and not _paragraph_ends(previous, start, end):
            lines[-1] = Line(previous.start, speaker, f"{previous.text} {text}")
        else:
            lines.append(Line(start, speaker, text))
    return lines


def _paragraph_ends(paragraph: Line, next_start: float, next_end: float) -> bool:
    """Whether the paragraph ends before the next segment, which starts and ends then."""
    sentence_ended = paragraph.text.rstrip(_CLOSERS).endswith((".", "?", "!", "…"))
    return next_end - paragraph.start > LONGEST_PARAGRAPH_SECONDS or (
        next_start - paragraph.start >= PARAGRAPH_SECONDS and sentence_ended
    )
