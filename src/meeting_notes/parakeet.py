"""Transcriber backed by NVIDIA Parakeet running on MLX (Apple Silicon)."""

# parakeet_mlx ships without type information.
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false

from pathlib import Path
from typing import Any

from meeting_notes.transcript import Segment

# Long recordings are transcribed in overlapping chunks to bound memory use.
CHUNK_SECONDS = 120.0
OVERLAP_SECONDS = 15.0


class ParakeetTranscriber:
    def __init__(self, model: str) -> None:
        self._model_name = model
        self._model: Any = None

    def transcribe(self, audio: Path) -> list[Segment]:
        if self._model is None:
            # Imported lazily: loading MLX is slow and tests don't need it.
            from parakeet_mlx import from_pretrained

            self._model = from_pretrained(self._model_name)
        result = self._model.transcribe(
            audio, chunk_duration=CHUNK_SECONDS, overlap_duration=OVERLAP_SECONDS
        )
        return [
            Segment(start=float(s.start), end=float(s.end), text=str(s.text).strip())
            for s in result.sentences
            if str(s.text).strip()
        ]
