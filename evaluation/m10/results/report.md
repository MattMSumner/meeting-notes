# M10 frozen evaluation results

**Quality acceptance: failed. M10 remains unbuilt.** Manual Obsidian acceptance was reported complete by the user. No additional inference, prompt tuning or model comparison was performed while scoring.

All five cases ran three times in each arm: 30 valid summaries, 30 requests total, zero format/number corrections and zero execution errors. Ollama 0.40.9 and model digest `ad815644918f0eaab341c12b67837cc6dd4562342cdaf118f83d5d554cb37226` stayed unchanged. Input hashes and case/repetition coverage were verified.

## Findings

- **Blocking: conflict handling fails in all 3 proposed conflict outputs.** Both accounts appear in Conflicts, but the core key point still states “Current budget estimate is $120,000.” (repetitions 1 and 3) or “Current estimate: 120 thousand dollars” (repetition 2), without acknowledging the written 150k dispute. The frozen prompt explicitly forbids presenting disputed facts as settled in any section. Showing the other account later does not satisfy that requirement.
- **Additional critical failure in conflict repetition 2:** “Delivery scheduled for June” strengthens “I think delivery is in June” into a settled schedule despite the written July account. The other two repetitions say “Delivery expected in June,” retaining some uncertainty, but still omit the conflict from that core bullet.
- **Conditional deadline weakness in both arms, 3/3 each:** the task retains “next Friday, or the Friday after if review slips,” while `due` becomes only “next Friday.” This is scored partly correct because the full condition remains in the task; it is not classified as a wholly invented calendar date. Both arms also infer a document as the referent of “it.”
- **Spoken commitment completeness passes in every output:** both deployment/recovery tasks survive sparse notes; draft/review commitments and estimate verification retain their owners. No written-only task becomes a spoken action item.
- **Written context is useful and correctly separated:** proposed additional-context outputs retain 40 seats and the venue-access task in From your notes (3/3); ambiguous-date outputs keep the holiday follow-up and tentative Casey help separate (3/3). This adds useful information over transcript-only results, although repeated decisions/actions and the copied sparse emphasis cue reduce concision.
- **Noncritical specificity regression in empty-note outputs (3/3 proposed):** “Release to be tagged and deployed on Friday” introduces explicit deployment where the transcript says “release Friday.” Deployment may be implied, so this is a partial attribution score, not the blocking criterion.

## Scores

Each dimension is 0–2. Order: commitment completeness, source attribution, conflicts, numbers, dates/owners, useful emphasis. An absent conflict or number earns 2 when nothing unsupported is introduced; baseline is judged only against its supplied transcript, never penalized for unseen handwritten facts. Aggregate scores are descriptive; the no-critical-failures acceptance gate decides the outcome.

| Arm | Case | Repetition 1 | Repetition 2 | Repetition 3 |
|---|---|---|---|---|
| baseline | empty | 2/2/2/2/2/2 | 2/2/2/2/2/2 | 2/2/2/2/2/2 |
| baseline | sparse | 2/2/2/2/2/2 | 2/2/2/2/2/2 | 2/2/2/2/2/2 |
| baseline | additional | 2/2/2/2/2/1 | 2/2/2/2/2/1 | 2/2/2/2/2/1 |
| baseline | conflicting | 2/2/2/2/2/2 | 2/2/2/2/2/2 | 2/2/2/2/2/2 |
| baseline | ambiguous_dates | 2/1/2/2/1/1 | 2/1/2/2/1/1 | 2/1/2/2/1/1 |
| proposed | empty | 2/1/2/2/2/1 | 2/1/2/2/2/1 | 2/1/2/2/2/1 |
| proposed | sparse | 2/2/2/2/2/1 | 2/2/2/2/2/1 | 2/2/2/2/2/1 |
| proposed | additional | 2/2/2/2/2/1 | 2/2/2/2/2/1 | 2/2/2/2/2/1 |
| proposed | conflicting | 2/1/1/1/2/1 | 2/1/1/1/0/1 | 2/1/1/1/2/1 |
| proposed | ambiguous_dates | 2/1/2/2/1/1 | 2/1/2/2/1/1 | 2/1/2/2/1/1 |

| Dimension | Baseline mean | Proposed mean |
|---|---:|---:|
| commitment completeness | 2.00 | 2.00 |
| source attribution | 1.80 | 1.40 |
| conflicts | 2.00 | 1.80 |
| numbers | 2.00 | 1.80 |
| dates and owners | 1.80 | 1.67 |
| useful emphasis | 1.60 | 1.00 |

## Variability and numeric checks

The baseline produced identical JSON summaries across all three repetitions of each case. The proposed arm did likewise for four cases; the conflict case had two distinct outputs, with repetition 2 strengthening delivery to “scheduled.” Three repetitions at temperature zero provide limited evidence about wider variability or long real meetings.

No numeric warnings or correction attempts were triggered. All checked numeric values occurred in their assigned source, yet the disputed estimate was still presented as an unqualified core fact. This demonstrates the documented limit of presence checks: they do not establish correct meaning or agreement. No retry failure was observed; retry quality was not exercised by these outputs.

## Review method and artifacts

Codex performed a qualitative review of every saved output, shuffled under opaque IDs with arm/repetition labels withheld. Assessments were saved in `blinded-scores.json` before joining `blind-key.json` to produce `scores.json`. This is label blinding, not full blinding: additional schema fields/content can reveal the arm. It is a single-agent assessment, not an independent human review. The numeric scores encode the written judgments, not an automated model judge.

`scores.json` records every case/repetition with exact source/output evidence, specific findings and critical failures. Raw results are in `baseline.jsonl` and `proposed.jsonl`; `run.json` preserves settings, model identity and frozen hashes. All published source/output text was reviewed as belonging to the five synthetic fixtures. No real meeting data is included. The original frozen inputs and their manifest remain unchanged.

## Next action

Fix conflict qualification across all sections, and preserve conditional wording in the due field. Consider removing unsupported deployment/document specificity and redundant emphasis cues. Any revision needs a new versioned freeze and a separately agreed rerun; do not replace the scored artifacts. Do not mark M10 built or merge on the strength of execution success or manual workflow acceptance alone.
