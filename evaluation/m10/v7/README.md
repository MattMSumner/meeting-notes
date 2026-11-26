# M10 V7 — conservative timing normalization and omission diagnostic

No inference has run. This freeze changes validation/compilation and retry retention only.
The V6 prompt, model-facing schema, per-case enums, 13 synthetic pairs, rubric, original
`199dd62` baseline and model settings remain unchanged. No prompt tuning or model comparison.

An action's initial timing may cite a different transcript statement. If that statement is
later than the original and the timing quote appears exactly once and matches the existing
timing pattern, code retains its full source text as unverified timing
review. It never assigns a due from that source. Unknown/wrong-kind references, backwards
references, absent/repeated quotes and non-timing quotes still block. No relationship is
inferred from shared prose. A valid reference can still link an unrelated task; the evidence
is labelled association-unverified. Complete conditions stay visible in the full quote.

The new omission diagnostic looks for unselected transcript statements starting with explicit
first-person future wording followed by a small allowlist of task verbs (see `coverage.py`).
For example, “I will review it next week” without an action produces a source-specific blocking
message and uses the existing one-correction budget. Prose or timing references do not substitute
for the original action. Code does not fabricate a task or infer an owner/deadline from absence.
If correction fails, generation fails and the previous successful result remains preserved.

This is deliberately not a general commitment classifier. Questions, quotes, tentative or
conditional language, negation and adjacent same-speaker retractions are excluded. Predictions
outside the task-verb allowlist are excluded. Paraphrases, front-loaded wording, non-English
speech and unlisted verbs can be missed; unusual non-task statements can still be false positives.
Nearby disclaimers may conservatively suppress a diagnostic. No claim of completeness follows
from a clean result. Existing action selection still requires semantic evaluation.

Numeric retries must preserve both explicit update links and normalized external timing links.
New saves use wrapper version 6 / grounding-v5; version 5 retains the V6 compiler and contract.
All 12 published V6 generations still load under their original rules, including the incomplete
additional case. Saved output is not retroactively changed by the new diagnostic.

[Offline replay](replay/README.md) compiles 13 of 15 V6 attempts and flags the missing task.
This is not a quality evaluation or proof that a model will repair the omission. V1–V6 freezes
and results remain unchanged. M10 remains unbuilt, with quality and current manual acceptance
pending. Future inference requires a separately selected repetition count and request budget;
these remain unset. `scripts/evaluate-enhancement.py --freeze v7` selects this candidate.
