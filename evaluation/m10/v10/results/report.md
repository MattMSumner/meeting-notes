# M10 V10 evaluation results

**V10 finds the previously missed support-price conflict, but fails the quality gate.** Baseline
produces 22/22 summaries; proposed produces 17/22. Five proposed cases block on bounded validation,
and the published unit-disagreement case invents an action from a price statement. The blocked
multi-claim case leaves a spoken invoice commitment unavailable. M10 remains unbuilt; do not merge.

## Authorization and provenance

The user replied “Approved” to the proposed one-repetition evaluation of all 22 frozen pairs,
with a 162-request ceiling. The active-turn acknowledgement fixed arm ceilings at 88 baseline
and 74 proposed. The run at revision `1d4f5b0` used **65 requests: 22 baseline and 43 proposed**,
leaving 97 unused. All 44 case/arm slots were attempted exactly once. No tuning, selective reruns,
additional repetitions or use of the unused allowance occurred. All material is synthetic;
no real meeting or vault content was used.

The candidate source is implementation commit `31323dc`, frozen at `35f9787`. Source/settings
provenance and pre-output expectations remain in the unchanged V10 inputs. The exact frozen
runner copy was launched through scripts/evaluate-enhancement.py, whose bytes matched runner.py;
that location resolves the runner's repository-relative input paths. Frozen settings still record
their pre-authorization state; results/run.json records the subsequent approval and actual run.

The run lasted **48 minutes 44 seconds**, from 15:43:21 to 16:32:05 Eastern on 2026-11-12.
Ollama 0.40.9 and qwen3:30b digest
`ad815644918f0eaab341c12b67837cc6dd4562342cdaf118f83d5d554cb37226` were stable before,
between and after arms. Temperature zero, thinking enabled, context 32768 and transport timeout
600 seconds were unchanged. No request timed out or failed transport. The baseline's original
13 summaries are identical to V9. One run does not establish repeatability or timeout causality.

## Requests, correction and latency

| Arm / stage | Initial requests | Corrections | Total requests | Result |
|---|---:|---:|---:|---|
| Baseline summary | 22 | 0 | 22 | 22/22 summaries |
| Proposed comparison | 15 | 4 | 19 | 12 validated comparisons; three cases block before summary |
| Proposed summary | 19 | 5 | 24 | 17 summaries; two cases block after comparison |

Seven proposed cases have no notes and skip comparison. All four comparison corrections and
five summary corrections stay within their separate one-correction limits. Every sent proposed
request matches its frozen per-case stage schema; request/response trace entries match the saved
audit. Every proposed request, including corrections and the selected comparison in summary
context, passes the full-body context estimate. No request was chunked, truncated or omitted
from the transport evidence. Reference validation does not certify meaning or commitments.

Baseline arm wall time was 8 minutes 51 seconds; proposed was 39 minutes 53 seconds. Ollama's
reported total_duration sums to 22 minutes 7 seconds for proposed comparison and 17 minutes
45 seconds for proposed summary. Median server durations were 62.6 seconds per comparison and
32.1 seconds per proposed summary, versus 23.5 seconds per baseline summary. Maximum server
durations were 129.8, 114.4 and 47.7 seconds respectively. These are server-reported durations,
not separately instrumented client request wall times. Arm wall times include both stages,
corrections and failures. The run demonstrates substantial added cost without passing quality.

## Outcomes and failure evidence

| Case | Proposed outcome |
|---|---|
| empty | Both tasks and independent release-Friday agreement survive. Agreement repeats three times; undated rollback has unnecessary timing review. |
| sparse | Both tasks, monitoring 120 and no selected option survive. Written focus stays separate. Next-week recovery is unnecessarily unassigned for review; source IDs leak and facts repeat. |
| additional | Both spoken tasks/dates survive. Written-only 40 seats and venue request remain separate. Headings become isolated note bullets; comparison dimensions include empty quantity and literal `null` strings. |
| conflicting | Separate unresolved estimate and delivery conflicts preserve both amounts, “I think,” unapproved budget and independent verification. Comparison quantity fields are null/empty and estimate status says confirmed, although quoted final accounts retain the estimate. |
| ambiguous_dates | Complete conditional relative due survives; notes requests stay separate. No-launch-decision repeats as a Decision. |
| same_speaker_tasks | Both tasks retained; Friday belongs only to sending. |
| coordinated_tasks | Both tasks and Friday retained together under review; no borrowed rollback due. |
| later_timing | Original rollback task and later Friday evidence retained in unverified review; due null. |
| revised_timing | Original task and later Monday correction retained under review; obsolete Friday not assigned unqualified. |
| shared_numbers | Explicit support 120 versus quote 150 conflict, with monitoring 120 and invoice task independent. This repairs the targeted V9 failure in this single pass. |
| status_conflict | Tentative ready versus paused-for-repair accounts unresolved; health-check task independent. One summary correction removes notes references from spoken core. |
| tentative_task | Only Alex's actual checklist-tomorrow commitment becomes an action. |
| front_loaded_timing | Original sending task and full Next Tuesday retained under review; due null. |
| unit_equivalence | Correctly consistent: 120 dollars versus 12000 cents. No false conflict or task. |
| unit_disagreement | Correct unresolved 120 dollars versus 15000 cents conflict, but selected summary invents an action from factual T1. Critical failure. |
| periods_separate | Comparison correction correctly makes this-quarter 150 unmatched additional. Both summary drafts still cite N1 in spoken core and attach 150 to transcript evidence. No output. |
| scope_separate | Both comparison attempts call west-office 150 additional while citing east-office 120. This violates the no-transcript-match contract; no summary request or output. |
| estimate_approval | Comparison calls approved budget 150 additional instead of the frozen expected uncertain relation to estimate 120. Both summary drafts cite notes in spoken core; no output. |
| proposal_rejected | Rejected launch versus approved-Friday note explicitly unresolved. Summary correction removes N1 from spoken core. No invented task or approval. |
| tentative_confirmed | Both comparison attempts call confirmed readiness additional while citing tentative readiness; fail validation. No published review outcome. |
| additive_context | Correct consistent support and additional room-capacity outcomes; exact notes retained separately. All quantity/unit dimensions are null despite explicit numbers/units. |
| multi_claim_notes | Both comparison attempts split the three semantic claims but drop commas, spaces, “and” and final punctuation from their note quote partition. Exact coverage fails; no summary or invoice commitment published. |

The invented action is visible in unit_disagreement's first summary draft and survives correction:
original_commitment_id is T1, whose entire text is “Support costs 120 dollars.” The correction
removes invalid handwritten core references but retains this purported action. Code faithfully
copies the selected text and assigns no owner/deadline; that does not make the fact a commitment.
This is a semantic selection failure with valid IDs, not a fabricated quote or numeric error.

The multi-claim failure is distinct: the model identifies support as conflicting, monitoring as
consistent and venue booking as additional, but its three note quotes do not reconstruct the
passage. Both attempts receive the same coverage finding. The check fails closed as designed,
yet the workflow is incomplete and loses access to the independent spoken task in this run.
Successful offline hand-authored partitions did not predict live model compliance.

The period/scope comparisons recognize genuine differences rather than inventing hard price
conflicts. The additional/no-match wire contract prevents publishing related transcript accounts
under that outcome. Periods corrects that structure, then summary source separation still fails;
scope does not correct. These observations support reviewing contract usability, not assuming
shared values prove identity or relaxing semantic checks without a new candidate.

Twelve selected comparisons contain 18 note claims: ten additional, six conflicting and two
consistent; **zero uncertain**. Two selected comparisons belong to cases that subsequently fail
summary generation. The estimate/approval case misses the frozen expected review relation, and
tentative/confirmed blocks on additional-with-match twice. No live selected output demonstrates
the intended uncertain-review workflow. The offline review-rendering tests remain valid, but
cannot establish live semantic classification or completeness.

No published proposed summary in this run misses the targeted hard conflicts or invents a hard
cross-source conflict. That limited observation excludes the five blocked outputs and does not
rescue the completion or invented-action failures. Blank, empty-string and literal-null meaning
dimensions also show that structured field presence is not complete semantic accounting.

## Scores and assessment limits

Dimension order: commitment completeness, source attribution, conflict completeness/false
conflicts, numeric meaning, dates/owners, useful emphasis. Each is 0–2. Baseline is judged only
against speech it received; it is not penalized for unavailable notes. Blocked outputs receive
zeros and are identified separately as incomplete, not treated as published hallucinations.
Conservative unassigned timing receives partial dates credit, following prior reports; review
on an actually undated task is polish. Numeric meaning also assesses comparison dimensions,
so missing explicit quantities/units can earn partial credit despite correct final quoted values.

| Case | Baseline | V10 |
|---|---|---|
| empty | 2/2/2/2/2/2 | 2/2/2/2/2/1 |
| sparse | 2/2/2/2/2/2 | 2/2/2/2/1/1 |
| additional | 2/1/2/2/2/1 | 2/2/2/1/2/1 |
| conflicting | 2/2/2/2/2/2 | 2/2/2/1/2/1 |
| ambiguous_dates | 2/1/2/2/1/1 | 2/2/2/2/2/1 |
| same_speaker_tasks | 2/1/2/2/0/1 | 2/2/2/2/2/2 |
| coordinated_tasks | 2/2/2/2/2/2 | 2/2/2/2/1/2 |
| later_timing | 2/1/2/2/2/1 | 2/2/2/2/1/2 |
| revised_timing | 2/2/2/2/2/2 | 2/2/2/2/1/2 |
| shared_numbers | 2/2/2/2/2/2 | 2/2/2/2/2/1 |
| status_conflict | 2/1/2/2/2/1 | 2/2/2/2/2/1 |
| tentative_task | 2/1/2/2/2/1 | 2/2/2/2/2/2 |
| front_loaded_timing | 2/2/2/2/2/1 | 2/2/2/2/1/2 |
| unit_equivalence | 2/2/2/2/2/2 | 2/2/2/2/2/1 |
| unit_disagreement | 2/2/2/2/2/1 | 0/1/2/2/2/0 |
| periods_separate | 2/2/2/2/2/1 | 0/0/0/0/0/0 |
| scope_separate | 2/2/2/2/2/1 | 0/0/0/0/0/0 |
| estimate_approval | 2/2/2/2/2/1 | 0/0/0/0/0/0 |
| proposal_rejected | 2/2/2/2/2/1 | 2/2/2/2/2/1 |
| tentative_confirmed | 2/1/2/2/2/1 | 0/0/0/0/0/0 |
| additive_context | 2/2/2/2/2/1 | 2/2/2/1/2/1 |
| multi_claim_notes | 2/2/2/2/0/1 | 0/0/0/0/0/0 |

Codex assessed shuffled opaque labels before reading the arm key. Source scope, summary structure
and comparison fields reveal arms, so this is weak label blinding, not independent or fully
blinded assessment. Same-agent authorship, the 13 familiar fixtures and nine implementer-authored
new fixtures limit confidence. There is one repetition and no variability estimate. Scores are
recorded in blinded-scores.json and joined in scores.json; per-row evidence spans explain them.

All original 13 proposed outputs retain their spoken commitments and independent release
agreement. The new multi-claim case is a completion/commitment regression versus baseline;
unit_disagreement creates a task that speech never expressed. Baseline itself upgrades tentative
readiness to confirmation, borrows Friday for rollback in prose and loses the not-before timing
qualifier in the multi-claim action's due. Those baseline failures do not excuse proposed failures.
The gate fails regardless of small judgment differences in polish or partial-credit scoring.

## Verification and next gate

All 17 selected proposed summaries validate and round-trip in wrapper 9 / grounding-v8, including
selected comparison, exact passages/context, actions, conflicts and warnings. Six actions retain
timing review and six have assigned due values. There are no selected numeric or comparison-review
warnings. All 340 prior manifest entries and all 42 V10 input entries remain unchanged.
results/verify.py reproduces transport/schema/context checks and saved-generation replay without
inference; results/analyze.py joins the opaque assessments and computes comparison diagnostics.
results/completion.json records mechanical checks; results/assessment.json records quality limits.

Formatting, lint, strict pyright and **539 offline tests** pass; six integration tests excluded.
No capture code changed. Current synthetic Obsidian acceptance was not advanced because quality
failed. M10 remains unbuilt and unmerged. No candidate code or frozen input was changed during
or after scoring; any repair needs a new offline candidate and freeze. Further model runs need
newly agreed scope and budget; this run's 97 unused requests are not authorization for reruns.
