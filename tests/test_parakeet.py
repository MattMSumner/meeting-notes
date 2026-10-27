"""ParakeetTranscriber with a fake model that splits sentences at punctuation like Parakeet."""

# parakeet_mlx ships without type information.
# pyright: reportMissingTypeStubs=false

from pathlib import Path
from typing import Any

import pytest
from parakeet_mlx.alignment import AlignedToken, sentences_to_result, tokens_to_sentences

from meeting_notes.merge import SpeakerTrack, merge
from meeting_notes.parakeet import CHUNK_SECONDS, OVERLAP_SECONDS, ParakeetTranscriber
from meeting_notes.transcript import Segment


def tokens(*words: tuple[str, float]) -> list[AlignedToken]:
    """Words starting at the given times, each lasting 0.3 s."""
    return [AlignedToken(id=0, text=text, start=start, duration=0.3) for text, start in words]


class FakeModel:
    def __init__(self, heard: list[AlignedToken]) -> None:
        self.heard = heard
        self.options: dict[str, Any] = {}

    def transcribe(self, audio: Path, **options: Any) -> Any:
        self.options = options
        return sentences_to_result(tokens_to_sentences(self.heard))


def transcribe(heard: list[AlignedToken]) -> list[Segment]:
    transcriber = ParakeetTranscriber("unused")
    transcriber._model = FakeModel(heard)  # pyright: ignore[reportPrivateUsage]
    return transcriber.transcribe(Path("me.wav"))


def test_transcribes_long_recordings_in_overlapping_chunks():
    model = FakeModel(tokens((" hi", 0.0)))
    transcriber = ParakeetTranscriber("unused")
    transcriber._model = model  # pyright: ignore[reportPrivateUsage]

    transcriber.transcribe(Path("me.wav"))

    assert model.options == {"chunk_duration": CHUNK_SECONDS, "overlap_duration": OVERLAP_SECONDS}


def test_splits_a_sentence_at_a_long_pause():
    # Unpunctuated, as Parakeet sometimes returns long stretches.
    segments = transcribe(tokens((" so", 0.0), (" the", 0.4), (" plan", 3.0), (" works", 3.4)))

    assert [s.text for s in segments] == ["so the", "plan works"]
    assert [(s.start, s.end) for s in segments] == [
        (0.0, pytest.approx(0.7)),
        (3.0, pytest.approx(3.7)),
    ]


def test_still_splits_at_punctuation():
    segments = transcribe(tokens((" done.", 0.0), (" next", 0.4)))

    assert [s.text for s in segments] == ["done.", "next"]


def test_never_splits_a_word_at_a_pause():
    # "Fri" and "day" are pieces of one word: only a word's first piece starts with a space.
    segments = transcribe(tokens((" on", 0.0), (" Fri", 0.4), ("day", 2.0), (" then", 4.0)))

    assert [s.text for s in segments] == ["on Friday", "then"]


def test_punctuation_timed_after_a_pause_stays_with_the_words_before_it():
    # "," isn't followed by a space, so tokens_to_sentences doesn't split there itself.
    segments = transcribe(tokens((" so", 0.0), (" yes", 0.4), (",", 2.0), (" Friday", 2.1)))

    assert [s.text for s in segments] == ["so yes,", "Friday"]
    assert segments[0].end == pytest.approx(0.7)  # "yes" ends then; "," is timed at 2.0


def test_keeps_a_sentence_together_across_short_pauses():
    segments = transcribe(tokens((" so", 0.0), (" the", 0.9), (" plan", 1.8)))

    assert [s.text for s in segments] == ["so the plan"]


def test_an_answer_no_longer_comes_before_its_question():
    # I start talking, pause while they ask a question, then answer it.
    mine = transcribe(tokens((" right", 0.0), (" so", 0.4), (" yes", 4.0), (" Friday", 4.4)))
    theirs = [Segment(1.5, 3.5, "When does it ship?")]

    lines = merge([SpeakerTrack("Me", 0.0, mine), SpeakerTrack("Them", 0.0, theirs)])

    assert [(line.speaker, line.text) for line in lines] == [
        ("Me", "right so"),
        ("Them", "When does it ship?"),
        ("Me", "yes Friday"),
    ]
