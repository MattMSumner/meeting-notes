# M10 v3 — evidence-backed candidate, not evaluated

V3 changes the model contract from finished prose to a draft of shared claims and source
references. Code compiles it into the existing Summary layout. The model still must find
commitments, associate claims with appropriate evidence and detect conflicts. Valid
citations do not establish entailment; no quality improvement is claimed before evaluation.

The first five pairs are unchanged regressions from v1/v2. Eight new synthetic cases cover
same-speaker tasks, coordinated tasks, later timing, revised timing, identical numbers for
different topics, nonnumeric conflict, tentative commitment and front-loaded timing.
They are newly frozen regression cases, not a claim of unseen generalization testing.
The baseline remains exactly `199dd62`; qwen3:30b, temperature zero, thinking and 32768
context are unchanged. V1/v2 inputs and scored results are preserved.

## Enforced behavior and limitations

- T/N passage IDs are deterministic within the saved input. Every exact quote must occur
  once in its referenced passage. Metadata cannot serve as spoken evidence.
- Tasks require a full transcript statement, with task wording taken from that statement.
  Names differing from the speaker label need a spoken self-introduction by that speaker.
  Multiple people sharing the Them label remain ambiguous and require quality review.
- Automatic due values require a recognized, complete trailing timing phrase after that
  task in the same statement. Coordination and omitted conditions block publication.
  Separate exchanges and front-loaded timing can be retained as quoted review warnings
  with due null. Timing omitted despite a recognized date also produces a review warning.
  These conservative rules can flag legitimate phrasing: measure false positives and loss
  of useful information, not just invented deadlines. They are not a language parser.
- Known conflict claims, including clones citing overlapping spans, become neutral core
  references. Disputed decisions/context are removed from those sections; the full source
  statements appear in Conflicts. Unrelated commitments remain actions. Large evidence
  spans can over-suppress unrelated material; absent or incorrect conflict links remain
  semantic risks. The shared-numbers case tests unwanted spread of a conflict.
- Numeric presence checks use each claim's cited spans. They remain warnings under the
  existing parser/matching rules, not proof of meaning, units or agreement.
- Format and blocking evidence issues share one correction attempt: at most two model
  requests. A failing draft never replaces the last successful generation. A structurally
  valid result with warnings may survive a malformed or worse correction, with its saved
  warnings visible. This does not certify the result as semantically correct.

## Evaluation procedure

Use `scripts/evaluate-enhancement.py --freeze v3`, with an explicit arm, repetition count,
request cap, exclusive output path and `--run`. Select the inference budget separately.
The runner now records every sent request and response/error; proposed results additionally
carry validator issues and selection history. The archived `runner.py` records provenance;
invoke the script in `scripts/` for correct repository-relative paths.

There are 13 cases. Three repetitions of both arms would produce 78 retained results or
explicit failures. Worst-case caps are 156 baseline requests and 78 proposed requests
(234 total). Budget these separately, not as spare allowance for tuning. Record local
Ollama version and model digest before/between/after arms. No runner has been invoked for v3.

`schema.json` is each arm's model-facing contract; `proposed/published-schema.json` is the
compiled Summary schema. The manifest covers sources, prompts, schemas, cases, settings,
runner and rubric. Verify hashes before inference. Do not edit a freeze after a run starts.

## Acceptance

Apply the unchanged six-dimension rubric in `rubric.md`, plus the following reporting
requirements for the new conservative behavior. Do not loosen the no-critical-failures
or spoken-commitment completeness gates.

Report automatic publication, blocked generation, withheld timing and warning counts by
case/repetition. A refusal is not a correct summary and cannot count as a quality pass.
Legitimate tasks must remain visible. An unassigned but explicitly quoted timing exchange
can earn partial date credit; silently lost timing earns none. Treat genuine corrections
(such as Monday replacing Friday) as evidence: an obsolete deadline is not rescued merely
by citing the original commitment. Judge entailment and agreement even if structural checks
pass. Review omitted and over-suppressed information as well as false claims.

Score the first five cases against the existing baseline comparison and report the eight
new cases separately. No critical invented task/deadline, unresolved-conflict presentation
failure, or regression in spoken commitments is acceptable. Retain the reviewer’s full
judgment of whether notes add useful context. Manual workflow acceptance was reported for
M10 earlier; exercise the new failure/warning behavior before declaring this revision built.
