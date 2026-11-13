# M10 V6 — preserve facts and separate timing updates

This candidate fixes deterministic information loss found in V5. No model inference has
run. The same 13 synthetic cases, baseline at `199dd62`, rubric, qwen3:30b, temperature zero,
thinking enabled, 32768 context and bounded correction behavior remain frozen.

Code no longer infers timing relationships from shared overview or key-point references.
When an item mixes task/disputed evidence with independent facts, code removes the mixed
model prose and preserves unaffected source statements as attributed quotes. Disputed facts
remain in Conflicts; independent agreements remain in Decisions when selected there.
This preserves evidence without attempting to split the model's prose semantically.

Actions identify `original_commitment_id`; initial timing must cite that statement.
Separate `timing_updates` link an existing original action to later transcript sources.
Backwards links block publication. Updates leave timing unassigned with the original task
and linked evidence visible for review. Self-links are redundant. Code does not prove that a
later statement actually updates the selected task. Valid but unrelated links, omitted updates,
wrong original-task selection and missing commitments still require quality evaluation.

The prompt demonstrates an original Friday task followed by a Monday correction. Model-facing
sources contain ID, source kind, speaker and exact text; character offsets and turn coordinates
remain in the saved audit only. Request-specific enums bind every reference field. Numeric
corrections cannot replace a valid result by dropping its task, conflict or update references.
Complete request size is checked before both initial and correction requests.

New summaries use wrapper version 5 / grounding-v4. Version 4 uses the preserved V5 compiler
and contract, so saved results are not reinterpreted. Earlier validators remain intact.

See [offline replay](replay/README.md). Its results test code behavior using old responses;
they do not measure how the model will use the new contract. All V1–V5 frozen inputs and
results remain unchanged. M10 remains unbuilt, with V6 quality and manual acceptance pending.

`proposed/schema.json` contains the generic contract; `proposed/request-schemas.json` contains
all 13 bound schemas. The manifest hashes source, prompt, schemas, settings, fixtures, rubric,
runner and replay. Use `scripts/evaluate-enhancement.py --freeze v6` only with a separately
agreed repetition count and request budget; both remain unset in settings.
