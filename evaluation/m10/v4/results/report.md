# M10 V4 evaluation results

**Quality acceptance failed. M10 remains unbuilt.** The approved one-repetition comparison
completed all 13 cases in both arms. V4 produced nine summaries and four validation failures;
baseline produced 13 summaries. V4 additionally loses the Friday answer in later_timing,
omits the monitoring cost in sparse, and frequently asks for unnecessary timing review.
No tuning, extra repetitions or further inference occurred.

## Run and provenance

The owner approved one repetition across 13 cases and both arms, capped at 78 requests
(52 baseline, 26 proposed). The run used **36 requests: 13 baseline and 23 proposed**,
leaving 42 unused. Twenty-two summaries and four explicit failures were saved. Here,
publication means a retained evaluator summary, not writing to a real Obsidian meeting.

Ollama 0.40.9 and qwen3:30b digest
`ad815644918f0eaab341c12b67837cc6dd4562342cdaf118f83d5d554cb37226`
were unchanged before, between and after arms. Temperature zero, thinking enabled and
32768 context were unchanged. There were no transport errors. All frozen inputs and
V1–V3 results verify unchanged. All baseline summaries are identical to the V3 baseline
summaries, though this run generated them afresh.

`run.json` records revision, environment, caps and hashes. `completion.json` records every
case's request, publication, assigned-due and review counts. JSONL files preserve full
requests, responses and proposed validation/selection audits. No real meeting data is used.

## Original five cases

| Case | V4 result | Finding |
|---|---|---|
| empty | Published after correction | Both named tasks and Friday release agreement retained. Sam's simple Friday due becomes review-only; Alex receives timing review despite having no deadline. Source IDs leak into prose. |
| sparse | Published first attempt | Both named commitments, recovery next week and no chosen option retained. Monitoring's 120 dollars is omitted from the model draft itself. The emphasis cue is copied as notes context. |
| additional | Published after correction | Written 40 seats and venue task stay separate; both spoken tasks remain. Each task incorrectly cites the other task as timing context, so both straightforward dates become review-only. |
| conflicting | Published after correction | Both 120k/150k and June/July accounts remain unresolved, including “I think.” Verification and unapproved budget remain. No disputed value is presented as a settled core fact. |
| ambiguous_dates | Blocked after correction | Both replies put full task prose in commitment rather than a source ID. No conditional sending task or written follow-up is delivered. |

Publication is 4/5 versus 5/5 baseline. The original conflict case improves on previous
observed outcomes, but one repetition does not establish reliability. Conditional timing
acceptance is unavailable because that case blocks. The additional written context is useful,
but excessive review makes its otherwise explicit task timing harder to use.

## Eight boundary cases

| Case | V4 result | Finding |
|---|---|---|
| same_speaker_tasks | Published after correction | Both tasks retained without a borrowed rollback deadline. Sending Friday is unnecessarily review-only because timing_context points to its own commitment. |
| coordinated_tasks | Published first attempt | One permitted grouped checkbox preserves both tasks and the Friday wording for review, with no assigned due. |
| later_timing | Published first attempt; fails timing criterion | Model proposes Friday as timing but cites only “When?” as timing_context. Compiler suppresses the prose containing Friday and retains only the question in review. Friday disappears entirely. |
| revised_timing | Blocked after correction | commitment is “Monday” rather than a source ID in both replies. Retry repairs context IDs but not the commitment. No sending task or revised deadline is delivered. |
| shared_numbers | Blocked after correction | Model cites written N1 in spoken key points. Retry fixes the task reference but leaves that wrong-source entry. No invoice commitment or support conflict is delivered. |
| status_conflict | Blocked after correction | Overview and key points cite N1 alongside T1. Retry fixes the task reference, but source validation still blocks those entries before conflict neutralization. |
| tentative_task | Published after correction | No Sam rollback task is invented; Alex's checklist remains. Tomorrow is unnecessarily review-only because context repeats the commitment itself. |
| front_loaded_timing | Published after correction | Sending task and Next Tuesday remain visible in a properly labelled review item. The source is repeated as additional timing evidence. |

Publication is 5/8 versus 8/8 baseline. Nine review items appear across seven published
V4 cases; only one assigned due value remains across all 13 published action items
(Alex's recovery next week in sparse). These counts do not imply every review item had a
valid deadline to withhold: Alex's empty-case rollback has none, and later_timing loses its
answer. The nine items include a grouped commitment containing two tasks.

## Scores

Order: commitment completeness, source attribution, conflicts, numbers, dates/owners,
useful emphasis. Each is 0–2. Blocked rows receive zero for missing deliverables, not six
observed fabrications. Baseline is judged against transcript only. A quoted review earns
partial date credit only when the relevant timing survives; later_timing earns none.

| Case | Baseline | V4 |
|---|---|---|
| empty | 2/2/2/2/2/2 | 2/2/2/2/1/1 |
| sparse | 2/2/2/2/2/2 | 2/2/2/1/2/1 |
| additional | 2/2/2/2/2/1 | 2/2/2/2/1/1 |
| conflicting | 2/2/2/2/2/2 | 2/2/2/2/2/1 |
| ambiguous_dates | 2/1/2/2/1/1 | blocked: 0/0/0/0/0/0 |
| same_speaker_tasks | 2/1/2/2/0/1 | 2/2/2/2/1/1 |
| coordinated_tasks | 2/2/2/2/2/1 | 2/2/2/2/1/1 |
| later_timing | 2/2/2/2/2/1 | 2/2/2/2/0/0 |
| revised_timing | 2/2/2/2/2/2 | blocked: 0/0/0/0/0/0 |
| shared_numbers | 2/2/2/2/2/2 | blocked: 0/0/0/0/0/0 |
| status_conflict | 2/1/2/2/2/1 | blocked: 0/0/0/0/0/0 |
| tentative_task | 2/2/2/2/2/1 | 2/2/2/2/1/1 |
| front_loaded_timing | 2/2/2/2/2/1 | 2/2/2/2/1/1 |

Codex reviewed outputs shuffled under opaque IDs, saving judgments before joining the arm
key. Schema, review fields, errors and supplied notes reveal arm information; this is label
blinding, not an independent or fully blinded review. Exact source/output evidence is in
`blinded-scores.json`; `scores.json` joins the key. The baseline repeats its unsupported
rollback deadline in overview and strengthens tentative readiness into confirmation.
Neither baseline error excuses the proposed completeness and timing failures.

## Corrections and diagnosis

Ten V4 cases requested one correction each. Six became publishable (empty, additional,
conflicting, same_speaker_tasks, tentative_task, front_loaded_timing); four remained blocked.
Sparse, coordinated_tasks and later_timing published on their first attempt. All selected
drafts have zero numeric warnings. Missing a number entirely, as in sparse, does not trigger
the numeric presence checker.

The raw attempts support these specific findings:

- **Source-ID confusion persists.** The schema accepts ordinary strings for commitment and
  timing_context. The model repeatedly supplies quotations, paraphrases or a date instead
  of IDs. Corrections repair some of these, but not ambiguous_dates or revised_timing.
- **Timing context is misused.** Self-references trigger review because the compiler treats
  any context as a separate timing exchange. Additional pairs unrelated task IDs. This
  prevents invented assigned dates, but makes valid explicit deadlines unnecessarily hard
  to use and even creates review for a task with no timing.
- **Source filtering and conflict assembly interact poorly.** Shared_numbers and
  status_conflict already identify both sides in conflicts, but written references in core
  prose cause blocking before neutralization can discard those entries. This is a
  representational failure; it does not establish the underlying conflict judgments passed.
- **Prose suppression can erase timing.** In later_timing, the model's overview and bullets
  contain Friday with T1/T3 evidence. The action instead has timing_context T2 (the question).
  Suppressing the prose leaves the action's review without the answer. Zero numeric warnings
  and a valid source ID do not catch this loss.

Compared with V3's single pass, V4 produces nine summaries rather than five and uses 23
proposed requests rather than 25. That is an observed output-rate improvement, not a quality
pass or a statistical reliability claim. The compiler's offline replay could not predict
these newly generated reference choices.

## Acceptance and next work

Four absent summaries regress spoken commitment completeness versus baseline. The missing
Friday answer independently fails an explicit timing criterion. Excessive review and omitted
monitoring context further reduce usefulness. The agreed one-repetition evaluation is complete;
no extra inference or candidate changes are included.

Any next revision should address source-ID representation, self/unrelated timing context,
and preservation of later answers before another freeze. Do not infer that more retries or
another wording change will solve the semantic cases. Preserve this scored candidate and
agree a separate budget for any new freeze.

Formatting, lint, strict types and 342 unit tests pass (six integration tests deselected).
No capture changes. The original manual workflow was reported complete; V4 review behavior
still needs manual acceptance. M10 remains unbuilt and PR #16 stays unmerged.
