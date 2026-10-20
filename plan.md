# Meeting Notetaker — Plan

A personal, local-first meeting notetaker for macOS. It's a CLI that records my mic and the
other side of a call, transcribes locally after the meeting, summarizes with a local model,
and writes an Obsidian-friendly markdown note.

Status: **M2 done** (both sides recorded and interleaved; first real meeting recorded). M1 and the spike done.
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
    to the vocabulary prompt on the M6 list.
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

**M4 — Start/stop + hotkey.** `notes start` / `stop` / `status` using a PID file in the
meeting directory. Hotkey via Raycast or Shortcuts calling the CLI. Crash safety: write the
WAV header on close but keep the data flushed as it records, and have `notes stop` recover
an orphaned recording.
- Tests: state transitions (start while already running, stop when nothing is running,
  stale PID).

**M5 — Calendar titles + Obsidian polish.** `notes-capture calendar-now` (EventKit) returns
the current or nearest event's title and attendees as JSON. Add frontmatter, and write the
transcript as a separate linked note.
- Tests: picking an event from a fixture list (overlapping events, no event, all-day
  events ignored).
- **Transcript readability** (found in the first real meeting):
  - Split long turns into paragraphs (every 30–60 s, at sentence boundaries). One turn
    was 2½ minutes in a single block.
  - Fold short backchannels ("Yeah.", "Okay.") inline instead of giving each its own
    turn. 155 turns in 27 minutes, many of them one word.
  - Optionally pad the channel that ends early, so both files cover the whole recording.

**M6 — Stretch.** Diarization of the "them" channel; a vocabulary prompt built from my
jargon list; FLAC; auto-start when Zoom joins a call.

---

## macOS permissions

| Permission | Who gets it | Needed for |
|---|---|---|
| Microphone | Handy; `notes-capture` (itself, via disclaim) | Dictation; "me" channel |
| System Audio Recording Only (Privacy & Security → Screen & System Audio Recording) | `notes-capture` (itself, via disclaim). Ghostty can't get it: it has no usage description, so the request is silently denied | "Them" channel |
| Accessibility | Handy | Pasting dictated text |
| Calendars (Full Access) | `notes-capture` (itself, via disclaim) | Meeting titles/attendees (M5) |
| Input Monitoring | Hotkey tool, if needed | M4 |

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
