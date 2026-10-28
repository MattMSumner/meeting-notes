"""Source turns that can be selected without rewriting their words."""

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace

from meeting_notes.summary import Detail, SummaryError

_HEADER = re.compile(r"^\[(\d+):([0-5]\d):([0-5]\d)\] ([^:\r\n]+): (.*)$")


@dataclass(frozen=True)
class Turn:
    id: str
    start: float
    speaker: str
    text: str


def parse_turns(transcript: str) -> list[Turn]:
    """Keep each timestamped turn intact, including continuation lines."""
    turns: list[Turn] = []
    # The canonical transcript uses LF; splitlines() would alter other source whitespace.
    for line in transcript.split("\n"):
        if match := _HEADER.fullmatch(line):
            hours, minutes, seconds, speaker, text = match.groups()
            try:
                start = float(3600 * int(hours) + 60 * int(minutes) + int(seconds))
            except (ValueError, OverflowError):
                raise SummaryError("Couldn't read transcript turns: invalid timestamp") from None
            turns.append(Turn(f"t{len(turns) + 1}", start, speaker, text))
        elif not turns and not line.strip():
            continue
        elif not turns or re.match(r"^\[\d", line):
            raise SummaryError("Couldn't read transcript turns: expected [HH:MM:SS] Speaker: text")
        else:
            previous = turns[-1]
            turns[-1] = replace(previous, text=previous.text + "\n" + line)
    # Newlines between records are delimiters; internal whitespace remains source text.
    turns = [replace(turn, text=turn.text.rstrip("\n")) for turn in turns]
    if any(not turn.speaker.strip() or not turn.text.strip() for turn in turns):
        raise SummaryError("Couldn't read transcript turns: speaker and text must not be blank")
    return turns


def verify_selection(turn_ids: Sequence[str], turns: Sequence[Turn]) -> None:
    known = {turn.id for turn in turns}
    unknown = sorted(set(turn_ids) - known)
    if unknown:
        raise SummaryError(
            f"Unknown turn IDs: {', '.join(unknown)}. Select only IDs from the supplied turns"
        )


def selected_details(turn_ids: Sequence[str], turns: Sequence[Turn]) -> list[Detail]:
    """Resolve IDs in source order, copying each selected turn only once."""
    verify_selection(turn_ids, turns)
    selected = set(turn_ids)
    return [
        Detail(speaker=turn.speaker, start=turn.start, quote=turn.text)
        for turn in turns
        if turn.id in selected
    ]
