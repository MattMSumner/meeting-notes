# First draft-generation diagnostic — approved 2026-11-13

The owner approved the normal and incomplete preview format on 2026-11-13 (“Yeah these
look good!”). This accepts the authored format, not generated quality or Obsidian use.

## One capability

Test whether one model response can produce the small reviewable draft contract from
saved source passages. Use an isolated request builder/decoder, the existing prototype
model and pure renderer. No production application, persistence or historical wrapper
changes. Original writing remains copied by code; automatic conflict classification,
semantic compilation and a separate comparison stage remain deferred.

The model supplies readable items, references, section state and focused notices.
Code supplies snapshot/generation identity and validates shape/source kinds. Unknown
references or malformed JSON fail the response; they do not trigger a repair request.
An unavailable section contains no accepted items and needs focused literal evidence.
Passing these mechanical checks does not prove factual meaning or completeness.

## Approved run

The owner replied “I approve” to at most six local model requests and fifteen minutes
elapsed. This approval persists through the remaining driver review and exact freeze;
do not ask again before the declared run. It authorizes no retries or follow-up run.

One candidate, one repetition, in this fixed order:

| Case | Predeclared diagnostic criterion |
| --- | --- |
| additional | Keep both spoken undertakings with owners/timing. Keep written venue work and capacity separate from spoken work. |
| unit_equivalence | Retain the spoken price and literal written price without claiming a conflict or computing a relationship. |
| accepted_status_answer | An affirmative availability answer creates no action suggestion. Empty writing remains supported. |
| cancellation_with_new_task | Remove the cancelled draft-review obligation while preserving the new invoice-sending undertaking, with no invented immediate deadline. |
| partial_coordination_retracted | Keep original undertaking and retraction together; make remaining invoice sending easy to find without claiming cancelled review is current. |
| qualified_external_timing | Retain the original sending undertaking with the full “Not before next Friday unless finance objects” condition, or focused review containing both complete passages. |

All six are familiar development inputs selected before any new response. All forty
original inputs/criteria and V11's failed verdict remain unchanged. This is a capability
diagnostic, not full regression, held-out evaluation or release acceptance.

Approved ceilings: **six inference requests total, one per case; fifteen minutes elapsed**.
Keep qwen3:30b, temperature zero, thinking enabled, context 32768 and per-request timeout
at most 600 seconds, further limited by remaining run time. No baseline arm, corrections,
transport retries, warm-up inference, selective reruns or prompt tuning inside the run.
The prior 167 unused requests grant nothing here. Approval covers this diagnostic only.

Before inference, freeze the exact candidate commit, prompt/schema, six prepared request
bodies, input/snapshot hashes, settings and expected model identity. Save all raw requests,
responses/errors and elapsed times in a new directory; preserve failure artifacts as well
as rendered drafts. Verify server/model identity against the declared local installation.
Do not infer unchanged identity from the older V11 run.

Stop submitting requests when the elapsed ceiling is reached, on identity/settings/input
drift, malformed/truncated/failed transport output, or a detected critical semantic defect.
An in-flight request must be bounded by the remaining time; record any overrun/cancellation
and unsent cases honestly. Do not call an incomplete diagnostic a pass. Score every captured
response against all applicable criteria before deciding what to change. If raw outputs
were captured before a semantic failure was detected, retain and assess all of them; do
not select only the favorable ones.

Across cases, invented facts/current obligations, wrong owners/quantities/timing, lost
qualifiers, missing genuine work, source mixing and invented conflict claims are defects.
Focused review can retain genuine ambiguity, but a warning or transcript dump alone is
not useful work. Record completion, critical defects, specific partial findings and latency
separately. The owner then judges whether reviewing the generated draft saves effort;
no numerical editing-time target has been agreed.

## Offline preparation

`generation.py` builds one request from a complete saved `Snapshot`, decodes a response
into the prototype model and supports an injected transport for offline tests. It has no
default network transport, application import, file persistence or inference on import.
The request includes original inputs/context and whole source passages; it includes no
authored target response. The prompt is an instruction; meeting content is untrusted data.
Model-supplied identity fields are disallowed; code binds output to the saved packet.

`prepare` creates the six packets in memory from a caller-supplied snapshot mapping and
host generation identity. The run driver must load and hash-check the unchanged synthetic
inputs; the pure preparation API does not read or attest files. Offline
checks use authored/fake responses only and establish no local-model capability. The
timed run/capture driver must be reviewed and frozen before invoking inference. The
preparation helper alone does not implement or establish enforcement of the run ceilings.

After this diagnostic, inspect the actual failure before adding machinery. Any new prompt,
request, retry or case needs a separately declared follow-up. Full regression, fresh-case
provenance, production persistence safeguards, current synthetic Obsidian acceptance and
owner `shipit` still precede M10 Built/merge.
