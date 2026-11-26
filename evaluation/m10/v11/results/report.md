# V11 evaluation — 2026-11-12

**V11 fails quality:** 34 of 40 proposed outputs published, six blocked, and one published
output invented a unit-conversion conflict. Baseline published all forty but had eight
cases with critical semantic failures. Every agreed slot and attempt was retained;
there was no tuning, selective rerun or extra inference. M10 remains unbuilt and the
current manual Obsidian acceptance gate does not advance.

The six incomplete cases and the false conflict are seven proposed cases with critical
failures. Mechanical replay passed; it does not establish correct meaning.

## Scope and execution

The owner replied “Sure, do it” to all forty frozen synthetic pairs once per arm,
with ceilings 160 baseline + 116 proposed = 276 requests. `run.json` records approval,
exact commands, frozen hashes, model identity before/after each arm and measured time.
The frozen settings retained their pre-approval null repetition/budget fields.

| Arm | Recorded slots | Published | Blocked | Requests / cap | Wall time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline | 40 | 40 | 0 | 40 / 160 | 17m05s |
| V11 proposed | 40 | 34 | 6 | 69 / 116 | 81m41s |
| Total | 80 | 74 | 6 | 109 / 276 | 98m46s |

The 167 unused requests provide no allowance for another run. Ollama 0.40.9 and
qwen3:30b digest `ad815644918f0eaab341c12b67837cc6dd4562342cdaf118f83d5d554cb37226`
were stable. Temperature zero, thinking enabled, context 32768 and timeout 600 seconds
were unchanged. The working runner matched its frozen copy; arms ran serially.

| Stage | Requests | Corrections | Blocked attempts | Unmappable replies | Median server seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline summary | 40 | 0 | 0 | 0 | 24.08 |
| V11 comparison | 22 | 4 | 7 | 0 | 79.79 |
| V11 summary | 47 | 10 | 13 | 0 | 73.81 |

There were no transport/response errors, unsent context failures or exhausted budgets.
The largest complete proposed request estimate was 7,179 tokens against 32,768.
All 69 model replies were schema-mappable; blocking came from evidence/contract checks.
Seven summaries selected correction index 1; 27 selected their initial attempt. No
successful summary used a prior-attempt fallback in this run.
Thirteen published proposed outputs contain sixteen action-review items. Five published
outputs retain six selected warnings. These counts describe retained review, not errors
or task correctness by themselves.

Latency uses arm wall time and Ollama `total_duration`. The frozen runner has no client
wall timer per request. Proposed wall time was about 4.78 times baseline for the same
forty slots; different request counts, schemas, prompts and thinking lengths are mixed
in that comparison. One serial run does not isolate any individual cause.

## Incomplete proposed outputs

| Case | Failed stage | Retained final blocking findings |
| --- | --- | --- |
| `shared_numbers` | Comparison | Quantity simultaneously marked unresolved and populated; relation not uncertain despite unresolved extraction. |
| `tentative_confirmed` | Comparison | Extracted status was not literal account evidence. |
| `multi_claim_notes` | Comparison | Unresolved extraction paired with a non-uncertain relation. |
| `accepted_status_answer` | Summary | Noncommitment/timing anchor failures and no supported content. |
| `accepted_request_retracted` | Summary | Same-speaker retraction invalidated the selected commitment. |
| `partial_coordination_retracted` | Summary | Negated undertaking remained selected; full original/retraction review was retained in diagnostics but no summary published. |

These are incomplete outputs, not published hallucinations. Correct fail-closed behavior
can protect a prior generation while failing this completion requirement. Independent
invoice work in `shared_numbers` and `multi_claim_notes`, and remaining sending work in
`partial_coordination_retracted`, never reached a new publication.

## Assessment

Two fresh read-only Codex assessors inspected randomly shuffled opaque packets, forty
each, including original inputs, all raw attempt replies/findings and selected outputs.
The Chief checked quoted sources and findings, then locked all eighty original scores
before opening the arm key. No score or classification changed. `scoring-lock.json`
records the time, hashes and limitations; `assessor-a.json` / `assessor-b.json` retain the
original assessments, `blinded-scores.json` the sealed union and `scores.json` the join.
Terminal hard wrapping required a temporary-file handoff; the original terminal responses
were retained and checked against those files. See the lock's recovery record.

Each dimension uses the frozen 0–2 rubric, totaling at most eighty per arm. Incomplete
outputs score zero in every dimension. Baseline is judged against transcript alone;
written coverage/comparison that it never received is inapplicable and receives two.
These are descriptive scores under different source scopes, not a controlled ranking.

| Dimension | Baseline / 80 | V11 / 80 |
| --- | ---: | ---: |
| Spoken commitments and agreements | 74 | 67 |
| Source attribution | 77 | 67 |
| Claim coverage and anchors | 80 | 68 |
| Comparison and uncertainty | 80 | 65 |
| Quantities and dimensions | 76 | 64 |
| Timing and owners | 71 | 68 |
| Usefulness and completion | 67 | 58 |

The published proposed critical failure is `unit_equivalence`: the transcript says
“Support costs 120 dollars.” and notes say “Support costs 12000 cents.” The selected
comparison calls them conflicting because their units and numerical representations
differ. The final summary consequently places equivalent amounts in Conflicts. Exact
anchors and faithful code assembly preserve that mistaken relation; valid IDs do not
make it correct. No invented executable task was identified in the thirty-four published
proposed outputs, which does not excuse the six blocked outputs or prove general admission.

Additional proposed partial findings include:

- `estimate_approval` uses related-distinct rather than the expected uncertain relation;
  retained “Comparison review required” preserves review and both epistemic roles.
- `proposal_not_commitment` publishes “Alex to check invoice (T1)” despite no acceptance.
  The overview retains the question/nonacceptance and only Sam's real sending commitment
  is executable; the misleading key point receives partial commitment/source credit.
- `ambiguous_dates` and `related_scopes_with_task` conflate absent dimensions with unresolved
  extraction. Full quotations preserve explicit content, but metadata/review is less useful.
- `conflicting` omits the explicit “We have not approved the budget.” statement without
  inventing approval. Conservative timing and partial-cancellation review also add work
  or require reading full warnings instead of clear core items.

Baseline critical cases were `status_conflict`, `same_speaker_tasks`, `multi_claim_notes`,
`approximate_timing`, `qualified_external_timing`, `cancellation_with_new_task`,
`partial_coordination_retracted` and `tentative_confirmed`. They promote tentative
readiness to confirmation, borrow/invent timing, remove approximate/not-before/conditional
qualifiers or leave cancelled review work executable. Baseline completion therefore
does not establish baseline correctness or lower the proposed acceptance bar.

## Integrity and replay

`verification/completion.json` reports **verified evidence integrity**, eighty recorded
slots and failed completion, with exactly six completion findings and no integrity
findings. Every baseline and proposed runtime execution was reproduced from saved
transport, including blocked attempts, corrections and selection. All 34 published
proposed summaries roundtrip exactly as wrapper 10 with original/effective inputs,
full audits and warnings. No replay used inference or reread an original note file.

All 396 V1–V10 and 67 V11 frozen manifest entries remain unchanged; all seventeen prior
V10 wrapper-9 summaries/warnings replay faithfully. Strict unchanged V10 replies remain
43 unmappable under V11 (19 comparison, 24 summary), which is schema incompatibility,
not a semantic repair. Authored fake-response/tool checks are separate from this fresh run.

New reporting tools passed separate Codex review after repairing verification freshness,
slot/key bindings, baseline diagnostics and score identity handling; see `tool-review.md`.
Formatting, lint, strict pyright and 978 offline tests passed; six model/hardware
integration tests were excluded. Capture was unchanged.

## Limits and next gate

The original twenty-two cases are familiar; eighteen additions were authored during
development. None is independently held out. There is one repetition, no reliability
estimate, and no evidence here of performance on real meetings. Opaque labels help
assessment logistics, but notes and output structure can reveal arms; agent assessment
does not establish fully blinded measurement.

No further inference, manual Obsidian acceptance, Built note or merge follows from this
failed run. Preserve this freeze and evidence. A follow-up should first investigate the
retained comparison dimension/uncertainty and summary admission/retraction failures
offline, preserve historical replay, then agree any successor candidate and evaluation
separately. Existing request allowances are not reused; `git shipit` still requires the
owner's explicit instruction.
