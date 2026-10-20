# meeting-notes

A local-first meeting notetaker for macOS. It records a meeting, transcribes it on-device
with NVIDIA Parakeet (via MLX), and writes markdown into an Obsidian vault. No audio or
transcripts leave the machine.

Status: **M1**, which records the mic only. See [plan.md](plan.md) for the roadmap, and
for the system audio spike in [`spike/`](spike/).

## Setup

Needs an Apple Silicon Mac, [uv](https://docs.astral.sh/uv/) and ffmpeg:

```sh
brew install uv ffmpeg
uv sync
```

The first transcription downloads the model (`mlx-community/parakeet-tdt-0.6b-v2`) from
Hugging Face. After that, everything runs offline.

## Usage

```sh
uv run notes record --title "Weekly Sync"   # record the mic until Ctrl-C, then transcribe
uv run notes transcribe <meeting-id>        # re-run transcription for a meeting
uv run notes render <meeting-id>            # re-write the transcript into the vault
```

Each meeting gets a folder of audio and intermediate files in
`~/Library/Application Support/meeting-notes/meetings/<meeting-id>/`. The transcript goes to
`~/development/notes/meetings/transcripts/YYYY-MM-DD_<title>_<HHMM>_transcript.md`.

Override locations with `MEETING_NOTES_DATA_DIR`, `MEETING_NOTES_NOTES_DIR` and
`MEETING_NOTES_MODEL`.

## Development

```sh
uv run pytest                  # unit tests (fast, no model or audio needed)
uv run pytest -m integration   # real model on speech generated with `say`; never runs in CI
uv run pyright                 # strict type checking
uv run ruff check . && uv run ruff format --check .
```
