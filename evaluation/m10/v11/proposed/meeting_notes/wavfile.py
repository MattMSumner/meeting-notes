"""Repairs WAV headers left unfinished when a recording is killed or crashes.

A WAV's header records the size of its audio data, and notes-capture only writes the
final sizes when it stops cleanly. If it's killed, the audio is all there but the header
says the file is nearly empty. ffmpeg works around that; most other tools don't."""

import struct
from pathlib import Path


def repair_wav_header(path: Path) -> bool:
    """Sets the RIFF and data chunk sizes from the file's actual length.

    Returns True if the header was changed. Leaves files that aren't WAVs alone."""
    with path.open("r+b") as wav:
        data = wav.read(12)
        if len(data) < 12 or data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
            return False
        file_size = wav.seek(0, 2)

        # Walk the chunks (fmt, JUNK, ...) to find "data", which runs to the end of the file.
        offset = 12
        block_align = 1
        while offset + 8 <= file_size:
            wav.seek(offset)
            chunk_id, chunk_size = struct.unpack("<4sI", wav.read(8))
            if chunk_id == b"fmt ":
                block_align = struct.unpack("<H", wav.read(14)[12:14])[0] or 1
            if chunk_id == b"data":
                data_size = file_size - (offset + 8)
                data_size -= data_size % block_align  # drop a partly written last frame
                changed = chunk_size != data_size
                wav.seek(offset + 4)
                wav.write(struct.pack("<I", data_size))
                wav.seek(4)
                riff_size = file_size - 8
                changed |= struct.unpack("<I", data[4:8])[0] != riff_size
                wav.write(struct.pack("<I", riff_size))
                return changed
            offset += 8 + chunk_size + (chunk_size % 2)  # chunks are padded to even sizes
        return False
