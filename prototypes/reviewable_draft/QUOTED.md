# Quoted actions and decisions — offline successor

The owner said “Great, get it done!” after the first diagnostic identified invented work
and poor surviving-work extraction. This task implements the focused offline successor,
keeps the approved presentation and prepares a reviewable diagnostic. It grants no new
inference budget, production integration or Built/merge. The old six requests are used;
the failed V11 and first-diagnostic results remain unchanged.

## Small contract

Use new `extraction.py`; leave the first generator, driver, model and renderer unchanged.
Reuse the immutable Snapshot/Draft/Section/Item model and pure renderer. One request still
returns summary, decisions, actions and review. Summary/review keep their existing shape:
`state`, `items` containing `text`/`sources`, `notice`, `review_sources`.

Actions/decisions instead contain exactly `state`, `items`, `review_sources`. They have
no free-form text, owner, deadline or notice field. Each item contains exactly:

```json
{"source": "T1", "quote": "send the invoice", "context_sources": ["T2"]}
```

`source` and context sources must be known transcript turns. The nonblank quote must be
one unique, literal, contiguous occurrence in the selected turn; reject absent/repeated
matches, normalization, composed spans and writing-only evidence. Context references are
unique and exclude the primary source. Code copies selected wording and each complete
context turn into the displayed suggestion, with source attribution and shared original
excerpts. The model cannot write new action/decision wording or an invented owner/date
through these fields. Original writing remains separate and unchanged.

On partial cancellation, select the literal surviving work as the focus and include the
withdrawal as full context. Later timing context includes the entire source turn, so
not-before/next/unless conditions cannot be shortened inside a selected context turn.
The model still has to select the correct work and relevant context; no code claim of
semantic admissibility, complete qualifier coverage or complete extraction is made.

All four sections still bind to one complete snapshot and host generation identity.
The model chooses section states; code supplies notices for quoted sections. Summary/
review prose remains generated and needs source-based quality assessment. Quotation can
still select a question, negated/cancelled work, a partial qualifier or an irrelevant
passage. An availability answer still must produce no action in the quality test.

## Failed selections and usable work

Return an immutable decoded result with its Draft and structured extraction issues.
An invalid literal selection on known spoken evidence is retained as focused review,
with no rejected quote/claim presented as an accepted item. Keep all independently valid
quoted items, including valid items in the same section, and all usable other sections.
Use needs_review plus a specific code-supplied incomplete-extraction notice when some
items survive; use unavailable/no items when none survive. Known selected/context turns
provide focused evidence; never substitute a generic transcript dump.

Missing/unknown source references without recoverable focused evidence, wrong structural
fields, incomplete input snapshots or invalid summary/review structure fail the response.
Do not silently convert first-contract responses or invent focus passages. The pure
result renderer prominently marks partial extraction incomplete even when its valid
items are retained. It must preserve Markdown/HTML/fence escaping and original context.
Raw responses and issues remain available to the diagnostic; no corrections or retries.

## Offline proof and limits

Test rejection of the invented rescheduling wording, incorrect source kind, ambiguous
literal matches, unsafe markup, identity mixing and malformed fields. Test surviving
invoice wording with full withdrawal context and full later timing context. Verify
partial failures retain independent valid items, omit rejected prose and expose focused
evidence/status. Include an explicit valid-quote/wrong-admissibility counterexample so
passing mechanical tests cannot be mistaken for model quality.

Authored selectors and previews are engineering examples, not fresh model replies.
Report the six unchanged first-contract replies as unmappable under this different wire
contract, separately from authored new-contract tests; incompatibility is not a repair.
Preserve all forty original inputs and expectations, 486 historical entries, eighteen
first-diagnostic freeze entries and 157 sealed result entries.

## Proposed diagnostic, execution pending

Prepare a separately reviewed/frozen `quoted_diagnostic.py` profile. Keep the existing
single-use, raw-capture, request-hash, identity and child-timeout controls. A selected-quote
validation failure retains any partial draft for inspection and stops further requests;
do not call that a successful complete selection. Model-reported unavailable analysis is
honest incompleteness, not quality acceptance. No production CLI/store/pipeline changes.

Proposed scope: the same six cases, fixed order, one request each, at most six requests
and fifteen minutes elapsed; unchanged qwen3:30b settings, no baseline, corrections,
retries, warm-up inference or selective reruns. Freeze source, this declaration, original
inputs, exact packets/snapshots, settings and verified model identity before requesting
execution approval. Make the run ready before that permission question.

| Case | Prospective criterion, unchanged in meaning |
| --- | --- |
| additional | Both spoken undertakings retain owners/timing and remain discoverable; writing-only venue work/capacity stays separate. |
| unit_equivalence | Literal spoken/written prices remain available without a conflict or computed relationship. |
| accepted_status_answer | An affirmative absence answer creates no action or decision to reschedule; empty writing works. |
| cancellation_with_new_task | Cancelled review is not current; independent invoice sending survives, without an invented deadline. |
| partial_coordination_retracted | Original and withdrawal remain together, with surviving invoice sending identified as work or focused review. |
| qualified_external_timing | Sending retains the complete not-before/next/finance condition, or focused review containing both whole passages without a misleading assigned due. |

Stop on source/input/request/settings/identity drift, elapsed/per-request deadline,
transport/truncation/shape/quote-selection failure, or a critical semantic defect once
detected. Capture may precede source-based semantic assessment; retain every already
captured reply and account for unsent slots. An honestly incomplete artifact is useful
failure handling, not an overall quality pass. Score source meaning, current work,
retention, separation, review focus and burden, not merely valid references/quotes.

These remain familiar development cases, one candidate and one repetition. Any model
run requires fresh explicit execution approval; no old allowance transfers. Full
regression, fresh-case provenance, persistence safeguards, current synthetic Obsidian
usefulness and owner `shipit` still precede M10 Built/merge.
