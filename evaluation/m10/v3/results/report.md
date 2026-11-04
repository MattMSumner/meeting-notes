# M10 v3 stage-one evaluation

**Quality acceptance failed. Stopped after the first repetition. M10 remains unbuilt.**
The evidence-backed candidate published 5/13 summaries and blocked 8/13 after its one
correction attempt. The baseline published all 13. Refusal preserves the previous saved
result in the application, but it does not satisfy generation or commitment completeness.
No remaining repetitions, prompt tuning, candidate changes or extra inference were run.

## Budget and provenance

The owner approved three repetitions across both arms, capped at 234 total requests,
with a first-repetition scoring gate before continuing. Stage one covered all 13 cases
in both arms: 26 completed cases, 18 summaries and eight explicit validation failures.
It used **38 requests: 13 baseline and 25 proposed**, below stage caps of 52 and 26.
The remaining 196 requests are unused, not authorization for tuning another candidate.

Ollama 0.40.9 and qwen3:30b digest
`ad815644918f0eaab341c12b67837cc6dd4562342cdaf118f83d5d554cb37226`
were unchanged before, between and after the arms. Temperature zero, thinking enabled,
and context 32768 were unchanged. No transport errors occurred. Every frozen hash,
case/repetition identity, request count, and v1/v2 result hash was verified.
`run.json` records execution revision, environment, approved staging and frozen hashes;
`completion.json` records counts and per-case publication/warning outcomes. Raw JSONL
contains every sent request and full response; proposed rows also retain validator audits.

## Original five regression cases

| Case | Baseline | Proposed | Finding |
|---|---|---|---|
| empty | Published | Blocked | Both drafts include Friday in the task text and separately cite Friday as timing. The validator expects timing after the task phrase. The correction only adds punctuation to the timing quote. |
| sparse | Published | Published after correction | Both commitments, 120 dollars and no selected option survive. Recovery owner becomes Them despite the spoken Alex introduction. Personal tasks are duplicated as decisions. |
| additional | Published | Blocked | Both task texts include their timing. Correction adds punctuation without separating timing from task wording. Spoken tasks and useful written context are unavailable. |
| conflicting | Published | Blocked | Notes contain two sentences in one N1 passage. Separate sentence quotes for estimate and delivery fail the full-passage requirement on both attempts. The missing-overview issue is corrected, but the quotation issue remains. |
| ambiguous_dates | Published | Published after correction | Proposed due preserves the complete conditional wording; written follow-up stays separate. Baseline due truncates the condition and its prose invents a review-document referent. Proposed prose is awkwardly concatenated. |

Original-case publication is 2/5 proposed versus 5/5 baseline. The old numeric conflict
failure is **not demonstrated fixed**: this case refuses to publish. The additional-context
benefit from v2 is likewise unavailable in this pass. Conditional timing succeeds in the
one published ambiguous-date result; one repetition does not establish reliability.

## Eight added boundary cases

| Case | Baseline | Proposed | Finding |
|---|---|---|---|
| same_speaker_tasks | Published | Published after correction | Proposed keeps Friday only on sending and null on rollback. Baseline action fields are correct, but its overview incorrectly says both are due Friday. |
| coordinated_tasks | Published | Blocked | Both drafts violate task/timing rules. Correction splits commitment quotes into fragments, which fails full-statement validation. Baseline retains both tasks and gives only sending a date. |
| later_timing | Published | Blocked | First draft uses valid review-mode timing but lacks an overview reference. Correction fixes overview while replacing review mode with disallowed cross-passage timing. Baseline correctly associates the Friday answer. |
| revised_timing | Published | Blocked | Model treats Monday correction as the task statement and initially creates a conflict with nonexistent notes claim `null`. Retry removes that conflict but still fails timing validation. Baseline correctly replaces Friday with Monday. |
| shared_numbers | Published | Published first attempt | Only support is disputed. Monitoring's 120 dollars and invoice-check commitment survive. This is a successful targeted conflict-isolation case. |
| status_conflict | Published | Published after correction | Both status accounts remain unresolved, including spoken “I think”; health-check task survives. Baseline incorrectly strengthens tentative readiness into confirmation. |
| tentative_task | Published | Blocked | First draft mistakes two spoken statements for a transcript/notes conflict. Retry fixes that but retains tomorrow inside checklist task text, failing timing validation. Baseline correctly avoids assigning Sam rollback. |
| front_loaded_timing | Published | Blocked | Both attempts use review-mode timing. Retry repairs the commitment span, but paraphrased task text fails exact-phrase validation. Baseline correctly retains next Tuesday. |

New-case publication is 3/8 proposed versus 8/8 baseline. The successful proposed cases
retain their commitments, but that cannot offset the five unavailable outputs. No
published proposed result invents a deadline or settles a known conflict in this sample.
This is not evidence of general correctness: most proposed cases never publish.

## Scores

Each dimension uses the frozen 0–2 scale: commitment completeness, source attribution,
conflicts, numbers, dates/owners, useful emphasis. Blocked outputs receive all zeros as
missing deliverables; this does **not** mean six separate fabrication errors were observed.
Baseline is assessed against transcript only. Totals cannot override acceptance blockers.

| Case | Baseline | Proposed |
|---|---|---|
| empty | 2/2/2/2/2/2 | blocked: 0/0/0/0/0/0 |
| sparse | 2/2/2/2/2/2 | 2/2/2/2/1/1 |
| additional | 2/2/2/2/2/1 | blocked: 0/0/0/0/0/0 |
| conflicting | 2/2/2/2/2/2 | blocked: 0/0/0/0/0/0 |
| ambiguous_dates | 2/1/2/2/1/1 | 2/2/2/2/2/1 |
| same_speaker_tasks | 2/1/2/2/0/1 | 2/2/2/2/2/1 |
| coordinated_tasks | 2/2/2/2/2/1 | blocked: 0/0/0/0/0/0 |
| later_timing | 2/2/2/2/2/1 | blocked: 0/0/0/0/0/0 |
| revised_timing | 2/2/2/2/2/2 | blocked: 0/0/0/0/0/0 |
| shared_numbers | 2/2/2/2/2/2 | 2/2/2/2/2/2 |
| status_conflict | 2/1/2/2/2/1 | 2/2/2/2/2/1 |
| tentative_task | 2/2/2/2/2/1 | blocked: 0/0/0/0/0/0 |
| front_loaded_timing | 2/2/2/2/2/1 | blocked: 0/0/0/0/0/0 |

Codex scored shuffled outputs under opaque IDs before joining the arm key. Schema,
notes and errors can reveal the arm; this is label blinding, not an independent or fully
blinded review. `blinded-scores.json` preserves judgments and exact source/output evidence;
`scores.json` joins them with the key. Baseline unsupported rollback timing is a critical
deadline error. Its tentative-to-confirmed readiness change is additionally flagged as an
unsupported-certainty semantic failure, not as a conflict with notes it never received.
The proposed stage gate fails independently on eight completeness regressions.

## Correction behavior and conservative-check cost

Twelve proposed cases needed correction. Four became publishable (sparse, ambiguous dates,
same-speaker tasks, status conflict); eight remained blocked. Shared numbers was the only
first-attempt publication. All five selected drafts have zero warnings. Four rejected
attempts across three cases (coordinated tasks, later timing, front-loaded timing) contain
review warnings, but **no review-mode result reaches publication**. Published withheld
timing count is zero; rejected warnings cannot earn partial credit as delivered notes.

The saved evidence supports three diagnoses for future work:

- **Task display and task evidence are too tightly coupled.** Including a correct date in
  otherwise exact task text repeatedly blocks publication because the same date must
  follow that text. Error feedback does not lead the model to repair this reliably.
- **Passage granularity affects conflict usability.** The single handwritten line contains
  two independent facts, but full-line citation is required for each. Valid smaller quotes
  are rejected; copying the whole line would also make both claims overlap. This needs a
  design review that preserves uncertainty without forcing unrelated facts together.
- **Correction can trade one failure for another.** The later-timing draft initially has
  usable review evidence but no overview. The corrected draft repairs the overview and
  introduces a new timing error. More retries were not tested and are not assumed to fix it.

These are observations from saved attempts, not changes to the frozen implementation.
Some proposed drafts also duplicate tasks as decisions and concatenate first-person claim
fragments into poor prose. Reference checks remain distinct from semantic quality.

## Status

The agreed staged stop condition is met. Repetitions two and three were not run, so there
is no v3 variability estimate or full three-repetition acceptance claim. The 13 fixtures
are synthetic regression cases, not evidence of generalization to real meetings.

Formatting, lint, strict types and 318 unit tests pass (six integration tests deselected).
No capture changes or Swift test requirement. Original manual workflow acceptance was
reported previously; new failure/review-warning behavior remains unaccepted. M10 stays
unbuilt and the PR stays unmerged. Preserve this freeze and report; any revised candidate
needs its own freeze and separately agreed inference budget.
