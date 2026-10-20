"""Records the default microphone to a WAV file until stopped.

M1 only: M2 replaces this with the Swift notes-capture binary, which records the mic and
the system audio tap together."""

# sounddevice and soundfile ship without complete type information.
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportMissingParameterType=false

import threading
from pathlib import Path
from typing import Protocol

import sounddevice as sd
import soundfile as sf


class Recorder(Protocol):
    def record(self, path: Path, stop: threading.Event) -> None:
        """Records to path until stop is set."""
        ...


class MicRecorder:
    def record(self, path: Path, stop: threading.Event) -> None:
        # Record at the device's own rate; transcription resamples to 16 kHz.
        device = sd.query_devices(kind="input")
        sample_rate = int(device["default_samplerate"])
        with sf.SoundFile(
            path, mode="w", samplerate=sample_rate, channels=1, subtype="PCM_16"
        ) as wav:

            def write(indata, frames, time, status) -> None:
                wav.write(indata.copy())

            with sd.InputStream(
                samplerate=sample_rate, channels=1, dtype="float32", callback=write
            ):
                stop.wait()
