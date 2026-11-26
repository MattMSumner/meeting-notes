"""Transcriber backed by NVIDIA Parakeet running on MLX (Apple Silicon)."""

# parakeet_mlx ships without type information.
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false

from pathlib import Path
from typing import Any

from meeting_notes.transcript import Segment

# Long recordings are transcribed in overlapping chunks to bound memory use.
CHUNK_SECONDS = 120.0
OVERLAP_SECONDS = 15.0
# Parakeet splits sentences only at punctuation, so a segment can run across long pauses
# (one 9 s segment held two words) and through the other side's turn, putting answers
# ahead of their questions. Splitting at pauses lets the turns interleave.
PAUSE_SECONDS = 1.0


def _split_at_pauses(tokens: list[Any]) -> list[list[Any]]:
    """A sentence's tokens, split wherever a word starts after a pause.

    Tokens are word pieces, and a word's first piece starts with a space. parakeet-mlx's
    own silence_gap splits between any two pieces, so a hesitation mid-word ("Fri... day")
    would split the word across two turns. Punctuation is often timed at the end of the
    pause ("so the plan <pause>. We ship"), so it stays with the words before it and the
    split comes at the next word."""
    groups = [[tokens[0]]]
    paused = False
    for previous, token in zip(tokens, tokens[1:], strict=False):
        if token.start - previous.end >= PAUSE_SECONDS and not token.text[:1].isalnum():
            paused = True
        if paused and token.text.startswith(" "):
            groups.append([])
            paused = False
        groups[-1].append(token)
    return groups


def _local_model_dir(model: str) -> Path:
    """The model's folder in the Hugging Face cache, downloading it only if it's missing.

    Loading by repo id would contact Hugging Face on every run to check for updates.
    Loading from the cached folder keeps transcription fully offline."""
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError

    try:
        return Path(snapshot_download(model, local_files_only=True))
    except LocalEntryNotFoundError:
        print(f"Downloading {model} (one time only)...")
        return Path(snapshot_download(model))


class ParakeetTranscriber:
    def __init__(self, model: str) -> None:
        self._model_name = model
        self._model: Any = None

    def transcribe(self, audio: Path) -> list[Segment]:
        if self._model is None:
            # Imported lazily: loading MLX is slow and tests don't need it.
            from parakeet_mlx import from_pretrained

            self._model = from_pretrained(str(_local_model_dir(self._model_name)))
        result = self._model.transcribe(
            audio, chunk_duration=CHUNK_SECONDS, overlap_duration=OVERLAP_SECONDS
        )
        segments: list[Segment] = []
        for sentence in result.sentences:
            for tokens in _split_at_pauses(sentence.tokens):
                text = "".join(str(token.text) for token in tokens).strip()
                words = [token for token in tokens if any(c.isalnum() for c in token.text)]
                if words:
                    # Ends at the last word: punctuation can be timed at the end of a pause.
                    segments.append(Segment(float(words[0].start), float(words[-1].end), text))
        return segments
