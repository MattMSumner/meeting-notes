# M10 v2 evaluation results

**Quality acceptance: failed. M10 remains unbuilt.** The approved v2 rerun and rubric review are complete. The user previously reported manual Obsidian acceptance complete. No further prompt changes, model comparisons or extra inference were made during scoring.

## Run

Five cases × three repetitions × two arms produced 30 valid summaries using 32 requests: 15 baseline and 17 proposed, below the approved 60-per-arm caps. There were no execution errors. The proposed conflict case used one correction request in repetition 1 and one in repetition 3. Every case/repetition pair and all frozen input hashes were verified.

Ollama 0.40.9 and qwen3:30b digest `ad815644918f0eaab341c12b67837cc6dd4562342cdaf118f83d5d554cb37226` were unchanged before, between and after the arms, and match v1. Temperature zero, thinking enabled and context 32768 were unchanged. Full metadata is in `run.json`.

## Findings

- **Conditional deadline improvement: 3/3 proposed ambiguous-date outputs** retain `next Friday, or the Friday after if review slips` in due, independently of the task text. The baseline still truncates due to `next Friday` in 3/3. This targeted v1 weakness is fixed on the frozen cases.
- **Blocking conflict failure remains: 3/3 proposed conflict outputs.** “The current estimate is $120,000.” (repetitions 1 and 3) or “The current budget estimate is 120 thousand dollars.” (repetition 2) remains an unqualified key point despite the handwritten 150k account. Repetitions 1 and 3 add an overview cross-reference to Conflicts, but that does not qualify the separate bullet. All three also repeat disputed written accounts under notes_context. The full numeric accounts are correct; their presentation as settled core facts is not.
- **New blocking deadline error: 2/3 proposed empty-note outputs** assign Alex Friday for checking the rollback procedure (repetitions 1 and 3). The spoken Friday timing applies to Sam tagging and the release; Alex only says “I will check the rollback procedure.” Baseline gives Alex null in all three repetitions. No precise calendar date is invented, but an unsupported task deadline is still a critical failure under the frozen rubric.
- **Spoken commitment completeness remains 2/2 throughout.** All spoken tasks and agreed decisions are retained, including both tasks with sparse notes; the deadline errors are assessed separately under attribution and dates/owners. No written-only task is promoted into a spoken action item.
- **Additional written context improves the result in 3/3 proposed outputs:** 40 seats and the venue-access task stay in notes_context, while spoken draft/review tasks retain their owners and relative dates. Duplicate decisions for those individual commitments are now empty. Both arms retain some overview/bullet/action repetition, but the extra decision duplication that cost v1 a point is removed here.
- **Remaining noncritical weaknesses:** all proposed sparse outputs copy “Focus on deployment options.” into notes_context; all proposed ambiguous-date outputs still infer “document” as the referent of “it.” Conflict transcript accounts shorten “I think delivery is in June” to “June”; core expected wording retains some uncertainty, so dates score partly correct. Unlike v1, no proposed output says delivery is scheduled or adds deployment to the empty-note release agreement.

## Scores

Each dimension is 0–2. Order: commitment completeness, source attribution, conflicts, numbers, dates/owners, useful emphasis. The rubric is unchanged. Baseline is judged only against its transcript, not unseen notes. A dimension with no relevant claims earns 2 when nothing unsupported is introduced. Totals cannot override a critical failure.

| Arm | Case | Repetition 1 | Repetition 2 | Repetition 3 |
|---|---|---|---|---|
| baseline | empty | 2/2/2/2/2/2 | 2/2/2/2/2/2 | 2/2/2/2/2/2 |
| baseline | sparse | 2/2/2/2/2/2 | 2/2/2/2/2/2 | 2/2/2/2/2/2 |
| baseline | additional | 2/2/2/2/2/1 | 2/2/2/2/2/1 | 2/2/2/2/2/1 |
| baseline | conflicting | 2/2/2/2/2/2 | 2/2/2/2/2/2 | 2/2/2/2/2/2 |
| baseline | ambiguous_dates | 2/1/2/2/1/1 | 2/1/2/2/1/1 | 2/1/2/2/1/1 |
| proposed | empty | 2/1/2/2/0/1 | 2/2/2/2/2/2 | 2/1/2/2/0/1 |
| proposed | sparse | 2/2/2/2/2/1 | 2/2/2/2/2/1 | 2/2/2/2/2/1 |
| proposed | additional | 2/2/2/2/2/2 | 2/2/2/2/2/2 | 2/2/2/2/2/2 |
| proposed | conflicting | 2/1/1/1/1/1 | 2/1/1/1/1/1 | 2/1/1/1/1/1 |
| proposed | ambiguous_dates | 2/1/2/2/2/1 | 2/1/2/2/2/1 | 2/1/2/2/2/1 |

| Dimension | Baseline mean | Proposed mean |
|---|---:|---:|
| commitment completeness | 2.00 | 2.00 |
| source attribution | 1.80 | 1.47 |
| conflicts | 2.00 | 1.80 |
| numbers | 2.00 | 1.80 |
| dates and owners | 1.80 | 1.53 |
| useful emphasis | 1.60 | 1.27 |

## Corrections, variability and limits

Final proposed summaries have zero source-specific numeric presence warnings. The two extra requests occurred in conflict repetitions 1 and 3, but the frozen runner saves only the retained summary and cumulative request counts, not intermediate replies. Therefore the correction type (format versus numbers), the discarded content, and whether the retry improved it cannot be established. Both retained outputs still fail conflict qualification. The report does not infer retry success from absence of final numeric warnings.

The baseline produced one distinct summary per case across repetitions. The proposed arm produced two distinct summaries each for empty, sparse and conflicting cases, and one each for additional and ambiguous-date cases. Three repetitions at temperature zero provide limited evidence of variability. These five inspected cases are regression material, not an unseen generalization set; passing them would not establish accuracy on long or real meetings.

Codex reviewed all saved outputs shuffled under opaque IDs, with arm/repetition labels withheld until assessments were saved to `blinded-scores.json`. Schema/content can reveal the arm, so this is label blinding only, not a fully blinded independent human review. `scores.json` joins those judgments to the original arm/repetition key, with exact source/output evidence and critical findings.

All published text was reviewed as belonging to the five synthetic fixtures. No real meeting data is included. The v1 freeze/results and v2 freeze manifest remain unchanged. Raw outputs, metadata, opaque review order, key and scored judgments are saved alongside this report.

## Acceptance and next action

The no-critical-failures gate fails in 5/15 proposed outputs: all three conflicting outputs and two empty-note outputs. Manual workflow success and complete execution do not change this outcome. Do not mark M10 built or merge.

The prompt/schema revision improved conditional due phrasing but did not reliably control conflicts or task-specific deadline attribution. The next implementation should investigate stronger evidence grounding or validation of individual claims and task timing, rather than assuming another wording change solves these failures. Preserve these results; any candidate needs a new versioned freeze and separately agreed inference budget. No such change or further run is part of this evaluation.
