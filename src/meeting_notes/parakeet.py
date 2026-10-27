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
        from parakeet_mlx import DecodingConfig, SentenceConfig

        result = self._model.transcribe(
            audio,
            chunk_duration=CHUNK_SECONDS,
            overlap_duration=OVERLAP_SECONDS,
            decoding_config=DecodingConfig(sentence=SentenceConfig(silence_gap=PAUSE_SECONDS)),
        )
        return [
            Segment(start=float(s.start), end=float(s.end), text=str(s.text).strip())
            for s in result.sentences
            if str(s.text).strip()
        ]
