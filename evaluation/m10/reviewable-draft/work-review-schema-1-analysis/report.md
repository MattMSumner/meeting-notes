# Schema-grounded prompt diagnostic — 2026-11-26

**All three prospective development controls met their criteria in this run.**
The clear commitment and timing were retained, the partial withdrawal kept surviving
work and cancellation context together, and the availability-only input selected no
passages. All three returned strict stop answers below the 4,096-token cap.
The Chief reviewed each actual render before continuation. Independent primary saved-evidence
and source-meaning review separately passes with zero necessary findings. No production
or M10 acceptance follows.

Read [prospective criteria](criteria.json), [authorization](authorization.json),
[assessment](assessment.json), [verification](verification.json),
[launch envelope](launch.json), [post-audit observation](launch-final-observation.json),
and [preservation seal](seal.json). The seal follows final independent report acceptance.

## Fixed change and observed meaning

The owner said “Great do it” to three controls, once in fixed order. Each request
appends the exact unchanged per-case JSON schema to the existing system prompt, after
`Output JSON Schema (also supplied in format):`. The API format, original prompt prefix,
user input, decoder and literal renderer stay unchanged. No answer example, authored
selection or forced nonempty group is supplied. This follows
[Ollama’s schema-grounding recommendation](https://docs.ollama.com/capabilities/structured-outputs);
that recommendation and this run do not establish the cause of earlier failures.

| Original control | Actual selected group references | Source-meaning assessment |
| --- | --- | --- |
| front_loaded_timing | [[T1]] | Meets: full sending undertaking and Next Tuesday timing. |
| partial_coordination_retracted | [[T1, T2]] | Meets: surviving invoice sending plus complete original/withdrawal context in one focused group. |
| accepted_status_answer | [] | Meets: availability facts create no undertaking and no passages are selected. |

The complete snapshots are preserved in the [frozen inputs](../work-review-schema-1/snapshots.json).
Actual results, renders and in-run meaning verdicts are linked per case in assessment.json.
In the partial-withdrawal view, the original compound undertaking and explicit withdrawal
are copied as source passages requiring human resolution; cancelled review is not
presented as a current suggested action. This accepted passage-review contract differs
from the earlier failed action-list contract. Original writing remains separately saved
and empty as supplied. A generic empty warning is not the basis for the negative grade:
the complete original question and answer contain no genuine undertaking.

## Captured metrics

| Metric | Clear commitment | Partial withdrawal | Availability only |
| --- | ---: | ---: | ---: |
| Generation HTTP wall (s) | 14.476 | 103.217 | 59.477 |
| Server total (s) | 14.400 | 103.122 | 59.427 |
| Model load (s) | 5.361 | 0.003 | 0.002 |
| Prompt evaluation (s) | 0.885 | 0.950 | 0.942 |
| Output evaluation (s) | 8.145 | 102.145 | 58.458 |
| Prompt tokens returned | 337 | 381 | 373 |
| Cached prompt tokens returned | 0 | 0 | 0 |
| Output tokens returned | 312 | 3765 | 2210 |
| First thinking receive (s) | 6.258 | 0.980 | 0.972 |
| First answer receive (s) | 13.774 | 102.799 | 59.291 |
| Thinking characters | 1265 | 15277 | 8996 |
| Answer characters | 44 | 26 | 14 |
| Complete NDJSON records | 295 | 3458 | 1935 |
| Raw generation body bytes | 43794 | 513565 | 287937 |
| Output tokens / output-evaluation second | 38.305 | 36.860 | 37.805 |

Receive timings are measured from each HTTP child’s monotonic origin, including load/
prompt costs, not GPU clocks. Server counters are returned terminal values. Records,
chunks and characters are not token counts. Full probe-call wall is **298.344 s**,
including Chief review waits, metadata, repeated source validation and finalization.
It is not the sum of generation latency. No latency or review-effort target is agreed.

## Execution, identity and accounting

The fixed profile is Qwen3.5 9B Q4_K_M with thinking/streaming true, temperature 1,
context 32768 and num_predict 4096, no seed override. Limits were **3 generation requests /
540 s overall / 180 s each / 10 s metadata / 0 retries**. A length terminal would have
stopped later requests without publishing a partial answer; none occurred.
All three requests were attempted, all three answers/renderings/reviews completed,
and no slot failed or remained unsent. The allowance is **closed**; no retry, resumption,
replacement or unused wall-time transfer is authorized.

There are 21 HTTP 200 exchanges: 3 generation and 18 metadata, with
6 before/after identity/default gate sets matching saved
Ollama 0.40.13, model digest, capabilities, thinking support and parameters. Every child
returned 0 and was reaped; no kill, timeout, error, artifact-save failure or overrun
was recorded. Strict stream/progress replay and unchanged decoder/renderer replay pass.
Raw thinking is retained as machine evidence only; this report reproduces no trace.

The authoritative saved capture accounting equals returned accounting. Its boundary is
after final.json saving and inventory hashing, before manifest writing; final.json is
explicitly non-authoritative. Sealed elapsed is 298.343619334046 s; separate
post-seal elapsed is 298.343838208995 s. Independent full probe-call wall is
298.343869209057 s. The execution.json audit is itself a labeled pre-save
snapshot. The separately archived terminal observation measures
298.344126625045 s after that audit was closed, with
execution_audit_saved=true and no 540 s overrun. Final completion requires this later
observation as well as the saved seal and post-seal observation.

## Source, publication and scope

Exact source candidate `2d48ec947d1676d6901d2fa2ea1d08d924536ed7` was independently accepted with
zero necessary findings and zero source repair rounds. The exact same five-file S1
snapshot passed 218 targeted offline tests in 109.38 s and the one required full suite:
**2,261 passed, 6 integration tests excluded, 635.69 s**, plus formatting, lint and strict
types. The worker independently verified Chief raw logs and before/after source pins
before committing; no duplicate worker full suite or live model calls occurred.

The 85-artifact freeze plus manifest was published at
`cf02e18b682050691abb2005cb3873d68c2c12ae` before inference. Freeze manifest SHA256:
`180b797197a8178db7aefeb467bdcfac8bdc7e007a615336355bde483a2f4876`. Generation:
`work-review-schema-848970109b774c66ba76b63352f5e686`. Capture has 174 artifacts plus manifest,
SHA256 `4674e69b107bceb14d9727818234e07b3addd542738dbe71cb4aa8a8de678cb9`. All 2,099 prior tracked evaluation/prototype
files remain byte-exact. Both inventories are immutable; later analysis lives only in
this sibling directory.

These are three familiar development inputs with one observation each and fixed order,
not blinded or held-out cases. Cold load, host state, prompt size and stochastic output
limit comparisons. The clear-control request differs from the saved temperature-1
request only in the schema appendix, but that old observation is historical context,
not a fresh matched control. No causal prompt-benefit, reliability, model-switch or
thermal/memory claim follows. No new thermal telemetry was collected.

This establishes initial feasibility on these three controls only. Broader regression,
fresh examples/repetitions, full-draft quality, persistence/edit protection, review effort
and current synthetic Obsidian usefulness remain unproven. Earlier failed/incomplete
grades and production V11 stay unchanged. M10 remains unbuilt and PR 16 is not ready
to merge. Further model runs need separately agreed scope and budget.
