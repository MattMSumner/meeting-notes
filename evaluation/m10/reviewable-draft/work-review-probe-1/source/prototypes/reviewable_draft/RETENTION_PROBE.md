# Approved four-case work-retention experiment

The owner approved the immediately proposed experiment with “Great, run the experiment”.
This authorization supersedes the older no-new-inference handoff only for this exact
profile. Chief alone executes ONCE after independent review and the exact source/freeze
commit and push. Preparation, review and publication precede the execution clock. No
approval re-ask is required. Implementation and tests are offline; no production changes.

`retention_probe.freeze(output: Path, identity: dict) -> str` exclusively creates a new
freeze and returns its manifest SHA256, without HTTP. Chief supplies preparation metadata
matching `runtime_probe.IDENTITY`: Ollama **0.40.13**, Qwen3.5 digest
`56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`, capabilities
`completion, vision, tools, thinking`, boolean thinking values `[false,true]`, default
`true`, and the exact existing parameters string. No version/digest/support/default drift
is accepted; never repair the service or model to make a gate pass.

Clean committed relevant source is required. The freeze binds every transitive runtime
module, old and new streaming tests/declarations, all forty original synthetic inputs,
complete selected snapshots (including separate unchanged writing), exact actual requests,
host generation/packet bindings, source and inherited import baselines, identity/defaults,
model-only show body, and committed historical frozen decoder evidence. Historical source
files are read from the current commit, without depending on unavailable historical Git
objects; depth-one CI can construct its synthetic fixtures. Candidate is an exact commit
SHA; descendants may publish a freeze only with identical relevant source. Inherited
`d.LOADED` baselines are preserved, never refreshed from disk. The inventory is exact and
excludes only `results/`; keep review, analysis and launch records in sibling directories.
Use ordinary paths without `..` or symlinks (`/private/tmp`, not `/tmp`, on macOS).

Exactly four packets use generation `retention-probe-<uuid>/<case>`, one repetition,
fixed order, `qwen3.5:9b-q4_K_M`, think=false, stream=true, temperature0, context32768:

| Order/case | Actual canonical wire SHA256 |
| --- | --- |
| 1 partial_coordination_retracted | `1936f87f816e3ba2c734abce7b84908821abacb1e2485857fc783c983a3d7114` |
| 2 cancellation_with_new_task | `27137409d45e2fb4c57a44754d7691031177ba97c086cabbd1b1b892be6d4da2` |
| 3 qualified_external_timing | `fb6a56fa79892a890c2f967f4a7ac8568d8d2b3003fe7e3456360017dedd1509` |
| 4 additional | `0f3b71b385dccd18d5e28938527ed27f24c811b277f2015776311d8cb0785eec` |

Wire is canonical `d._bytes(actions.prepare(...).body())` with ONLY model/stream/think
replaced as above. Preserve speech, prompt, response schema and options exactly. Writing
is excluded from model input and retained separately in snapshots and rendered drafts.
The unchanged decoder's internal baseline packet still uses its original settings;
`internal_baseline_decoder_request_sha256` is explicitly labeled and never sent or recorded
as the actual wire request. There is no old two-request pair or other case in this profile.

`retention_probe.run(output: Path, approval: str, pin: str) -> dict` is the only HTTP entry
point. It returns `{accounting, post_seal_observation}`. Approval is nonempty audit context,
not authentication. Exclusive creation of `results/` consumes the profile even on failure.
No retry, resume, budget transfer, other model/case, warm-up, unload, download, service or
configuration change is allowed. There are at most **four generation requests**, **180
seconds per generation**, **900 seconds overall**; every metadata exchange is at most
**10 seconds**. Shared wall time includes validation, metadata, loading, generation,
capture, decoding, saving and cleanup. Emergency evidence saving may overrun and must
report that overrun honestly. No new experiment follows unused allowance.

The separate `_retention_http.py` policy is a small reviewed copy of the accepted transport
mechanics. Each exchange launches its own isolated subprocess bound to this new child
source and its four exact body pins, with fixed loopback `127.0.0.1:11434` only. Allow only
GET `/api/version`, GET `/api/tags`, model-only POST `/api/show`, and the four fixed POST
`/api/chat` bodies. The old HTTP policy and constants stay unchanged. Before/after each
returned generation, version/digest/capabilities/thinking/defaults must match the freeze.
No redirects or retries. Stop the WHOLE experiment on first source/input/request/identity
drift, deadline, transport, structural, literal or interrupt failure. Never queue the next
generation behind uncertain compute. Kill/reap only our child; server compute cancellation
is unguaranteed. A failed transport skips post-generation metadata and all later cases.

Capture raw flushed bytes/chunk offsets and relative receive times, monotonic/UTC origin,
headers, stdout/stderr, errors and process/deadline accounting. Reuse the unchanged strict
stream parser and replay: exactly one done=true/done_reason=stop at EOF; reject duplicate
keys, bad UTF-8/shapes/model, missing/length/multiple terminal events and trailing bytes.
Preserve complete-line progress and partial raw bytes; retain known prefix timings and
leave unlogged-tail timing unknown. Partial replies never become drafts. Report characters
as characters, not tokens; returned model counts/timings are separate observed values.
Raw thinking is machine-only in `observed.json`; never reproduce it in human reports.
Only a full valid stream reaches unchanged `actions.decode`/renderer. Preserve rejected
literal issues in `result.json` without publishing a partial draft.

Persist conservative `possibly_sent` before generation launch, including spawn failure.
All four slots retain actual request/snapshot/generation bindings after successful pure
preflight, completed/failed/unsent states, progress and honest timings. If pure preflight
cannot establish a binding, it stays explicitly unknown; pinned wire hashes remain known.
Independent artifacts are saved best effort; one read/save failure must not erase all
counts or mask the original BaseException, which is re-raised after accounting.
`final.json` is explicitly a **non-authoritative pre-save snapshot**. Authoritative
`results/manifest.json.accounting` includes final save/inventory time up to the stated
boundary immediately before the manifest write. Returned `accounting` equals that seal;
never silently revise persisted status. A failed seal returns non-authoritative unsealed
accounting. `post_seal_observation` separately exposes seal wall time/deadline/overrun.
Chief preserves the envelope and independently measured full run wall time outside capture;
any sealed failure, post-seal deadline or full-wall overrun makes the run incomplete.

Meaning assessment is independent, not a new validator. Stop if a critical semantic
defect is identified during capture; capture may precede independent assessment, so no
interim semantic PASS or automatic continue approval is fabricated. Preserve every already
captured output. The following prospective criteria precede execution:

| Case | Required useful retention |
| --- | --- |
| partial_coordination_retracted | Retain invoice sending as work or focused review with original and withdrawal context together; never present cancelled review as current. |
| cancellation_with_new_task | Retain independent sending with full relevant context and no invented due. |
| qualified_external_timing | Retain sending with the full not-before/next/finance turn, or both whole turns in focused review, without a misleading due. |
| additional | Retain BOTH genuine undertakings with supported attribution and timing, plus separate unchanged writing. |

Generic warnings or whole-transcript dumps alone do not pass. Assess invented commitments,
source meaning, owners and qualifiers, lost current work and review burden. Familiar cases,
one repetition and action-only results establish no broader draft quality, historical
cause, reliability, model switch, full40 regression or M10 readiness. Existing production,
persistence/edit safeguards, synthetic Obsidian usefulness and owner shipit gates remain.
