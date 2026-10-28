# Notes for coding agents

meeting-notes is a local-first meeting notetaker for macOS. [README.md](README.md) covers
setup and usage. [plan.md](plan.md) has the decisions, the milestones and a dated "Built"
note for each finished one, so read it before starting a milestone.

## How it fits together

- `capture/`: the Swift `notes-capture` tool (built into `NotesCapture.app`). It records
  two channels, `me.wav` (the mic) and `them.wav` (system audio), and writes `capture.json`
  with each channel's start offset.
- `src/meeting_notes/parakeet.py`: transcribes each channel with Parakeet (parakeet-mlx)
  into `segments.<channel>.json`, splitting sentences at pauses.
- `merge.py`: interleaves both channels by start time, joins a speaker's consecutive
  segments into turns and splits long turns into paragraphs.
- `ollama.py`, `summary.py`, `prompts/summary.md`: the summary, from Ollama (`qwen3:30b`)
  as JSON matching the `Summary` model. `figures.py` finds numbers in the summary that
  nobody said, which get one retry and then a warning in the note.
- `pipeline.py`, `render.py`: write the note and transcript into the Obsidian vault.
- `store.py`: each meeting's folder in
  `~/Library/Application Support/meeting-notes/meetings/<id>/`.
- `cli.py`: `uv run notes ...`.

## Checks

Run all of these before committing. CI runs the same ones on `macos-15`
(`.github/workflows/ci.yml`).

```sh
uv run ruff format
uv run ruff check
uv run pyright            # strict
uv run pytest             # unit tests only
capture/test.sh           # Swift tests, when capture/ changes
```

`uv run pytest -m integration` runs tests that need the real models (Parakeet, Ollama with
`qwen3:30b`) or audio hardware. They're slow, they never run in CI, and the Ollama ones vary
from run to run, so run them a few times before trusting a change in result.

## Privacy: this repo is public

- Never commit recordings, transcripts, summaries, or names or details from real
  meetings. That includes plan.md, commit messages, PR descriptions and test names.
- Test fixtures stay synthetic (`tests/fixtures/` has made-up transcripts).
- To check a change against real meetings, read their folders with a script kept outside
  the repo (`segments.*.json` have the transcriptions), and report counts only, such as
  "turns over 60 s: 4 → 0".

## Conventions

- Match the surrounding code: plain names, short docstrings and comments that say why,
  and tests named after the behavior they check.
- parakeet_mlx has no type stubs. Files that import it start with a
  `# pyright: reportMissingTypeStubs=false` pragma.
- Keep plan.md changes in their own commits, titled "Plan: ...". When a milestone is built,
  add a dated "Built" note under it with what was learned (counts only).
- Work on a branch per milestone and open a PR. `gh` is signed in as the owner, so start
  every GitHub comment, review or PR description with a line saying which agent wrote it,
  such as "🤖 **Codex**:", then a blank line.
- When the owner says "shipit", run `git shipit` from the feature branch. That alias
  merges the branch into main, pushes, and deletes the branch locally and on GitHub,
  which closes the PR. Don't merge on GitHub.

## Things learned the hard way

- Parakeet tokens are word pieces, and a word's first piece starts with a space.
  Punctuation is often timed at the end of a pause, so segments end at their last word,
  not their last token.
- A summary prompt change that looks better on one run can be run-to-run noise. Compare
  on the integration tests over several runs.
- A bigger model (qwen3:32b) wasn't more accurate on numbers and was about 4× slower.
  Fix number mistakes with checks in code, not by changing the model.
