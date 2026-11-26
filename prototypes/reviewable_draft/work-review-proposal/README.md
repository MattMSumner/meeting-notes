# Reassessing work extraction — 2026-11-25

**Owner accepted the passage-review direction on 2026-11-26.** The owner replied
“This works!” to the examples and the choice between focused passages and suggested
action bullets. Focused passages with manual task resolution are useful enough for
the first work-review section. The separate [offline prototype](../WORK_REVIEW.md)
now implements the reference-group/result/renderer contract, with
[reproducible authored previews](../work-review-previews/index.md). This is
format/workflow acceptance and an engineering prototype, not model-quality evidence
or an inference budget.
No model requests, live metadata calls or production changes are part of this
reassessment. Six examples use existing synthetic sources; a seventh uses a new
Chief-authored synthetic transcript. None is model-generated or held out. Earlier
failures and grades remain unchanged, and M10 remains unbuilt.

## What the evidence says

| Observed failure | Consequence for the next design |
| --- | --- |
| The [action-only baseline](../../../evaluation/m10/reviewable-draft/diagnostic-3/results/report.md) returns no actions or focused review after partial withdrawal. | Exact quotations do not ensure that surviving work is found. Missing work remains a separate quality failure. |
| The [thinking-disabled retention run](../../../evaluation/m10/reviewable-draft/retention-probe-1-analysis/report.md) retains sending but suggests the whole compound statement, including cancelled review. | A literal match proves wording, not currentness. Full cancellation context and a draft label do not remove cancelled work from a suggested action. |
| That run joins a sending passage and a later timing passage into one primary-source quotation. | The full timing qualifier is present, but the response cannot satisfy the quotation contract. Selecting evidence and reproducing a valid span are separate tasks. |
| The replacement reply includes its retraction inline and meets its criterion, with repetition. | Complete passages can preserve meaning, but redundant display adds editing work. |
| The [first diagnostic](../../../evaluation/m10/reviewable-draft/diagnostic-1/results/report.md) turns availability into invented rescheduling. | No new representation may declare availability, prices or unaccepted requests to be current work. Negative controls remain necessary. |

These are observed output failures, not a diagnosis of model internals. The current
[prompt](../actions.py) already explicitly requests surviving work, complete timing
context, exact quotations and exclusion of cancelled work. A more emphatic prompt is
a hypothesis to test, not an established fix. Another literal validator cannot detect
the observed cancelled-work selection: its wording already passes the literal check.

## Accepted work-review direction

Ask the model to select **small groups of complete speech passages about possible
work**, including relevant withdrawal and timing context. Code copies those passages
verbatim from the saved snapshot. The user decides what is current and writes or
promotes tasks while reviewing in Obsidian.

An illustrative reply for the partial-withdrawal source would be:

```json
{"groups": [["T1", "T2"]]}
```

The prototype's model-neutral content has no quotation, task title, owner, deadline, currentness
label, confidence or generated explanation. Each identifier refers to one complete
speech turn in the same frozen snapshot. Writing stays outside this model task and
is copied separately from the complete saved input.

The work section would say **Review these passages**, with speaker/time labels and
separate original quotations shown together. It would not present a current-action
list, checkboxes or an assertion that all work has been found. Empty selection means
no passages selected, not verified absence of work. Source order is preserved; a
group does not rewrite or resolve its source statements. The user-facing examples
hide the wire identifiers and carry no generated semantic title.

The prototype uses a new result type and renderer contract. Do not feed groups into the
existing `actions.Result`, rename its headings, transform failed saved replies into
accepted examples, or reuse its old quality verdicts. These authored groups were
chosen by hand; they are not repaired model results.

## What changes, and what remains unproven

| Responsibility | Proposed allocation | Remaining limitation |
| --- | --- | --- |
| Literal source wording | Code copies each selected complete passage. | The prototype has no model-written quotation field; selection quality remains unproven. |
| Which work is current | User reads the passages and promotes tasks. | This gives up ready suggested-action bullets, as accepted for the first work-review section. It does not repair the old action extractor. |
| Relevant passage selection and grouping | Model selects references and associated context. | It can still omit work, miss a withdrawal/condition, associate unrelated turns or select excessive material. Reference validity cannot detect those mistakes. |
| Attribution and timing | Code retains recorded speaker/time and original wording. | Source speaker labels can be imperfect; the user still interprets self-identification, timing and conditions. No owner inference or deadline normalization is promised. |
| Original writing | Code copies it separately, unchanged. | This work-review experiment does not reconcile written and spoken accounts. |
| Useful review effort | Owner evaluates concrete examples, then actual outputs if warranted. | More source reading and manual task writing may erase the benefit. Authored previews establish no time saving. |

The selection must be focused enough to find the relevant work without rereading the
whole transcript. A selected group that omits the withdrawing or qualifying passage
still fails. A genuine undertaking missing from selected groups still fails useful
retention, even when it remains in the full-transcript annex. Selecting every turn or
adding a generic warning is not a shortcut to a pass. An all-retracted request may be
shown with its withdrawal as historical context; it cannot imply a current task.

Unrelated facts, availability and unaccepted requests must not be promoted into work.
Even under a review-only heading, unrelated selections or misleading groupings count
as relevance/review-burden defects. Record missing work, misleading context and excess
review material separately rather than declaring every literal group safe or useful.

## Concrete authored examples

Read these as proposed **work-section mockups**, not new full-draft outputs:

- [Partial withdrawal](partial-withdrawal.md): whole original and withdrawal adjacent;
  no positive current-action assertion about the cancelled component.
- [Replacement task](replacement.md): complete utterance retains its inline revocation.
- [Qualified timing](qualified-timing.md): sending and the whole later condition remain
  separate source passages; no invented quotation spanning both.
- [Two undertakings](additional.md): both spoken commitments remain visible in separate
  groups; original writing remains separate.
- [Availability](availability.md) and [price fact](price-fact.md): no work group is
  authored; complete source remains available for inspection.
- [Longer context](longer-context.md): four of sixteen speech turns are manually
  selected, retaining partial withdrawal, the complete later timing condition and a
  second undertaking. The other twelve turns illustrate distracting material. These
  authored counts establish no model retrieval performance or review-time saving.

[examples.json](examples.json) records the manually chosen groups, snapshot identities,
source hashes and preview hashes. [sources.md](sources.md) contains the complete original
synthetic transcripts and writing for inspection. That annex does not satisfy the
focused-retention requirement on its own. The first six use familiar development inputs;
[authored-longer-input.json](authored-longer-input.json) separately records the new
longer input and its honest authorship. Neither category is independently held out or
evidence of a quality improvement. The longer example tests whether the presentation
could make two work items easy to find without requiring a full-transcript read; its
selection was still made by hand.

The proposed section would replace only the work-extraction experiment. It does not
produce or qualify summaries, decisions, key points or a complete meeting note. The
approved full-draft presentation, protected writing and production safeguards remain
requirements; generated summaries must also avoid reintroducing cancelled work or
invented commitments. Full forty-case regression and current Obsidian usefulness
acceptance remain ahead of M10 Built and owner `shipit`.

## Alternatives and decision

| Direction | Benefit | Cost or reason to defer |
| --- | --- | --- |
| Keep current-action span extraction; test one focused prompt/representation revision. | Preserves concise suggested-action bullets. | Currentness and useful retention remain hard selection tasks; the existing prompt already states the rules. Needs new evidence on fresh cases and controls, not selective reruns until familiar failures pass. |
| Select complete work-review groups, as illustrated here. | Removes model-written span reproduction and avoids an unchecked current-action assertion. | Transfers resolution and task writing to the user. Missing/misleading groups remain possible; usefulness needs owner judgment. |
| Add semantic judges, more validation rules or another model comparison now. | Might eventually improve a particular capability. | Adds unproven complexity before deciding the output contract. No current evidence establishes this as the next useful step. |

**The owner chose focused source passages for the first work-review section.** The
user resolves currentness and writes/promotes tasks. Concise generated action bullets
are not required for this section's first version. Missing work, misleading context and
excessive review burden remain defects; the old action-only failures are unchanged.

The isolated offline prototype supplies normal/empty/incomplete/unavailable examples
and source-binding checks. A subsequent model experiment must fix prospective criteria for cancellations,
qualified timing, multiple independent work items, full withdrawal and negative controls;
reserve independently authored fresh cases/repetitions where practical. Correct syntax
alone cannot pass it. Any request/time budget, stopping rule, exact implementation and
freeze need separate agreement and review. No new inference budget is proposed here,
and the unused fourth slot from the last experiment remains closed.
