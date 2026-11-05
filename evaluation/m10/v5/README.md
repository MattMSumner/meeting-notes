# M10 V5 — reference and timing repairs

This candidate addresses four failures from the V4 evaluation without new inference:

- `commitment_id` contains a source ID, and timing is `{source_id, quote}` or null.
  Each request constrains reference fields to available IDs with JSON-schema enums.
  Runtime checks still reject unknown IDs and inappropriate sources. The actual backend's
  output behavior under these schemas has not been evaluated; valid IDs do not prove meaning.
- A commitment citing itself in timing_context does not create review. Other context is
  retained conservatively; an unrelated but valid task reference can still cause review.
- Timing's own source is retained for review when it is outside the commitment. If timing
  cannot be assigned, dated source statements from suppressed action prose are also quoted
  for review, excluding other selected commitments. This fallback never assigns a due value.
- Redundant prose citing a known conflict is neutralized even when it cites the handwritten
  side. Unknown references and unrelated wrong-source references still block publication.

Model identification of commitments, later corrections and conflicts remains necessary.
Choosing the wrong valid commitment ID or omitting a later revision can still produce a
semantic failure. Additional source evidence does not prove its association with a task.
No claim of quality improvement is made before a separately budgeted model evaluation.

## Freeze and acceptance

The 13 synthetic cases, original `199dd62` baseline, six scoring dimensions and model
settings remain unchanged. Keep every important spoken task and decision, separate written
context, preserve conflict uncertainty and all relevant timing. A review without the actual
answer does not earn partial credit. Increased publication alone cannot satisfy acceptance.

`proposed/schema.json` is the generic contract; `proposed/request-schemas.json` freezes the
actual per-case schemas after binding available IDs. The compiler, prompt, schema builder,
settings, inputs, runners and replay are hashed together. Empty notes disable notes_context
and conflicts rather than inventing a sentinel note ID. Source-kind checks remain in code;
generic prose reference enums include both kinds to allow known-conflict neutralization.

Use `scripts/evaluate-enhancement.py --freeze v5` only after agreeing a new budget.
qwen3:30b, temperature zero, thinking enabled, context 32768 and the two-request proposed
limit are unchanged. Complete request size, including expanded enums and correction history,
is checked before every request. No inference or manual acceptance is included in this freeze.

New saves use wrapper version 4 and grounding-v3. Earlier wrappers retain their original
validation, including V4's version-3/grounding-v2 saves. No old output is recompiled under
new semantics. V1–V4 freezes and scored results remain unchanged. M10 remains unbuilt.

See [offline replay](replay/README.md) for targeted behavior checks and unresolved failures.
