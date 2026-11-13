# M10 handoff — 2026-11-12, approved V11 evaluation running

## Start here

Continue on `m10/notes-guided-enhancement`, [PR #16](https://github.com/MattMSumner/meeting-notes/pull/16).
Read AGENTS.md, this handoff, the V11 section of plan.md and the
[V11 freeze contract](evaluation/m10/v11/README.md). Use `.chief/CHIEF.md` and the Herdr
skill when coordinating workers; small work can stay in the main session.

The owner replied **“Sure, do it”** to the frozen evaluation proposal: all 40 synthetic
pairs once per arm, ceilings **160 baseline + 116 proposed = 276 requests**. The serial
run started at 2026-11-12T19:04:05-05:00. Run metadata and every attempt are in
`evaluation/m10/v11/results/`; the orchestrator is `.chief/runs/evaluate-v11.py`.
**Do not launch a second run.** Check active process/status and `.chief/STATE.md` first.
No tuning, selective reruns, extra inference, current manual acceptance, Built or merge.
Frozen settings stay unchanged; the approval is recorded in new results/run.json.
The original offline-only wording below describes the prior checkpoint and predeclared
evaluation contract; this paragraph records the newer approval.

## Current source and evidence

- Reviewed implementation: `fb3b130fb0d6a48859b96c7e9e74ffbd6152c878`.
  Freeze: `e866b10e23ebf4c359c0c7e643f92cb8a3640c37`.
- Formatting, Ruff lint, strict pyright and **978 offline tests** pass; six model/hardware
  integration tests excluded. Full tests needed broader local access for Metal imports
  and process inspection, not inference. Capture is unchanged; no local Swift rerun.
- All **396 V1–V10 entries** remain unchanged. All **67 V11 entries** verify. All 43 copied
  runtime/prompt files match the recorded source commit; frozen baseline bytes match V10.
  Generic and all 40 per-case schemas match frozen imports. The original 22 pair values
  and baseline `199dd62` are preserved. Never rewrite frozen manifests/provenance.
- All 17 selected V10 summaries/warnings replay exactly under wrapper 9, including known
  mistakes. Strict unchanged-V10-response compatibility under V11: 0 compiled, 0 blocked,
  43 unmappable replies (19 comparison, 24 summary; 22 cases). Schema incompatibility is
  not a semantic repair. Authored V11 fake responses are separate from fresh model evidence.
- Independent source review passed at `fb3b130`: eight reported findings resolved,
  555 selected tests and twelve production fake-transport/wrapper-10 scenarios passed.
  Read [review.md](evaluation/m10/v11/review.md) and
  [verification.json](evaluation/m10/v11/verification.json) for scope and limitations.
- Independent package audit passed at `e866b10`: all 67 entries, source/baseline bytes,
  generic/per-case schemas, approval-null settings and fresh-process frozen imports verify.
- Main's recording safeguards remain intact. Leave the separate
  `/tmp/meeting-notes-safeguards` worktree and unrelated processing-spawn recovery issue alone.

## Implemented contract

New modules: `contract_v11`, `spans_v11`, `comparison_v11`, `commitments_v11`,
`compiler_v11` and `request_v11`. Historical definitions/transitive helpers are unchanged.
New saves use wrapper 10 / grounding-v9; wrappers 1–9 retain original validators/outcomes.

The summary stage supplies task IDs, exact undertaking/context anchors, basis and
committed/uncertain disposition. Narrow English diagnostics inspect actual evidence
for noncommitments/retractions; code assembles task, owner and timing. Unknown candidates
remain attributed, non-executable review. Partial cancellations retain full original and
retraction context even when omitted or selected with incomplete acceptance context.
Recognized mixed actors and negative modal forms participate. This is not a general
semantic classifier or a proof that every genuine undertaking is detected.

Code resolves claim anchors, occurrence, order/overlap and retained gaps. Meaningful
uncovered words are not formatting. Comparison separates consistent/conflicting,
related-distinct, uncertain and unmatched additional accounts. Absent/unresolved extraction
differ; lexical quantity overlap proves no identity. Spoken draft references are
transcript-only; comparison owns code-assembled written context/conflicts.

Original/effective inputs, raw attempts, resolutions, compilation and selection evidence
save atomically. Replay verifies source/context/raw-selection bindings, request budgets
and raw failure state. Failed comparisons stay closed; failed corrections can use only
a fully valid prior fallback. Prior generations/evidence survive failed generation/writes.
Rendering reads neither original notes nor inference. Fake filesystem tests cover these
mechanics, not current manual Obsidian acceptance.

Unchanged settings: qwen3:30b, temperature zero, thinking enabled, context 32768, timeout
600 seconds; four requests with note passages, two without. No extra model pass, transport
retry, silent truncation, chunking or partial publication.

## Next gate: agree evaluation before inference

V11 has **40 predeclared synthetic pairs**: 22 familiar V10 pairs and 18 authored additions.
Criteria/expectations match every case. None is independently held out. The
[rubric](evaluation/m10/v11/rubric.md) scores semantic commitment admission, splitting,
relations, source meaning, quantities/qualifiers, agreements and completion, not just IDs.

Proposed scope, not approval: one repetition of all 40 pairs in both arms, 80 slots,
ceiling **160 baseline + 116 proposed = 276 requests**. Eighteen cases have note passages;
22 do not. Repetitions/budget stay null in frozen settings. V10 took 48m44s for 65 requests;
agree latency expectations as well as request ceilings and stopping rules.

Before an approved run:

1. Agree exact cases/repetitions, per-arm and total budgets, stopping rules and output
   locations. Preserve source/prompts/settings/expectations; no tuning or selective reruns.
   Record new approval and actual run ceilings separately; never edit frozen settings.
2. Run `.venv/bin/python -B evaluation/m10/v11/check_offline.py`. It selects frozen
   imports and reads only saved evidence. Never run historical `results/verify.py` or
   `analyze.py` directly; they rewrite frozen results.
3. Run `cmp scripts/evaluate-enhancement.py evaluation/m10/v11/runner.py` before using
   the scripts entry point. The frozen copy preserves scripts-relative layout; do not
   execute a changed working runner or silently repair frozen code. Verify all frozen
   inputs/settings and model identity before each arm. Stop on integrity/settings changes
   or budget exhaustion. Old unused allowances provide no authorization.
4. Preserve every attempt/error and account for every slot, including missing/blocked
   ones. All agreed outputs must complete; invented/lost commitments, critical missed/
   invented conflicts, wrong source meaning or lost qualifiers fail quality.
5. Replay every selected result as wrapper 10 and verify historical manifests unchanged.
   Report actual latency and limitations; one run on these cases establishes no reliability.

Only passing quality advances current synthetic Obsidian acceptance: unchanged writing,
links, opening behavior, protected summaries, failure/review warnings and rendering after
originals change/disappear. Only then consider M10 Built and the owner's merge approval.
No merge now; `git shipit` remains the sole merge path.

## Separate follow-up

The processing-spawn failure after confirmed orphan shutdown can clear a pending session.
It was reproduced on main. Track/repair separately with a synthetic regression; V11 does
not change capture/recovery behavior.
