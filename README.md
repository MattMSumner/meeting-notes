# meeting-notes

A local-first meeting notetaker for macOS. It records both sides of a call (your mic and
the computer's audio), transcribes them on-device with NVIDIA Parakeet (via MLX), summarizes
the conversation with a local model served by [Ollama](https://ollama.com), and writes a
note and its transcript into an Obsidian vault. No audio, transcripts or summaries leave
the machine.

Status: **M3**, summaries. See [plan.md](plan.md) for the roadmap.

## Setup

Needs an Apple Silicon Mac, [uv](https://docs.astral.sh/uv/), ffmpeg and Ollama:

```sh
brew install uv ffmpeg ollama
brew services start ollama
ollama pull qwen3:30b      # ~19 GB
uv sync
capture/install.sh         # builds and signs NotesCapture.app, then checks it can record
```

The first transcription downloads the speech model (`mlx-community/parakeet-tdt-0.6b-v2`)
from Hugging Face. After that, everything runs offline.

Get consent from everyone in a meeting before recording it.

## Usage

```sh
uv run notes record --title "Weekly Sync"   # record until Ctrl-C, transcribe, summarize
uv run notes transcribe <meeting-id>        # re-run transcription (and the summary)
uv run notes summarize <meeting-id>         # re-run the summary
uv run notes render <meeting-id>            # re-write the note and transcript
uv run notes check                          # check the mic and system audio can be recorded
```

Each meeting gets a folder of audio and intermediate files in
`~/Library/Application Support/meeting-notes/meetings/<meeting-id>/`. The note goes to
`~/development/notes/meetings/YYYY-MM-DD_<title>_<HHMM>.md` and links to its transcript in
`~/development/notes/meetings/transcripts/`. If you edit either file in Obsidian, re-running
a stage leaves it alone rather than overwriting your changes.

Settings are environment variables:

| Variable | Default |
|---|---|
| `MEETING_NOTES_DATA_DIR` | `~/Library/Application Support/meeting-notes/meetings` |
| `MEETING_NOTES_NOTES_DIR` | `~/development/notes/meetings` |
| `MEETING_NOTES_MODEL` | `mlx-community/parakeet-tdt-0.6b-v2` (speech to text) |
| `MEETING_NOTES_MY_NAME` | first name on your macOS account (what the summary calls you) |
| `MEETING_NOTES_SUMMARY_MODEL` | `qwen3:30b` (Ollama) |
| `MEETING_NOTES_NUM_CTX` | `32768` (tokens; must fit the whole transcript) |
| `MEETING_NOTES_SUMMARY_THINK` | `1` (let the model reason first; `0` for models that can't) |
| `MEETING_NOTES_OLLAMA_URL` | `http://localhost:11434` |

The summary prompt is in [`src/meeting_notes/prompts/summary.md`](src/meeting_notes/prompts/summary.md).

## Development

```sh
uv run pytest                  # unit tests (fast, no model or audio needed)
uv run pytest -m integration   # real models and audio hardware; never runs in CI
uv run pyright                 # strict type checking
uv run ruff check . && uv run ruff format --check .
```
