# M10 V9 — agreement coverage and simpler reference grammar

Frozen before the authorized evaluation: one repetition of all 13 cases in each arm,
78 requests maximum (52 baseline, 26 proposed). No selective reruns or tuning during the run.
The baseline remains commit 199dd62. Fixtures, rubric, qwen3:30b, temperature zero, thinking,
32768 context and the one-correction limit are unchanged. V1–V8 inputs/results are preserved.

A single shared flat SourceID enum replaces the nested transcript/notes union. All IDs
remain constrained to the snapshot, while source-kind checks run in the compiler on each
attempt. This retains compact request size without truncating sources. The two V8 timeouts
have no returned replies; the schema change is a hypothesis to evaluate, not an established
root cause or fix. Transport timeout remains 600 seconds; no hidden retries were added.

A narrow diagnostic flags uncited explicit agreement markers (Agreed, We agreed/decided),
excluding uncertain/quoted text and adjacent same-speaker retractions. It requests correction;
it never manufactures decisions. It does not prove semantic coverage or recognize every
paraphrase. A conflict mixing selected tasks with other factual statements requests correction
rather than automatically declaring the tasks disputed. Genuinely disputed commitments can
have their own conflict. The prompt clarifies both boundaries.

The post-V8 temporal qualifier fix is included: partial dates can remain under Review required.
New generations use wrapper 8/grounding-v7; versions 6 and 7 retain their original compilers.
Offline tests replay the V8 missing agreement and mixed conflict into diagnostics, then verify
hand-authored corrections through a fake transport. These are regression checks, not live
quality evidence. replay.jsonl records all available V8 replies under the candidate validator;
timeouts have no draft to replay. No private meeting data is included. M10 remains unbuilt.

Subsequent live outcomes belong in results/report.md; this document records the freeze state.
