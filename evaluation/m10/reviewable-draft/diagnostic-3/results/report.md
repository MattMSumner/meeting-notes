# Action-only diagnostic — 2026-11-13

**All six captures completed; one critical surviving-work omission remains.** Five cases meet the
prospective action-only criteria. Partial cancellation produces no action or focused
review, omitting surviving invoice sending from the rendered draft. This is no overall
quality pass, full draft evaluation or production-readiness claim.

The owner replied “yes please!” to the frozen six-case experiment, at most six local
qwen3:30b requests / fifteen minutes, no retries. The once-only run used **six requests in
247.310 seconds (4m07s)**. All six replies decoded and rendered, with no transport/format/
literal-validation failures, incomplete extraction records, retries, unsent cases or
overrun. Capture completion is separate from useful retention and semantic quality.
All six approved requests are used; no further inference or resumption followed.

## Source-based assessment

| Case | Outcome | Evidence and limits |
| --- | --- | --- |
| [unit equivalence](01-unit_equivalence/actions.md) | Meets action-only criterion | No action from the price fact. Speech and writing remain in the complete saved snapshot; writing was excluded from the model request and is copied separately into Markdown. No conflict or computed relationship is asserted. This does not test summary/comparison quality. |
| [availability answer](02-accepted_status_answer/actions.md) | Meets criterion | No action or invented rescheduling from the availability question/affirmation. Empty writing remains valid. Decision generation was outside this experiment. |
| [partial cancellation](03-partial_coordination_retracted/actions.md) | **Critical retention failure** | Actions and review references are both empty. The source promises draft review and invoice sending, then withdraws review only. Invoice sending is not identified as work or focused review. |
| [cancellation with replacement](04-cancellation_with_new_task/actions.md) | Meets criterion | Invoice sending survives cancelled draft review, with the complete primary passage visible and no invented due date. Redundant self-context is normalized; raw output remains exact. |
| [qualified timing](05-qualified_external_timing/actions.md) | Meets criterion | Invoice sending retains the complete later not-before/next-Friday/finance turn as context and focused review. No new deadline is assigned. |
| [additional context](06-additional/actions.md) | Meets criterion, with partial repetition | Both spoken undertakings retain owners/timing. Original venue task/capacity remains separate writing. Reciprocal context repeats material; the channel label remains Them although Alex self-identifies in the quote. No work is invented. |

The failed source says that the speaker will review the draft and send the invoice, then
says they will not review the draft. The reply is exactly `actions: []`, `review_sources: []`.
The rendered artifact supplies only a generic no-suggestions disclaimer and no spoken
source excerpts. The complete source remains in `result.json` and the frozen snapshot;
that backend retention does not satisfy the declared requirement to make surviving work
available as work or focused review. No incorrect replacement task is invented, and this
is reported separately from false obligations or source/number changes. The current
critical classification reflects its rendered omission and does not regrade earlier results.

The literal validator cannot detect this omission. No selection was returned to check,
so the response is mechanically complete. The disclaimer that no suggestions does not
prove no work was missed is honest; it does not turn the missing work into a pass.

These are the same familiar six development inputs and one repetition, with a smaller
model task. Summary and decisions are not requested; writing is not model input. Do not
compare pass counts as a full-draft quality improvement or regrade V11/earlier failures.
No reliability, full forty-case regression, measured editing-time benefit or current
Obsidian usefulness acceptance follows from this run. See [assessment.json](assessment.json)
for the independent post-capture classifications and [verification.json](verification.json)
for the separate Chief integrity/replay checks. The independent assessor prepared criteria
before viewing outputs; the Chief separately checked sources and agreed. Assessment was
not blinded or held out.

The capture-time “assessment pending” labels and final audit remain unchanged. Subsequent
assessment is recorded here rather than rewriting the captured artifacts.

## Engineering evidence

- Exact reviewed source: `287d85b2229e0c03c6434337a2337bf777e5a136`.
- Freeze committed/pushed before approval/inference: `7381d8e7316bfe2e5cdac7277e9cbb789b3bd2e4`.
- Manifest SHA256: `472027ef8be047233a3a8cf75630c922afe28c96b73911b844619c16b33e8bd3`.
- All twenty current frozen artifacts and 736 previous historical/frozen/result entries
  verify unchanged. All forty original regression inputs remain exact.
- Six recorded POSTs and 24 metadata GETs, all HTTP 200 without captured errors. Every
  reply has `done=true`, `done_reason=stop`; all saved JSON/Markdown artifacts reproduce
  exactly from raw content and frozen host snapshot/generation bindings.
- All before/after identities match Ollama 0.40.9 / qwen3:30b, digest
  `ad815644918f0eaab341c12b67837cc6dd4562342cdaf118f83d5d554cb37226`.
  Temperature zero, thinking enabled, context 32768; no source/settings drift.
- Replacement-task raw context contains its own primary T1; code removes the redundant
  context after validating it. The full primary source remains visible. This follows
  the frozen normalization contract; no raw reply or historical result is repaired.
- [final.json](final.json) is authoritative run accounting; `running.json` is the initial
  snapshot. [launch.json](launch.json), every per-slot attempt/request/outcome, raw reply
  and before/after metadata are retained. Separate assessment/verification/result hashes
  preserve subsequent findings.

| Case | Slot elapsed |
| --- | ---: |
| unit equivalence | 32.011 s |
| availability answer | 22.681 s |
| partial cancellation | 19.594 s |
| cancellation with replacement | 46.725 s |
| qualified timing | 66.483 s |
| additional context | 59.666 s |

Preflight and capture overhead are included in total 247.310 seconds, below the 900-second
ceiling with zero overrun. Client termination cannot prove server compute cancellation;
no timeout or interruption occurred.

Independent engineering review passed after one accounting repair. Formatting, lint,
strict types and **1335 offline tests pass**; six integration tests excluded, capture
unchanged. Frozen-head Python and Swift CI passed. Mechanical checks and faithful replay
establish no semantic acceptance. Production CLI, pipeline, prompts, settings, store,
wrappers and vault remain unchanged; application behavior stays V11 and M10 stays unbuilt.

## Next decision

Keep this smaller contract as a benchmark. The remaining observed failure is selecting
surviving work after a partial withdrawal, rather than response formatting. Do not add
more quote validators or automatically rerun these cases to obtain a pass. Consider a
bounded model comparison under the same contract before further pipeline changes; that
is a recommendation, not an implemented candidate or new inference budget.

Full regression, production snapshot/persistence/edit safeguards and current synthetic
Obsidian usefulness remain pending. Only owner `shipit` authorizes merging. No real-meeting
pilot, production integration, new requirements acceptance or Built note followed.
