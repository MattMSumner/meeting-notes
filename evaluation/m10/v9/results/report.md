# M10 V9 evaluation results

**V9 fixes the observed completion and agreement-loss failures in this run, but still fails
quality because it does not identify the shared-numbers disagreement.** All 13 proposed
summaries complete on the first request. Both previously stalled cases finish; the independent
release agreement survives; the status conflict no longer includes the verification task.
M10 remains unbuilt, and the PR is not ready to merge.

## Scope and provenance

The user explicitly approved the same bounded evaluation: one repetition of all 13 synthetic
cases in each arm, at most 78 requests (52 baseline, 26 proposed). This run at `cc661cf` used
**26 requests: 13 baseline and 13 proposed**, leaving 52 unused. Both arms completed all cases.
No corrections, transport failures, selective reruns, extra repetitions or in-run tuning occurred.
No real meetings or vault files were used. The run lasted about 9 minutes 46 seconds.

Ollama 0.40.9 and qwen3:30b digest
`ad815644918f0eaab341c12b67837cc6dd4562342cdaf118f83d5d554cb37226`
remained stable before, between and after arms. Temperature zero, thinking enabled, context
32768, transport timeout 600 seconds and bounded correction policy were unchanged. Fresh
baseline summaries are identical to V8. All prior frozen artifacts and V9 inputs verify.
The freeze README records the pre-run state; this directory records subsequent results.

All 13 proposed requests match the frozen per-case schemas, and returned reference IDs
belong to the flat source vocabulary. Source-kind checks still run at validation. All 13
selected summaries replay exactly from saved drafts/passages/context, including warnings
and blocking findings, and validate in wrapper version 8. No selected numeric warnings remain.
Five actions have review text; seven have assigned due values.

## Outcomes

| Case | V9 outcome |
|---|---|
| empty | Both tasks and the independent “Agreed, release Friday.” survive. Code retains the separate agreement source while suppressing task prose. Agreement repeats in three sections; rollback has an unnecessary timing review. |
| sparse | Both tasks, next-week recovery, monitoring $120 and no selected option survive. Written focus is separate; repeated facts and raw ID markers reduce polish. |
| additional | Both spoken tasks and dates survive; written-only 40 seats and venue request remain separate. N1/N2 markers appear in prose. |
| conflicting | Finishes in about 25 seconds, versus a V8 timeout. Price and date conflicts are separate and unresolved, “I think” survives, budget remains unapproved, and verification is retained. |
| ambiguous_dates | Complete conditional relative due survives. Notes suggestions stay separate; no launch decision is duplicated and T4 leaks into prose. |
| same_speaker_tasks | Both tasks retained; Friday only belongs to sending. |
| coordinated_tasks | Both tasks and Friday preserved together under review, no assigned rollback deadline. |
| later_timing | Original rollback task and Friday answer preserved in unverified review; due null. |
| revised_timing | Original task and Monday correction preserved under review; Friday not assigned unqualified. |
| shared_numbers | Finishes in about 17 seconds, versus a V8 timeout, but conflicts is empty. Support 120 is stated unqualified in key points and support 150 separately in notes, without identifying their disagreement. Monitoring 120 and invoice task survive. |
| status_conflict | Only the two readiness accounts appear in the conflict. “I think” survives, and the health-check task remains independent with no review. |
| tentative_task | Only Alex's checklist tomorrow is assigned. Sam's noncommitment is omitted from prose, not promoted to an action. |
| front_loaded_timing | Original sending task and Next Tuesday preserved under review; due null. |

The source grammar and prompt both changed. A single successful pass cannot prove what
caused V8's timeouts or isolate which change improved completion. The old timed-out requests
returned no draft. There is no timeout-only rerun or claim of established reliability.

## Scores

Order: commitment completeness, source attribution, conflicts, numbers, dates/owners,
useful emphasis; each 0–2. Baseline is assessed only against its transcript input. The
same partial-credit treatment of conservative timing review is retained.

| Case | Baseline | V9 |
|---|---|---|
| empty | 2/2/2/2/2/2 | 2/2/2/2/2/1 |
| sparse | 2/2/2/2/2/2 | 2/2/2/2/2/1 |
| additional | 2/2/2/2/2/1 | 2/2/2/2/2/1 |
| conflicting | 2/2/2/2/2/2 | 2/2/2/2/2/1 |
| ambiguous_dates | 2/1/2/2/1/1 | 2/2/2/2/2/1 |
| same_speaker_tasks | 2/1/2/2/0/1 | 2/2/2/2/2/2 |
| coordinated_tasks | 2/2/2/2/2/1 | 2/2/2/2/1/1 |
| later_timing | 2/2/2/2/2/1 | 2/2/2/2/1/1 |
| revised_timing | 2/2/2/2/2/2 | 2/2/2/2/1/1 |
| shared_numbers | 2/2/2/2/2/2 | 2/2/0/1/2/1 |
| status_conflict | 2/1/2/2/2/1 | 2/2/2/2/2/2 |
| tentative_task | 2/2/2/2/2/1 | 2/2/2/2/2/1 |
| front_loaded_timing | 2/2/2/2/2/1 | 2/2/2/2/1/1 |

Codex scored shuffled opaque labels before joining the key. Notes, output structure and
review fields reveal arm information, so this is label blinding, not independent or fully
blinded assessment. Evidence is in blinded-scores.json; scores.json joins the arm key.
One repetition of familiar fixtures does not estimate variability or performance on new data.

All spoken commitments and the independent release decision survive. Written context is
useful and separated. However, shared_numbers fails the explicit unresolved-conflict
requirement: the spoken support price is presented unqualified despite a conflicting note.
Both numbers are copied correctly, so source attribution scores 2, but conflict scores 0 and
numeric meaning scores 1. This is a critical quality failure, not a missing numeric token.
Even under a less strict criticality interpretation, it does not satisfy the required conflict
behavior. Baseline again extends Friday to rollback and turns tentative readiness into
confirmation; those errors do not excuse the proposed failure.

## What the changes do and do not establish

The narrow agreement diagnostic and mixed task/fact conflict diagnostic request correction;
they never manufacture decisions or remove disputed tasks. Offline replay of the V8 replies
in ../replay.jsonl exposes the observed failures, and fake-transport tests verify corrections.
No live V9 draft triggered either diagnostic, so this run does not demonstrate live correction
success. The first drafts already include the independent agreement and a narrow status
conflict. Both proposed and baseline retain the existing bounded correction behavior.

For empty notes, the draft cites the independent agreement along with tagging; the compiler
preserves its source text when suppressing task prose. The draft also supplies the whole
rollback statement as a timing quote, which has no date and yields unnecessary review rather
than a fabricated deadline. For status_conflict, duplicate references are deduplicated; the
verification task is not among them.

The remaining shared-numbers failure is visible in the raw draft: conflicts is empty, with
T2 support 120 in key points and N1 support 150 in notes_context. Current checks establish
reference integrity and numeric presence, not semantic disagreement completeness. A future
candidate needs to address missed cross-source conflicts without conflating unrelated facts
that happen to share numbers. Do not treat keyword or numeric overlap as proof of conflict.
That work requires a new freeze and separately agreed evaluation scope; no further inference
was performed from the unused allowance.

## Verification and status

Formatting, lint, strict types and all **482 offline unit tests** pass (six integration tests
excluded). Published prior generations retain their original validators. No capture code
changed; no hardware tests were needed. All frozen manifests verify unchanged. No private
meeting material is included.

The prior three PR review bugs remain fixed. V9 improves the specific V8 failures, but the
remaining conflict failure and current manual review-workflow acceptance keep M10 unbuilt.
No Built note or merge is warranted by this result.
