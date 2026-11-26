# Approved streaming runtime pair

This isolated collector prepares the approved prospective availability probe, not a
quality comparison or diagnosis of the old timeouts. Production and historical evidence
remain unchanged. Only Chief executes the fresh pair after independent review and
committing/pushing the exact source and freeze. There is no retry or resume.

`runtime_probe.freeze(output: Path, identity: dict) -> str` creates a new directory and
returns the SHA256 of its manifest. It does no HTTP. Supply the exact identity/default
fields in `runtime_probe.IDENTITY`, confirmed by Chief's preparation metadata: installed
Ollama **0.40.13**, the unchanged Qwen3.5 digest, boolean thinking support, capabilities
and the exact parameters string. The old 0.40.9 proposal stays immutable. The new freeze
binds 0.40.13; a drift is an error and never triggers a repair or service change.

Freeze requires clean committed relevant source. Its exact inventory hashes transitive
imports, both declarations, the tests, all forty synthetic input pairs, the selected
complete snapshot, historical committed frozen decoder files, proposal, old actual request,
both new wire requests, identity/defaults, model-only `/api/show` body and host generation
bindings. Validation regenerates these artifacts and checks their bytes against the pin.
HEAD may descend from the reviewed source when publishing the freeze; relevant source
must still match that source commit. No historical Git objects are required for fixtures.
Use ordinary paths without symlinks or `..` (on macOS use `/private/tmp`, not `/tmp`).

`runtime_probe.run(output: Path, approval: str, pin: str) -> dict` is the only network
entry point. It returns `{accounting, post_seal_observation}` as described below.
Approval must be nonempty audit context; it is not authentication. A new
exclusive `results/` directory consumes the freeze even on failure. Chief must preserve
that directory and never try a second invocation or transfer unused budget.

The pair is exactly `accepted_status_answer`, think=false then think=true, stream=true
for both. SHA256s of actual wire bodies:

- false: `0a3f588c7f5958786e32b3034168bc1efea09f800a5da1fb806447bd7d99301b`
- true: `444a5b8ba57e17dd54b7e57da2d00f3c6c8934c0b3582bfaf961ea77d7e4bd18`

Only think varies within the pair. Only stream/think vary from the old actual request.
The unchanged host-bound `actions.Prepared` is internal to decoding; its baseline body
is never sent or recorded as the wire request. Its hash is explicitly labeled internal.

One fixed subprocess per exchange connects only to `127.0.0.1:11434`. Allowed endpoints
are GET `/api/version`, GET `/api/tags`, POST `/api/show` (fixed model-only metadata), and
POST `/api/chat` (only either exact pinned body). Before and after each returned generation,
version/tags/show must match the freeze. No empty generation request, warm-up, unload,
download, server action or retry exists. Every metadata exchange is at most 10 seconds;
every generation exchange at most 180; all validation, metadata, generation, saving and
cleanup consume the shared 420-second wall deadline. Stop on its expiry or the first
transport, identity, source, structural or literal failure, or interrupt. A timeout skips
post-generation metadata and the second generation. Only the HTTP child is killed and
reaped. **Server compute cancellation is unguaranteed.**

The child flushes `body.raw`, `headers.json`, a monotonic/UTC origin, and byte offset/length/
relative-receive-time records in `chunks.jsonl`. The parent retains stderr, stdout, child
errors, exit/timeout/kill/reap accounting, and partial data. Raw bytes can survive a child
kill between body and index writes; an unlogged tail is retained and invalidates the reply
instead of inventing receive timing. A system/storage failure can prevent further audit
writes; errors in independent artifacts do not intentionally discard other accounting.

Strict UTF-8/JSON rejects duplicate keys, malformed shapes, wrong models, errors, length
stops, missing/multiple terminal events and any trailing bytes/events. Only one final
done=true/done_reason=stop at EOF is valid. Content and thinking concatenate all events,
including nonempty terminal content. Complete-line progress survives a timeout. Partial
progress never becomes a draft. `observed.json` retains machine-readable thinking; never
copy it into human-facing Markdown reports. `progress.json` reports character counts,
not token counts, and first byte/thinking/content receive timings, not GPU production
timings. Final returned counts/cache/load/prompt/eval durations are retained only when
returned. No inferred token counts, output or quality verdicts are produced.

Only a valid full reply goes through unchanged `actions.decode` and renderer. Literal
issues remain in `result.json` and stop the pair. Semantic assessment is separate; if a
critical semantic defect is identified during capture, interrupt immediately, preserve
accounting and do not continue. There is no new semantic validator.

`attempt.json` records conservative possibly_sent before launching each generation child,
including spawn failure. Final accounting lists both slots, attempted/failed/unsent states,
progress, elapsed times, overruns and stop reason. Interrupts re-raise after persistence.
`final.json` is explicitly labeled a **non-authoritative pre-save snapshot**, measured
before its own write. The authoritative accounting is `manifest.json.accounting`: full
status, slots, elapsed/overrun, stop reason and artifact errors measured after saving that
snapshot and hashing the inventory, immediately before writing the manifest. The manifest
contains the exact inventory excluding itself. Returned `accounting` equals the saved
manifest accounting exactly, with no later status mutation. A failure to create a valid
seal returns explicitly non-authoritative, unsealed accounting instead.

Returned `post_seal_observation` separately records elapsed/overrun and deadline status
after the manifest write attempt and child cleanup. This includes seal latency, which a
write-once file cannot measure about its own completed write. Treat either a sealed
accounting failure or a post-seal deadline observation as an incomplete probe. Preserve
the return envelope in Chief's launch log **outside** the capture directory. A post-seal
observation never silently changes the saved accounting or adds a file to its inventory.
Emergency saving/cleanup can overrun a deadline and must preserve evidence. Keep all
later reviews, launch logs and analysis **outside** the freeze and results directories.
Do not mutate or extend the captured inventory. Offline tests use authored fake clients,
processes and clocks only; they make no model-quality claim.

Slot statuses settle before their write-once outcomes are saved during finalization.
The whole probe can still be incomplete if final saving crosses the deadline. Inventory
read failure cannot prevent independent final counts or replace an original interrupt;
an unreadable inventory is reported as an artifact error, never fabricated as a valid seal.
