"""ParakeetTranscriber with a fake model; the sentence splitting is parakeet-mlx's own."""

# parakeet_mlx ships without type information.
# pyright: reportMissingTypeStubs=false

from pathlib import Path
from typing import Any

import pytest
from parakeet_mlx.alignment import AlignedToken, sentences_to_result, tokens_to_sentences

from meeting_notes.merge import SpeakerTrack, merge
from meeting_notes.parakeet import ParakeetTranscriber
from meeting_notes.transcript import Segment


def tokens(*words: tuple[str, float]) -> list[AlignedToken]:
    """Words starting at the given times, each lasting 0.3 s."""
    return [AlignedToken(id=0, text=text, start=start, duration=0.3) for text, start in words]


class FakeModel:
    def __init__(self, heard: list[AlignedToken]) -> None:
        self.heard = heard

    def transcribe(self, audio: Path, **options: Any) -> Any:
        config = options["decoding_config"].sentence
        return sentences_to_result(tokens_to_sentences(self.heard, config))


def transcribe(heard: list[AlignedToken]) -> list[Segment]:
    transcriber = ParakeetTranscriber("unused")
    transcriber._model = FakeModel(heard)  # pyright: ignore[reportPrivateUsage]
    return transcriber.transcribe(Path("me.wav"))


def test_splits_a_sentence_at_a_long_pause():
    # Unpunctuated, as Parakeet sometimes returns long stretches.
    segments = transcribe(tokens((" so", 0.0), (" the", 0.4), (" plan", 3.0), (" works", 3.4)))

    assert [s.text for s in segments] == ["so the", "plan works"]
    assert [(s.start, s.end) for s in segments] == [
        (0.0, pytest.approx(0.7)),
        (3.0, pytest.approx(3.7)),
    ]


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
