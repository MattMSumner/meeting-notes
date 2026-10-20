"""Records with the real notes-capture while speech plays. Run with:
    uv run pytest -m integration

Needs NotesCapture.app built (capture/install.sh) with its permissions granted, and opens
the mic. Best run with Bluetooth headphones connected: opening their mic is what used to
silence the system audio tap. Never runs in CI."""

import json
import subprocess
import threading
import wave
from array import array
from math import sqrt
from pathlib import Path

import pytest

from meeting_notes.config import DEFAULT_CAPTURE
from meeting_notes.recorder import CaptureRecorder

pytestmark = pytest.mark.integration

RECORD_SECONDS = 12
SPEECH = " ".join(
    f"This is sentence number {i} of the capture test. The quick brown fox jumps over the dog."
    for i in range(1, 6)
)


def rms_per_second(path: Path) -> list[float]:
    with wave.open(str(path)) as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (16_000, 1, 2)
        samples = array("h", wav.readframes(wav.getnframes()))
    return [
        sqrt(sum(s * s for s in samples[i : i + 16_000]) / 16_000) / 32_768
        for i in range(0, len(samples) - 16_000 + 1, 16_000)
    ]


@pytest.mark.skipif(not DEFAULT_CAPTURE.is_file(), reason="run capture/install.sh first")
def test_system_audio_keeps_flowing_while_the_mic_is_open(tmp_path: Path):
    speech = tmp_path / "speech.aiff"
    subprocess.run(["say", "-v", "Samantha", "-o", str(speech), SPEECH], check=True)
    player = subprocess.Popen(["afplay", "-v", "0.2", str(speech)])
    try:
        stop = threading.Event()
        threading.Timer(RECORD_SECONDS, stop.set).start()
        CaptureRecorder(DEFAULT_CAPTURE).record(tmp_path, stop)
    finally:
        player.terminate()

    channels = json.loads((tmp_path / "capture.json").read_text())["channels"]
    assert not channels["me"]["all_zero"]
    assert not channels["them"]["all_zero"]
    # The bug this guards against: opening an idle Bluetooth headset's mic switches it into
    # call mode, and the tap went silent for the rest of the recording while playback
    # carried on. notes-capture now rebuilds the tap, so expect at most a short gap
    # around the switch, and audio again by the end.
    levels = rms_per_second(tmp_path / "them.wav")
    assert len(levels) >= RECORD_SECONDS - 2
    silent = [level <= 0.001 for level in levels]
    longest_gap = max(
        (len(run) for run in "".join("x" if s else " " for s in silent).split()), default=0
    )
    assert longest_gap <= 2, levels
    assert not any(silent[-3:]), levels
