# M10 handoff — 2026-11-12, V10 evaluation failed

## Start here

Continue on `m10/notes-guided-enhancement`, [PR #16](https://github.com/MattMSumner/meeting-notes/pull/16).
Read AGENTS.md, this file, the M10 section of plan.md, the
[V9 failure report](evaluation/m10/v9/results/report.md) and the
[V10 freeze contract](evaluation/m10/v10/README.md).

**The approved V10 evaluation is complete and failed quality. No further inference is
authorized.** Read [the results report](evaluation/m10/v10/results/report.md) before designing
an offline successor. Do not tune V10, reuse its unused request allowance, merge or mark M10 Built.

## Current state

- Implementation commit `31323dc`; freeze commit `35f9787`; evaluation evidence commit
  `9f6084d`. Source/settings provenance remains in evaluation/m10/v10/provenance.json.
  V10 inputs retain their pre-authorization state; results/run.json records subsequent approval.
- Formatting, lint, strict pyright and **539 offline tests** pass; six integration tests
  excluded. The offline suite needs access outside the sandbox for Metal imports and `ps`;
  it does not run model inference. No capture changes, so no Swift tests were needed.
- All 340 V1–V9 manifest entries verify unchanged. V10 has 42 input entries and 14 result
  entries. The original 13 pairs and baseline 199dd62 are byte-preserved. Historical revision hashes retain their
  original meaning across the prior rebase; never rewrite frozen provenance.
- Existing recording safeguards from main `8428868` remain intact. Completion/recovery do
  transcription only. Leave `/tmp/meeting-notes-safeguards` and the pre-rebase backup alone.
- Existing PR #16 remains open; this work is committed locally, not pushed or posted to GitHub.

## Implemented contract

Comparison runs first only when note passages exist, using every saved note/transcript
passage and meeting context. Each note passage is partitioned into exact ordered quotes;
these must concatenate to its full text. Claims receive code-assigned N1.C1, N1.C2 IDs.
Every claim has structured meaning dimensions, account kind, exact source references and
one outcome: consistent, additional, conflicting or uncertain. Additional is unmatched;
consistent/conflicting require transcript accounts. Uncertain may have no established match.
Nonfactual notes still receive coverage; requests/context cannot assert factual conflict.

`comparison.py` validates coverage and references. **These checks cannot prove atomic semantic
splitting, correct subject identity, qualifier preservation or classification.** A model can
still misclassify support 120 versus 150 as agreement; evaluation must test that. Shared
numbers or keywords are never used by code as proof of identity or disagreement.

`compiler_comparison.py` owns compilation for new saves. It copies conflict accounts from
comparison quotes, qualifies disputed core references, preserves independent sources in mixed
items and shows uncertain relations as persistent review warnings. It copies consistent and
additional note claims into From your notes. Draft conflicts must be empty; comparison owns
them. Written requests never become spoken tasks. Original commitment/timing assembly and
agreement/commitment omission diagnostics remain. Factual disputes do not automatically dispute
adjacent tasks; comparison commitment accounts can retain a disputed task with review.

`ollama.py` allows one comparison correction plus one summary correction: at most four calls
with notes (two initial/two correction), two without notes. No transport retries or silent
chunking/truncation. Coverage failure blocks summary generation; uncertainty is visible review,
not a correction request. Full body context estimates count schema/settings/sources/history,
and summary requests also count the selected comparison. Model/settings remain qwen3:30b,
temperature zero, thinking enabled, context 32768, timeout 600 seconds.

Wrapper 9 / grounding-v8 saves exact snapshot inputs, both stages' attempts/selections,
summary and warnings atomically. Failed comparison/generation/audit-save/summary-save preserves
the previous successful generation/evidence. Rendering recompiles from saved evidence without
reading original notes or invoking a model. Wrappers 1–8 keep original validators, including
the V9 compiler and its known semantic failure. No unrelated recovery redesign was bundled.

## Completed evaluation and next gate

V10 freezes 22 synthetic pairs: original 13 plus nine new unit/period/scope/status/additive/
multi-claim cases. expected.json and rubric.md precede generated outputs. Both prompts,
generic and per-case stage schemas, wrapper schema, source, settings and runner are hashed.
The new cases were written by the implementing agent; they are not independently held out.
The approved one-repetition run attempted all 22 cases per arm under ceilings of 88 baseline
and 74 proposed (162 total). It used **65 requests: 22 baseline + 43 proposed**, leaving 97
unused. No tuning, selective reruns or extra repetitions occurred. Baseline produced 22/22;
proposed produced 17/22. All five failed cases and every attempt are retained. No timeout or
transport error occurred. Model/settings/digest were stable; run wall time was 48m44s.

Proposed comparison used 15 initial + four correction requests; summary used 19 initial + five
corrections. Three cases blocked comparison, two blocked summary. All 17 selected outputs
replay exactly as wrapper 9. Offline verification is results/verify.py; scoring joins and
diagnostics are results/analyze.py. The original 13 baseline summaries match V9 exactly.

The targeted shared_numbers conflict now appears with both support accounts while monitoring
and invoice action remain independent. Original 13 spoken tasks and release agreement survive.
Nevertheless the quality gate fails:

- unit_disagreement publishes a factual price statement as an action (T1). Its correction
  removes invalid notes references from core prose but preserves the invented action.
  Source-ID membership and exact code assembly do not prove that an action was spoken.
- scope_separate and tentative_confirmed call claims additional while retaining transcript
  accounts on both attempts. The no-match contract blocks them. Scope differences are
  recognized in the reasons; tentative versus confirmed should have received visible review.
- multi_claim_notes finds the three semantic relations but drops separators/punctuation from
  the exact partition on both attempts. Coverage fails and the independent invoice task is
  unavailable. This is a commitment/completion regression against baseline.
- periods_separate repairs additional/no-match structure, then both summary drafts still cite
  handwritten N1 in spoken core. estimate_approval also blocks summary for N1 in core; its
  selected comparison incorrectly avoids the frozen expected uncertain review relation.
- Comparison quantity/unit fields can be null/empty despite explicit values; absent dimensions
  can contain literal `null` strings. Zero selected comparisons use uncertain. Offline review
  rendering tests do not establish live uncertainty classification or semantic completeness.

There are 12 selected comparisons with 18 claims (ten additional, six conflicting, two
consistent); two selected comparisons belong to blocked summaries. No published proposed
output in this one run misses the targeted hard conflicts or invents a hard conflict, but
that observation excludes blocked cases and does not satisfy acceptance.

Scores were entered against shuffled opaque labels before joining the arm key. Output/source
structure reveals arms; this was neither fully blinded nor independent review. One run on
familiar/implementer-authored cases does not establish reliability. No current Obsidian
acceptance was attempted because quality failed. M10 remains unbuilt.

## Offline successor work only, if requested

Design a fresh contract from the recorded failures before implementation. Keep task text and
timing code-assembled; investigate how to reject factual IDs selected as commitments without
inventing tasks or brittle subject/number matching. Reconsider requiring the model to assign
punctuation/whitespace between semantic claim spans and whether related-but-distinct transcript
accounts need an explicit representation separate from a matching account. Preserve semantic
coverage and uncertainty requirements; do not weaken them just to publish blocked fixtures.
Review repeated source-kind correction failures separately from claim classification.

Add fake-transport regressions from saved V10 responses and retain every historical validator.
Any successor needs a new freeze with expected outcomes before outputs, and separately agreed
cases/repetitions/per-arm ceilings/total budget. The 97 unused V10 requests authorize nothing
further. Do not edit V10 inputs/results to fit a repair. The runner's frozen copy resolves paths
from its original scripts location; scripts/evaluate-enhancement.py was byte-identical at run.

Only after a passing evaluation do current synthetic Obsidian acceptance: unchanged writing,
links, enhancement/opening behavior, protected summaries, failure/review warnings and render
from saved evidence after originals change/disappear. Earlier acceptance does not cover this
workflow. Only then consider a Built note and merge approval.

## Separate follow-up

The processing-spawn failure after confirmed orphan shutdown can clear a pending session.
It was reproduced on main as well. Track/repair separately with a synthetic regression;
this comparison work does not fix it or recording behavior.
