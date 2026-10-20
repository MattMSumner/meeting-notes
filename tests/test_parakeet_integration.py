"""Transcribes real speech with the real model. Run with: uv run pytest -m integration

Needs macOS (`say`), ffmpeg, and the model (downloaded on first run). Never runs in CI."""

import subprocess
from pathlib import Path

import pytest

from meeting_notes.config import DEFAULT_MODEL
from meeting_notes.parakeet import ParakeetTranscriber

pytestmark = pytest.mark.integration

SCRIPT = (
    "Let's ship the notetaker on Friday. "
    "Alex owns the calendar integration, and we decided to use Parakeet for transcription."
)


def speak(text: str, path: Path) -> Path:
    # The default system voice can be a Siri voice, which can't render to a file.
    subprocess.run(
        [
            "say",
            "-v",
            "Samantha",
            "--file-format=WAVE",
            "--data-format=LEI16@16000",
            "-o",
            str(path),
            text,
        ],
        check=True,
    )
    return path


def test_transcribes_speech_with_timestamps(tmp_path: Path):
    segments = ParakeetTranscriber(DEFAULT_MODEL).transcribe(speak(SCRIPT, tmp_path / "me.wav"))

    text = " ".join(s.text for s in segments).lower()
    for word in ["ship", "notetaker", "friday", "alex", "calendar", "parakeet", "transcription"]:
        assert word in text
    assert segments[0].start < 1.0
    assert all(s.start <= s.end for s in segments)
