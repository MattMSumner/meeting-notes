# Meeting Notetaker — Plan

A personal, local-first meeting notetaker for macOS. It's a CLI that records my mic and the
other side of a call, transcribes locally after the meeting, summarizes with a local model,
and writes an Obsidian-friendly markdown note.

Status: **M8 done** (fold backchannels). M1–M7 and the spike done. Next: M9.
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

```
notes start [--title T]
  ├─ notes-capture (Swift)  ── me.wav   (mic, 16 kHz mono)
  │                         └─ them.wav (global tap: all system output, 16 kHz mono)
  └─ writes PID + meeting.json (start time, calendar event from notes-capture)

notes stop
  ├─ signal capture to stop, wait for WAVs to finalize
  ├─ transcribe me.wav, them.wav  → segments with timestamps (JSON)
  ├─ merge by time                → transcript.md  ("**Me:** … / **Them:** …")
  ├─ summarize (Ollama)           → summary.json (summary, decisions, action items)
  └─ render                       → ~/development/notes/meetings/2026-10-17_Weekly Sync_1400.md
                                  → ~/development/notes/meetings/transcripts/2026-10-17_Weekly Sync_1400_transcript.md
```

**Each stage reads the previous stage's files and writes its own**, so any stage can be
re-run on its own:

```
~/Library/Application Support/notes/meetings/2026-10-17-1400-weekly-sync/
  meeting.json        # times, calendar event, attendees
  me.wav  them.wav    # ~115 MB/hour each at 16 kHz/16-bit; FLAC later if disk matters
  segments.me.json  segments.them.json
  transcript.md
  summary.json
```

Audio and intermediate JSON stay **out of the Obsidian vault**, which keeps sync and search
fast. Only the note and its transcript go into the vault, as separate files: the note links
to the transcript with a wikilink, and the transcript links back to the note. The tool
never writes outside `~/development/notes/meetings/`.

CLI surface (v1):

```
notes start [--title T]
notes stop
notes status
notes transcribe <meeting-id>   # re-run a stage
notes summarize  <meeting-id>
notes render     <meeting-id>
```

Config file `~/.config/notes/config.toml`: notes folder (default `~/development/notes/meetings`), Ollama
model and `num_ctx`, transcription model path.

### Obsidian note shape

```markdown
---
date: 2026-10-17
time: "14:00"
title: Weekly Sync
attendees: [Alex, Sam]
tags: [meeting]
source: notes-cli
---
## Summary
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
    to the vocabulary prompt on the M11 list.
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
    pass straight through (vocabulary prompt, M11). But it **over-reads stance**: tentative
    remarks can come out as firm positions, even with a prompt rule against it. Asking for
    first person ("I") made things worse (it mixed "I" with third person), so it was
    dropped. Follow-up (M10): build a few synthetic transcripts with known-correct notes and
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
    in the schema, before the overview, is the next thing to try (M9).

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

**M9 — Hybrid notes with quoted details.** Run three independent model tasks against the
full transcript. One selects the IDs of complete source turns containing meaningful
figures, constraints, operational quantities and availability. Code copies each selected
turn in full, preserving neighboring claims and qualifications, and labels it with its
source speaker and time. A second task extracts decisions and action items with supporting
turn IDs; a third writes only the short overview. Code assembles the three results, with
no final rewriting pass or generated topic labels for Details. The overview leaves precise
amounts and schedules to the details; decisions and actions retain necessary specifics
when explicitly agreed or committed.

IDs follow source position, so equal timestamps remain distinct turns. Deduplicate
selected IDs and restore source order. A missing list, malformed reply or unknown ID gets
one correction; persistent failures stop before writing and preserve any previous
summary. Reject malformed source transcripts rather than silently dropping text. Meeting
metadata is not selectable, and source timestamps do not count as spoken numbers. Older
key points and topic labels still render; draft `figures` load as `details` without
rewriting saved JSON. The commitments task includes explicit deferrals and small follow-ups,
allows several items from one turn, and preserves conditions and uncertain ownership.
Actions distinguish direct promises, accepted requests and reported commitments, with
separate references for the commitment, original request and needed context. Accepted
requests require both sides. Timing evidence separates the action's own schedule from
related work dates or availability; only the action's own timing becomes its saved
deadline. Each time phrase must occur in a verbatim quote from its referenced source turn,
allowing whitespace differences only. Source matching does not prove which event is timed.
Code normalizes references and removes only exact duplicate records. Evidence stays
internal, keeping saved decisions and actions compatible. Invalid extraction gets one
correction before failing without saving a partial summary. Number corrections retry only the task that introduced the unsupported number.
Keep the accepted Details selector fixed during this refactor, along with model, thinking
and context settings. The overview keeps its existing requirements with a narrower schema.

Milestone acceptance remains five fresh full generations each of the synthetic golden,
pricing and scheduling variant fixtures, checking prose and evidence separately. For the
selector refactor, first require five selection-only runs per fixture and a greeting-only
control, checking exact source copying, important-turn coverage and irrelevant selections.
Then run one fresh full summary per original fixture to check assembly and report writer
failures separately. Measure latency and quoted text size against the previous hybrid
candidate. For the commitments timing revision, run five extraction-only generations for
each original fixture plus four focused controls: proposals without commitments,
conditional or unknown-owner promises, action versus related timing, and adjacent or
separated request/acceptance pairs (35 checks). Check decision and action coverage,
ownership, timing, qualifications and evidence roles separately. After isolated acceptance
passes, run one complete summary per original fixture, requiring commitments and source
selection to pass 3/3. Keep the overview fixed and report its failures separately; overview
repair and the larger full-note acceptance batch remain subsequent work. Whole-turn
copying guarantees source wording, not complete selection or faithful interpretation in
generated prose.
- **Implemented, not built (2026-10-28).** Draft PR #13 adds extraction, source verification,
  the separate writing pass, saved figures and rendering. All 270 unit tests, lint and strict
  types pass. The model-quality acceptance gate is still open:
  - Five baseline generations per fixture: pricing checks 0/5, golden checks 5/5.
    The two-pass candidate passed pricing 5/5 and the original golden assertions 5/5,
    but inspection found an availability reversal in 2/5 golden summaries. A new
    regression assertion catches it, leaving the expanded golden check at 3/5.
  - All ten extractions ultimately passed source verification; three needed the one
    correction attempt. Exact source words and speaker labels do not guarantee that
    the writing pass preserves their meaning. The renderer suppresses exact duplicate
    figure entries produced by a correction, without changing the saved evidence.
  - Median elapsed time on the synthetic fixtures: golden 13 s → 128 s; pricing
    43 s → 193 s. Extraction dominates: median 113 s and 175 s, including corrections.
    The existing model, thinking mode and context settings were kept.
  - A targeted writer-prompt change, tested against the same five independent extractions
    per fixture, regressed to golden 2/5 and pricing 0/5. It was reverted. The better
    candidate and the stronger regression test remained in the draft; the pricing xfail
    was retained at this stage. Further prompt tuning alone had not
    established reliable prose coverage and interpretation.
  - A fresh end-to-end Ollama integration run with xfail disabled also reproduced the
    availability reversal: three pricing tests passed and the golden test failed.
- **Hybrid revision, not built (2026-10-28).** The draft now implements the independent
  extraction and writing tasks described above, with legacy loading and rendering.
  All 274 unit tests, formatting, lint and strict types pass. The model-quality gate
  remains open, so this architecture has not been adopted on main:
  - Two writer-only comparisons, five generations per original fixture, both passed
    the revised pricing prose checks 5/5 but repeated dates in golden overviews 5/5.
    Adding the overview restriction to the response schema did not resolve it.
  - Five fresh full generations per fixture: golden 0/5, pricing 0/5, scheduling variant
    0/5 on the complete acceptance checks. The original absence-to-return reversal
    appeared in 0/10 scheduling summaries, and their availability quotes passed 10/10.
  - A planning commitment was omitted from action items in 10/10 scheduling summaries.
    Inspection of the archived baseline and prior candidate found the same omission
    in 5/5 each; it is now an explicit regression assertion. Golden overviews also
    repeated dates in 5/5; variant overviews met the format requirement in 5/5.
  - Source verification succeeded for 14/15 generations, with six correction requests.
    One pricing extraction failed after correction, so writing did not run. The other
    four pricing summaries omitted a qualified budget constraint from the quotes.
    Source matching alone does not detect missing evidence or misleading labels.
  - Coverage assertions now check quoted details rather than requiring every figure
    in prose. Assertions still check any amounts repeated in prose, and reject labels
    that reinterpret feasible amounts as targets or ceilings. No model-quality failures
    are hidden behind xfail.
  - Median attempt times: golden 43 s, pricing 85 s, scheduling variant 50 s; pricing
    includes the failed extraction. Model, thinking and context settings are unchanged.
    This fixed candidate remains a draft pending better evidence coverage and action
    completeness; no reviewing model pass or broad M10 evaluation set was added.
- **Source-turn revision, not built (2026-10-28).** The selector returns only turn IDs;
  code copies complete source turns with speaker and time headings. All 298 unit tests,
  formatting, lint, strict types, and Python and Swift CI pass. The selector component
  passes its repeated acceptance checks; M9 still requires the full-note quality gate:
  - The first selector passed pricing and greeting controls 5/5 each, but both scheduling
    fixtures 0/5 because it skipped operational facts. Those facts were also absent from
    the previous hybrid quotes. The final prompt explicitly includes operational
    background and keeps qualifying facts even when their turns also contain actions.
  - Five fresh selection-only runs per fixture: pricing 5/5, golden 5/5, scheduling
    variant 5/5, greeting-only control 5/5. All required turns were retained; no forbidden
    greeting or acknowledgment turns were selected. No invalid IDs, source-copy failures
    or correction requests occurred. Greeting controls selected zero turns in 5/5 runs.
  - Copying the entire budget turn retained the previously omitted qualification in
    5/5 pricing runs. Whole turns also preserve nearby claims, so the notes are longer:
    median quoted characters were 340 → 829 for golden, 463 → 527 for pricing and
    302 → 800 for the scheduling variant. The prior pricing size uses its four returned
    summaries; one prior extraction failed.
  - ID selection is not always faster. Median extraction/selection times were 22 s → 83 s
    for golden, 74 s → 43 s for pricing and 34 s → 58 s for the scheduling variant.
    Greeting controls took 5 s. The model, thinking mode and context size are unchanged.
  - One fresh full summary per original fixture passed source selection and assembly
    3/3. Complete checks passed pricing 1/1, golden 0/1 and scheduling variant 0/1.
    Both scheduling summaries still omitted the planning commitment from action items;
    the golden overview also repeated a date. The writer's prompt, schema and original
    transcript context were unchanged. Full elapsed times were 58 s for pricing, 117 s
    for golden and 76 s for the scheduling variant. These smoke checks do not replace the
    milestone's five full generations per fixture. PR #13 remains a draft for writer
    completeness and overview format; the selector changes have not been adopted on main.
- **Commitments revision, not built (2026-10-29).** Decisions and actions now have a
  dedicated extraction task with supporting turn IDs; the final task writes only the
  overview. All three tasks read the original conversation, and code assembles their
  results. The accepted selector, model, thinking mode and context settings are unchanged.
  All 326 unit tests, formatting, lint, strict types, and Python and Swift CI pass.
  The implementation is complete, but its model-quality gate remains open:
  - Five fresh extraction-only generations per fixture: golden 5/5, pricing 5/5,
    scheduling variant 0/5, proposals without commitments 5/5, conditional and
    unknown-owner commitments 5/5. The 25-run batch resumed after a pause with identical
    prompts, schemas, settings, fixtures and checks; completed results were preserved.
  - Both scheduling fixtures retained two decisions and four actions in all 10 runs,
    including the previously omitted planning commitment. Archived hybrid outputs had
    that action in 0/10 runs, and the latest source-turn summaries had it in 0/2.
    Ownership, decision time scope and uncertainty checks passed in all 10 extractions.
  - The scheduling variant incorrectly used the planned start of related work as a
    conversation deadline in 5/5 runs, and cited only the acceptance rather than both
    the request and acceptance for another action in 5/5. The deadline is a regression:
    none of its five archived hybrid outputs assigned that deadline. Reference
    completeness is a new check; a known turn ID alone does not prove full support.
  - All 25 responses were structurally valid and used known IDs, with no correction
    requests. The negative control invented no decisions or actions in 5/5 runs;
    conditional and unknown-owner controls retained both commitments, the condition,
    and unknown ownership and deadline in 5/5. These checks do not establish reliability
    beyond the small synthetic set.
  - Median extraction times were 114 s for golden, 82 s for the scheduling variant,
    39 s for pricing, 16 s for the negative control and 54 s for conditional commitments.
    The first resumed control includes model loading; medians include that observation.
  - One fresh complete summary per original fixture passed source selection and assembly
    3/3 and commitments checks 2/3. Full automated checks passed pricing 1/1, golden 0/1
    and scheduling variant 0/1. Both scheduling notes retained the planning action; the
    variant repeated its deadline and reference failures. All nine requests succeeded
    without corrections.
  - Both scheduling overviews repeated dates. Manual inspection also found one overview
    presenting a proposed work start as settled; the pricing overview was ambiguous about
    which build amount was considered feasible despite passing its automated checks.
    Full elapsed times were 203 s, 159 s and 113 s for golden, variant and pricing,
    compared with 117 s, 76 s and 58 s in the previous single-summary smoke checks.
  - The three-summary prerequisite failed, so the larger full-note acceptance batch was
    not run. PR #13 remains a draft pending deadline attribution, complete supporting
    references and overview fidelity. M9 has not been adopted on main.

- **Timing-evidence revision, not built (2026-10-29).** Actions now separate commitment,
  request and context references, and distinguish their own timing from related timing.
  Quotes and values are source-checked; only action timing supplies the saved deadline.
  All 367 unit tests, formatting, lint and strict types pass. The frozen implementation
  remains at `b980935`; model-quality acceptance failed:
  - Five extraction-only runs across seven fixtures passed 13/35: golden 0/5,
    scheduling variant 0/5, pricing 5/5, proposals without commitments 0/5,
    conditional or unknown-owner commitments 0/5, action versus related timing 5/5,
    and adjacent or separated accepted requests 3/5. On the original five-fixture
    subset this is 5/25, down from the previous design's 20/25.
  - Request and acceptance references are now complete in both scheduling fixtures
    (10/10) and the accepted-request control (5/5). The variant previously omitted
    the request in 5/5. This improvement does not establish faithful timing:
    the variant still assigns a related work start as a communication deadline in
    5/5, and its decision leaves the subject as an unresolved pronoun in 5/5.
  - Golden merges two independent promises into one item in 5/5 (three actions instead
    of four), despite correct timing. Both negative and conditional controls invent
    decisions in 5/5; conditional actions themselves remain present. Accepted requests
    retain their references but misclassify action deadlines as related timing in 2/5,
    leaving deadlines empty and also adding decisions.
  - Manual review covers all nine distinct summaries; the four resumed outputs match
    previously reviewed hashes. Pricing passes automated checks in 5/5 but omits the
    explicit promise to report back after discussing the proposal. Exact source quotes
    do not prove event attribution, completeness or faithful task wording.
  - All 35 model responses validated without correction requests. The 31 saved results
    were combined with only the four missing fifth runs after verifying identical
    prompts, schemas, implementation, settings, fixtures and checks. Four sandbox-denied
    localhost attempts returned no model responses; their transport errors are preserved
    separately and excluded from the 35 model generations. No failed model row was replaced.
  - Median extraction seconds versus the prior commitments design: golden 114 → 137,
    variant 82 → 168, pricing 39 → 78, negative control 16 → 22, conditional control
    54 → 62. New timing and accepted-request controls took 107 s and 67 s. The first
    resumed call may include model loading; these medians include it. Model, thinking,
    context, selector and overview remain unchanged.
  - The 35/35 prerequisite failed, so no complete summaries or larger full-note batch
    were run for this candidate. PR #13 stays a draft; M9 is not built or adopted on main.
    A different approach requires a separate discussion.

**M10 — Synthetic evaluation set.** Two or three more made-up transcripts with
known-correct notes, beside the golden and numbers ones, so prompts and models are
compared on tests rather than by eye on real meetings: stance (a "maybe" turned into a
decision) and action-item owners.

**M11 — Stretch.** Diarization of the "them" channel; a vocabulary prompt built from my
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
