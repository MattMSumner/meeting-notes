# Assessment protocol

The owner approved one run of the frozen forty pairs in each arm, with request caps
160 baseline and 116 proposed. This file describes assessment logistics; the frozen
[rubric](../rubric.md) and [expectations](../expected.json) remain authoritative.
No prompt, fixture, expectation, schema, runtime or model setting changes are allowed.

After both arms finish, `prepare-blind.py` creates eighty shuffled opaque labels with
the key stored separately. Assessors read their assigned labels, the rubric and source
material before seeing the key. Notes and output structure can reveal the arm. Separate
agent assessment and opaque labels do not establish fully blinded measurement or
independent held-out reliability. All forty fixtures are development/evaluation material.

Each assessor reads every assigned packet, including all comparison/summary replies,
errors, corrections, selected indices and code findings. They judge source meaning and
the final publication, rather than treating IDs, quotes or compilation as semantic proof.
They retain evidence of corrected intermediate errors separately from final defects.
Unclear admission remains visible non-executable review; a factual statement must not
become a checkbox merely because it has plausible commitment metadata.

Return one entry per opaque label, with this structure:

```json
{
  "id": "R001",
  "complete": true,
  "scores": {
    "commitments": 2,
    "sources": 2,
    "coverage": 2,
    "comparison": 2,
    "quantities": 2,
    "timing_owners": 2,
    "usefulness_completion": 2
  },
  "critical_failures": [],
  "observations": ["Exact source quote and corresponding output behavior."],
  "intermediate_findings": ["Corrected attempt defects, if any."]
}
```

Scores use the seven frozen dimensions, in their declared order: zero wrong/missing,
one partial, two correct. A critical failure is an object with `kind`, `source_quote`,
`output_quote` (or null when absent) and `reason`. Name concrete invented/lost work,
wrong source meaning, missed/invented conflict, uncertainty, lost qualifier or incomplete
publication. Do not infer that a blocked attempt published a hallucination.

A slot without a published summary is incomplete and scores zero in all dimensions;
record its failure stage and lost commitments separately. This convention describes
unavailable output, even when fail-closed storage correctly protected a prior result.
Every agreed slot must publish a usable result to pass the completion gate.

Assess outputs with no supplied notes against their transcript alone. Written coverage
and comparison are not applicable and receive two unless the output invents written
material. Do not penalize a transcript-only output for not using notes it never received.
The expectation string also describes V11-specific review representations; a different
faithful transcript-only representation can receive full credit. Normalize a relative
date only when the meeting date and complete wording unambiguously support it.

For outputs supplied with notes, inspect claim splitting, exact anchors and gaps,
related-distinct versus consistent/conflicting/uncertain relations, all dimensions and
source separation. Retaining a quotation does not excuse a wrong relation or lost task.
Check all task/retraction/acceptance and independent agreement context, including
non-executable partial-cancellation review. Review that silently loses remaining work
does not pass. Conservative review can preserve content while still reducing usefulness.

Scores lock before joining the arm key. Preserve the original assessor responses and
their hashes. The Chief checks completeness and factual support, records any corrections
with reasons, then joins labels and reports both arms. A critical proposed failure or an
incomplete proposed output fails quality regardless of average score or baseline result.
Only passing quality advances current manual Obsidian acceptance. No selective reruns,
extra inference, Built note or merge follows from assessment.
