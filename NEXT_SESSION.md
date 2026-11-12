# M10 handoff — 2026-11-12, V11 offline plan ready

## Start here

Continue on `m10/notes-guided-enhancement`, [PR #16](https://github.com/MattMSumner/meeting-notes/pull/16).
Read AGENTS.md, this file, the M10 section of plan.md, the
[V9 failure report](evaluation/m10/v9/results/report.md) and the
[V10 freeze contract](evaluation/m10/v10/README.md).

**The approved V10 evaluation is complete and failed quality. No further inference is
authorized.** Read [the results report](evaluation/m10/v10/results/report.md) before designing
an offline successor. The user asked for the next steps to be planned before a fresh session.
This session changes documentation only. On a request to continue, follow the V11 offline plan
in plan.md through implementation, verification and a fresh freeze; stop before inference.
Do not tune V10, reuse its unused request allowance, merge or mark M10 Built.

## Current state

- Implementation commit `31323dc`; freeze commit `35f9787`; evaluation evidence commit
  `9f6084d`. Source/settings provenance remains in evaluation/m10/v10/provenance.json.
  V10 inputs retain their pre-authorization state; results/run.json records subsequent approval.
- Formatting, lint, strict pyright and **539 offline tests** pass; six integration tests
  excluded. The offline suite needs access outside the sandbox for Metal imports and `ps`;
  it does not run model inference. No capture changes, so no Swift tests were needed.
- All 340 V1–V9 manifest entries verify unchanged. V10 has 42 input entries and 14 result
  entries (396 total). The original 13 pairs and baseline 199dd62 are byte-preserved.
  Historical revision hashes retain their original meaning across the prior rebase; never
  rewrite frozen provenance.
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

## Fresh-session objective: V11 offline candidate

Follow **“Next: M10 V11 candidate — offline work, then a separate evaluation decision”**
in plan.md. V11 is a candidate version inside M10, not the separate M11 milestone. Stay on
the existing M10 branch/PR. The working tree is clean before this handoff's documentation
commits; nothing has been pushed. No V11 source, fixtures or freeze exist yet.

The recommended order and deliverables are:

1. Reproduce the six V10 failure cases from saved replies. Specify commitment admissibility,
   claim-span coverage, comparison relations, uncertainty and stage failure/fallback behavior
   before implementation. No additional model pass is planned.
2. Repair fact-as-action selection first. Exact source IDs and model-supplied status cannot
   prove commitment. Preserve code assembly and legitimate third-person/implied/coordinated
   commitments; test noncommitments, facts, retractions and independent decisions too.
   Record the scope and semantic limits of any new diagnostic or evidence requirement.
3. Have code resolve exact claim anchors to saved spans and retain separators. Settle unique
   matching, order, overlaps, repeated anchors and uncovered semantic words. Never silently
   drop negation/uncertainty/conditions to make a partition pass. Semantic splitting remains
   model work even when every source character is retained.
4. Represent related-but-distinct accounts separately from matching evidence. Preserve
   periods, units, scope and epistemic status. Make uncertain relations visible, and handle
   blank/literal-null meaning fields without inventing values. Written-only facts/requests
   remain notes. Do not infer identity/conflict from number or keyword overlap.
5. Keep conflicts/written context code-assembled and constrain generated spoken fields to
   transcript references in a compact schema. Preserve runtime validation; test wrong-source
   prose with valid transcript IDs as well as forbidden N references. Avoid another nested
   reference-union redesign. Restricting ID enums alone does not prove semantic grounding.
6. Introduce wrapper 10 / grounding-v9 for changed semantics, preserving wrappers 1–9 and
   their transitive compilers/contracts. Save all new evidence atomically, replay without
   original reads/inference, preserve successful generations on failure. Keep the existing
   four-request-with-notes/two-without ceiling and full request-size checks unless a policy
   change is separately agreed. No hidden retry, truncation or chunking.
7. Run required offline checks, replay historical saves, verify all 396 manifest entries,
   and freeze V11 source/prompts/schemas/settings/fixtures/provenance/rubric/expectations.
   Retain the 22 V10 pairs, predeclare additions and report familiar-case limitations.
   End the offline phase with a concrete candidate and separately proposed evaluation scope;
   do not run models from the old approval.

Important implementation traps:

- `compiler_comparison.py`, `comparison.py` and the shared `contract.py` participate in
  wrapper-9 replay. A new action field or comparison rule cannot silently change old saves.
  Preserve historical schemas/validators in versioned modules before introducing new ones.
  Inspect transitive helpers (`coverage.py`, figure checks, source splitting) too.
- `tests/test_comparison.py::test_frozen_candidate_inputs_schemas_and_sources_match_runtime`
  currently requires V10 frozen source to equal the working implementation. Replace that
  current-tree assumption with manifest/recorded-commit checks plus all 17 V10 saved-generation
  replays. The current implementation is allowed to advance; frozen evidence is not.
- Old V10 replies will not automatically fit a new contract. Keep unchanged-response replay
  (compile/block/unmappable counts) separate from explicitly authored V11 fake responses.
  Neither is a fresh model quality evaluation.
- Model output grammar can prevent N IDs in spoken fields, but a T ID can still cite the
  wrong meaning. Do not label structural compliance a semantic completeness guarantee.
- V10's frozen runner copy resolves paths from its original scripts location;
  scripts/evaluate-enhancement.py was byte-identical at run. Do not rewrite the old freeze
  to repair invocation convenience.

Start with `src/meeting_notes/{comparison,compiler_comparison,contract,ollama,audit,evidence,
store,pipeline}.py`, prompts, `tests/test_comparison.py`, `tests/test_current_ollama.py`,
`tests/test_enhance.py`, and the six failed V10 cases in results/proposed.jsonl. Read AGENTS.md
and the plan before editing. Use synthetic material only; leave the unrelated recovery issue
below and the safeguards worktree alone.

## Later gates — not authorized by the old evaluation

After V11 is frozen, agree cases, repetitions, per-arm ceilings, total budget and stopping
rules before inference. The V10 run's 97 unused requests are not available for new experiments.
Account for its 48m44s latency. No tuning or selective reruns during a scored run. Require all
outputs complete; no invented tasks, lost commitments/agreements, critical missed/invented
conflicts or incorrect source separation; explicit uncertainty must be reviewed. Score semantic
splits and dimensions as well as rendered text, then replay every selected result from evidence.

Only a passing quality evaluation advances current synthetic Obsidian acceptance: unchanged
writing, links, opening behavior, protected summaries, failure/review warnings and later render
after originals change/disappear. Earlier acceptance does not cover this workflow. Only then
consider a Built note and the owner's merge approval. No merge is authorized now.

## Separate follow-up

The processing-spawn failure after confirmed orphan shutdown can clear a pending session.
It was reproduced on main as well. Track/repair separately with a synthetic regression;
this comparison work does not fix it or recording behavior.
