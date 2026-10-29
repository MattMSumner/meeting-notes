"""Finds the numbers in a summary that nobody said in the meeting.

The summary model sometimes works out a number (the rest of a total, say) and states it as
if someone said it. Every number in the summary is looked for in what was said, whether it
was written in digits ("$120,000", "120k") or, as speech recognition often does, in words
("a hundred and twenty thousand")."""

import re
from collections.abc import Iterator, Sequence

from meeting_notes.summary import Detail, Summary, SummaryError
from meeting_notes.turns import parse_turns

_TOKEN = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|[a-z]+", re.IGNORECASE)
# The transcript's line timestamps, which nobody said.
_TIMESTAMP = re.compile(r"\[\d+:\d\d:\d\d\]")

_UNITS = {
    word: value
    for value, word in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve thirteen "
        "fourteen fifteen sixteen seventeen eighteen nineteen".split()
    )
}
_TENS = {
    word: 10 * value
    for value, word in enumerate(
        "twenty thirty forty fifty sixty seventy eighty ninety".split(), start=2
    )
}
_SCALES = {"thousand": 1e3, "million": 1e6, "billion": 1e9}
# After digits: "120k", "1.5M", "80 thousand".
_SUFFIXES = {"k": 1e3, "m": 1e6, "bn": 1e9, **_SCALES}
_NUMBER_WORDS = {*_UNITS, *_TENS, "hundred", *_SCALES}

# Smaller numbers are mostly counts ("two options", "one more thing"), which are rarely
# what goes wrong and often aren't said in so many words.
SMALLEST_CHECKED = 10


def numbers(text: str) -> Iterator[tuple[str, float]]:
    """Each number in the text, as written there and as a value."""
    text = _TIMESTAMP.sub(lambda match: " " * len(match[0]), text)
    tokens = list(_TOKEN.finditer(text))
    words = [token[0].lower() for token in tokens]

    def joined(i: int) -> bool:
        """Token i follows the one before with only a space or hyphen between."""
        return i > 0 and text[tokens[i - 1].end() : tokens[i].start()].strip(" -") == ""

    i = 0
    while i < len(tokens):
        start = tokens[i].start() - (text[tokens[i].start() - 1 : tokens[i].start()] == "$")
        if words[i][0].isdigit():
            value = float(words[i].replace(",", ""))
            if i + 1 < len(tokens) and words[i + 1] in _SUFFIXES and joined(i + 1):
                i += 1
                value *= _SUFFIXES[words[i]]
            yield text[start : tokens[i].end()], value
            i += 1
            continue
        total = current = 0.0
        end: int | None = None
        j = i
        while j < len(tokens) and (j == i or joined(j)):
            word = words[j]
            following = words[j + 1] if j + 1 < len(tokens) else ""
            if word in _UNITS and current % 10 == 0 and (current % 100 == 0 or _UNITS[word] < 10):
                current += _UNITS[word]
            elif word in _TENS and current % 100 == 0:
                current += _TENS[word]
            elif word == "hundred":
                current = (current or 1) * 100
            elif word in _SCALES:
                total += (current or 1) * _SCALES[word]
                current = 0
            elif word == "a" and end is None and following in ("hundred", *_SCALES):
                pass  # "a hundred", "a million"
            elif word == "and" and end is not None and following in _NUMBER_WORDS:
                pass  # "a hundred and twenty"
            else:
                break
            if word not in ("a", "and"):
                end = tokens[j].end()
            j += 1
        if end is None:
            i += 1
        else:
            yield text[start:end], total + current
            i = j


def unsaid_numbers(summary: Summary, said: str) -> list[str]:
    """The numbers in the summary that aren't in what was said, as the summary wrote them."""
    texts = [
        summary.overview,
        *summary.key_points,
        *summary.decisions,
        *(f"{item.task} {item.due or ''}" for item in summary.action_items),
        *(f"{detail.subject or ''} {detail.quote}" for detail in summary.details),
    ]
    return unsaid_numbers_in(texts, said)


def unsaid_numbers_in(texts: Sequence[str], said: str) -> list[str]:
    heard = {round(value, 6) for _, value in numbers(said)}
    unsaid: list[str] = []
    for text in texts:
        for written, value in numbers(text):
            # Allows for a scale said once for a range: "eighty to ninety thousand" is
            # 80 and 90,000, and "$80-90k" is 80 and 90,000.
            candidates = {round(value * scale, 6) for scale in (1, 1e3, 1e-3, 1e6, 1e-6)}
            if value >= SMALLEST_CHECKED and not candidates & heard and written not in unsaid:
                unsaid.append(written)
    return unsaid


def verify_details(details: Sequence[Detail], transcript: str) -> None:
    """Quotes must belong to one turn by their stated speaker, not to meeting metadata."""
    turns = parse_turns(transcript)
    problems = [
        f"details.{index}.quote was not found verbatim under speaker {detail.speaker!r}"
        for index, detail in enumerate(details)
        if not any(
            turn.speaker == detail.speaker
            and (
                (detail.start == turn.start and detail.quote == turn.text)
                if detail.start is not None
                else " ".join(detail.quote.split()) in " ".join(turn.text.split())
            )
            for turn in turns
        )
    ]
    # The writer cannot fix these labels: they are attached unchanged after it finishes.
    for index, detail in enumerate(details):
        if unsaid := unsaid_numbers_in([detail.subject or ""], transcript):
            problems.append(
                f"details.{index}.subject contains numbers nobody said: {', '.join(unsaid)}"
            )
    if problems:
        raise SummaryError(
            "Couldn't verify quoted details: "
            + "; ".join(problems)
            + ". Copy continuous excerpts from the stated speaker, keeping wording and punctuation."
        )
