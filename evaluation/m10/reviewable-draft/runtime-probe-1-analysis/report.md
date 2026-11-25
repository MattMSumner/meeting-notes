# Streaming thinking-mode probe — 2026-11-25

The approved pair completed in **104.676 seconds**, using exactly two generation
requests with no retries, failures, unsent slots or overruns. Both outputs meet the
unchanged availability/no-action criterion. Thinking enabled produced substantially
more generation work in this pair. The historical timeout did not recur on the new
Ollama 0.40.13/streaming setup; its cause remains unproven.

## Observations

| Metric | Thinking false, first | Thinking true, second |
| --- | ---: | ---: |
| HTTP worker wall seconds | 11.538597 | 91.686823 |
| Whole slot seconds, including metadata/save | 12.222030 | 92.391045 |
| Server total seconds | 11.466030 | 91.643535 |
| Server model-load seconds | 9.384157 | 0.002591 |
| Server prompt-evaluation seconds | 1.202620 | 0.054943 |
| Returned prompt tokens / cached tokens | 420 / 0 | 418 / 416 |
| Server output-evaluation seconds | 0.863868 | 91.565607 |
| Returned output tokens | 33 | 3,110 |
| First received byte seconds | 10.605371 | 0.079863 |
| First thinking event seconds | none | 0.079863 |
| First answer-content event seconds | 10.605371 | 91.189523 |
| Thinking characters | 0 | 13,509 |
| Answer characters | 65 | 43 |
| Raw response bytes | 3,142 | 415,078 |
| Complete events / logged chunks | 22 / 22 | 2,788 / 2,788 |
| Actions | 0 | 0 |
| Unnecessary focused review passages | 2 | 0 |

Both streams have one valid terminal `done=true` / `stop`, no trailing bytes and no
literal-validation issues. Raw chunks replay exactly to progress and observed text;
the unchanged decoder and renderer reproduce saved result/draft bytes. All child
processes were reaped normally. Event times are received-event observations relative
to each HTTP child's monotonic origin, not GPU timings. Character counts are not
tokens; returned output-token counts do not separate thinking from answer tokens.

The synthetic case contains an availability question and an affirmative answer, with
no assigned work. Chief and independent read-only review agree that neither output
invents an action or scheduling. The false output includes two unnecessary focused
review passages; the true output includes none. This is a narrow negative-control
pass, with no evidence about retaining useful work or timing. The assessment was not
blinded to the thinking setting. See [assessment.json](assessment.json).

## Execution and evidence

The owner's “Great, run the test” approved the prospective pair: false then true,
streaming fixed, two generation requests, 180 seconds per generation, 420 seconds
overall and no retries. Preparation, offline checks and independent source review
preceded the single execution. See [authorization.json](authorization.json).

The collector source is `58bf14f216aa642bc3ab4d14022b17469724f787`. The exact
[freeze](../runtime-probe-1/manifest.json) was committed and pushed at
`a5f0e64e00adb8e09be61834b8bfa8d0351d57d6` before inference. Freeze manifest SHA256:
`d459841b61df3ed2ecdab8e9866b7da280b2744707c56b4d2b574e7d1e4b22f2`.
Generation: `runtime-probe-956c51abc1a849aa9eeccee33793ceb7`.

The fresh identity is Ollama **0.40.13**, model `qwen3.5:9b-q4_K_M`, digest
`56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`.
The version differs from historical 0.40.9; this was disclosed before execution.
No service, model or configuration was changed. All four before/after identity gates
match version, digest, thinking support and relevant model defaults. The two actual
wire bodies match their frozen hashes and differ only in `think`; both use the same
complete synthetic snapshot, schema, streaming, temperature zero and context32768.

Fourteen captured HTTP200 exchanges account for **two generation POSTs, eight metadata
GETs and four model-show POSTs**. Three preparation metadata calls preceded the freeze
and run clock; no warm-up or baseline inference ran. All in-run metadata, loading,
generation, capture and finalization are included in the overall clock.

The [capture manifest](../runtime-probe-1/results/manifest.json) contains 114 artifact
entries; all verify exact, as do the 36 frozen artifacts plus their manifest and all
1182 prior tracked evaluation/prototype files. Independent read-only audit passed
request/attempt/snapshot bindings, identity gates, raw/chunk replay, decoding/rendering,
cleanup, deadlines and single-use accounting. Capture manifest SHA256:
`e434da3270e6af2f0c0b27952128a483fed0a5a229d531dbe053d903190bcaa2`.

Authoritative `manifest.json.accounting` equals the preserved returned accounting.
Its elapsed time is 104.675896292 seconds at the stated pre-manifest-write boundary.
The separate post-seal observation is 104.676100875 seconds; independently measured
full `run()` wall time is **104.676197667 seconds**. All report zero overrun.
`final.json` remains an explicitly non-authoritative pre-save snapshot. The capture's
then-pending semantic-assessment wording remains unchanged; the later assessment is
recorded here. See [verification.json](verification.json), [launch.json](launch.json)
and the reviewed single-call [launch script](launch-script.txt). Analysis and the final
[seal](seal.json) stay outside both strict freeze and capture inventories.

Format/lint/strict Pyright and **1489 offline tests pass**, six integration tests
excluded; 103 new tests cover the collector. Independent source review passed after
two repair rounds. Chief integration checks also passed on the unchanged source.
Production and capture code are unchanged.

## Limits and next decision

The enabled arm emitted thinking from 0.080 to 91.071 seconds and answer content only
from 91.190 seconds. Its returned output-evaluation cost is materially greater than
the disabled arm's in this pair, even though its model load was much shorter. This
supports investigating thinking disabled as a prospective setting.

One ordered pair does not establish causality or reliability: the first request loads
the model cold, the second benefits from residency and prompt cache, and returned
prompt counts differ. Streaming and service version also differ from the historical
non-streaming failures. Neither old timeout was reproduced under its old conditions,
and no historical result or grade is revised.

Keep the existing baseline and production behavior. A positive work-retention check
with thinking disabled is a possible next step before broader quality comparison or
pipeline work, requiring separately agreed scope and execution budget. **No further
generation calls are authorized.** This pair establishes no model switch, broader
quality, full regression, persistence safety, Obsidian usefulness or M10 readiness.
M10 remains unbuilt; PR #16 remains open and is not ready to merge.
