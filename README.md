# meeting-notes

A local-first meeting notetaker for macOS. It records both sides of a call (your mic and
the computer's audio), transcribes them on-device with NVIDIA Parakeet (via MLX), summarizes
the conversation with a local model served by [Ollama](https://ollama.com), and writes a
note and its transcript into an Obsidian vault. No audio, transcripts or summaries leave
the machine.

Status: **M10 implementation**, explicit notes-guided enhancement.
Quality evaluation has failed; M10 is not yet built. The original manual Obsidian workflow passed,
but the new validation failure/review-warning workflow still needs acceptance. See [plan.md](plan.md)
for the roadmap.

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

For meeting titles from your calendar, sync it to macOS: System Settings → Internet
Accounts → add your Google account with only Calendars on (no calendar app needed). The
first recording asks for Calendars access for NotesCapture.

Get consent from everyone in a meeting before recording it.

## Usage

### From Spotlight

```sh
uv run scripts/install-shortcuts.py
```

This adds three shortcuts (confirm each import in Shortcuts, and allow them to run scripts
when asked). Run the installer from your configured terminal: it captures supported
`MEETING_NOTES_*` settings and PATH, including Homebrew tools. The launchers use plain
`/bin/sh` without reading interactive shell startup files. Reinstall after changing settings;
delete existing copies first to avoid duplicate shortcuts. Run them from Spotlight by name:

- **Start meeting notes** asks for a title, suggesting the meeting on your calendar now
  (empty means Untitled), and starts recording in the background. The orange and purple menu bar indicators show it's recording.
- **Stop meeting notes** stops capture and writes the transcript in the background,
  then reports ready to enhance.
- **Enhance meeting notes** lists ready meetings newest first, including previously
  enhanced ones. Choose one to enhance in the background and open its summary in a new
  Obsidian tab. Cancel does nothing. Reinstall shortcuts to add this action.

Recordings stop automatically after **one hour**, including those started from Spotlight.
At the limit, capture closes cleanly, transcription runs, and a background recording reports
that it reached the limit. Enhancement still requires an explicit action. To choose a different
positive, finite limit, set `MEETING_NOTES_MAX_RECORDING_SECONDS` before starting (for example, `5400`
for 90 minutes). Reinstall shortcuts from that configured terminal to save an override.
`notes record --duration SECONDS` can shorten a recording but cannot exceed the configured cap.

### From a terminal

```sh
uv run notes start --title "Weekly Sync"    # record in the background
uv run notes status                         # what's recording or being written
uv run notes stop                           # stop; the note is written in the background
uv run notes record --title "Weekly Sync"   # or: record in the foreground
uv run notes transcribe <meeting-id>        # re-transcribe; clear generation; ready to enhance
uv run notes enhance <meeting-id>           # snapshot writing and generate a summary
uv run notes summarize <meeting-id>         # alias for enhance
uv run notes enhance --choose               # chooser; detached enhancement
uv run notes render <meeting-id>            # re-write the note and transcript
uv run notes check                          # check the mic and system audio can be recorded
```

Starting through Spotlight or `notes record` creates a separate `_handwritten.md` file
beside the generated summary and opens it in a new Obsidian tab. Write ordinary bullets
or prose below its title and links. The summary and transcript links become available
after processing; no placeholder files are created. The generated summary links back to
your writing. The notes directory must belong to an existing Obsidian vault.

Enhancement reads your associated handwritten file once, preserving exact UTF-8 text,
and saves both the original and the effective input (without recognized generated title
and link lines). It builds the model transcript from stored segments, with your speaker
name substituted; editing the vault transcript does not change that input. Missing,
unreadable or invalid UTF-8 handwritten files must be restored before enhancement.
Renamed or moved handwritten files are not tracked. Older meetings with no associated
path, blank writing, and untouched templates use transcript-only enhancement.

Your writing is never rewritten. Notes guide emphasis; Decisions and Action items remain
spoken commitments. Written-only observations and tasks appear under **From your notes**.
**Conflicts** identifies both sources without resolving them. Number warnings check each
section against its assigned saved evidence, distinguishing other-source numbers and
metadata; presence checks cannot establish correct attribution or meaning.

Stop, foreground recording completion, recovery, and `transcribe` never invoke the summary
model. Successful transcription clears the prior generated result and evidence and writes
“ready to enhance” at the summary path. Edited vault files remain protected, with a warning
that the status note was not published. No-speech meetings retain your writing and cannot
be enhanced. Each meeting permits only one processing command at a time.

Enhancement atomically saves the summary and evidence in a versioned `summary.json`.
Failures preserve the previous result; re-enhancement takes a fresh snapshot. `render`
uses saved evidence, so deleting or changing the original writing after enhancement does
not change the result or its warnings. If an edited summary prevents publication, the
result is saved internally and the shortcut does not open the old file as the new result.
Move the protected file aside and run `notes render <meeting-id>` to publish it.

If a recording's process dies (a crash, a restart), `notes status` says so and `notes stop`
recovers it: it stops the orphaned capture and writes the note from what was recorded.
Recovery retains a stopping session until the capture helper is confirmed gone. Interrupted
recovery stays retryable. Repeated Stop commands wait for active recovery without interrupting
it, including the handoff from foreground capture to transcription. Stop reports failure if
a competing recovery leaves capture unresolved instead of treating the attempt as success.
Start rechecks for unfinished capture before creating a meeting, including orphaned
sessions; foreground recording also refuses until they are recovered. Malformed
sessions and missing or damaged meeting metadata do not prevent capture shutdown; notifications
fall back to the meeting ID. Missing metadata may still need repair before processing audio.
The automatic recording timer runs in Python; a surviving helper after a process crash is
handled by this recovery path.
A crashed enhancement does not automatically rerun or transcribe; retry with
`notes enhance <meeting-id>`. Background jobs log to `notes.log` in the meeting's folder.

Each meeting gets a folder of audio and intermediate files in
`~/Library/Application Support/meeting-notes/meetings/<meeting-id>/`. The note goes to
`~/development/notes/meetings/YYYY-MM-DD_<title>_<HHMM>.md` and links to its transcript in
`~/development/notes/meetings/transcripts/`. If you edit either file in Obsidian, re-running
a stage leaves it alone rather than overwriting your changes.

In the transcript, short acknowledgments that overlap the other speaker appear inline,
with their own speaker and timestamp. Standalone replies stay separate, and the summary
model still receives the original turns. Run `notes render <meeting-id>` to apply this
formatting to an older meeting's stored segments, without transcribing or summarizing again.

Settings are environment variables:

| Variable | Default |
|---|---|
| `MEETING_NOTES_MAX_RECORDING_SECONDS` | `3600` (one-hour recording cap) |
| `MEETING_NOTES_DATA_DIR` | `~/Library/Application Support/meeting-notes/meetings` |
| `MEETING_NOTES_NOTES_DIR` | `~/development/notes/meetings` |
| `MEETING_NOTES_MODEL` | `mlx-community/parakeet-tdt-0.6b-v2` (speech to text) |
| `MEETING_NOTES_MY_NAME` | first name on your macOS account (what the summary calls you) |
| `MEETING_NOTES_SUMMARY_MODEL` | `qwen3:30b` (Ollama) |
| `MEETING_NOTES_NUM_CTX` | `32768` (tokens; must fit both sources, prompt, schema, corrections and reply) |
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

The frozen M10 comparison and manual rubric are in [evaluation/m10/README.md](evaluation/m10/README.md).
The [v1 scored report](evaluation/m10/results/report.md) preserves the completed comparison.
Agree on a budget and repetitions before running a new freeze.

The first frozen comparison failed conflict qualification. A revised prompt/schema candidate
is frozen in [evaluation/m10/v2/](evaluation/m10/v2/README.md). Its
[scored rerun](evaluation/m10/v2/results/report.md) improved conditional due phrasing but
still failed conflicts and introduced unsupported task deadlines. M10 remains unbuilt.

The [v3 candidate](evaluation/m10/v3/README.md) adds evidence references and validation.
Its [first-stage evaluation](evaluation/m10/v3/results/report.md) published only 5/13 summaries;
eight cases remained blocked after correction. The staged run stopped after one repetition,
using 38 requests across both arms. The model proposes claims with exact source spans;
code checks references, compiles known conflicts into neutral core references, and keeps
both full accounts under Conflicts. Automatic deadlines require a complete trailing timing
phrase from the same statement as that task. Other timing exchanges are quoted in review
warnings without assigning a deadline. These conservative checks may withhold valid timing;
real citations still do not prove correct meaning or detect every omitted conflict.

The [V4 candidate](evaluation/m10/v4/README.md) uses direct source references. Code assembles
source-worded tasks and conservative owners; uncertain deadlines appear for review beside
the action with no assigned due value. Task details are confined to Action items. V4 has
completed its [one-repetition evaluation](evaluation/m10/v4/results/report.md): nine of
13 proposed summaries were generated, four blocked, and the later-timing answer was lost.
The run used 36 requests across both arms. Quality acceptance failed; compilation and
review warnings alone do not establish useful or complete output. New saves use wrapper version 3; existing version-2 saves retain their original
validation rules.

The [V5 candidate](evaluation/m10/v5/README.md) binds source-ID enums into each request,
uses an explicit source for timing quotes, ignores redundant self-context, and neutralizes
redundant known-conflict prose before source-kind rejection. Unassigned timing evidence
survives in review when action prose is suppressed. Unknown or unrelated wrong-source
references still fail. Its [one-repetition evaluation](evaluation/m10/v5/results/report.md)
produced 12/13 proposed summaries using 27 requests across both arms, but failed quality
acceptance: a revised date becomes the task, a release decision moves into unrelated timing
review, and conflict neutralization removes an undisputed price. Sparse notes still block.
V5 saves use wrapper version 4, while prior versions retain their original validators.

The [V6 candidate](evaluation/m10/v6/README.md) preserves unaffected facts from mixed prose
as attributed source quotes and stops inferring timing links from shared prose. Original
commitments and later timing updates are separate references; backwards updates fail.
Updates remain unassigned with source evidence for review. Source coordinates stay in the
audit rather than model input. [Offline replay](evaluation/m10/v6/replay/README.md) restores
the release decision and monitoring cost. The [V6 evaluation](evaluation/m10/v6/results/report.md)
used 28 requests and produced 12/13 summaries, but still failed quality: additional notes
accompany a missing spoken commitment, and later timing blocks after correction. The targeted
V5 losses improved in this pass; current manual acceptance remains pending. New saves use wrapper
version 5, with the original V5 validator retained for version-4 saves.

The [V7 candidate](evaluation/m10/v7/README.md) accepts a unique exact timing quote from a
later transcript source as unverified review evidence, never an assigned deadline. A narrow
first-person task-verb diagnostic flags missing actions for the existing bounded correction;
it does not generate actions or prove completeness. [Offline replay](evaluation/m10/v7/replay/README.md)
recovers the later-Friday review and detects the omitted task. The [V7 evaluation](evaluation/m10/v7/results/report.md)
produced all 13 summaries using 28 requests across both arms. Correction restored the missing
task, and no critical proposed failures or commitment regressions were observed. It meets the
frozen single-run criteria; this is not a reliability estimate, and current manual acceptance
remains pending.
V7 introduced wrapper version 6; version-5 saves retain the original V6 rules.

The [V8 request representation](evaluation/m10/v8/README.md) shares source-ID enum definitions
and uses compact, separately labelled source rows. It preserves every source while fitting
larger transcripts at the unchanged context size. Full request-size checks still apply before
initial and correction requests. The output contract and saved validators are unchanged;
The [V8 evaluation](evaluation/m10/v8/results/report.md) used 29 requests across both arms
and produced 11/13 proposed summaries. Two cases timed out, and another lost an independent
release agreement: V8 fails its single-run criteria. A fresh [PR review](evaluation/m10/v8/results/pr-review.md)
also found two recovery defects and a timing-qualifier defect; the follow-up fixes below
address these reproduced bugs.
M10 remains unbuilt pending quality evaluation and current manual acceptance.

The [V9 candidate](evaluation/m10/v9/README.md) uses one flat source-ID vocabulary, retaining
runtime source-kind checks. Narrow diagnostics flag uncited explicit agreements and conflicts
that mix tasks with other statements; correction must resolve them without inventing content.
The [V9 evaluation](evaluation/m10/v9/results/report.md) produced all 13 summaries using 26
requests across both arms, with no timeouts or corrections. The release agreement survives and
the status conflict excludes the verification task. It still fails quality: the shared-numbers
case presents both support prices without identifying their disagreement. This one run does
not establish the cause of the prior timeouts or reliability on new inputs. M10 remains unbuilt.

Recovery retains a stopping session until the detached capture helper is confirmed stopped.
Malformed session files have a stable recovery identity, and session discovery works even
without meeting metadata. Title lookup falls back to the meeting ID, so damaged metadata
cannot prevent shutdown. Interrupted recovery remains retryable and blocks a concurrent
recording start. The Enhance
chooser skips unreadable meetings with a warning, allowing healthy meetings to remain available.

The next offline candidate adds a separate comparison before summary generation when notes
are present. It partitions every note passage into claims and records consistent, additional,
conflicting or uncertain outcomes against exact source quotes. Code checks text coverage and
references, assembles conflicts and shows uncertainty in review warnings. Claim splitting,
subject identity and semantic classification still need quality evaluation; full text coverage
alone does not prove all disagreements were recognized.

Comparison and summary generation each allow one correction, for at most four requests with
notes (two initial, two correction), or two without notes. Transport failures do not retry.
Every request includes the complete sources, schema, settings and stage correction history;
the summary request also includes the comparison. Requests that exceed the existing conservative
context estimate fail before sending; inputs are never truncated or chunked. The extra stage
adds sequential inference latency. Its cost and evaluation budget require separate approval
before live runs; the prior V9 budget does not authorize this candidate.

Unresolved blocking errors leave the previous successful summary/evidence untouched. Drafts,
requests, replies and validation findings are saved locally under the meeting's `attempts/`
folder. Both stages' attempts, selections and saved passages accompany successful results in
summary wrapper version 9 / grounding-v8. Rendering replays comparison and compilation from
saved evidence, with no model call or rereading of original notes. Versions 1–8 retain their
original validators.
Partial timing quotes that leave qualifiers or timing behind in the task retain the whole
commitment under Review required, with no assigned deadline. Complete quotes preserve those
qualifiers. Version-6 and version-7 saves retain their original compilers for reproducible rendering.
Older summaries and version 1 wrappers remain readable. Abrupt process termination can
prevent the current audit from being finalized; it does not automatically retry generation.
Numeric warnings now use each claim's cited spans and remain visible from the saved audit.
The evaluator records every sent request/reply as well as the selected validation attempt.
