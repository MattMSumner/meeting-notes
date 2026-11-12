# M10 handoff — 2026-11-12

## Start here

Continue on `m10/notes-guided-enhancement`, [PR #16](https://github.com/MattMSumner/meeting-notes/pull/16).
Read AGENTS.md, this file, the M10 section of plan.md and the
[V9 report](evaluation/m10/v9/results/report.md) before changing the contract.
The next task is to design and implement a bounded conflict-completeness stage, then
freeze a candidate for separately authorized evaluation. Do not merge or mark M10 Built yet.
No new model run is authorized by this handoff.

## Working state

- Rebased onto main at `8428868cb141de06e98d444b26a8ec717bab88a2`, which shipped
  [PR #17](https://github.com/MattMSumner/meeting-notes/pull/17): one-hour default recording
  cap, configurable shortcut launchers, durable recovery and concurrent Start/Stop safeguards.
  These safeguards are retained, with M10 completion doing transcription only.
- Local backup `backup/m10-before-main-rebase-20261112` preserves the old enhancement
  head `4ea3f40b43650b1be9210868dc642a77438dc465`. The safeguards worktree at
  `/tmp/meeting-notes-safeguards` is on main; leave it alone unless needed.
- Explicit enhancement, chooser, immutable input snapshots, protected vault publication,
  per-meeting locks, and atomic summary/evidence storage are implemented.
- Tasks and deadlines are assembled by code from referenced source statements. Keep this
  simpler contract; do not return to free-form model-generated tasks/deadlines.
- Current saves use wrapper 8 / grounding-v7. Earlier saves retain their original validators.
- Rebase verification: formatting, lint, strict types and 495 offline tests pass; six
  integration tests excluded. No capture changes. All 340 frozen manifest entries verify,
  and the entire evaluation tree is byte-identical to the pre-rebase branch. No inference ran.
- Historical evaluation revision hashes refer to the original commits. Do not rewrite frozen
  provenance to the new rebased hashes or describe these tests as a fresh quality evaluation.

## Remaining failure

V9 used 26 requests (13 cases per arm, one repetition) of its approved 78-request cap.
All cases completed without corrections/timeouts; the release agreement and independent
verification task survive. This does not establish repeatability or the cause of V8 timeouts.

The synthetic `shared_numbers` case still fails: transcript monitoring 120 and support 120;
notes support 150. The summary presents support 120 in key points and support 150 in notes,
but has no conflict. Reference integrity and numeric presence both pass. Neither proves
that all cross-source disagreements were identified. Do not solve this by assuming shared
numbers or keywords establish subject identity or conflict.

Source-ID leakage, repetition and unnecessary timing review are secondary polish issues.
Keep them distinct from the missing-conflict gate and avoid bundling unrelated redesigns.

## Proposed next candidate

1. Specify a structured comparison pass over the saved notes and transcript evidence,
   separate from numeric validation. Require coverage of handwritten factual claims and
   explicit outcomes: consistent, additional, conflicting, or uncertain. Outcomes cite stable
   note/transcript source IDs; additional claims may have no transcript match. A note passage
   may contain several claims, so passage coverage alone cannot prove semantic completeness.
   Define how split claims and unmatched/uncertain statements are represented before coding.
2. Compare subject, quantity/unit, period, scope and epistemic status (estimate, proposal,
   approval, uncertainty), preserving qualifiers and relative dates. Different subjects or
   periods can explain different values. Written-only requests remain notes, not spoken tasks.
   Explicit uncertainty must be visible for review rather than treated as agreement.
3. Let code assemble identified conflicts with both accounts and qualify disputed core facts.
   Do not suppress independent commitments or attach unrelated tasks to a factual dispute.
   Validate references and coverage mechanically, while acknowledging that semantic
   classification remains model work and must pass evaluation.
4. Prefer a separately bounded comparison stage over another prompt-only instruction in the
   existing summary call. Settle its placement, failure behavior and correction policy first.
   Document maximum initial/correction requests for the whole workflow, latency implications,
   and exact context accounting. Do not silently add retries, truncate, or chunk inputs.
   Decide with the user whether the additional inference cost is acceptable before live runs.
5. Save comparison inputs, outputs and compilation evidence atomically with the result.
   Introduce a new wrapper/validator version if semantics change; retain versions 1–8 and
   their historical compilers. Rendering must replay saved evidence without rereading notes.
   Failed audit/generation must preserve the previous successful result and evidence; define
   a visible review or failure outcome for incomplete coverage rather than publishing silently.

Inspect `src/meeting_notes/grounding.py`, `compiler.py`, `coverage.py`, `ollama.py`,
`evidence.py`, `pipeline.py`, the current prompts and `scripts/evaluate-enhancement.py`.
Read corresponding tests and frozen V9 schemas before settling the new data model.
The comparison contract above is a proposed direction, not a proven or frozen implementation.

## Offline implementation and verification

Add synthetic tests with fake transports before any live evaluation:

- The missed support-price conflict, plus unrelated monitoring with the same number.
- Same subject with different units, periods or scope; estimate versus approval; tentative
  versus confirmed claims; genuinely conflicting facts versus additive context.
- Multiple claims in one note passage, unmatched notes, incomplete or duplicated coverage,
  invalid/wrong-source references, and uncertain comparisons with visible review behavior.
- Independent decisions and tasks survive factual disputes; written-only tasks never become
  spoken commitments. Timing qualifiers and ambiguous dates remain intact.
- Full context limits on every request and correction, exact bounded call counts, transport
  failures, malformed responses and atomic-save failure preserving the previous generation.
- Exact snapshots despite edits/deletion of originals, replay of new saved evidence, old
  wrapper compatibility and no model calls during rendering/transcription/recovery.

Run ruff format, ruff check, strict pyright and the full offline pytest suite before commits.
Swift tests only if capture changes. Keep roadmap updates in separate `Plan: ...` commits.
No real meeting content, names or details belong in this public repository.

## Freeze and evaluation gate

Preserve V1–V9 inputs/results and baseline commit `199dd62`; do not reuse the rejected
quoted-figures implementation. Freeze a new candidate directory with prompt, schemas,
settings, fixture hashes, provenance and a manual scoring rubric before inference.
Keep the original 13 pairs for comparison and add discriminating synthetic cases covering
subject, units, periods, status and multi-claim notes. Reserve unseen cases where practical.
Freeze expected outcomes before viewing generated outputs; report familiar-case limitations.

Agree on case count, repetitions, per-arm ceilings and a total request budget separately.
A second stage changes the cost; neither the old 78-request limit nor its unused allowance
implicitly authorizes another run. Retain qwen3:30b, temperature zero, thinking enabled,
context 32768 and timeout 600 seconds unless a separate decision changes them. Make any
new retry policy explicit. No tuning or selective reruns inside a scored run.

Score commitment completeness, attribution, conflict completeness and false conflicts,
numeric meaning, dates/owners and useful emphasis. Require complete outputs, no critical
missed/invented conflict, no spoken-commitment regression and correct source separation.
Replay every selected result from saved evidence and verify old frozen manifests unchanged.
If the quality gate passes, do current synthetic Obsidian acceptance: unchanged writing,
correct links, enhancement/opening behavior, protected summaries, failure/review warnings
and later render from saved evidence. Earlier manual acceptance does not cover the current
review workflow. Only then consider a Built note and merge approval.

## Separate follow-up

An existing processing-spawn failure after confirmed orphan shutdown can clear the pending
session. It was reproduced on main as well. Track/repair separately with a synthetic
regression; do not confuse it with conflict quality or claim this rebase fixed it.
