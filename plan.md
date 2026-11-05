# Meeting Notetaker — Plan

A personal, local-first meeting notetaker for macOS. It's a CLI that records my mic and the
other side of a call, transcribes locally after the meeting, summarizes with a local model,
and writes an Obsidian-friendly markdown note.

Status: **M8 shipped**. M9 and M10 implementations are present; manual Obsidian
acceptance was reported complete for M10. Its frozen quality evaluation failed; M10 remains unbuilt.
No model calls are authorized as part of this implementation.
Phase 0 (Handy) set up.

---

## Decisions so far

| Topic | Decision | Notes |
|---|---|---|
| Glue language | **Python** (uv, pytest, Pydantic, pyright) | Best local-ML libraries and fastest iteration. Go and Rust were considered; see "Glue language" |
| Native macOS code | **Swift** helper binary | Core Audio taps + EventKit (calendar) |
| Glue ↔ Swift | **Subprocess**, JSON lines on stdout | No FFI |
| System audio | **Core Audio process taps** | Narrowest permission; no change to audio routing |
| Which audio to tap | **All system output** (global tap) | Simplest option, and it avoids the Chrome helper-process problem. Cost: notification sounds and anything else playing get recorded too. An exclude list can come later |
| Speaker separation | Mic = "me", tap = "them" | I always wear headphones, so the mic won't pick up the other side; no echo cancellation needed |
| Transcription | **Parakeet Unified EN 0.6B** (Apr 2026, English only, what Handy now lists first), via `parakeet-mlx` if it supports it | Not verified yet: whether `parakeet-mlx` supports Unified (an RNN-T model, not TDT) and whether it returns timestamps. Fallbacks: Parakeet TDT 0.6B v2/v3 via `parakeet-mlx`, then Whisper |
| Summary model | **Ollama** (or `mlx-lm` in-process), ~30B-class model, 4-bit | 1 hour max ≈ 10–15k tokens, so a single pass is enough and no chunking is needed |
| Meeting title | **Calendar** (EventKit), with `--title` override | Fallback: `untitled-HHMM` |
| Notes output | `~/development/notes/meetings/` (Obsidian vault; folder created, vault README updated) | Named `YYYY-MM-DD_<title>_<HHMM>.md`, following the vault's `granola-notes/` convention. YAML frontmatter, attendees, tags. The tool writes only inside this folder |
| Transcripts | Separate files in `meetings/transcripts/`, named `…_transcript.md`, linked from the note | The `_transcript` suffix keeps Obsidian wikilink names unique |
| Browser | Chrome | |
| Audio retention | **Keep everything** | So each stage can be re-run while iterating |
| Terminal | Ghostty | Permissions will likely be granted to Ghostty |
| Meeting length | Mostly 30 min, max 1 hour | |

---

## Glue language: Go vs Rust vs Python (decided: Python)

All three options keep the macOS-specific work (Core Audio, EventKit) in a small Swift
binary, and the glue language runs it as a subprocess. So this choice only affects
orchestration, transcription, the LLM call, and text/markdown output.

| | Go | Rust | Python |
|---|---|---|---|
| New typed language to show off | ✅ New to me, typed | ✅✅ New to me; the strongest type system | ❌ Familiar territory; types are optional hints (pyright/mypy) |
| Learning curve | Gentle: productive within days | Steep: borrow checker, lifetimes, error types | Minimal |
| Type safety where it matters (pipeline state, LLM JSON) | OK: structs, but nil, no sum types | Excellent: `enum` states, `serde` validates the LLM's JSON at the boundary | Good *in practice* with Pydantic, but only checked at runtime |
| Local Parakeet/Whisper | Shell out to `whisper-cli` (cgo bindings exist but are painful) | `transcribe-cpp` (Handy uses it) or `whisper-rs`; C++ builds when you install | ✅✅ `parakeet-mlx`: prebuilt, fastest on Apple Silicon |
| Local LLM | Ollama over HTTP (trivial) | Ollama over HTTP (trivial) | Ollama *or* `mlx-lm` in-process |
| Subprocesses + signals (start/stop capture) | ✅✅ Excellent and simple | ✅ Good | ✅ Fine |
| Testing / TDD | Built-in `go test`, table tests; interfaces make fakes easy | Built-in `cargo test`; fakes need traits (more boilerplate) | ✅✅ pytest + fixtures: the best of the three |
| Prompt iteration speed | Fast compiles | Slowest (compile times) | ✅✅ Fastest |
| Distribution | Single binary | Single binary | `uv tool install`: fine for a personal tool |
| Reference code | — | Handy is Rust | Most open-source notetakers are Python |
| Biggest risk | Ending up shelling out for every interesting step, so the Go is mostly plumbing | Time spent fighting the language/build instead of the problem | Nothing new to learn, so less fun |

**How to choose:**
- **If learning a typed language is a main goal → Rust.** Its type system pays off for
  pipeline state and LLM output validation, and Handy gives you working reference code
  for transcription. Budget extra time for M1.
- **If you want an easier new language and the most finished tool for the effort → Go.**
  This tool is mostly "run processes, move files, make one HTTP call", which is Go's sweet
  spot. Transcription would shell out to `whisper-cli`.
- **If you want the best ML and the fastest iteration → Python.** But it doesn't meet the
  "new language" goal.

**Decision: Python.** To get some of the typed-language benefits anyway: type-check with
pyright in strict mode, validate the LLM's JSON with Pydantic models, and represent
pipeline state with enums and dataclasses.

---

## Architecture

**Implemented workflow (M10 quality/manual acceptance pending):**

```
notes start / record
  ├─ create and open handwritten note in Obsidian
  └─ record me.wav + them.wav and capture offsets
notes stop / foreground completion / recovery / transcribe
  ├─ transcribe usable channels → segments.*.json
  ├─ clear saved generation and evidence
  └─ render transcript and ready-to-enhance status (preserve edited vault files)
notes enhance <id> / summarize <id> / enhance --choose
  ├─ claim meeting; reject incomplete, no-speech or busy meetings
  ├─ snapshot handwritten bytes, effective text, segment transcript and context
  ├─ generate with separately labelled sources → source-specific number checks
  ├─ atomically replace versioned summary.json (summary + evidence)
  └─ render; Spotlight notifies and opens a newly published summary in a new tab
notes render <id>
  └─ use saved generation/evidence; never reread original handwritten file
```

A nonblocking per-meeting lock serializes processing; short global claims coordinate
session ownership. An `enhancing` crash requires explicit `notes enhance <id>` retry.
Legacy flat summaries and meetings with no handwritten-path metadata remain supported.

**Each stage reads the previous stage's files and writes its own**, so any stage can be
re-run on its own:

```
~/Library/Application Support/meeting-notes/meetings/2026-10-17-1400-weekly-sync/
  meeting.json        # times, calendar event, attendees
  me.wav  them.wav    # ~115 MB/hour each at 16 kHz/16-bit; FLAC later if disk matters
  segments.me.json  segments.them.json
  capture.json        # channel start offsets and capture results
  summary.json
```

Audio and intermediate JSON stay **out of the Obsidian vault**, which keeps sync and search
fast. Only the note and its transcript go into the vault, as separate files: the note links
to the transcript with a wikilink, and the transcript links back to the note. The tool
writes vault files only inside `~/development/notes/meetings/`; audio and intermediate
files live in the application-support folder above.

Current CLI usage (see [README.md](README.md) for setup and Spotlight shortcuts):

```
notes start [--title T]
notes stop
notes status
notes record [--title T]        # foreground capture; Ctrl-C ends the meeting
notes transcribe <meeting-id>   # re-transcribe; ready to enhance
notes enhance   <meeting-id>   # explicit generation
notes enhance --choose         # chooser and detached worker
notes summarize  <meeting-id>
notes render     <meeting-id>
```

Configuration uses the environment variables documented in [README.md](README.md).
Keep the shipped models and settings: Parakeet TDT 0.6B v2, Ollama `qwen3:30b`,
`num_ctx=32768` and thinking enabled. All processing stays local.

Handwritten notes remain separate files. Successful enhancement saves exact source inputs
alongside its summary. Later rendering uses that evidence even if the handwritten file
changes or disappears. A missing associated handwritten file prevents new inference.
Summary/Decisions/Action items remain grounded in speech; optional From your notes and
Conflicts sections separate written-only material and unresolved accounts.

### Core generated Obsidian note shape (optional M10 sections follow Action items)

```markdown
---
date: 2026-10-17
time: "14:00"
title: Weekly Sync
attendees: [Alex, Sam]
tags: [meeting]
source: meeting-notes
---
## Summary
Overview, followed by key-point bullets.
## Decisions
## Action items
- [ ] Owner — task (due if mentioned)

Transcript: [[2026-10-17_Weekly Sync_1400_transcript]]
```

---

## Riskiest piece: system audio from a CLI → Spike first

**The risk:** if a Core Audio tap's permission is missing, every API call still succeeds
but the buffers are all zeros. The permission is tied to an `NSAudioCaptureUsageDescription`
Info.plist key. A bare CLI needs that plist embedded with
`-sectcreate __TEXT __info_plist`. The grant probably lands on Ghostty, the responsible
process, rather than on the binary.

**Why the global tap makes this easier:** tapping *all* system output avoids having to find
Chrome's audio helper processes. The tap doesn't include mic input, so my voice isn't
recorded twice. The global tap should exclude `notes-capture` itself.

**Spike (throwaway, about half a day):** a Swift CLI of roughly 150 lines that:
1. Starts the mic (AVAudioEngine), then creates a global tap on all system output (excluding
   itself) behind a private aggregate device.
2. Writes `me.wav` and `them.wav` for 30 seconds.
3. Prints the loudness (RMS) of each channel every second, so zeros are obvious right away.

**It passes when:** run from Ghostty, it shows signal on both channels for (a) a Zoom test
meeting and (b) a YouTube or Meet tab in Chrome; the permission prompt appears; and I know
which app the grant attached to (Ghostty or the binary).

References to read before writing it: Apple's "Capturing system audio with Core Audio taps"
sample, and open-source tap tools on GitHub (e.g. AudioCap, audiotee).

### Spike results (2026-10-20, `spike/` on branch `spike/system-audio-tap`)

**Passed:** recorded mic + global tap from Ghostty with real signal on both channels
(98.5% non-zero samples on the tap), at the correct rate (47,805 frames per second measured
against 48,000 expected).

What I learned:
1. **When launched from a terminal, macOS attributes permission checks to the terminal
   app.** The mic prompt named Ghostty and worked. The system-audio request was denied
   silently, with **no prompt and no error, only zeros**, because Ghostty doesn't declare
   `NSAudioCaptureUsageDescription`. The `Info.plist` embedded in the binary was ignored.
2. **Fix: relaunch with responsibility disclaimed.** The binary re-runs itself via
   `posix_spawn` + `responsibility_spawnattrs_setdisclaim` (private API, also used by
   Chromium, Qt and LLDB). macOS then treats `tapspike` as the requesting app, uses its
   embedded `Info.plist`, and shows prompts that name it. CLI behavior (stdout, Ctrl-C)
   is unchanged. Fallback if this API ever breaks: a minimal `.app` bundle launched with
   `open`.
3. **The audio must be timed from the built-in output, not the default device.** With
   Bluetooth headphones whose mic is in use, they switch to call mode (24 kHz) while the
   tap still reports 48 kHz. The first run, timed from the headphones, delivered about
   22.5k frames per second instead of 48k. Timing from `BuiltInSpeakerDevice` fixed it.
4. **Formats differ per channel:** mic = 1 ch, 24 kHz (Bluetooth call mode); tap = 2 ch,
   48 kHz interleaved float. `notes-capture` should resample both to 16 kHz mono for
   transcription.
5. **Timing:** no startup delay when audio is already playing. The tap delivers from the
   first second, and **keeps delivering zero-filled buffers through silence** (paused the
   video for 6 s: `SILENT`, not `no data`), so `them.wav` stays on real time (19.95 s for a
   20 s run). Unverified: in runs where nothing was playing at start, the tap sent *no
   buffers* until audio began, so it may only start once something plays. `notes-capture`
   should still record each channel's first-sample host time (`AudioTimeStamp.mHostTime` /
   `AVAudioTime.hostTime`) and align the merge on it, padding the later channel's start
   with silence.
6. **The Bluetooth mic delivers silence for about 1 s at the start** (likely while it
   switches into call mode). Harmless, but start the mic before the meeting begins.

7. **A bare binary with an ad-hoc signature is too fragile an identity for macOS's
   system-audio permission.** After a code change (new build hash) it was silently
   refused again: a fresh prompt and grant still gave zeros, it never appeared in System
   Settings, and `tccutil` couldn't reset it (not registered with Launch Services).
8. **Fix: a minimal signed `.app`.** `spike/build.sh` builds `TapSpike.app` (with
   `CFBundleExecutable`, `LSUIElement`), signs it with a self-signed certificate
   (`scripts/create-signing-cert.sh`, no Apple developer account or Xcode needed), and
   registers it with `lsregister`. Its signing requirement is then "this identifier + this
   certificate" rather than one build's hash. A `spike/tapspike` wrapper `exec`s the
   binary inside the bundle, so CLI use is unchanged. Result: after a real code change
   and rebuild, system audio worked; the grant took effect in the same run; `tccutil
   reset AudioCapture com.mattmsumner.tapspike` works.
9. **Channel start offset:** the first samples were 26.7 ms apart on the host clock
   (tap after mic), measured with `AVAudioTime.hostTime` and `AudioTimeStamp.mHostTime`.

10. **Zoom (real call, 30 s, taking turns): passed.** While I talked, "them" sat at about
    -88 dB (Zoom's noise floor; no echo of my voice). While she talked, "me" dropped to
    about -60 dB. Zoom sends a faint background noise through silence (99.9% non-zero),
    so the tap timeline stays continuous. Start offset was 22.2 ms. Zoom and the spike
    shared the mic without problems.

11. **With the signed `.app`, the first run after any rebuild records zeros, then every
    run works.** Tested by rebuilding with unchanged source and a new build hash: no
    prompt, the permission still shown as on in System Settings, first run 0.0% non-zero,
    second run 99.2% non-zero. The earlier "prompt after rebuild" run fits the same
    pattern (its output wasn't checked; the next run worked). Without the signed `.app`,
    rebuilds were silently denied every time (finding 7).

**Design consequences for `notes-capture`:**
- Ship it as a signed `.app` (stable identity) with the relaunch-with-responsibility-
  disclaimed trick.
- Add a `notes-capture check` command: start the tap, play a short quiet sound from a
  *separate* process (the tap excludes its own process), and confirm the samples aren't
  zero. Retry once, since the first run after a rebuild records zeros. Any prompt also
  happens here, not in a meeting.
- The install/build script runs `notes-capture check` straight after every rebuild, so
  that throwaway first run never happens during a meeting.
- While recording, warn loudly if the tap channel is all zeros for more than a few
  seconds.

---

## Milestones

Every milestone ends with something I can run and tests that pass.

**M0 — Spike** (above). Throw it away afterwards, but keep the notes on what worked.

**M1 — Mic-only, end to end.** `notes record` (Ctrl-C to stop) records the mic,
then transcribes and writes `transcript.md` to the notes folder.
- Set up the project: uv, pytest, pyright (strict), and a `notes` entry point.
- Transcription: Parakeet Unified EN 0.6B if `parakeet-mlx` (or another MLX/Core ML
  runtime) can run it with timestamps, otherwise Parakeet TDT 0.6B v2. Put it behind a
  `Transcriber` protocol so other models can be swapped in for comparison.
- Tests: fixture WAVs generated with `say -o fixture.wav --data-format=LEI16@16000 "..."`.
  Assert the transcript contains the key words. Unit-test the filename/slug logic.
- **Done (2026-10-20).** What I learned:
  - **Parakeet Unified has no MLX conversion** (Hugging Face only has NeMo, GGUF for
    transcribe.cpp, ONNX/sherpa-onnx and Core ML versions). Using **TDT 0.6B v2** via
    `parakeet-mlx`. Unified via sherpa-onnx is a possible later experiment behind
    `Transcriber`.
  - **Speed:** 72 s of audio transcribed in 1.3 s, model load 0.4 s once cached.
  - **Accuracy on my voice:** very good. Errors are mostly product/proper names
    ("Claude" → "Word", "Antique" for a product name), an occasional dropped or misheard
    word ("rate" → "race"), British spellings, and numbers written as words. Names point
    to the vocabulary prompt on the M12 list.
  - **Fully offline:** loading by repo id contacted Hugging Face on every run. It now
    loads from the local cache and only downloads if the model is missing (verified with
    network access blocked).
  - **Stopping:** Claude Code's `!` mode kills the command rather than sending Ctrl-C,
    which left a WAV with a zero-length header and no transcript. Now SIGINT, SIGTERM
    and SIGHUP all stop cleanly; `--duration` stops on its own; the WAV header is
    flushed every 5 s, so a killed recording is still valid.
  - **`say` fixtures need a named voice** (`-v Samantha`): the default voice can be a Siri
    voice, which renders an empty file.
  - **The Bluetooth mic records at 24 kHz** here too. Fine: ffmpeg resamples to 16 kHz for
    the model.

**M2 — Two channels.** Build `notes-capture` in Swift, properly this time (it reuses what
the spike learned), plus the glue code's subprocess wrapper and the time-merge into Me/Them.
- Tests: the merge is a pure function with lots of unit tests (overlapping, interleaved,
  and empty channels). Integration test: run capture while `afplay`ing a fixture, then assert `them.wav` isn't silent.
- Spike findings → tests. Build `notes-capture` test-first against these:

  | Finding | How it's tested |
  |---|---|
  | Clock from the built-in output, not the default (Bluetooth) device | **Unit:** device selection as a pure function over a fake device list (Bluetooth default + built-in speakers) |
  | Channels start ~25 ms apart; align on first-sample host time | **Unit:** alignment and silence padding with exact timestamps |
  | Mic is 24 kHz mono, tap is 48 kHz stereo; both go to 16 kHz mono | **Unit:** resample a known tone and check its length and pitch |
  | The tap can be silently all zeros | **Unit:** zero detector. **Integration:** `notes-capture check` (play a sound from a separate process, assert it's captured) |
  | The first run after a rebuild records zeros | **Build script:** runs `notes-capture check` after every rebuild, retrying once |
  | Responsibility disclaim, signed `.app`, real Zoom call | **Manual release checklist** (depends on macOS permissions, real devices and a real call) |

  Integration tests and the manual checklist run only on my Mac, never in CI: CI runners
  have neither the permissions nor the audio hardware. Mark them so CI skips them.
- **Built (2026-10-20).** `capture/` Swift package (`CaptureCore` + `notes-capture record|check`),
  `capture/install.sh` (signed `NotesCapture.app` + check), Python `CaptureRecorder`, `merge`,
  `notes check`. What I learned:
  - **Idle AirPods break the tap.** Opening an idle Bluetooth headset's mic switches it into
    call mode (output 48 → 24 kHz, a few seconds of garbled playback). A tap that exists
    during the switch goes to **exact zeros** while playback carries on: in tests, after
    1–4 s and for the rest of the recording. Not every step is visible as a device event,
    and starting the mic before the tap did *not* fix it (I wrongly thought it had,
    because the bug only shows after the headset has been idle for a few minutes;
    back-to-back runs pass). **Fix:** rebuild the tap (a) 1.5 s after output-device changes
    settle and (b) whenever it has delivered exact zeros for 1 s (at most every 3 s;
    harmless when nothing is playing). `TapRebuildScheduler`, unit-tested. Result: one gap
    of about 1.25 s near the start, then continuous audio.
  - **An auto-started tap blocks other apps' Bluetooth mic (found 2026-10-21).** Joining
    Zoom after starting a recording hung Zoom: Core Audio timed out (`0x3C`, 14 s a try)
    starting its AirPods mic, over and over, until the recording stopped. Joining first
    worked. Tested with a stand-in for Zoom (a program opening the default input directly)
    against notes-capture variants: the tap alone, without our mic, blocks it; so do taps
    without drift compensation or without a clock device; a tap of no processes, or with
    `kAudioAggregateDeviceTapAutoStartKey` off, doesn't. **Fix:** auto-start off (our
    `AudioDeviceStart` runs the tap anyway). Checked both join orders with AirPods: the
    stand-in gets the mic at once and a test sound is recorded. AVAudioEngine's mic was a
    red herring: it does wrap the AirPods in an aggregate device, but two direct opens of
    the mic share it fine and the tap alone reproduces the hang.
  - **Gaps are filled by timestamp.** `ChannelWriter` places audio by host time and writes
    silence for gaps of 0.1 s or more, after draining the converter (which holds about
    75 ms back). It also accepts a format change mid-recording.
  - **Permission is checked asynchronously.** On a new build, the tap delivered real audio
    for about 2 s, then zeros until the (late-appearing) permission prompt was answered.
    `check` now lets the tap run 3 s before playing its test sound; before that it could
    pass inside the first window.
  - **The live warning covers zeros at any point**, not just from the start: 10 s of
    continuous exact zeros warns, and it says when audio comes back.
  - **The tap delivers nothing until something plays** (confirmed): a video started 7 s in
    gave `them` an offset of 7.17 s, and the transcript placed it correctly.
  - **Swift Testing works with only the Command Line Tools,** but the macro plugin isn't on
    the default search path: `capture/test.sh` passes `-plugin-path`.
  - **Manual checklist** (not automatable): first recording after the headset has been idle
    for 3 or more minutes; a real Zoom/Meet call; a rebuild followed by `notes check`.
  - **First real meeting (2026-10-20, 27 min Zoom): worked.** Both sides captured; the
    conversation interleaves correctly start to end (no drift). `them.wav` ended 7.8 s
    before `me.wav` only because nothing played after the call ended (the tap delivers
    nothing then); no audio was lost. Recognition errors were mostly company and product
    names, plus jargon like "eng" heard as "Edge", which supports the vocabulary prompt.
    **Real meetings are confidential: never commit them, excerpts, or details from them
    (including names in examples) to this public repo.** Committed fixtures stay synthetic.

**M3 — Summary.** Ollama call with an explicit `num_ctx` (32k; the default silently
truncates), prompt loaded from a file, JSON output validated against a struct, rendered to
markdown.
- Tests: a fake `Summarizer` for the pipeline tests; a test that parses the JSON (including
  malformed output → one retry → a readable error); one ignored-by-default test against a
  real model on a golden transcript.
- **Built (2026-10-20).** `notes summarize`, `OllamaSummarizer` (stdlib HTTP, Ollama's
  JSON-schema `format`, Pydantic validation, one retry), the note rendered beside its
  transcript with links both ways. What I learned:
  - **Model: `qwen3:30b`** (MoE, ~3B active, 18 GB) via Homebrew Ollama, on a 48 GB Mac.
    A 30-minute meeting summarizes in ~35–40 s; 32k context is plenty.
  - **Thinking mode is worth it.** Without it (4 s) the model invented decisions and left a
    named person's action item as "Them"; with it (16 s on the golden transcript) both were
    right. On by default, `MEETING_NOTES_SUMMARY_THINK=0` for models that can't think.
  - **Ollama truncates silently, and its counts don't show it:** with a 4k context, a 7.4k
    token transcript was cut to 2k and reported as 2k. So the size is estimated before
    sending (3 characters per token; measured ~3.5) plus 4k for the reply, and the summary
    fails with the `num_ctx` needed rather than summarizing part of the meeting.
  - **Edits in the vault are kept.** Each meeting folder records a hash of the files it
    wrote (`written.json`); re-running a stage leaves a file alone if it changed since.
    Files written before M3 have no hash, so they count as edited (move them away once).
  - **A failed summary still writes the note,** with a callout giving the retry command.
  - **Tell the model who "Me" is.** Labelled only "Me", the model guessed who that was:
    it sometimes credited what I said or agreed to do to another participant, or described
    me by a role instead of by name. My lines are now labelled with my name
    (`MEETING_NOTES_MY_NAME`, default the macOS account's first name) and the prompt says
    to always use it, which fixed both. Owners are named when the transcript says who the
    other person is ("Hey Alex"); "Them" otherwise.
  - **Quality on real meetings:** facts and numbers accurate and specific; misheard names
    pass straight through (vocabulary prompt, M12). But it **over-reads stance**: tentative
    remarks can come out as firm positions, even with a prompt rule against it. Asking for
    first person ("I") made things worse (it mixed "I" with third person), so it was
    dropped. Follow-up (M11): build a few synthetic transcripts with known-correct notes and
    compare prompts and models against them (e.g. a larger dense model), rather than tuning
    on real meetings by eye.
  - **Numbers it was never told (2026-10-22).** A real summary merged a total and one part of
    it into one range. On a synthetic version (`numbers_transcript.txt`) the model, every
    time, worked out a number nobody said (the rest of a total) and turned "definitely
    doable" into "the maximum". A prompt rule helped only 1 run in 3 and made it leave my
    name out of the overview; qwen3:32b (dense, 24 GB loaded, ~4× slower) was no better.
    So code checks instead: `figures.py` finds every number in the summary, in digits or
    words, and looks for it in what was said. Ollama gets one retry naming the unsaid
    numbers (it dropped them 3/3), and any left are flagged in the note. Stance
    ("doable" vs "maximum") and dropped figures are still open: a quoted list of figures
    in the schema, before the overview, was the original M9 proposal. That approach
    later failed acceptance and is parked (see the history below).

**M4 — Start/stop from Spotlight.** No terminal needed to record a meeting.
- `notes start [--title T]`: starts recording in the background and returns at once. It
  runs the existing record → transcribe → summarize → render flow detached, logging to the
  meeting folder, and records the running meeting in a state file.
- `notes stop`: tells the recording to stop; transcription and the summary then run in the
  background (about a minute for 30 minutes of audio).
- `notes status`: whether a meeting is recording, its title and how long it's been going.
- **Feedback:** macOS notifications when recording starts, when it stops, and when the
  note is ready (or failed, with the retry command). No auto-opening Obsidian. The
  system's orange (mic) and purple (system audio) menu bar indicators show it's live.
- **Triggers: Shortcuts, run from Spotlight.** "Start meeting notes" (asks for a title in a
  text box; empty means Untitled, and M5 will pre-fill it from the calendar) and "Stop
  meeting notes", each a "Run Shell Script" step calling the CLI. Found by typing their
  names in Spotlight, or a Quick Key. No global hotkey (nothing to clash with Ghostty or
  Handy) and no Raycast. A script installs them if Shortcuts can be scripted; otherwise
  written setup steps.
- **Check first (riskiest):** that a recording started from a shortcut survives the
  shortcut finishing, and that mic and system audio permission still go to
  NotesCapture.app (via the disclaim relaunch), not to Shortcuts.
- Crash safety: `notes status` reports, and `notes stop` recovers, a recording orphaned by a crash or
  reboot, using the WAV repair from M2.
- Not doing: a native Spotlight action (App Intents) in NotesCapture.app. Neater, but
  App Intents metadata needs a full Xcode build.
- Tests: state transitions (start while already recording, stop when nothing is
  recording, a stale state file after a crash, recovering an orphaned recording).
- **Built (2026-10-21).** `notes start` / `stop` / `status`, background `record` and
  `transcribe` jobs, `scripts/install-shortcuts.py`. What I learned:
  - **Shortcuts work as a launcher.** A "Run Shell Script" step runs under
    `ShortcutsMacHelper`; a process started with its own session outlives the shortcut,
    and notes-capture's disclaim relaunch keeps permissions with NotesCapture.app (no new
    prompts). Each shortcut asks once for permission to run scripts.
  - **Shortcuts can be generated:** a plist workflow signed with `shortcuts sign --mode
    anyone` imports with one click. No Xcode needed.
  - **Shortcut scripts get a bare environment,** so they run `notes` through `zsh -lic` to
    pick up Homebrew's PATH (ffmpeg) and `MEETING_NOTES_MY_NAME` from my shell config.
  - **State lives with each meeting** (`session.json`: pid, process start time, phase), so
    a meeting can be summarized while the next one records, and a crash leaves its marker
    next to the audio. The process start time guards against pid reuse after a reboot.
  - **Recovery tested for real:** after `kill -9` of the background job, notes-capture kept
    recording with nothing in charge; `notes stop` stopped it cleanly and wrote the note.
  - **The title dialog is the CLI's own** (`osascript display dialog`), not a Shortcuts
    step, so M5 can pre-fill it from the calendar.

- **Safeguard extraction (2026-11-12; PR pending):** extracted independently from the
  enhancement branch. Foreground/background capture gets a positive finite one-hour default
  cap; explicit duration can shorten but not exceed it. Automatic stop reports its reason and
  continues main's existing transcription and summary flow. Start/Stop shortcuts use a plain
  shell with installation-time settings and PATH, avoiding interactive startup errors.
  Recovery holds a durable stopping claim until helper exit is confirmed, including after
  forced shutdown; failures remain retryable. Stable corrupt-session identity, session-based
  discovery and fallback titles permit shutdown with damaged or missing metadata. Global
  locking covers only short claims, not shutdown waits. All 276 offline unit tests, formatting,
  lint and strict types pass. No capture or model changes, inference, recording or shortcut
  installation performed for this extraction. M10 remains separate and is not marked built.

- **Safeguard review fixes (2026-11-12; PR pending):** repeated Stop waits for a live
  stopping owner without sending another signal or stop request. Start rechecks all unfinished
  recording/stopping sessions under its final creation lock, including an orphan restored by
  interrupted competing recovery. Foreground recording uses the same unfinished-capture guard.
  Six synthetic regressions cover concurrent Stops during shutdown and before processing handoff,
  lost recovery claims, and foreground refusal. All 282 offline unit tests, formatting, lint
  and strict types pass. No capture/model changes or real recording used for verification.

- **Safeguard handoff review fixes (2026-11-12; PR pending):** ordinary recordings publish
  stopping state under the Stop signalling lock before restoring normal signal handlers.
  Repeated Stop therefore waits through the foreground processing handoff without another
  SIGINT. Stop rechecks unresolved orphan state after its recovery pass and after recovering
  an owner that died during the wait; a lost claim cannot imply success. Five new regression
  cases fail on the prior CLI and pass with the fixes. All 287 offline unit tests, formatting,
  lint and strict types pass. Synthetic fakes only; no capture or model changes.

- **Stop snapshot review fix (2026-11-12; PR pending):** Stop uses one unfinished-session
  snapshot for its orphan check and wait targets under the global lock. A recovery owner that
  dies after the liveness observation remains a wait target, so shutdown/handoff is attempted
  rather than reporting success from a second empty scan. Both new synthetic regression cases
  fail on the prior CLI and pass with the fix, covering successful recovery and retryable
  shutdown failure. All 289 offline unit tests, formatting, lint and strict types pass.
  The separate preexisting transcription-spawn failure gap remains outside this extraction.

**M5 — Calendar titles.**
- **Calendar source: Google Calendar, synced by macOS.** I use Google Calendar (personal
  Gmail) in the browser, not Apple's Calendar app. macOS can still keep a local copy:
  System Settings → Internet Accounts → Google, with only Calendars on. EventKit then reads
  it with no Google sign-in in our code, and works offline once synced. (Considered: the
  calendar's private iCal address, which needs recurring-event expansion and a secret URL
  kept safe; the Google Calendar API, which needs a Cloud project and OAuth. Fallbacks if
  sync doesn't work.)
- **Check first:** after adding the account, `notes-capture calendar` (EventKit, with
  Calendars permission going to NotesCapture.app via the disclaim relaunch) lists today's
  Google events with titles, times and attendees.
- `notes-capture calendar --from T --to T` prints events in a window as JSON (title,
  start, end, all-day, attendees, my response). Swift stays a thin reader; choosing the
  event is Python, so it's unit-tested.
- **Picking the meeting:** events happening now or starting within the next ~5 minutes;
  ignore all-day events and ones I've declined; prefer the one whose start is closest to
  now. Nothing found → no suggestion.
- **Using it:** the Start dialog is pre-filled with the event's title (still editable; an
  empty answer is Untitled). Attendees go into the note's frontmatter, and their names go
  to the summary prompt, which should help it name owners and spell names correctly.
- Tests: picking an event from fixture lists (overlapping events, back-to-back meetings,
  early start, no event, all-day and declined events ignored); the dialog default; the
  frontmatter.
- **Built (2026-10-21).** What I learned:
  - **Internet Accounts sync works for a personal Gmail calendar.** EventKit sees its
    events (and a shared family calendar) with titles, times and attendees, and marks
    which attendee is me (`isCurrentUser`), so declined meetings can be skipped. The
    Calendars permission prompt went to NotesCapture.app, as planned.
  - **Missing fields are left out, not null:** Swift's JSONEncoder omits nil optionals
    (an attendee without an email), so the Python side reads every field with a default.
  - **Back-to-back meetings:** "nearest start wins" means at 10:58 the 11:00 meeting is
    suggested over the 10:00 one that hasn't ended yet.
  - **An edited title keeps the attendees:** retitling in the dialog is still that
    meeting. Clearing it drops them: it's an unplanned call, not the calendar's meeting.
  - **Only people are attendees:** Google lists booked rooms and equipment as attendees.
  - **Reading the calendar is never allowed to block recording:** it times out after
    5 s (a permission prompt can hide behind other windows) and happens outside the
    start/stop lock.

**M6 — Turn order.** Found in the second real meeting. Parakeet's sentence segments can
run across long pauses (one 9 s segment held two words) and sometimes come back as a
single unpunctuated, lowercase block of 1½–2 minutes. A segment that starts before the
other speaker's question and continues after it sorts ahead of the question, so answers
appeared before the questions they answered, and merging same-speaker segments folded
interjections into one early-stamped block. The summary model reads the same order, so
this also muddles who said what. Fix: split segments wherever the gap between token
timestamps is ≥ ~1 s (each sentence carries per-token timings), before merging. Also try
a shorter `CHUNK_SECONDS` to see whether it brings back punctuation in the long blocks.
- **Built (2026-10-27).** `ParakeetTranscriber` splits each sentence wherever a word
  starts after a pause of 1 s or more (`PAUSE_SECONDS`), and ends each segment at its last
  word. What I learned, re-transcribing two real meetings (counts only):
  - parakeet-mlx's own `SentenceConfig(silence_gap=…)` splits between word pieces, so it
    can cut a word in two. It also leaves punctuation timed at the end of a pause (about
    a quarter of pauses) at the start of the next segment: 30 segments started with "."
    or "," and 14 were nothing else. Punctuation stays with the words before it instead,
    and a segment's end is its last word, not that late punctuation.
  - Segments over 20 s went from 11 to 2 and from 3 to 0; the longest from 60 s to 23 s.
  - Segments that run through the other side's turn went from 132 to 87 and 22 to 13
    (`silence_gap`: 108 and 19). The rest are mostly overlapping speech with no pause (a
    "yeah" mid-sentence), which splitting can't fix; M8 is for those.
  - 60 s chunks didn't help: the longest segment got longer in both meetings and
    punctuation was no better. Kept 120 s. Neither meeting had an unpunctuated 1½–2
    minute block, so that case is covered only by a synthetic test (`say` with a pause).
  - Only new transcriptions change. Older meetings keep their segments until
    `notes transcribe <id>` is run again.

**M7 — Paragraphs.** Found in the first real meeting: one turn was 2½ minutes in a single
block. Split long turns into paragraphs every 30–60 s, at sentence boundaries.
- **Built (2026-10-28).** `merge` starts a new line for the same speaker at the first
  sentence end once a paragraph has run 30 s, or before a segment that would take it past
  60 s. The transcript shows a continuing paragraph with its timestamp but not the
  speaker's name again. The summary model gets the turn as one line, so a long monologue
  doesn't read as several interjections. On
  three real meetings' stored segments (counts only): turns over a minute went from 4
  and 2 to none, and the longest from 142 s to 51 s. Paragraphs break only between
  segments, so one long unpunctuated segment (from before M6) still makes a 240-word
  paragraph; new transcriptions split at pauses first.

**M8 — Fold backchannels.** Found in the first real meeting: 155 turns in 27 minutes,
many of them one word. Fold short backchannels ("Yeah.", "Okay.") inline instead of giving
each its own turn.
- **Built (2026-10-28).** Short acknowledgment-only runs (at most 2 s and 3 words) fold
  inline when they fit entirely inside the preceding segment from the other speaker.
  Each aside keeps its words, speaker and timestamp, after the containing segment;
  questions, standalone replies and substantive interruptions stay separate. What I learned:
  - **Check whole runs before paragraphing:** a short acknowledgment at the start of a
    longer response must stay with that response. A fixed phrase list and full overlap
    favor leaving uncertain cases alone.
  - **Display and summary need separate views.** Only the readable transcript folds;
    the summary input and number checks retain the original turns. Paragraph breaks
    still depend on the main speaker's text and timing, not the asides.
  - **Read-only replay of 18 stored meetings (counts only):** 133 runs folded; displayed
    speaker changes 1,742 → 1,476 and paragraphs 1,989 → 1,747. No word, attribution or
    insertion-position failures; summary input unchanged byte-for-byte for all 18.
  - **No retranscription needed:** `notes render <id>` uses the saved segments and keeps
    existing summaries. Edited vault files are still left alone. Synthetic tests cover
    overlap boundaries, channel offsets, phrase matching, paragraphs and rerendering.

**Parked experiment (2026-11-03).** The former M9 quoted-figures approach failed
acceptance and remains unbuilt and unadopted. See the pushed
[experiment summary at `00b44a8`](https://github.com/MattMSumner/meeting-notes/commit/00b44a8).
Its implementation stays on the experiment branch; do not merge or cherry-pick it into
these milestones. M8 remains the shipped behavior.

**M9 — Take meeting notes in Obsidian.** Starting a meeting creates and opens a
handwritten note with the meeting title, links to the generated summary and transcript,
and an otherwise empty writing area. Plain bullets and prose need no special syntax.
Stopping still transcribes and automatically summarizes the transcript. Handwritten
notes are not model input in this stage.

- Create the handwritten file beside the summary with a `_handwritten.md` suffix. Keep
  existing summary and transcript filenames, and link the summary back to the writing.
  Create files exclusively and resolve filename collisions without overwriting. Persist
  the actual handwritten-note path with the meeting so later stages use the same file.
- Extend the desktop adapter in `macos.py` to open Obsidian's built-in open URI with an
  encoded absolute path. Use no Obsidian plugin or custom editor.
- Apply the same behavior to background `start` and foreground `record`, creating only
  one handwritten note per meeting. Failure to create or open it reports a clear warning
  without preventing audio capture.
- Never rewrite the handwritten file during stop, recovery, transcription, summarization
  or rendering. Preserve it even if capture fails or produces no speech. Historical
  meetings stay unchanged; absent handwritten-note metadata is valid for older meetings.
  Automatic discovery of renamed or moved handwritten files is outside this stage.
- **Validation:** unit-test creation, filename collisions, URI encoding, opening failures,
  background and foreground starts, recovery and preservation across reruns. Manually
  verify the Obsidian workflow with a synthetic meeting.
- **Acceptance:** the owner can start, type in Obsidian, stop, and find both their unchanged
  writing and the normal generated summary. Re-running existing stages cannot erase the
  writing. This is a planned milestone, not a Built note.

**M10 — Enhance notes with the transcript.** Make notes-guided enhancement explicit.
Stop (including the end of foreground recording) ends capture and transcribes, then reports
that the meeting is ready to enhance; it no longer automatically generates a summary.
Re-running transcription also leaves generation to the explicit enhancement action.

- Add an **Enhance meeting notes** Spotlight shortcut with a chooser of completed,
  transcribed meetings identified by title and time. Selection resolves to a stable
  meeting ID; cancellation does nothing. Add `notes enhance <meeting-id>` and retain
  `notes summarize <meeting-id>` as a compatible entry point to the same generation behavior.
- Snapshot the saved handwritten text when enhancement starts and store that exact input
  alongside the generated result. Later rendering uses the same evidence. Pass handwritten
  notes and transcript as separately labelled inputs; count both in context-size checks.
- Keep Summary, Key points, Decisions and Action items (M8 currently renders key points
  as bullets under Summary). Add separate sections for useful context found only in the
  handwritten notes and for conflicts between sources; omit those sections when empty.
  Notes guide emphasis, but omissions do not instruct the model to discard other important
  commitments. Do not silently turn personal observations into spoken agreements or choose
  between conflicting sources.
- Update number checking to distinguish written from spoken evidence. A handwritten number
  is neither automatically invented nor automatically supported by the transcript.
- Preserve the original handwritten file and existing protection for user-edited generated
  summaries. Empty notes permit transcript-only enhancement. A missing or unreadable
  previously associated note is an error, not permission to silently drop that input.
  Older meetings without note metadata remain readable and renderable without migration.
- **Validation:** test chooser cancellation and stable selection, exact input snapshots,
  empty versus missing or unreadable notes, source separation, context limits, number
  checks, preservation and backward compatibility. Manually verify enhancement with a
  synthetic meeting.
- **Quality acceptance:** before inference, freeze a bounded comparison covering sparse
  notes, empty notes, additional written context, conflicting facts and ambiguous dates.
  Passing that evaluation is a separate prerequisite for declaring M10 built; implementing
  the workflow alone is insufficient. This roadmap update authorizes no model calls.

- **Implementation (2026-11-03; not Built):** explicit enhancement, saved input wrappers,
  source-aware number checks, chooser, per-meeting serialization and unit coverage are
  implemented. Five synthetic comparison pairs, baseline source at `199dd62`, proposed
  prompt/schema/settings, guarded runner and manual rubric are frozen in `evaluation/m10/`.
  No model runs, quality scores or real-meeting evaluation were performed. Decide inference
  budget/repetitions separately. Quality evaluation and manual acceptance remain required.

- **Evaluation (2026-11-03; not Built):** user reported manual Obsidian acceptance
  complete. The approved five-case comparison ran three repetitions per arm (30 summaries,
  30 requests, no corrections/errors). Rubric review found critical conflict qualification
  failures in all three proposed conflict outputs; spoken commitments were preserved.
  Both arms weakened conditional due wording. Full synthetic evidence and per-repetition
  scores: [evaluation report](evaluation/m10/results/report.md). Quality acceptance failed;
  fixes require a new freeze and agreed rerun. No Built note or merge yet.

- **Revision (2026-11-04; not Built):** revised prompt and schema descriptions require
  unresolved conflict references in core sections and complete conditional due phrases.
  Added request-contract and saved-render regression checks. The original scored freeze
  is unchanged; `evaluation/m10/v2/` freezes the candidate with the same five pairs,
  baseline, settings and rubric. Versioned runner selection is available. No v2 inference
  has run; its rerun budget requires separate agreement. Quality acceptance remains failed
  for v1 and pending for v2; manual workflow acceptance was previously reported complete.

- **V2 evaluation (2026-11-04; not Built):** approved rerun produced 30 summaries
  using 32 requests, with no execution errors. Conditional due phrasing passed in 3/3
  proposed cases, but conflict qualification failed in 3/3 and unsupported task deadlines
  appeared in 2/3 empty-note outputs. Five proposed outputs have critical failures; M10
  remains unbuilt. [V2 scores and evidence](evaluation/m10/v2/results/report.md) preserve
  the run, corrections/observability limits and per-repetition assessment. No further
  prompt changes or inference were performed; any next candidate needs a new freeze.

- **Evidence-backed candidate (2026-11-04; not Built):** shared claim IDs and exact source
  spans replace freely repeated model prose. Code controls known-conflict placement,
  checks task-local timing and spoken owner evidence, and retains uncertain timing in
  review warnings. Blocking failures get one shared correction attempt, then preserve
  the prior result. Requests, replies, validation findings and selection are saved with
  successful generation or separately for failures; legacy wrappers still load.
  V3 freezes 13 synthetic cases (five unchanged, eight new) with the same baseline,
  model/settings and six-dimension rubric. Unit tests cover structural checks and saved
  audit rendering; they do not establish entailment or completeness. No v3 model runs
  have occurred. Choose a new inference budget before evaluation and check the new
  failure/review-warning behavior manually. V1/v2 failures remain recorded and unmodified.

- **V3 stage-one evaluation (2026-11-04; not Built):** approved three repetitions with
  a 234-request cap and first-pass quality gate. One repetition across 13 cases and both
  arms used 38 requests (13 baseline, 25 proposed). Baseline published 13/13; proposed
  published 5/13 and blocked 8/13 after correction, regressing commitment completeness.
  Stopped at the agreed gate; no remaining repetitions or candidate tuning. Task/timing
  text coupling and full-line note citations repeatedly prevent valid output; shared-number
  and status-conflict handling succeed in their single published cases. All attempts and
  [scores](evaluation/m10/v3/results/report.md) are preserved; freezes remain unchanged.
  A revised candidate needs a new freeze/budget and new failure/review-warning manual
  acceptance. M10 remains unbuilt.

- **V4 implementation (2026-11-05; not Built):** direct source IDs replace generated claim
  IDs. Code assembles tasks, conservative owners, complete trailing timing and inline review
  evidence. Task prose is suppressed elsewhere; handwritten facts receive sentence IDs.
  Wrapper version 3 preserves original validation for legacy saves. Offline replay of 25
  V3 attempts compiles 23, rejects two and produces review evidence in seven; these are
  not quality scores. A revised-date selection still loses the original commitment and
  leaves obsolete timing in prose. V4 freezes the same 13 cases and baseline/settings.
  No new inference; agree a separate budget and test the new manual review workflow.
  [Replay details](evaluation/m10/v4/replay/README.md) preserve limitations. M10 remains unbuilt.

- **V4 evaluation (2026-11-05; not Built):** approved one repetition across 13 cases and
  both arms, capped at 78 requests. Completed with 36 requests (13 baseline, 23 proposed).
  Baseline produced 13 summaries; V4 produced nine and blocked four. Later timing loses
  its answer; sparse notes omit a spoken cost; unnecessary review obscures simple deadlines.
  The original conflict case retains both accounts correctly in this single pass. Quality
  acceptance failed. [Full scores and attempts](evaluation/m10/v4/results/report.md) are
  preserved, with no tuning or extra inference. Frozen inputs and earlier results remain
  unchanged. Source-ID confusion, context misuse and timing loss need a new revision;
  agree its freeze/budget separately. M10 remains unbuilt, manual V4 acceptance pending.

- **V5 reference repair (2026-11-05; not Built):** explicit commitment IDs and source-bearing
  timing quotes replace overloaded strings; request schemas enumerate available IDs.
  Self-context no longer creates review, later timing evidence survives suppression when
  timing is unassigned, and known conflicts neutralize redundant cross-source prose.
  Unknown/unrelated references still block; valid IDs do not prove semantic selection.
  Wrapper version 4 preserves validation of earlier saves. Offline replay of 23 V4 attempts
  compiles 11, blocks nine and leaves three unmappable; four compiled attempts contain review.
  Revised-date references and missing context remain unresolved. V5 freezes the same inputs,
  baseline, settings and actual per-case schemas. No inference; budget and quality/manual
  acceptance remain separate. [Replay evidence](evaluation/m10/v5/replay/README.md).

- **V5 evaluation (2026-11-05; not Built):** requested one repetition across 13 cases and
  both arms under the same 78-request cap. Completed using 27 requests (13 baseline,
  14 proposed); proposed produced 12 summaries and one block. All proposed references
  conform to the recorded allowed-ID enums. Quality still fails: revised timing selects
  the correction as the task; compiler suppression moves a release decision into unrelated
  review and removes an undisputed price. Sparse also omits a commitment before blocking.
  Conditional timing, later-answer review and written context improve in this single pass.
  [Scores and audit evidence](evaluation/m10/v5/results/report.md) are preserved; no tuning
  or extra inference. Previous freezes/results are unchanged. M10 remains unbuilt; future
  revisions require a new freeze/budget and current review-workflow manual acceptance.

- **V6 compiler preservation (2026-11-05; not Built):** shared prose no longer creates
  timing links. Mixed items preserve unaffected sources as attributed quotes; disputed
  accounts remain unresolved. Original tasks and later timing updates have separate
  references, with backwards links rejected. Model-facing sources omit coordinates;
  saved audits retain them. Numeric correction cannot discard an existing update link.
  Wrapper version 5 preserves original V5/version-4 validation. Offline replay compiles
  11 of 14 saved responses: the release decision and monitoring cost survive, sparse stays
  blocked twice, and reversed timing now blocks instead of becoming a misleading task.
  [V6 freeze and replay](evaluation/m10/v6/README.md) retain the same 13 cases, baseline,
  rubric and settings. All 365 unit tests pass; no inference ran. Budget/repetitions remain
  unset. Semantic selection, completeness, quality and current manual acceptance still
  require evaluation. M10 remains unbuilt.

- **V6 evaluation (2026-11-05; not Built):** requested one repetition of all 13 cases in
  both arms under the same announced 78-request cap. Used 28 requests (13 baseline,
  15 proposed), producing 12 proposed summaries and one block. Release decision, monitoring
  cost, sparse-note completeness and original revised-date task survive in this pass.
  Quality still fails: additional context accompanies an omitted spoken review commitment;
  later timing identifies the correct sources but blocks on cross-statement initial timing
  after a failed correction. Budget conflict also includes an unrelated delivery source.
  [Scores and audit evidence](evaluation/m10/v6/results/report.md) preserve all outputs;
  all prior freezes/results remain unchanged. No tuning or extra inference. All 365 unit
  tests pass. Next design work should examine conservative timing normalization and explicit
  commitment coverage diagnostics offline. M10 remains unbuilt; future revisions need a
  new freeze/budget and current manual review-workflow acceptance.

- **V7 offline repair (2026-11-05; not Built):** exact unique timing quotes from later
  transcript sources become unverified review evidence, never assigned deadlines. A narrow
  first-person task-verb diagnostic flags omitted actions for the existing bounded correction,
  without inventing tasks; negation, uncertainty, quotations and nearby retractions are
  excluded. It does not establish completeness or classify all commitments. Numeric retries
  retain normalized timing links. Wrapper version 6 preserves V6/version-5 validation.
  [V7 freeze and replay](evaluation/m10/v7/README.md) compile 13 of 15 saved attempts:
  both later-timing drafts now review Friday; additional now blocks on the missing task;
  sparse's original invalid draft remains blocked. Same prompt/schema, 13 cases, baseline,
  rubric and model settings. All 395 unit tests pass. No inference; budget/repetitions unset.
  Quality and current manual acceptance remain pending. M10 remains unbuilt.

For both stages, run formatting, lint, strict types and unit tests before committing;
run Swift tests only if capture code changes. Keep shipped model settings unchanged.
Live transcription, in-place AI editing, custom Obsidian plugins and automatic tracking
of renamed or moved notes are outside this roadmap replacement.

**M11 — Synthetic evaluation set.** Two or three more made-up transcripts with
known-correct notes, beside the golden and numbers ones, so prompts and models are
compared on tests rather than by eye on real meetings: stance (a "maybe" turned into a
decision) and action-item owners.

**M12 — Stretch.** Diarization of the "them" channel; a vocabulary prompt built from my
jargon list; FLAC; auto-start when Zoom joins a call.

---

## macOS permissions

| Permission | Who gets it | Needed for |
|---|---|---|
| Microphone | Handy; `notes-capture` (itself, via disclaim) | Dictation; "me" channel |
| System Audio Recording Only (Privacy & Security → Screen & System Audio Recording) | `notes-capture` (itself, via disclaim). Ghostty can't get it: it has no usage description, so the request is silently denied | "Them" channel |
| Accessibility | Handy | Pasting dictated text |
| Calendars (Full Access) | `notes-capture` (itself, via disclaim) | Meeting titles/attendees (M5) |

Because of the disclaim relaunch, grants go to `notes-capture` itself, not Ghostty, so
other programs run in Ghostty don't inherit them.

---

## Phase 0 — Handy (in progress)

- [x] Install (`brew install --cask handy`) and grant Microphone + Accessibility
- [ ] Model: Parakeet Unified EN 0.6B first; try Whisper Turbo for a day to compare
- [ ] Hotkey: hold-to-talk, on a chord that doesn't clash with Ghostty or Claude Code
      (avoid Esc, Ctrl-C, Ctrl-R)
- [ ] Turn off any trailing newline / auto-submit; check whether Handy can restore the
      clipboard after pasting
- [ ] If pastes get dropped in Ghostty: try Debug → Reliable Paste (Beta)
- Practice:
  1. Narrate a bug as if to a pair partner, then fix the transcript by hand
  2. Do one real task fully by voice
  3. Dictate structured lists ("three things: first…")
  4. Keep a jargon list of words it gets wrong → becomes the notetaker's vocabulary prompt

---

## Open questions

- Exclude list for the global tap (e.g. Music, Spotify)? Probably later, if noise turns out
  to be a problem.

---

## Original brief

I want to build a personal, local-first meeting notetaker for my Mac. Help me plan it before we write any code.

My machine: MacBook Pro 14" M4 Pro, 48 GB RAM, macOS Tahoe 26.7.

Phase 0 — get comfortable with Handy first:
I've never used Handy (https://github.com/cjpais/Handy), a free, open source, offline speech-to-text app. My first goal is to get it installed and become comfortable using it to talk to Claude Code in the terminal, before we build anything. Help me:
- Install and configure it (permissions, model choice, hotkey, push-to-talk vs toggle)
- Make it work well in my terminal with Claude Code, including any paste or clipboard quirks
- Suggest a few practice exercises so dictating prompts becomes natural
I'm not planning to fork Handy, but its model choices and architecture may be useful reference for the notetaker.

Then, the notetaker. What I want it to do:
1. Start/stop recording with a hotkey or CLI command
2. Capture BOTH my mic and the other side of the call (Zoom, Google Meet in a browser, etc.)
3. Transcribe locally after the meeting (whisper.cpp and/or Parakeet — the same model family Handy uses)
4. Summarize the transcript into markdown with a local model (Ollama/MLX): summary, decisions, action items
5. Save it to a notes folder with a sensible filename (date + meeting title)

Preferences:
- Everything runs locally; no audio or transcripts leave my machine
- Simple over clever: a CLI tool, not a GUI app, at least for v1
- Speaker separation can be crude ("me" vs "them" via separate audio channels) — real diarization is a stretch goal

What I want from you in planning:
- Talk through technology choices for the core glue with me, with tradeoffs, rather than picking one for me
- Research the current best way to capture system audio on macOS Tahoe (Core Audio process taps vs ScreenCaptureKit vs BlackHole) and recommend one, with tradeoffs
- Propose an architecture and the smallest end-to-end v1
- Identify the riskiest piece and suggest a throwaway spike to de-risk it first
- Plan the build as small, shippable milestones, each with tests, so I have something working end-to-end as early as possible
- Call out macOS permissions I'll need to grant
- Ask me clarifying questions before finalizing anything
