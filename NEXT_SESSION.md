# M10 handoff — 2026-11-13, six-case diagnostic approved

Continue on `m10/notes-guided-enhancement`, [PR #16](https://github.com/MattMSumner/meeting-notes/pull/16).
Read AGENTS.md, this handoff, the reviewable draft section of plan.md and the
[V11 results](evaluation/m10/v11/results/report.md). Use `.chief/CHIEF.md` and the Herdr
skill when coordinating workers; small work can stay in the main session.

## Latest product decision

The owner confirmed that a draft saving time while requiring review is useful. The
next first-release design targets a reviewable AI draft: readable source-backed summary,
suggested decisions/actions, separately attributed writing and honest uncertainty.
Automatic conflict classification is deferred; relevant passages can be shown for review.
Actions become checkboxes only through the user's ordinary Obsidian editing. A draft
label permits neither wrong facts nor unaccepted/cancelled work claimed as commitments.

After inspecting the normal and incomplete authored previews, the owner said “Yeah these
look good!” The preview format is approved. This does not establish generated quality,
measured editing-time savings or current synthetic Obsidian acceptance.

The prospective contract in plan.md allows clear section-level incompleteness while
retaining independently useful work. It requires focused source/context, not a generic
warning or a transcript dump. Missing input snapshots remain fatal, and protected edits,
prior results, atomic saving and old wrapper behavior remain safeguards. Define the
snapshot/generation and prior-result coexistence policy before production integration.

This requirements update changes no application behavior. The current implementation
still follows V11. Its failed evaluation stays failed; no historical criteria or results
are rewritten. The bounded offline prototype is now implemented as specified below.

## Outcome and current authorization

The owner replied “Sure, do it” to all forty frozen synthetic pairs once per arm,
with ceilings 160 baseline + 116 proposed = 276 requests. That single run is complete.
Baseline published **40/40**; V11 published **34/40**, with **six blocked outputs** and
**one published false unit-conversion conflict**. V11 fails quality. Baseline also has
eight cases with critical semantic failures; its completion does not lower the V11 bar.

The run used **109 requests** (40 baseline, 69 proposed) in **98m46s**. There were fourteen
proposed corrections, no transport/response errors, no unmappable replies and no unsent
context failures. The six blocks are three comparison failures and three summary failures.
Every agreed slot and attempt is retained. There was no tuning or selective rerun.
The 167 unused requests authorize nothing further. Do not restart the completed run.

The owner subsequently approved the separate six-case diagnostic described below. No
other inference, current manual Obsidian acceptance, Built note or merge is authorized.
M10 remains unbuilt. Only the owner's explicit `shipit` authorizes `git shipit`; never
merge on GitHub. Leave the separate safeguards worktree and unrelated recovery issue alone.

## Source, freeze and settings

- Candidate source: `fb3b130fb0d6a48859b96c7e9e74ffbd6152c878`.
  Freeze: `e866b10e23ebf4c359c0c7e643f92cb8a3640c37`. Neither changed during the run.
- Frozen baseline remains `199dd62858b6bda6c13dc749424f6bd9de03f8ba`, copied exactly from V10.
- All **396 historical + 67 V11 entries** verify. All 43 copied runtime/prompt files and
  generic/per-case schemas retain the reviewed source; all seventeen V10 wrapper-9
  summaries/warnings replay exactly, including historical mistakes.
- New saves use wrapper **10 / grounding-v9**. All 34 published V11 summaries replay and
  roundtrip exactly with original/effective inputs, complete audits, selection and warnings.
  Failed attempts replay too. Evidence integrity passed; completion and quality failed.
- Strict unchanged V10 replies remain 43 unmappable under V11 (19 comparison, 24 summary).
  Schema incompatibility is not a semantic repair; authored fake responses are separate.
- qwen3:30b, temperature zero, thinking enabled, context 32768, timeout 600 seconds;
  at most four requests with notes, two without. Ollama 0.40.9 and model digest
  `ad815644918f0eaab341c12b67837cc6dd4562342cdaf118f83d5d554cb37226` were stable before
  and after each serial arm. Frozen settings keep approval fields null; run.json holds approval.

## Evidence and assessment

Everything new is in `evaluation/m10/v11/results/`: raw `baseline.jsonl` / `proposed.jsonl`,
`run.json`, `verification/completion.json`, `verification/replay.jsonl`, the report,
per-case scores, scoring lock, Chief source check and a separate results hash manifest.
Never rewrite frozen inputs, historical results or sealed assessments. New tools default
to read-only/exclusive outputs; do not run historical results/verify.py or analyze.py.

Two fresh read-only Codex assessors inspected shuffled opaque halves (forty rows each),
including raw replies and corrections. All eighty original scores locked before the Chief
opened the key; every critical quote and partial finding was checked, with no rescoring.
The report separates incomplete outcomes, corrected attempts, publication defects and
conservative review. All twenty-two familiar plus eighteen authored cases are development
material; none independently held out. One repetition and arm-revealing structure establish
no statistical reliability or fully blinded measurement.

New reporting tools were independently reviewed through two bounded repair cycles. Final
PASS at `795c38db2aafd125ab6ffe91836e59cf8156d423` covers verification freshness, exact
slot/packet/key bindings, baseline parser/selection/fallback diagnostics and identity-safe
score joining. The accepted verifier matches worker `54bb1c3` exactly. Fake-transport and
logical tool checks are not model quality evidence; read results/tool-review.md.
Formatting, lint, strict types and **978 offline tests** pass; six model/hardware integration
tests excluded. Capture is unchanged. CI and publication status are recorded in the PR/local ledger.

## Offline prototype checkpoint

The owner's “Great, do it” authorized the isolated prototype, now in
[prototypes/reviewable_draft](prototypes/reviewable_draft/README.md). Start with the
[normal draft](prototypes/reviewable_draft/previews/additional.md),
[unavailable comparison retaining invoice work](prototypes/reviewable_draft/previews/multi_claim_notes.md)
or [all ten previews](prototypes/reviewable_draft/previews/index.md). Each is explicitly
authored from unchanged frozen synthetic inputs; none was generated by a model.

The immutable model binds four section outcomes and literal source references to one
complete input snapshot and generation. The pure Markdown renderer makes suggestions
and focused review readable, quotes shared sources once, and retains original writing
separately. An unavailable section publishes no rejected item and displays an incomplete
banner while independent useful work remains visible. This is a mechanical contract,
not a semantic validator or confidence estimate. All forty original regression inputs
and their historical criteria remain unchanged.

The demo-only exporter writes ten previews, an index and provenance manifest exclusively
to a new directory. Run `uv run python -B -m prototypes.reviewable_draft --case additional`
to print one, or add `--output-dir /tmp/reviewable-draft-previews` for a fresh export.
Existing output directories and user edits are never overwritten. Production CLI,
pipeline, prompts, settings, store, wrappers and vault behavior are unchanged. Future
atomic persistence, prior-result coexistence and edit protection are specified as
integration requirements, not implemented here.

Formatting, lint, strict types and **1016 offline tests** pass, including 38 prototype
checks; six integration tests excluded. All **396 historical + 67 V11 + 23 sealed result
entries** remain unchanged, and seventeen wrapper-9 generations replay exactly.
Reproducible authored previews and passing engineering tests establish no model quality
or measured owner editing-time benefit. Capture is unchanged.

## Next decision and authorization

The format feedback is recorded. The isolated `generation.py` now prepares the small
model-facing schema/prompt, binds output to saved snapshot/host generation identity and
decodes one response using only an explicit injected transport. It has no default network
transport or production imports. Fake responses exercise shape, source-kind, identity,
unavailable-section and failure behavior; they establish no model capability.
The combined offline suite passes 1046 tests (30 additional generator checks), plus
formatting, lint and strict types; six integration tests remain excluded.

The [first diagnostic](prototypes/reviewable_draft/EXPERIMENT.md) predeclares six familiar
cases, one request each, unchanged qwen3:30b settings, six requests / fifteen minutes and
explicit stopping/assessment rules. The owner replied “I approve” to that scoped run.
No baseline, corrections, retries or selective reruns are authorized. This approval
persists while the driver is finished/reviewed and exact source, packets, input hashes
and expected local model identity are frozen; no second permission question is needed.
The clock starts with run preflight and includes metadata/capture, not offline setup.
Keep every original input/verdict and honest fresh-case provenance. Stop and report
unused/unsent cases honestly if a gate fails; the remaining allowance grants no rerun.

Passing prospective quality, current synthetic Obsidian usefulness acceptance and the
owner's `shipit` remain required before Built/merge. Numerical latency/review-effort
targets are not yet agreed; record them rather than inventing approval.

## Separate follow-up

The processing-spawn failure after confirmed orphan shutdown can clear a pending session.
It was reproduced on main. Track/repair separately with a synthetic regression; this
V11 evaluation changes neither capture nor recovery behavior.
