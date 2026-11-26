# M10 V6 evaluation results

**Quality acceptance failed. M10 remains unbuilt.** V6 produced 12/13 summaries, compared
with baseline's 13/13. It restores the release decision, monitoring price, sparse-note
completeness and original revised-date task in this pass. However, additional written context
now accompanies a missing spoken review commitment, and later timing blocks after correction.

## Scope and provenance

The requested run used the same announced scope as V5: one repetition of all 13 synthetic
cases in both arms, capped at 78 requests (52 baseline, 26 proposed). It used **28 requests:
13 baseline and 15 proposed**, leaving 50 unused. All cases were attempted; 25 summaries and
one explicit failure were saved. “Published” in the machine-readable results means an evaluator
summary, not a real meeting or an Obsidian write. No tuning or extra repetitions occurred.

Ollama 0.40.9 and qwen3:30b digest
`ad815644918f0eaab341c12b67837cc6dd4562342cdaf118f83d5d554cb37226`
were unchanged before, between and after arms. Temperature zero, thinking enabled and context
32768 were unchanged. No transport errors occurred. All V1–V6 input manifests and previous
result manifests verify unchanged. Baseline outputs, generated afresh, equal V5's summaries.

All 15 proposed requests use their frozen per-case schemas, and all response reference values
belong to their allowed enums. This does not prove correct source selection or completeness.
`run.json` records provenance and caps; `completion.json` records case outcomes and integrity
checks. JSONL preserves every sent request, full response and validation/selection audit.

## Original five cases

| Case | V6 outcome | Evidence |
|---|---|---|
| empty | Improved | Both named tasks remain. Friday applies only to tagging; release Friday remains an independent decision and overview quote. Rollback has no due or unrelated review. |
| sparse | Correct after correction | Both tasks, Alex's next week, monitoring $120 and no chosen option remain. First draft incorrectly also puts spoken monitoring cost under notes_context; correction removes that duplicate. |
| additional | Commitment lost | Sam sends Friday, but Alex's “I will review it next week” is absent everywhere. Forty seats and venue-access task correctly remain written context. |
| conflicting | Preserved but imprecise grouping | Both price and date disagreements remain unresolved, with “I think” and the verification task. Budget conflict unnecessarily includes the June delivery statement as well as the estimate. |
| ambiguous_dates | Correct conditional timing | Complete conditional relative due survives. No launch decision and separate written follow-up/Casey suggestion remain. Repetition across sections reduces usefulness. |

All five produce summaries, but additional fails commitment completeness. The missing Alex task
is already absent from the raw draft; the compiler did not delete it. The input contained the
complete transcript. Notes are present, but this single run cannot establish why omission occurred.

## Eight boundary cases

| Case | V6 outcome | Evidence |
|---|---|---|
| same_speaker_tasks | Correct | Both tasks retained, Friday only for sending; rollback has no deadline or unrelated review. |
| coordinated_tasks | Conservative review | Both tasks remain in one permitted source-worded checkbox; Friday quoted for review, no assigned rollback deadline. |
| later_timing | Blocked | Both responses put Friday from T3 in T1's initial timing field, violating the same-source rule. No task reaches the final note. |
| revised_timing | Improved | Original T1 sending task and Sam remain. Monday correction is linked from T2 and quoted for review; due null. Friday is qualified as review-required, not assigned. |
| shared_numbers | Improved | Monitoring's undisputed 120 dollars survives in overview; only support 120 versus 150 is disputed. Invoice-check task remains without unnecessary review. |
| status_conflict | Correct | Both status accounts unresolved; spoken “I think” preserved; health-check task retained. |
| tentative_task | Correct | Only Alex's checklist becomes an action, due tomorrow; Sam's explicit noncommitment retained. |
| front_loaded_timing | Conservative review | Next Tuesday remains with the source-worded sending task under review; no due assigned. |

Three proposed actions require review, and six assigned due values remain. Fewer review items
is not itself evidence of better quality; an omitted commitment also reduces the count.

## Scores

Order: commitment completeness, source attribution, conflicts, numbers, dates/owners, useful
emphasis; each 0–2. A blocked result receives zeros for missing output, not six fabrication
errors. Baseline is scored against its transcript only. Review evidence earns partial timing
credit consistently with the earlier evaluations. Missing Alex/next week earns partial commitment
and date credit because Sam/Friday survives. Unrelated June text in the budget conflict reduces
attribution and conflict precision despite preserving both factual accounts.

| Case | Baseline | V6 |
|---|---|---|
| empty | 2/2/2/2/2/2 | 2/2/2/2/2/1 |
| sparse | 2/2/2/2/2/2 | 2/2/2/2/2/2 |
| additional | 2/2/2/2/2/1 | 1/2/2/2/1/1 |
| conflicting | 2/2/2/2/2/2 | 2/1/1/2/2/1 |
| ambiguous_dates | 2/1/2/2/1/1 | 2/2/2/2/2/1 |
| same_speaker_tasks | 2/1/2/2/0/1 | 2/2/2/2/2/2 |
| coordinated_tasks | 2/2/2/2/2/1 | 2/2/2/2/1/1 |
| later_timing | 2/2/2/2/2/1 | 0/0/0/0/0/0 |
| revised_timing | 2/2/2/2/2/2 | 2/2/2/2/1/1 |
| shared_numbers | 2/2/2/2/2/2 | 2/2/2/2/2/1 |
| status_conflict | 2/1/2/2/2/1 | 2/2/2/2/2/2 |
| tentative_task | 2/2/2/2/2/1 | 2/2/2/2/2/1 |
| front_loaded_timing | 2/2/2/2/2/1 | 2/2/2/2/1/1 |

Codex reviewed shuffled outputs with opaque labels before joining the key. Schema, notes and
review fields reveal arm information, so this is label blinding rather than an independent or
fully blinded assessment. `blinded-scores.json` records evidence and judgments; `scores.json`
joins the arm labels. Baseline still incorrectly extends Friday to rollback in overview and
strengthens tentative readiness to confirmation. Those errors do not excuse V6's omissions.

## What the audits establish

- **Additional is a model omission.** Only T1 is selected as an action or prose source. T3,
  Alex's review commitment, is present in the supplied source array but omitted throughout
  the draft. The reference/number validator sees no invalid claim, emits no warning and
  requests no correction. This is a coverage gap, not a compiler suppression error.
- **Later timing is contract rigidity plus failed correction.** The first draft identifies
  original task T1 and explicitly links T3 as a timing_update, but also repeats T3/Friday in
  initial timing. The compiler rejects that cross-statement initial quote. The correction
  retains the invalid initial timing and removes the valid update, so it remains blocked.
  The task and timing relationship are recoverable from the first draft's references, but
  this frozen compiler intentionally does not normalize them. No evidence of a missing
  Friday answer or wrong original task in this case.
- **Revised timing now uses the intended representation.** T1 remains the original action;
  T2 is its later update. Code withholds due and shows both accounts under review. This is
  improvement in one response, not evidence of reliable extraction across repetitions.
- **Conflict grouping remains semantic.** The budget conflict references T1 (estimate) and
  unrelated T3 (delivery). All IDs are valid. Code faithfully copies both, producing a
  cluttered budget account; it cannot certify that each selected source fits the topic.
- **Sparse correction works.** Removing the spoken T4 entry from notes_context resolves
  the source-kind error while preserving spoken tasks and cost. All selected drafts have
  zero numeric warnings. Numeric checks do not detect omitted commitments or loose grouping.

The new source payload omits offsets as intended. No source-coordinate timing quote appears
in this run. Several aspects changed together; this comparison does not isolate their causal
contributions. With one repetition, no variability or reliability estimate is available.

## Acceptance and next work

Quality fails because additional loses an important spoken commitment and later_timing
provides no summary. Both regress versus baseline completeness. The V5 losses targeted by
V6 are improved in this pass, but the errors have moved rather than disappeared.

A next design should test two narrow changes offline before another freeze:

1. Normalize an exact external timing quote into review evidence for its original action,
   rather than requiring the model to encode the same relationship in only one field.
   Never turn that normalization into an assigned deadline or infer a relationship from prose.
2. Detect uncovered explicit first-person commitments as a completeness diagnostic. The
   additional case supplies “I will review it next week” but nothing cites it. Any coverage
   check must handle negation, tentative wording and non-task speech; it should request review
   or bounded correction rather than invent an action. Add negative tests before inference.

These are proposals, not changes made during evaluation. The frozen candidate remains intact.
The 50 unused requests do not authorize tuning or further trials. A revision requires a new
freeze and separately chosen budget. M10 remains unbuilt; the original workflow was reported
manually accepted, but current review behavior still needs acceptance. PR #16 stays unmerged.

Formatting, lint, strict types and 365 unit tests pass (six integration tests deselected).
All 12 saved V6 generations reproduce through wrapper validation, and model-facing source
payloads contain no offsets or turn coordinates. Capture code is unchanged.
