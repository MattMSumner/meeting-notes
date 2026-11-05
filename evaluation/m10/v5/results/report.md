# M10 V5 evaluation results

**Quality acceptance failed. M10 remains unbuilt.** V5 produced 12/13 proposed summaries,
compared with 13/13 baseline. The remaining block is sparse. Two published outputs regress
commitment/decision presentation: revised_timing uses the correction as its task, and empty
moves the release agreement under rollback timing review. Shared_numbers loses an undisputed
price during conflict neutralization. Increased publication does not satisfy acceptance.

## Run and provenance

The user requested a new evaluation. The same bounded scope as the previous run was announced
before starting: one repetition across all 13 cases and both arms, capped at 78 requests
(52 baseline, 26 proposed). The run used **27 requests: 13 baseline and 14 proposed**, leaving
51 unused. Twenty-five summaries and one explicit validation failure were saved. Publication
here means a retained evaluator summary, not writing a real meeting into Obsidian.

Ollama 0.40.9 and qwen3:30b digest
`ad815644918f0eaab341c12b67837cc6dd4562342cdaf118f83d5d554cb37226`
were unchanged before, between and after arms. Temperature zero, thinking enabled and
32768 context were unchanged. There were no transport errors. All V1–V5 frozen inputs and
previous scored results verify unchanged. Baseline summaries are identical to V4, generated
afresh in this run. No tuning, extra repetitions or candidate changes occurred.

Every proposed request's schema matches its frozen per-case schema. All reference values
in all 14 proposed responses belong to their recorded allowed-ID enums. This establishes
observed reference conformance, not correct source selection or attribution. `run.json`
records provenance and caps; `completion.json` records per-case outcomes and these checks.
Full requests, responses and validator/selection audits are preserved in the JSONL files.

## Original five cases

| Case | V5 result | Finding |
|---|---|---|
| empty | Published; decision presentation regresses | Both named tasks remain and Sam's Friday due is assigned. The release agreement survives only as unverified timing evidence under Alex's rollback; Decisions is empty. |
| sparse | Blocked after correction | Overview cites handwritten N1 as spoken evidence. Both attempts also omit Alex's recovery commitment and the monitoring cost. The timing quote `16-58` is absent from speech. |
| additional | Published | Both tasks have correct names and due values. Forty seats and the venue-access task remain exclusively written context. No unnecessary review. |
| conflicting | Published | Both estimate and June/July accounts remain unresolved with full source wording, including “I think.” Verification and unapproved budget remain. |
| ambiguous_dates | Published | The complete conditional due survives; no launch decision and written follow-up/Casey suggestion remain separate. Raw source IDs leak into prose. |

Four of five cases publish. Conditional timing and additional written context are useful
in this pass. The release agreement is **not entirely absent**: its literal words remain
in review, but its status as an independent agreed decision is obscured by wrong placement.
That earns partial commitment credit, not full preservation.

## Eight boundary cases

| Case | V5 result | Finding |
|---|---|---|
| same_speaker_tasks | Published | Both tasks remain; no rollback deadline is invented. Model supplies null timing for sending, so the simple Friday due is retained only in review. |
| coordinated_tasks | Published | One permitted grouped checkbox preserves both tasks and Friday wording for review. No due is assigned to rollback. |
| later_timing | Published | Review now contains both “When?” and the Friday answer. Task remains for Sam with due null; this earns partial date credit. |
| revised_timing | Published; commitment presentation regresses | Model chooses the valid ID of “Actually, Monday instead.” as the task. Owner is null. The real sending commitment appears only as other timing evidence. Dates survive in review, but the checkbox is not the sending task. |
| shared_numbers | Published; undisputed information lost | Only support is identified as disputed; invoice task remains. Neutralizing a combined bullet removes monitoring's undisputed 120 dollars. A whole-task timing quote also creates review despite no deadline. |
| status_conflict | Published | Both status accounts remain unresolved, including spoken “I think.” Health-check task survives without spurious timing review. |
| tentative_task | Published | Alex's checklist task and tomorrow due remain; no Sam rollback commitment is invented. |
| front_loaded_timing | Published | Sending task and Next Tuesday remain quoted for review, with due null. |

All eight publish, but revised_timing and shared_numbers still fail their intended behaviors.
Seven review items appear across seven proposed cases; five assigned due values remain.
Review count is not a safety or quality score: some review is useful, some is unnecessary,
and some hides an incorrectly selected task or displaced decision.

## Scores

Order: commitment completeness, source attribution, conflicts, numbers, dates/owners,
useful emphasis. Each dimension is 0–2. The blocked case receives zeros for missing output,
not six observed fabrication errors. Baseline is assessed against its transcript only.
Quoted timing may earn partial credit; a task or decision misplaced as review evidence
cannot earn full commitment completeness.

| Case | Baseline | V5 |
|---|---|---|
| empty | 2/2/2/2/2/2 | 1/1/2/2/1/1 |
| sparse | 2/2/2/2/2/2 | blocked: 0/0/0/0/0/0 |
| additional | 2/2/2/2/2/1 | 2/2/2/2/2/2 |
| conflicting | 2/2/2/2/2/2 | 2/2/2/2/2/1 |
| ambiguous_dates | 2/1/2/2/1/1 | 2/2/2/2/2/1 |
| same_speaker_tasks | 2/1/2/2/0/1 | 2/2/2/2/1/1 |
| coordinated_tasks | 2/2/2/2/2/1 | 2/2/2/2/1/1 |
| later_timing | 2/2/2/2/2/1 | 2/2/2/2/1/1 |
| revised_timing | 2/2/2/2/2/2 | 1/1/2/2/1/0 |
| shared_numbers | 2/2/2/2/2/2 | 2/2/2/1/2/1 |
| status_conflict | 2/1/2/2/2/1 | 2/2/2/2/2/2 |
| tentative_task | 2/2/2/2/2/1 | 2/2/2/2/2/2 |
| front_loaded_timing | 2/2/2/2/2/1 | 2/2/2/2/1/1 |

Codex reviewed shuffled outputs under opaque IDs and saved judgments before joining the arm
key. Schema, review fields and supplied notes can reveal the arm. This is label blinding,
not an independent or fully blinded review. `blinded-scores.json` preserves exact source/output
evidence; `scores.json` joins the key. Baseline again assigns rollback Friday in overview and
strengthens tentative readiness into confirmation. Those failures do not excuse proposed
completeness regressions or the loss of an undisputed price.

## What the audits establish

Only sparse requests a correction. Its second response retains the wrong-source N1 overview,
so the run ends blocked. All other cases publish their first response. Every selected draft
has zero numeric warnings; neither missing facts nor incorrect timing relationships are
established by that check.

The remaining failures have different causes:

- **Model selection remains semantic.** In revised_timing, commitment_id is T2, the valid
  correction statement, instead of T1, the sending commitment. The date relationship is
  expressed correctly in the draft's prose, but task compilation and prose suppression
  leave the wrong checkbox. Enums prevent arbitrary reference strings, not wrong choices.
- **The compiler creates the empty-case placement error.** The raw draft has a proper Friday
  release decision referencing T4, and rollback has no timing or timing_context. A combined
  overview cites T1/T3/T4. The fallback copies dated T4 into rollback review, adds T4 to the
  suppressed task sources, and then removes the independently supported release decision.
  This is not a model-proposed rollback deadline.
- **Whole-entry neutralization over-suppresses facts.** The shared_numbers draft combines
  monitoring's undisputed 120 dollars with the support conflict in one bullet. The compiler
  neutralizes the whole bullet, losing monitoring's price. The conflict accounts themselves
  are correctly limited to support.
- **Sparse is not merely one rejected reference.** Even before rejection, its draft lacks
  Alex's recovery task and the monitoring cost. Its proposed timing `16-58` matches T1's
  stored character offsets (start 16, end 58), not spoken timing. Confusion with source
  metadata is a plausible inference; the text alone cannot establish why the model chose it.
  The invalid quote is not published.

Compared with V4's single pass, proposed publication rises from 9/13 to 12/13 and requests
fall from 23 to 14. No out-of-set reference values are observed. Changes to schema, naming,
prompt and compilation occurred together, so this comparison does not isolate a causal
contribution or establish statistical reliability. One repetition has no variability estimate.

## Acceptance and next work

Sparse delivers no commitments; empty and revised_timing retain relevant source text but
misrepresent its role in the final note. These regress versus baseline completeness.
Shared_numbers independently loses a required undisputed fact. Quality acceptance fails.
The permitted one-repetition evaluation is complete; 51 unused requests are not used for
extra trials or tuning.

The next design review should distinguish model extraction from compiler loss: preserve
independently supported decisions and undisputed facts when suppressing mixed prose, avoid
creating timing relationships from generic source overlap, and represent a revision separately
from the original commitment. The results do not justify another run of this unchanged candidate.
Any revision needs a new freeze and separately chosen budget.

Formatting, lint, strict types and 355 unit tests pass (six integration tests deselected).
Capture is unchanged. The original manual workflow was reported complete; current review
behavior still needs acceptance. M10 remains unbuilt and PR #16 stays unmerged.
