# M10 handoff — 2026-11-12, V11 evaluation failed quality

Continue on `m10/notes-guided-enhancement`, [PR #16](https://github.com/MattMSumner/meeting-notes/pull/16).
Read AGENTS.md, this handoff, the V11 section of plan.md and the
[V11 results](evaluation/m10/v11/results/report.md). Use `.chief/CHIEF.md` and the Herdr
skill when coordinating workers; small work can stay in the main session.

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

No further inference, current manual Obsidian acceptance, Built note or merge is authorized.
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

## Next decision

Preserve this failed freeze and evidence. Agree any successor scope after offline investigation:

1. Fix the demonstrated 12000-cents versus 120-dollars false conflict without relying on
   shared lexical quantities or weakening subject/unit/period/scope checks.
2. Investigate comparison extraction/uncertainty failures in shared_numbers,
   tentative_confirmed and multi_claim_notes. Independent invoice work was unavailable
   when comparison blocked. No new partial-publication policy is assumed.
3. Investigate the actual rejected summary replies in accepted_status_answer,
   accepted_request_retracted and partial_coordination_retracted. Correct rejection of
   noncommitments did not produce a complete useful result within the existing budget.
4. Keep the remaining partial findings visible: misleading unaccepted-task prose,
   absent versus unresolved dimensions, omitted explicit nonapproval and review noise.
   Preserve independent agreements, genuine undertakings and full timing qualifiers.
5. Any successor needs a fresh reviewed source/schema freeze, preserved historical replay
   and a separately agreed evaluation. Only passing quality advances current synthetic
   Obsidian acceptance; then consider Built and the owner's merge approval.

## Separate follow-up

The processing-spawn failure after confirmed orphan shutdown can clear a pending session.
It was reproduced on main. Track/repair separately with a synthetic regression; this
V11 evaluation changes neither capture nor recovery behavior.
