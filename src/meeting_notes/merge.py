"""Interleaves each speaker's transcript into one conversation, by real time."""

from collections.abc import Sequence
from dataclasses import dataclass

from meeting_notes.transcript import Segment


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
    """One line per turn: consecutive segments from the same speaker are joined.

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
        if lines and lines[-1].speaker == speaker:
            previous = lines[-1]
            lines[-1] = Line(previous.start, speaker, f"{previous.text} {text}")
        else:
            lines.append(Line(start, speaker, text))
    return lines
