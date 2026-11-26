"""Interleaves each speaker's transcript into one conversation, by real time."""

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from itertools import groupby

from meeting_notes.transcript import Segment

# A long turn is split into paragraphs: at the first sentence end once a paragraph has run
# this long...
PARAGRAPH_SECONDS = 30.0
# ...or, for speech that comes back without punctuation, before it would run past this.
LONGEST_PARAGRAPH_SECONDS = 60.0
# Closing quotes and brackets can follow a sentence's last mark: 'he said "done."'
_CLOSERS = "\"')]”’"
BACKCHANNEL_SECONDS = 2.0
BACKCHANNEL_WORDS = 3
_ACKNOWLEDGMENT = r"(?:yeah|yep|yup|yes|ok|okay|right|uh huh|mm hmm|mhm)"
_ACKNOWLEDGMENTS = re.compile(rf"{_ACKNOWLEDGMENT}(?: {_ACKNOWLEDGMENT})*")


@dataclass(frozen=True)
class Aside:
    position: int
    """Insert after this many characters of the main speaker's text."""
    start: float
    speaker: str
    text: str


@dataclass(frozen=True)
class Line:
    start: float
    """Seconds from the start of the recording."""
    speaker: str
    text: str
    asides: tuple[Aside, ...] = ()


@dataclass(frozen=True)
class SpeakerTrack:
    speaker: str
    offset: float
    """Seconds from the start of the recording to this channel's first sample. Segment
    times are relative to the channel's own file, so this lines the channels up."""
    segments: list[Segment]


def merge(tracks: Sequence[SpeakerTrack], *, fold_backchannels: bool = False) -> list[Line]:
    """One line per paragraph: consecutive segments from the same speaker are joined, and
    a long turn is split into several lines.

    Segments are ordered by when they start. Ties go to the track listed first.
    Folding is for display only; summaries keep the original speaker-separated turns."""
    timed = sorted(
        (
            (
                track.offset + segment.end,
                Line(track.offset + segment.start, track.speaker, segment.text),
            )
            for track in tracks
            for segment in track.segments
        ),
        # Stable sorting preserves track order when starts tie.
        key=lambda item: item[1].start,
    )
    if fold_backchannels:
        timed = _fold_backchannels(timed)
    lines: list[Line] = []
    for end, line in timed:
        previous = lines[-1] if lines else None
        if (
            previous
            and previous.speaker == line.speaker
            and not _paragraph_ends(previous, line.start, end)
        ):
            asides = previous.asides + tuple(
                replace(aside, position=len(previous.text) + 1 + aside.position)
                for aside in line.asides
            )
            lines[-1] = replace(previous, text=f"{previous.text} {line.text}", asides=asides)
        else:
            lines.append(line)
    return lines


def _words(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.casefold()))


def _fold_backchannels(timed: list[tuple[float, Line]]) -> list[tuple[float, Line]]:
    """Fold whole runs so an acknowledgment starting a substantive reply stays with it."""
    folded: list[tuple[float, Line]] = []
    previous: tuple[float, Line] | None = None
    for _, items in groupby(timed, key=lambda item: item[1].speaker):
        run = list(items)
        first = run[0][1]
        end = max(end for end, _ in run)
        text = " ".join(line.text for _, line in run)
        words = _words(text)
        if (
            previous is not None
            and previous[1].start < first.start
            and end <= previous[0]
            and 0 <= end - first.start <= BACKCHANNEL_SECONDS
            and len(words.split()) <= BACKCHANNEL_WORDS
            and _ACKNOWLEDGMENTS.fullmatch(words)
            and "?" not in text
            and "?" not in previous[1].text
            and not _ACKNOWLEDGMENTS.fullmatch(_words(previous[1].text))
        ):
            host_end, host = folded[-1]
            aside = Aside(len(host.text), first.start, first.speaker, text)
            folded[-1] = (host_end, replace(host, asides=host.asides + (aside,)))
        else:
            folded.extend(run)
        # Use the original predecessor: an aside cannot itself host another aside.
        previous = run[-1]
    return folded


def _paragraph_ends(paragraph: Line, next_start: float, next_end: float) -> bool:
    """Whether the paragraph ends before the next segment, which starts and ends then."""
    sentence_ended = paragraph.text.rstrip(_CLOSERS).endswith((".", "?", "!", "…"))
    return next_end - paragraph.start > LONGEST_PARAGRAPH_SECONDS or (
        next_start - paragraph.start >= PARAGRAPH_SECONDS and sentence_ended
    )
