# M10 V4 — direct source references

This candidate replaces model-generated claim IDs with supported prose and direct source
references. Tasks contain only a commitment ID, optional timing quote, and timing-context
IDs. Code copies task wording, derives conservative owners, and assembles due values or
inline review evidence. Model inference has not run for V4.

The model still identifies commitments, links timing, detects conflicts, and supplies prose.
Reference integrity is not semantic correctness. In particular, a model can select a
correction instead of its original commitment, miss a timing relationship, or classify a
tentative statement as an action. These remain evaluation failures even if compilation passes.

## Frozen comparison

The 13 input pairs and baseline at `199dd62` are unchanged from V3. The six scoring dimensions
remain unchanged. A grouped checkbox is acceptable only if all spoken tasks are visible.
Review is partial timing credit only when the relevant original and later statements are
present and no obsolete deadline is presented as settled. A quoted suggestion must not be
counted as an agreed action. Missing tasks and unsupported prose still fail acceptance.

Settings remain qwen3:30b, temperature zero, thinking enabled, context 32768. Proposed calls
remain limited to two per case; timing review alone does not request correction. Choose a
new budget before invoking `scripts/evaluate-enhancement.py --freeze v4`. No unused V3
budget is carried forward. Preserve this freeze after inference starts.

`schema.json` is the model contract; `published-schema.json` describes compiled summaries.
The freeze includes the legacy compiler needed to read existing version-2 generations.
New generations use version 3 and grounding-v2; old validation rules remain unchanged.
The archived runners record provenance; invoke scripts from `scripts/` for correct paths.

## Offline replay

[Replay findings](replay/README.md) describe an inference-free adapter over all 25 saved V3
attempts. This tests compilation and cannot predict how the model will respond to V4.
V1–V3 source freezes and results remain unchanged. M10 is not Built; new quality evaluation
and manual acceptance of the review workflow remain required.
