import struct
import wave
from pathlib import Path

from meeting_notes.wavfile import repair_wav_header

SAMPLES = struct.pack("<8000h", *range(-4000, 4000))  # 0.5 s of 16 kHz mono


def write_wav(path: Path, junk: bool = False) -> None:
    """A 16-bit mono WAV, optionally with the JUNK chunk AVAudioFile writes before fmt."""
    fmt = struct.pack("<HHIIHH", 1, 1, 16_000, 32_000, 2, 16)
    chunks = b""
    if junk:
        chunks += b"JUNK" + struct.pack("<I", 28) + bytes(28)
    chunks += b"fmt " + struct.pack("<I", len(fmt)) + fmt
    chunks += b"data" + struct.pack("<I", len(SAMPLES)) + SAMPLES
    path.write_bytes(b"RIFF" + struct.pack("<I", 4 + len(chunks)) + b"WAVE" + chunks)


def break_header(path: Path) -> None:
    """What a killed recording leaves: sizes from when the file was created."""
    raw = bytearray(path.read_bytes())
    raw[4:8] = struct.pack("<I", 4088)
    data_at = raw.index(b"data")
    raw[data_at + 4 : data_at + 8] = struct.pack("<I", 0)
    path.write_bytes(bytes(raw))


def frames(path: Path) -> int:
    with wave.open(str(path)) as wav:
        return wav.getnframes()


def test_repairs_sizes_from_the_file_length(tmp_path: Path):
    path = tmp_path / "them.wav"
    write_wav(path, junk=True)
    break_header(path)
    assert frames(path) == 0

    assert repair_wav_header(path)

    assert frames(path) == 8000
    with wave.open(str(path)) as wav:
        assert wav.readframes(8000) == SAMPLES


def test_drops_a_partly_written_last_frame(tmp_path: Path):
    path = tmp_path / "me.wav"
    write_wav(path)
    break_header(path)
    with path.open("ab") as wav:
        wav.write(b"\x01")  # killed mid-sample

    repair_wav_header(path)

    assert frames(path) == 8000


def test_leaves_a_good_file_unchanged(tmp_path: Path):
    path = tmp_path / "me.wav"
    write_wav(path)
    before = path.read_bytes()

    assert not repair_wav_header(path)
    assert path.read_bytes() == before


def test_ignores_files_that_are_not_wavs(tmp_path: Path):
    path = tmp_path / "me.wav"
    path.write_bytes(b"fake audio")

    assert not repair_wav_header(path)
    assert path.read_bytes() == b"fake audio"
