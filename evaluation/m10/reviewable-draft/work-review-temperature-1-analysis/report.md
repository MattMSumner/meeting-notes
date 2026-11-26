# Two-temperature thinking comparison — 2026-11-26

**Quality outcome: FAILED / INCOMPLETE.** Temperature 1 returned a completed empty
selection, critically omitting the clear control undertaking and its timing.
Temperature 0 reached the common output-token cap with no answer and is ungraded.
Both authorized generation transports returned strict terminal streams. The declared
capture-complete flag is false because the final Chief meaning gate identified the
critical defect; this is not a transport timeout or missing capture evidence.
No retry, resumption, replacement or further model request is authorized.
Independent read-only capture and telemetry audit passes, and independent source-meaning
review agrees with the critical omission and the censored/ungraded distinction.

Read [prospective criteria](criteria.json), [assessment](assessment.json),
[verification](verification.json), [full launch envelope](launch.json),
[telemetry summary](telemetry-summary.json), and the [preservation seal](seal.json).
The seal is created after final independent report consistency acceptance.

## Fixed comparison and source meaning

The owner said “Great, do the temperature comparison.” The two new requests use the
same complete original familiar `front_loaded_timing` snapshot, accepted work-review
prompt/schema/renderer, model/digest/runtime, think=true, stream=true and context 32768.
Both introduce num_predict=4096; their only between-arm difference is temperature.
Order is fixed 0 then 1, with one observation each, no seed override, no warm-up or retry.
The older uncapped timeout is context only and is not a matched control.

| Temperature | Transport terminal | Returned output tokens | Accepted answer / source meaning |
| --- | --- | ---: | --- |
| 0 | length at the 4096 cap | 4096 | No answer content, result, render or callback; censored and ungraded. |
| 1 | stop | 3130 | Valid groups=[] and an empty rendered view; critical omission of the explicit wholeT1 undertaking and NextTuesday timing. |

The complete [source snapshot](../work-review-temperature-1/snapshots/02-temperature-1.json)
reached the model unchanged. There is no withdrawal or competing context. The completed
[temperature 1 result](../work-review-temperature-1/results/02-temperature-1/result.json)
and [render](../work-review-temperature-1/results/02-temperature-1/work-review.md) retain
no selected passage. A generic empty-selection notice does not satisfy required work
coverage. The [Chief verdict](../work-review-temperature-1/results/02-temperature-1/meaning-review.json)
was explicitly recorded before finalization. This is a completed-answer omission,
distinct from the first arm's censor; no hidden-thinking text is reproduced or graded
as an answer. Original writing remains separately saved and empty as supplied.

## Captured metrics

| Metric | Temperature 0 | Temperature 1 |
| --- | ---: | ---: |
| Generation HTTP wall (s) | 116.868 | 86.369 |
| Server total (s) | 116.824 | 86.289 |
| Model load (s) | 6.380 | 0.002 |
| Prompt evaluation (s) | 0.730 | 0.064 |
| Output evaluation (s) | 109.707 | 86.188 |
| Prompt tokens returned | 281 | 281 |
| Cached prompt tokens returned | 0 | 277 |
| Output tokens returned | 4096 | 3130 |
| First thinking receive (s) | 7.122 | 0.103 |
| First answer receive (s) | — | 86.131 |
| Thinking characters | 17131 | 13068 |
| Answer characters | 0 | 14 |
| Complete NDJSON records | 3710 | 2816 |
| Raw generation body bytes | 551672 | 418826 |
| Returned output tokens / output-evaluation second | 37.336 | 36.316 |
| Indexed receive chunks | 3710 | 2816 |

Receive timings are relative to each HTTP child's monotonic origin and include its
connection/load/prompt costs; they are not GPU clocks. Server durations and token counts
are reported terminal values. NDJSON records/chunks/characters are not token counts.
The first arm loaded the model for 6.380 s; the second loaded for0.002 s and reused 277
prompt tokens. Input prompt-token counts were 281 each. Total generated-token throughput
was37.336 versus 36.316 tokens/s. A censored first answer has no known completion latency;
these values do not establish a percentage improvement in time to a correct answer.

## Thermal and memory observations

The read-only sampler recorded **120 samples, all thermal severity nominal**,
with zero sample errors and a final sample after the call. All 58 samples within
first-generation HTTP and all 44 within second-generation HTTP were nominal. This is
macOS OS thermal severity, not temperature or frequency measurement. The temperature
and GPU-clock channels are unavailable; nominal samples cannot exclude every brief or
mild throttling event between samples. There is no recorded thermal-pressure event
explaining these outcomes.

Memory state was not constant: raw dispatch pressure codes were 1 in 22 samples and 2
in 98 samples. During the first generation, counts were 21/37; during the second they
were 0/44. Apple publishes these codes as normal/warning through its
[sysctl conversion](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_memorystatus_notify.c#L1753)
and [event definitions](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/event_private.h#L276).
This source mapping is not attestation of the exact running kernel. Host memory pressure
remains a performance confound; it does not establish the cause of the missing selection.
Swap used remained 12449617019bytes (about 11.595 GiB),
with zero additional swapouts across the trace. Per-generation swapins increased73 and28;
zero swapouts do not rule out memory contention. Sampler work is itself a measured
perturbation: maximum sample duration 0.079s at a nominal 2 s cadence.
Raw aggregate observations remain in [telemetry.jsonl](telemetry.jsonl); no application,
meeting, prompt or generated text was collected by the host sampler.

## Execution and accounting

Caps were **2requests/600s overall/180s generation/10s metadata/4096output tokens/0retries**.
A strict length terminal with eval_count=4096 was prospectively allowed to continue after
post-identity/artifact gates, while publishing no answer/render/meaning grade. The first
arm followed that path. The second stop answer reached the Chief meaning gate, which
identified the critical omission and stopped. Both slots were attempted; none remain
unsent. The allowance is closed, and no future retry or additional format-control request
is approved by this record.

There are 14 saved HTTP200 exchanges: 2 generation and 12 metadata, with 4 matching before/after
identity/default gate sets. All 14 HTTP children returned0 and were reaped without kill,
timeout, error or deadline overrun. Raw/index/progress replay and unchanged decoder/render
replay verify. Temperature 0 has no result/render/review; temperature 1 has exactly one
render and Chief verdict. No automated source-meaning PASS is emitted.

Authoritative sealed accounting equals the returned accounting and verification.
Its boundary is after final.json saving/inventory hashing and before manifest writing;
final.json is explicitly non-authoritative. Sealed elapsed is238.319804375002s,
separate post-seal elapsed 238.320195875014s, and independent
full probe-call wall **238.320249333046s**, including Chief review wait.
Launch wall including telemetry setup/cleanup is238.460623625026s. Global overrun and
artifact errors are zero. Telemetry closed normally, returned0 and was reaped; its
full trace brackets the call. Sealed capture_complete, answer_complete and semantic_complete
are false because the declared acceptance sequence did not finish successfully. Both
transport_complete flags are true. stop_completed and failed overlap for the second slot:
they describe terminal evidence and a failed meaning gate, respectively.

## Exact source, freeze and limits

Reviewed source: `8a1c6827ce8e193a970b87c994a22f119c922bd1`. One consolidated engineering repair round
closed the stop-counter cap check and an unfrozen test-fixture dependency. All 1895 prior
tracked evaluation/prototype files remain byte-exact. Targeted 189 tests pass in 74.60 s;
the exact-source required full offline suite passes 2043 tests with 6 integration tests
excluded in 552.35 s, plus formatting/lint/strict types. The superseded S1 worker run was
interrupted after 1702 passes and is not represented as a full-suite PASS.

Published freeze head: `f9f7ea4e60b4d84adf01319f12686f8a288830cf`.
Manifest SHA256: `f7947eac68cdab7c0ecaa9d2b2c80c03facb14cb80daf8979a950b079b33360a`.
Generation: `work-review-temperature-db0372417d2c40439a297f3833a61372`.
The freeze contains70artifacts plus manifest; capture contains114artifacts plus its manifest.
Capture-manifest SHA256: `31460c0754f4d4835e6eb5c1dc4053031d89ccdf7b86cc79729b6d1386a2b365`.
All 71 frozen files match the published head; source remains an ancestor unchanged.
Initial GitHub GraphQL head lag was resolved by matching the actual remote ref, REST PR
head and local head before execution. No generation was launched under a mismatched head.

This is one familiar synthetic control, one observation per temperature, with fixed order,
cold load/cache differences, stochastic sequence and changing host memory state. It shows
that this temperature 1 observation terminated below the cap but **did not fix selection
quality**. It establishes no causal attribution, reliability, general thinking benefit,
model switch, saved effort, full40/full-draft or production/M10 acceptance. Historical
verdicts, productionV11, remaining persistence/edit-protection/usefulness gates and the
owner's shipit gate remain unchanged. Production settings and the running model service were unchanged and
no further allowance is implied.
