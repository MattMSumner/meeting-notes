# M10 V8 evaluation results

**V8 fails this frozen single-run evaluation.** It produces 11 of 13 summaries; two
requests time out. The empty-notes summary also omits the independent Friday release
agreement retained by the baseline and V7. M10 remains unbuilt. A separate maximum-effort
PR review found two P1 recovery defects and one P2 deadline defect, all still unfixed.

## Scope and provenance

One repetition of all 13 synthetic cases in each arm ran at commit
`2e0455996c80aae196d7c5ef2f25082d15fc89bf`, under the announced 78-request cap
(52 baseline, 26 proposed). **29 requests were used: 13 baseline and 16 proposed**, leaving
49 unused. All 26 case records are retained, including failed cases. No selective reruns,
extra inference, candidate changes, prompt tuning or real-meeting evaluation occurred.
Publication here means an evaluator summary, not a vault write.

Ollama 0.40.9 and qwen3:30b digest
`ad815644918f0eaab341c12b67837cc6dd4562342cdaf118f83d5d554cb37226`
remained stable before, between and after arms. Temperature zero, thinking enabled and
context 32768 were unchanged. The run lasted about 30 minutes, including two 600-second
transport timeouts. Fresh baseline summaries are identical to V7. V1–V7 frozen inputs and
results and all V8 inputs verify unchanged. The freeze README describes the historical
pre-run state; this results directory records the subsequent authorized evaluation.

All 16 proposed request schemas match the frozen per-case schemas. All 14 returned draft
responses use allowed reference IDs; the other two requests have no response to inspect.
Allowed IDs do not establish correct source use or meaning. Every one of the 11 selected
summaries replays exactly from its saved draft, passages and context through the unchanged
compiler; blocking findings and warnings also match. Selected summaries have zero numeric
warnings. There are five actions with review text and seven assigned due values.

## Outcomes

| Case | V8 result |
|---|---|
| empty | Correction restores Alex's rollback task, but both drafts omit the independent agreement “Agreed, release Friday.” Tagging Friday is retained; the release decision is not. |
| sparse | Correction removes a notes-source reference from unsupported core prose. Both commitments, next week, monitoring $120 and no selected option survive; written focus is separate. |
| additional | Both spoken tasks and deadlines survive on the first attempt. Written-only 40 seats and venue request are separate. |
| conflicting | Transport times out; no summary or reply is available. |
| ambiguous_dates | Correction removes numbers drawn only from meeting metadata. Full conditional relative deadline survives; written follow-up and Casey suggestion remain separate. No launch decision is repeated in two sections. |
| same_speaker_tasks | Both tasks survive; only sending has Friday assigned. |
| coordinated_tasks | Both tasks remain in one source-worded checkbox with Friday in review, without an assigned rollback deadline. |
| later_timing | Original task and later Friday answer remain in unverified review; due is null. |
| revised_timing | Original task and Monday correction remain in review; Friday is not an unqualified assigned deadline. |
| shared_numbers | Transport times out; no summary or reply is available. |
| status_conflict | Both readiness accounts remain unresolved with “I think,” but the draft includes the unrelated health-check task in the conflict, causing an unnecessary disputed-task review. |
| tentative_task | Only Alex's checklist is assigned, tomorrow. Sam's explicit noncommitment is omitted from prose but not promoted to a task. |
| front_loaded_timing | Sam's original sending task and Next Tuesday remain in review; due is null. |

The two timeouts occurred on initial requests and did not trigger selective retries. The
successful status-conflict case means conflicting source material does not always time out.
The trace cannot establish whether schema grammar, model generation, server behavior or
another factor caused the timeouts. No failed response exists to diagnose its content.

## Scores

Order: commitment completeness, source attribution, conflicts, numbers, dates/owners,
useful emphasis; each 0–2. Baseline is assessed only against its transcript input. Zero
scores for unavailable outputs indicate missing results, not six fabricated claims.
Review-preserved timing earns partial credit consistently with prior evaluations.

| Case | Baseline | V8 |
|---|---|---|
| empty | 2/2/2/2/2/2 | 1/2/2/2/2/1 |
| sparse | 2/2/2/2/2/2 | 2/2/2/2/2/2 |
| additional | 2/2/2/2/2/1 | 2/2/2/2/2/2 |
| conflicting | 2/2/2/2/2/2 | 0/0/0/0/0/0 |
| ambiguous_dates | 2/1/2/2/1/1 | 2/2/2/2/2/1 |
| same_speaker_tasks | 2/1/2/2/0/1 | 2/2/2/2/2/2 |
| coordinated_tasks | 2/2/2/2/2/1 | 2/2/2/2/1/1 |
| later_timing | 2/2/2/2/2/1 | 2/2/2/2/1/1 |
| revised_timing | 2/2/2/2/2/2 | 2/2/2/2/1/1 |
| shared_numbers | 2/2/2/2/2/2 | 0/0/0/0/0/0 |
| status_conflict | 2/1/2/2/2/1 | 2/1/1/2/2/1 |
| tentative_task | 2/2/2/2/2/1 | 2/2/2/2/2/1 |
| front_loaded_timing | 2/2/2/2/2/1 | 2/2/2/2/1/1 |

Codex scored shuffled outputs with opaque labels before joining the arm key. Supplied notes,
output schema and review fields reveal arm information, so this is label blinding, not an
independent or fully blinded assessment. `blinded-scores.json` records evidence and
`scores.json` joins the key. One repetition of familiar fixtures cannot estimate variability
or reliability on new meetings. The baseline repeats its unsupported Friday rollback
claim and its conversion of tentative readiness to confirmation; those errors do not excuse
V8 failures. No published V8 output was scored as inventing a deadline, owner or number, or
settling a disputed fact. Nevertheless, missing outputs and the lost release agreement fail
the completion and no-completeness-regression criteria.

## Correction evidence

Three cases use the single correction allowance:

- **Empty:** the first draft contains only T1 tagging. The omitted-commitment diagnostic
  flags T3 rollback; correction restores it. Neither draft cites T4, “Agreed, release Friday.”
  Task-prose suppression removes redundant T1 prose; it cannot restore the uncited agreement.
- **Sparse:** the first draft triggers `Invalid transcript source: N1`. The corrected result
  retains the spoken commitments and cost, with the note's deployment focus kept separate.
- **Ambiguous dates:** the first draft's overview includes metadata-only numbers 2026, 10,
  20 and 14. Source-specific warnings trigger correction, which removes them and preserves
  the complete conditional deadline. Both attempts are valid; the improved second is selected.

The additional-notes case needs no correction in V8, unlike V7. Differences in this one run
are observations, not evidence that the new representation consistently improves that case.

## Independent PR review and next work

The fresh maximum-effort subagent reviewed the full PR at the evaluated commit without
reading these results. It reproduced three defects using synthetic inputs and passed 180
focused offline tests. [Full review evidence](pr-review.md):

1. **P1:** malformed session JSON produces a different fallback timestamp on each read;
   the recovery claim never matches, so capture is not stopped and another start is possible.
2. **P1:** corrupt meeting metadata raises during title lookup before recovery stops capture.
3. **P2:** partial timing quote `Friday` can turn `after Friday`, `not before Friday`, or
   `at least one week after Friday` into an unqualified Friday deadline without review.

These defects remain unfixed in this run and block merging independently of model quality.
Fix shutdown/recovery and complete timing preservation with synthetic regressions first.
Then investigate timeout behavior and missed independent decisions before freezing another
candidate and agreeing any further inference budget. No next candidate or additional model
run is authorized by this report. Current manual review-workflow acceptance remains pending.

Formatting, lint, strict types and all 433 offline unit tests pass (six integration tests
excluded). No Swift/capture code changed. No private meeting material is included.
