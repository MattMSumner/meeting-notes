# M10 V11 — anchored commitments and code-resolved comparison

**Offline candidate; no V11 inference or quality result is authorized.** M10 remains
unbuilt. The freeze boundary is `sha256.json`: until that file exists, this directory
is offline preparation. The final package records source revision in provenance.json,
settings, generic/per-case schemas, prompts, fixtures, expectations and the scoring rubric.
V1–V10 evidence and baseline `199dd62` remain unchanged.

## Candidate behavior

The [contract](design.md) was specified before implementation and model outputs.
The summary stage selects original transcript sources with exact undertaking/context
anchors, a commitment basis and committed/uncertain disposition. Code checks literal
evidence and narrow task/noncommitment/retraction forms, then assembles task, owner and
timing. A declared commitment kind, valid ID or quote is not proof that a task was spoken.

Detected noncommitments use the existing correction budget. Unresolved candidates stay
in attributed, non-executable review. Partial coordination cancellation retains the
complete original and retraction for review rather than silently losing remaining work.
Known accepted-request, cancellation and timing-review defects found by independent
code review have targeted regressions; final verification/review evidence records the
actual accepted revision. English paraphrases, sarcasm, clause scope and semantic
completeness remain quality-evaluation concerns.

Comparison selects literal claim anchors; code resolves ordered offsets, rejects
ambiguous/overlapping/absent anchors and retains original gaps. Repeated text requires
an occurrence discriminator. Punctuation/whitespace and narrow additive separators can
be residual; negation, conditions, alternatives, headings and other semantic content
need explicit coverage. Complete source snapshots retain text between passages too.
Coverage cannot prove that claims were split or classified correctly.

Consistent, conflicting, related-distinct, uncertain and unmatched additional accounts
remain separate. Distinct periods/scopes can retain related context without agreement
or conflict. Blank/literal-null dimensions are rejected; absence and unresolved
extraction differ. Quantity/unit/status diagnostics are deliberately narrow and cannot
establish identity or entailment from lexical overlap.

Generated spoken core/actions/timing use one flat transcript-only vocabulary. Comparison
owns code-assembled written context/conflicts. Runtime still checks source kinds, exact
anchors and numbers, including correction/fallback paths. Supported prose can still
misstate a valid T source; this candidate is not a semantic grounding guarantee.

## Requests, failure and persistence

With note passages: comparison initial plus one correction, then summary initial plus
one correction, at most four requests. Without note passages: at most two summary
requests. Keep qwen3:30b, temperature zero, thinking enabled, context 32768 and timeout
600 seconds. Full request-size estimates include source text, schema/settings, selected
comparison and correction history. There are no transport retries, extra model passes,
silent truncation or chunking. The character estimate is conservative, not a tokenizer.

Exhausted comparison failure remains fail-closed and cannot publish a new partial
summary. It preserves the prior successful result, but may prevent new independent
tasks from reaching publication; such a blocked case fails completion. Uncertain
comparisons/candidates retain visible review. Correction selection protects admitted
undertakings, timing evidence and independent agreements; only a fully valid prior
candidate can be fallback.

New saves use wrapper **10 / grounding-v9**. Exact original/effective inputs, requests,
raw replies, selected attempts, code-resolved spans/relations, commitment checks and
compilation/selection findings are saved together. Replay recomputes them from saved
evidence and verifies bindings. Audit/summary-save failures preserve the previous
generation atomically. Rendering reads neither original notes nor inference. Wrappers
1–9 retain original behavior, including known historical mistakes.

## Offline evidence and its limits

Run the read-only verifier without models:

```sh
.venv/bin/python -B evaluation/m10/v11/check_offline.py
```

It selects frozen `proposed/` imports once packaged, verifies manifest integrity,
roundtrips all 17 selected V10 wrapper-9 generations and recomputes strict old-response
compatibility. It never runs the historical verification scripts that write results.
[offline-report.json](offline-report.json) records 396 unchanged historical entries,
17 faithful replays and 43 unchanged V10 replies unmappable under the new schema
(19 comparison, 24 summary; 22 cases). Nothing is silently converted to V11 fields.
Schema incompatibility is not evidence of a semantic repair.

Authored new-contract fake responses separately exercise cost-as-action rejection even
with plausible committed metadata, full coverage/gaps, related/uncertain accounts,
source separation, admissible task preservation, timing, corrections, persistence and
tamper rejection. Code review is independent of implementation, but these tests and
agent-authored fixtures do not establish fresh model quality or held-out reliability.
The recorded source revision identifies exact tests; provenance also hashes V11 tests.

## Proposed evaluation — a separate approval

[pairs.json](pairs.json) retains all 22 original V10 pairs and adds 18 predeclared
synthetic cases. [expected.json](expected.json) and [rubric.md](rubric.md) precede any
V11 generated output. All previously evaluated cases are marked familiar. New additions
are development/evaluation material, not independent held-out evidence.

For one repetition of all 40 cases in both arms:

| Arm | Cases | Maximum requests |
| --- | --- | --- |
| Frozen baseline | 40 | 160 |
| V11 proposed | 18 with notes, 22 without | 116 |
| Total | 80 case/arm slots | 276 |

This is a ceiling calculation, **not approval**. Settings keep repetitions/budget null.
V10 took 48m44s for 65 requests; plan an extended local run and report actual latency,
not just request count. Do not reuse its 97 unused requests.

Agree the exact scope/repetitions, per-arm and total ceilings, latency expectations and
stopping rules before launching the runner. Verify hashes/settings and model identity
before each arm. Stop on an integrity/settings change or budget exhaustion, preserve
every attempt/failure and account for missing slots. No tuning, selective reruns or
dropping failed cases during scoring. Score semantic commitment admission, splitting,
relations/uncertainty, source attribution, qualifiers and completeness, then replay every
selected wrapper-10 result. A blocked output is a quality failure even when fail-closed
storage worked. One run cannot establish reliability or isolate prompt/schema effects.

The live entry point, after explicit approval, is scripts/evaluate-enhancement.py with
`--freeze v11`; runner.py preserves its exact source at freeze and uses the scripts
entry point's repository-relative layout. Do not run it from an old evaluation approval.
Only passing quality advances current synthetic Obsidian acceptance. Built and merging
still require their own completed gates and the owner's `shipit`.
