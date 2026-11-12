# M10 handoff — 2026-11-12, V10 offline candidate

## Start here

Continue on `m10/notes-guided-enhancement`, [PR #16](https://github.com/MattMSumner/meeting-notes/pull/16).
Read AGENTS.md, this file, the M10 section of plan.md, the
[V9 failure report](evaluation/m10/v9/results/report.md) and the
[V10 freeze contract](evaluation/m10/v10/README.md).

**The bounded conflict-completeness candidate is implemented and frozen offline. No new
inference is authorized.** Agree added inference cost, cases, repetitions, per-arm ceilings
and total budget separately before any model run. Do not merge or mark M10 Built.

## Current state

- Implementation commit `31323dc`; freeze commit `35f9787`. Source/settings provenance is
  in evaluation/m10/v10/provenance.json. Neither commit has a live quality result.
- Formatting, lint, strict pyright and **539 offline tests** pass; six integration tests
  excluded. The offline suite needs access outside the sandbox for Metal imports and `ps`;
  it does not run model inference. No capture changes, so no Swift tests were needed.
- All 340 V1–V9 manifest entries verify unchanged. V10 has 42 manifest entries. The original
  13 pairs and baseline 199dd62 are byte-preserved. Historical revision hashes retain their
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

## Freeze and next gate

V10 freezes 22 synthetic pairs: original 13 plus nine new unit/period/scope/status/additive/
multi-claim cases. expected.json and rubric.md precede generated outputs. Both prompts,
generic and per-case stage schemas, wrapper schema, source, settings and runner are hashed.
The new cases were written by the implementing agent; they are not independently held out.
No V10 generated output or quality score exists. Offline hand-authored comparisons exercise
compilation and bounds; they do not establish model classification accuracy.

Discuss and authorize scope BEFORE inference. A possible one-repetition run over all 22 pairs
has ceilings **88 baseline + 74 proposed = 162 requests** (seven proposed cases skip comparison).
These are cost calculations, not approved budgets. Do not reuse unused V9 requests.
Any different case count/repetitions/held-out set needs explicit agreement and frozen expectations.
The runner requires `--freeze v10`, `--arm`, `--repetitions`, `--max-requests`, `--output` and
`--run`; merely having that CLI is not authorization. No tuning/selective reruns in scored runs.

Score all outputs with the frozen rubric: commitment completeness, source separation, complete
and accurate conflicts, numeric meaning, dates/owners and useful emphasis. Inspect semantic
claim splitting and uncertain relations, not just text coverage. Any critical missed/invented
conflict, false agreement over uncertainty, incomplete output or spoken-commitment regression
fails the gate. Replay every selected result as wrapper 9 using saved comparison evidence;
verify old manifests unchanged. Report stage-specific requests, corrections, failures and latency.
One repetition of familiar/implementer-authored cases cannot establish reliability.

Only after a passing evaluation do current synthetic Obsidian acceptance: unchanged writing,
links, enhancement/opening behavior, protected summaries, failure/review warnings and render
from saved evidence after originals change/disappear. Earlier acceptance does not cover this
workflow. Only then consider a Built note and merge approval.

## Separate follow-up

The processing-spawn failure after confirmed orphan shutdown can clear a pending session.
It was reproduced on main as well. Track/repair separately with a synthetic regression;
this comparison work does not fix it or recording behavior.
