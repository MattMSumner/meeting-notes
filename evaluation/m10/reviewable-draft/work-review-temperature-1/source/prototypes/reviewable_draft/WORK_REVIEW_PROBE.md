# Seven-case passage-selection experiment collector

The owner accepted this one-pass experiment with “Ok, run those examples and fix CI!”.
Chief alone publishes the reviewed candidate/freeze and executes it once. Implementers
and tests make no inference or metadata calls. This new isolated collector changes no
production code, existing collector policies, authored examples, model evidence or grades.

`freeze(output: Path, identity: dict) -> str` creates a new exclusive freeze and returns
its manifest SHA256, with no HTTP. Identity must equal saved `runtime_probe.IDENTITY`:
Ollama 0.40.13, model `qwen3.5:9b-q4_K_M`, digest
`56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`, capabilities
`completion, vision, tools, thinking`, boolean thinking values false/true and default true,
and its exact existing parameters string. No model, daemon, configuration or clock changes
are permitted to pass a gate.

The freeze requires clean relevant source equal to the exact committed candidate, and
that candidate must be an ancestor of current HEAD. Publication descendants must preserve
all relevant bytes. It inventories transitive old/new modules, inherited declarations/tests,
new source/tests/declaration, original work-review contract, forty-input fixture, original
seven mappings, longer input, annex and seven original previews. Historical frozen source
is checked from current tracked files; no historical Git object fetch is needed, including
in shallow CI fixtures. Independent inherited import baselines are copied without refresh;
accepted work-review source hashes also protect modules that publish no own baseline.

`work_review_examples.load_examples()` verifies all seven ORIGINAL complete synthetic
snapshots and their authored provenance. New `work_review.prepare()` uses those snapshots
and generation `work-review-probe-<uuid>/<case>`; authored selected references never enter
the payload. Complete snapshots include original writing and every turn. The freeze saves
original provenance, full/per-slot snapshots, prepared bindings, payload hashes and actual
wire hashes for ALL seven slots before generation. All fixture/mapping/annex/preview hashes
are rechecked against the frozen source. Authored groups, answers and assessment criteria
are not sent. The payload's messages/schema remain byte-exact from accepted work_review.py;
append only model, think=false, stream=true, options={temperature:0,num_ctx:32768}.

One repetition, fixed `examples.CASES` order and canonical actual wire SHA256:

| Case | Wire SHA256 |
| --- | --- |
| partial_coordination_retracted | `19b8a827b51d332b998481a530d7bcb2a36fb0340f799520f4bca11402fd70c6` |
| cancellation_with_new_task | `75b7e1da6a5e97bcdb147d82ed0101f74b1d48ebeb02bb4d83c0831cb15834d9` |
| qualified_external_timing | `0362971694b8fbe17f9e5eef4df9d0fc27db6fe9bd2aa50ddebb35d5c2e01148` |
| additional | `899a1d8123b3406314389f3d6e9713a81bb1aa2297fa7ed2250af29414bc2eff` |
| accepted_status_answer | `97a94077e011ee54caf983395057b4ba2f40f862cf718ff17d29e361894f1f2c` |
| unit_equivalence | `8944f81a8abe06a73cf737ec3b5709cb5eb79b73983452fb7c7fd90ed9274122` |
| authored_longer_context | `f19485b3f2a30a235e26569b7e09a599d1d09c0f650dfbc7de664e7cc1c4af6e` |

`run(output: Path, approval: str, pin: str, assess) -> dict` consumes `results/` exclusively,
even on preflight failure. Approval is nonblank audit context, not authentication. Only
this explicit entry point performs HTTP. Maximum SEVEN generation requests, 1500 seconds
shared wall time, 180 seconds per generation and 10 seconds per metadata exchange, zero
retries. Loading, validation, metadata, generation, decoding, assessment waits, artifact
saving and cleanup all count. Never resume or transfer unused allowance. Existing results,
edits, symlink paths/parents and parent traversal are refused. Keep analysis/launch records
in sibling directories; both inventories are exact and only results are omitted from freeze
validation. A failed freeze/export cannot be overwritten.

The new `_work_review_http.py` independently owns exactly seven fixed request pins and
launches its own isolated `-I -u` child source. It allows only loopback 127.0.0.1:11434:
GET /api/version, GET /api/tags, model-only POST /api/show and the pinned POST /api/chat
bodies. No redirects, retries, warm-ups or other requests. Before/after every returned
generation, live version/digest/capabilities/thinking/defaults must match the freeze.
Drift or any transport/deadline/structural/assessment failure stops the whole run.
A failed transport skips the after gate and later requests. Persist conservative
`possibly_sent` BEFORE child launch, even if spawn fails. Kill/reap only our child;
server compute cancellation is not guaranteed.

Reuse accepted retention accounting and unchanged runtime Stream/replay. Preserve raw
flushed bytes, chunk offsets/times, monotonic/UTC origin, headers, stderr/stdout, partial
progress and process/deadline evidence. Require strict NDJSON, one terminal done=true with
done_reason=stop at EOF, correct identity/shapes/UTF-8 and no trailing events/bytes. Unlogged
tail receive timing stays unknown; known prefix times remain. Partial/malformed content
cannot become an incomplete or unavailable draft. Only structurally valid completion
reaches unchanged `work_review.decode` and `render_result`. Save bound `result.json` and
exact `work-review.md` only on that route. Raw thinking is machine-only evidence and is
never reproduced in human reports. Character counts are not token counts.

After EVERY saved valid render, including empty selections and the seventh result, invoke
Chief's explicit `assess(slot: str, result: work_review.Result, deadline: float)` BEFORE
any later request. There is no default callback, matcher, automatic continue or model-quality
PASS. The Chief agent reads the actual Markdown against prospective criteria and decides.
Chief's launch approval uses `chief_review_between_requests` for this required gate.
Per-case verdicts record Chief/host-owned review, without claiming owner or human approval.
The callback returns exactly `{critical: bool, assessment: nonblank str}`. Save that exact
verdict in `meaning-review.json`; a critical verdict preserves result/render/verdict, stops
with later slots unsent and leaves overall capture incomplete. Callback exceptions, timeout,
invalid verdict or assessment save failure also stop. No inferred approval from silence.

Chief supplies a deadline-aware stdin/select wrapper. The collector additionally bounds
callback waiting with a scoped SIGALRM timer using the remaining shared budget, restoring
the previous handler afterward. Run on the main thread with no active real-time timer;
preflight refuses otherwise before HTTP. The trusted host callback must not suppress the
timeout or replace process signal/timer state. Time spent saving the verdict is checked
against the same deadline. Source/request/identity gates remain before the next generation.

Independent artifact saves/inventory errors cannot erase other counts or mask an original
BaseException, which is re-raised after best-effort accounting. `final.json` is explicitly a
NON-AUTHORITATIVE pre-save snapshot. `results/manifest.json.accounting` is authoritative at
its stated pre-write boundary after final save/inventory hashing, and returned `accounting`
is unchanged from that seal. Failed seals return non-authoritative accounting. The envelope
also returns separate `post_seal_observation`; Chief preserves it and an independent full
run wall measurement outside strict capture. Any failure or overrun makes the experiment
incomplete, including manifest write/full-call time after the authoritative boundary.
Emergency evidence saving can overrun and must report it honestly.

Six cases are familiar; the seventh is Chief-authored, not held out. One repetition tests
source fidelity and the collector's mechanics, not selection quality, reliability, saved
effort, historical causes, full-draft quality or M10 readiness. The Chief agent's meaning
assessment is host-owned review evidence. Full-source annexes/warnings cannot rescue
missing work or context.
Existing historical failures/grades stand. Production integration, full40 regression,
persistence/edit protection, summary/decisions, Obsidian usefulness and shipit remain
separate gates. Chief owns preparation/publication, prospective criteria, once-only live
execution, independent audit and cleanup.
