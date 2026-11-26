# First reviewable-draft diagnostic — 2026-11-13

**Six captures completed; semantic defects remain.** Four cases meet their declared
criteria, one has a critical invented-work defect and one fails its surviving-work
criterion without changing the source facts. The approved format remains useful as a
design reference; this candidate is not ready for production integration or M10 Built.

The owner approved at most six local requests and fifteen minutes. The single fixed-order
run used **six requests in 312.629 seconds (5m13s)**, with no retries, corrections, baseline,
transport/format failures, unsent slots, unavailable sections or elapsed overrun. All six
requests are used; no further inference followed. Capture preceded semantic assessment,
and all captured replies are retained.

## Source-based assessment

| Case | Result | Evidence and useful limits |
| --- | --- | --- |
| [additional](01-additional/draft.md) | Meets criteria, with partial findings | Both spoken owners and timing survive; writing stays separate. Sending appears in Summary/Decisions but is missing from Actions. Commitments are repeated under Decisions. |
| [unit equivalence](02-unit_equivalence/draft.md) | Meets criteria, with partial findings | Both literal prices are available without a conflict, conversion or equivalence claim. Inline source IDs, repetition and generic notices increase review burden. |
| [availability answer](03-accepted_status_answer/draft.md) | **Critical defect** | An absence confirmation becomes an invented schedule-adjustment decision and meeting-rescheduling task. |
| [cancellation with new task](04-cancellation_with_new_task/draft.md) | Meets criteria, with partial findings | Cancelled review is not current; invoice sending survives without an invented deadline. Inline IDs and repetition remain. |
| [partial cancellation](05-partial_coordination_retracted/draft.md) | **Noncritical criterion failure** | The original undertaking and withdrawal remain together, but surviving invoice work is not identified as work or focused review. Actions and review both say no suggestions. |
| [qualified timing](06-qualified_external_timing/draft.md) | Meets criteria, with partial findings | The complete not-before/next-Friday/finance condition remains. Suggestions use “on or after next Friday, unless finance objects.” Redundancy and a stray draft notice remain. |

The critical availability source contains only “Will you be away Friday?” and “Yes.”
The model invents “Reschedule Friday meeting to alternative date” and a decision to
adjust the schedule. Neither a Friday meeting nor rescheduling work was stated. A draft label
and valid references do not make these source-backed suggestions.

The partial-cancellation result faithfully repeats both statements, including invoice
sending. Its defect is weaker useful retention: it leaves the reader to infer remaining
work while Actions and Passages to review report no suggestions. This is not a complete
factual omission or invention, and it is reported separately from the critical case.

An independent read-only Codex reviewer assessed every captured output against the
[frozen declaration](../EXPERIMENT.md). The Chief independently checked original sources
and agreed with the findings. See [assessment.json](assessment.json). This was not blinded;
the reviewer had prepared criteria and reviewed the driver. These six familiar development
cases and one repetition establish no held-out performance, reliability, measured editing
benefit, current Obsidian acceptance or full forty-case regression.

## Engineering evidence

- Candidate source: `2934d1004fb592d5ff0708fa2068532c7d51b543`.
- Freeze committed and pushed before inference: `1a3acebc8192647aa114ec16728264cba414ab93`.
- Manifest SHA256: `8c1b2ee279047f3c751311c73e0c9ff4680b0e5cc0afbd7fc4b147d283680168`.
- All eighteen frozen entries, all nineteen committed freeze files including the manifest,
  all forty original inputs and all 486 historical/sealed result entries remain unchanged.
- Exactly six recorded POSTs and 24 metadata GETs. Every POST has HTTP 200, `done=true`
  and `done_reason=stop`; all before/after identity checks match Ollama 0.40.9 / qwen3:30b,
  digest `ad815644918f0eaab341c12b67837cc6dd4562342cdaf118f83d5d554cb37226`.
- Temperature zero, thinking enabled, context 32768; one response per case. No tuning,
  selective rerun, additional semantic classifier or automatic comparison stage.
- Saved requests match frozen bytes. All six saved draft JSON/Markdown artifacts replay
  exactly from their saved snapshots, host generation identity and raw response content.
- [final.json](final.json), [launch.json](launch.json), per-slot raw response bodies,
  before/after metadata and [verification.json](verification.json) preserve accounting.

| Case | Slot elapsed |
| --- | ---: |
| additional | 72.786 s |
| unit_equivalence | 34.953 s |
| accepted_status_answer | 35.228 s |
| cancellation_with_new_task | 25.546 s |
| partial_coordination_retracted | 66.639 s |
| qualified_external_timing | 77.361 s |

Driver review passed independently with no findings or formal repairs. Formatting, lint,
strict types and 1109 offline tests pass; six integration tests excluded, capture unchanged.
An existing clock-sensitive CLI test failed once during worker checks and passed on rerun;
the Chief's combined checks and freeze CI passed. No production/test workaround was made.
These engineering checks and faithful replay are not a semantic quality pass.

## Next bounded work

Keep the approved presentation and target the two observed gaps: free-form decisions/
actions can become advice nobody stated, and surviving work is not consistently surfaced.
Investigate source-extracted task wording or a narrower summary-first draft before adding
more semantic validation machinery. Exact quotation can constrain wording; it still cannot
prove that a passage is a current undertaking or that all work was retained.

This is an offline successor-design recommendation, not a new contract, implementation or
request budget. Any follow-up model experiment needs separately declared scope/criteria/
freeze and approval. V11's failed verdict remains unchanged. Production persistence,
full regression, current synthetic Obsidian usefulness and owner `shipit` still precede
Built/merge. No real-meeting pilot or production integration ran.
