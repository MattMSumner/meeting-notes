# Quoted-selection draft diagnostic — 2026-11-13

**INCOMPLETE: two requests captured, one draft compiled, one response rejected and four
cases unsent.** The approved run stopped after source-reference validation failed in the
second response. Exact quotation constrained wording, but the rejected response still
selected a factual price statement as an action/decision. This is no quality pass and
establishes no repair of the original availability or surviving-work failures.

The owner explicitly approved six local qwen3:30b requests / fifteen minutes, no retries.
This once-only run used **two requests in 184.814 seconds (3m05s)**, with zero overrun.
There were no retries, corrections, baseline or selective reruns. The predeclared stopping
rule terminated the run on validation failure. The four unused slots authorize neither
resumption nor another experiment. Every captured response and failed outcome is retained.

## Source-based assessment

| Case | Outcome | Findings |
| --- | --- | --- |
| [additional](01-additional/draft.md) | Compiled; meets its case criterion with partial findings | Both spoken undertakings retain owners/timing; original writing stays separate. Summary, decisions, actions and review repeat the same material, with excessive reciprocal context and generic notices. |
| [unit equivalence raw reply](02-unit_equivalence/response/body.raw) | **Incomplete; rejected before draft creation** | The response repeats T1 in summary citations and review references. It also selects a price fact as an action/decision. Its critical raw source/separation defect includes a written price in a speech-only summary with speech-only citations. No rejected claim was published. |
| accepted_status_answer | **Unsent** | No evidence that availability no longer creates invented work under this contract. |
| cancellation_with_new_task | **Unsent** | No new model evidence about cancellation and independent invoice sending. |
| partial_coordination_retracted | **Unsent** | No evidence that the surviving-work failure is repaired. |
| qualified_external_timing | **Unsent** | No new model evidence about complete timing/condition handling. |

In the rejected reply, both Actions and Decisions select the exact spoken price sentence.
Its wording is literal, but a price fact is not an undertaking or decision. The summary
mentions the spoken and written prices while listing only speech references, duplicated.
It also requests a needs-review state with an empty notice. No conflict, equivalence or
computed conversion was asserted. The first observed failure is `Source references must
be unique`; no draft/extraction artifact was created for this case. Do not repair its
references offline and count the altered response as a successful generation.

The completed additional-context draft improves action discoverability in this one
capture: both undertakings appear under Actions. Heavy repetition still adds review
burden. One familiar case does not establish an improvement in general reliability.
The saved draft retains its original capture-time “assessment pending” label; this report
and the separate assessment record the subsequent verdict without rewriting that artifact.

An independent read-only Codex assessor and the Chief inspected the sources, raw replies,
one rendered draft and accounting against the [frozen criteria](../EXPERIMENT.md).
See [assessment.json](assessment.json) for classifications. Assessment was post-capture,
not blinded; all six cases are familiar development material. Only two were captured once.
No reliability, full forty-case regression, measured editing benefit, current Obsidian
acceptance or Built/merge readiness is established. V11 and the first diagnostic retain
their original failed outcomes.

## Engineering evidence

- Source candidate: `9e369ad51b55ed324a5377463e76822a5951def6`.
- Freeze committed and pushed before inference: `77fd9d3526ce8759ab9915c852209be820d84c0b`.
- Manifest SHA256: `0cbaafa34c9f538eaa6b5cc43158d1f21429e7e85c197fc79372bc0f24ad28bf`.
- All nineteen frozen artifacts, all forty original inputs, 486 historical/sealed entries,
  eighteen first-diagnostic freeze entries and 157 first-result entries verify unchanged.
  All six earlier draft JSON/Markdown artifacts reproduce exactly.
- Two POSTs and eight metadata GETs, all HTTP 200 with no captured transport errors.
  Both replies have `done=true`, `done_reason=stop`. No truncation or identity drift.
- Before/after identities match Ollama 0.40.9 / qwen3:30b, digest
  `ad815644918f0eaab341c12b67837cc6dd4562342cdaf118f83d5d554cb37226`.
  Temperature zero, thinking enabled, context 32768; no settings or source changes.
- Requests equal frozen packet bytes. The first draft JSON/Markdown reproduces exactly;
  decoding the unchanged second reply reproduces the same reference-uniqueness error.
- [final.json](final.json) is the authoritative final accounting. `running.json` is the
  initial audit snapshot, not current progress. [launch.json](launch.json), all per-slot
  requests/statuses/raw bodies and [verification.json](verification.json) preserve bindings.
- Slot elapsed: additional 103.687 seconds; unit_equivalence 80.978 seconds. Run preflight
  and capture overhead are included in the total 184.814 seconds / 900-second ceiling.
  Client termination cannot prove server compute cancellation; no timeout occurred.

The extractor and separate profile passed independent engineering review at `9e369ad`
with no findings/formal repairs. Formatting, lint, strict types and **1234 offline tests
pass**; six model/hardware integration tests excluded, capture unchanged. Authored examples
and faithful replay establish mechanical behavior, not admissibility or model quality.
Production CLI, pipeline, prompts, store, wrappers, model settings and vault are unchanged.

## Next work

Keep the approved reviewable presentation. Reassess the smallest model-facing task before
another experiment: simplify avoidable response-state/reference burden, and inspect
whether work extraction should be evaluated separately from summary generation. Treat
semantic selection as a distinct capability; additional quote checks cannot establish it.
Do not grow a semantic validator or keep rerunning the same cases to obtain a pass.

This is a recommendation, not another implemented candidate or inference authorization.
A subsequent candidate requires concrete criteria, independent review, exact freeze and
fresh request/time approval. Full regression, production snapshot/persistence/edit
safeguards and current synthetic Obsidian usefulness acceptance remain pending. M10 stays
unbuilt, application behavior stays V11, and only owner `shipit` authorizes merging.
