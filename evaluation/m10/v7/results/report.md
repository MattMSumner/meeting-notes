# M10 V7 evaluation results

**V7 meets the frozen acceptance criteria in this single run. M10 remains unbuilt pending
current manual acceptance.** All 13 proposed cases produce summaries, with no observed
critical failures and no spoken-commitment completeness regression versus baseline. Written
context is useful and separated from spoken commitments. This is one reviewer and one
repetition; it does not establish reliability on new inputs or across repeated runs.

## Scope and provenance

The requested evaluation used the announced previous scope: one repetition of 13 synthetic
cases in both arms, capped at 78 requests (52 baseline, 26 proposed). It used **28 requests:
13 baseline and 15 proposed**, leaving 50 unused. All 26 outputs were retained. Publication
means an evaluator result, not a real meeting or an Obsidian write. No extra inference, prompt
tuning, candidate changes or real-meeting evaluation occurred.

Ollama 0.40.9 and qwen3:30b digest
`ad815644918f0eaab341c12b67837cc6dd4562342cdaf118f83d5d554cb37226`
were stable before, between and after arms. Temperature zero, thinking enabled and context
32768 were unchanged. No transport errors occurred. All previous frozen inputs/results and
V7 inputs verify unchanged. Fresh baseline summaries are identical to V6.

All 15 proposed requests match their frozen per-case schemas and every response reference
belongs to the recorded allowed enums. All 13 initial proposed drafts, parsed as JSON, equal
V6's initial drafts. The changed outcomes are therefore directly inspectable as validator,
compiler and correction behavior on the same initial selections in these runs. This does not
prove deterministic behavior for other inputs or environments.

## Outcomes

| Case | V7 result |
|---|---|
| empty | Both named tasks retained, Friday only assigned to tagging. Independent Friday release agreement remains; no unrelated rollback review. |
| sparse | Both tasks, recovery next week, monitoring $120 and no selected option retained after correction removes spoken cost from notes_context. |
| additional | Omission diagnostic triggers correction. Alex's review commitment and next-week due are restored; Sam's task and written-only 40 seats/venue request remain. |
| conflicting | Both price and date accounts remain unresolved, with “I think,” verification task and unapproved budget retained. Budget conflict unnecessarily includes the June delivery statement too. |
| ambiguous_dates | Complete conditional relative due retained; no launch decision or assigned Casey task. Written follow-up and suggestion separated. |
| same_speaker_tasks | Both tasks retained; Friday only for sending, rollback due null. |
| coordinated_tasks | Both tasks retained in a grouped source-worded checkbox with Friday review evidence, no assigned rollback deadline. |
| later_timing | First draft accepted conservatively: original Sam rollback task and full Friday answer under review, due null. |
| revised_timing | Original sending task and Sam retained, Monday correction quoted, Friday qualified as review-required rather than an assigned deadline. |
| shared_numbers | Monitoring's undisputed 120 survives; only support 120 versus 150 disputed. Invoice task retained without needless review. |
| status_conflict | Both readiness accounts unresolved, including spoken “I think”; health-check commitment retained. |
| tentative_task | Only Alex's checklist assigned, due tomorrow. Sam's explicit noncommitment retained. |
| front_loaded_timing | Sam's sending task and Next Tuesday retained as review evidence, due null. |

Four proposed actions require review and seven assigned due values remain. Review presentation
is permitted by the frozen boundary-case criteria and earns partial dates/usefulness credit;
it does not count as a silent omission. No facts are treated as settled merely because their
numbers occur in source text.

## Scores

Order: commitment completeness, source attribution, conflicts, numbers, dates/owners, useful
emphasis; each 0–2. Baseline is assessed against transcript-only evidence. Scores use the same
partial-credit interpretation as V5/V6. No requirement that every dimension score 2 was added.
The untidy budget conflict receives partial attribution/conflict credit: it includes unrelated
but accurately quoted June text, while both intended disagreements remain identified and
unresolved. It is not scored as settling a disputed fact or fabricating an amount/date.

| Case | Baseline | V7 |
|---|---|---|
| empty | 2/2/2/2/2/2 | 2/2/2/2/2/1 |
| sparse | 2/2/2/2/2/2 | 2/2/2/2/2/2 |
| additional | 2/2/2/2/2/1 | 2/2/2/2/2/2 |
| conflicting | 2/2/2/2/2/2 | 2/1/1/2/2/1 |
| ambiguous_dates | 2/1/2/2/1/1 | 2/2/2/2/2/1 |
| same_speaker_tasks | 2/1/2/2/0/1 | 2/2/2/2/2/2 |
| coordinated_tasks | 2/2/2/2/2/1 | 2/2/2/2/1/1 |
| later_timing | 2/2/2/2/2/1 | 2/2/2/2/1/1 |
| revised_timing | 2/2/2/2/2/2 | 2/2/2/2/1/1 |
| shared_numbers | 2/2/2/2/2/2 | 2/2/2/2/2/1 |
| status_conflict | 2/1/2/2/2/1 | 2/2/2/2/2/2 |
| tentative_task | 2/2/2/2/2/1 | 2/2/2/2/2/1 |
| front_loaded_timing | 2/2/2/2/2/1 | 2/2/2/2/1/1 |

Codex reviewed shuffled outputs with opaque labels before joining the key. Supplied notes,
schema and review fields reveal arm information, so this is label blinding, not independent
or fully blinded assessment. Evidence is recorded in `blinded-scores.json`; `scores.json`
joins the arm key. Baseline again extends Friday to rollback in overview and turns tentative
readiness into confirmation. Those failures are recorded, not used to excuse proposed errors.

## Correction and compiler evidence

**Additional:** the first response omits T3, “I will review it next week.” The diagnostic
blocks it and requests a source-specific correction. The second response adds T3 with exact
“next week” timing. Code derives Alex from the same-turn introduction and preserves both
spoken tasks and written-only context. The model also adds the personal task to Decisions;
existing task-prose suppression removes that duplication. Selected attempt is 1 (zero-based).

**Later timing:** the first draft is the same as V6's. It has original T1, initial timing
T3/Friday, and a T1→T3 update. V7 normalizes the external timing into unverified review and
suppresses definitive task prose. The original task and full Friday source survive with due
null. Selected attempt is 0; no correction is needed. V6 instead rejected this representation.

**Sparse:** its first draft again duplicates spoken monitoring cost into notes_context.
Source-kind and numeric checks identify that error; correction removes only the inappropriate
entry while preserving both commitments and cost. Selected attempt is 1.

All selected drafts have zero numeric warnings. Only sparse and additional use correction.
No omission diagnostic fires on the tentative/noncommitment case. This small suite does not
measure false-positive or false-negative rates for the limited task-verb heuristic. It misses
unlisted verbs, paraphrases and several constructions by design.

## Acceptance and limits

The original five pairs and eight boundary cases complete. All proposed commitment scores
are 2, with no regression versus baseline. There are no observed proposed critical failures.
Notes add workshop/venue context and separate written follow-up, while conflicts expose
otherwise unseen disagreement. Under the frozen rubric, this meets the single-run gate.

Remaining issues are noncritical in these fixtures: unrelated delivery text in the budget
conflict, internal source-ID markers, repeated status statements, and conservative timing
that requires human review. The current rendered review workflow still needs manual acceptance.
M10 is not marked Built and PR #16 stays unmerged.

One repetition supplies no estimate of run-to-run variability; these repeatedly inspected
synthetic fixtures are not held-out evidence. Before broader confidence claims, agree a
separate repeat/held-out evaluation scope and budget. Do not treat the 50 unused requests as
permission for extra runs. No implementation changes are made in this evaluation.

Formatting, lint, strict types and 395 unit tests pass (six integration tests deselected).
All 13 saved generations reproduce through version-6 wrapper validation. Model-facing sources
contain no offsets or turn coordinates. Capture code is unchanged.
