# Manual scoring rubric — frozen before outputs

Score each case/repetition independently with exact evidence spans, using 0 (wrong/missing),
1 (partly correct), 2 (correct). Score baseline only against its transcript; missing handwritten
information is not a baseline error. Shuffle opaque arm labels before scoring where practical,
but report that notes, comparison structure and review fields can reveal the arm. The implementing
agent's assessment is neither independent review nor fully blinded measurement.

| Dimension | Full credit | Critical failure |
|---|---|---|
| Commitment completeness | Every important spoken commitment and independent agreement retained | A spoken commitment/decision is lost or overwritten by notes |
| Source attribution | Written-only facts/requests remain visibly separate | A written request becomes a spoken task or agreement |
| Conflict completeness and false conflicts | Every incompatible account is explicit and unresolved, with only directly relevant accounts; uncertain relations visibly reviewed | Any missed/invented hard conflict, disputed value stated as settled, or uncertainty called agreement |
| Numeric meaning | Correct subject, amount, unit, period, scope and epistemic status | Shared numbers link unrelated subjects; mismatched units/status create false agreement or conflict |
| Dates and owners | Full relative/conditional/uncertain timing and supported owners | Invented owner/deadline or stripped timing qualifier |
| Useful emphasis | Important facts retained, concise source-separated context, useful review | Noise or notes overwhelm spoken content |

Inspect comparison splitting and classification as well as the final summary. Concatenated note
quotes establish text coverage only; multiple independent claims left inside one claim fail
semantic coverage. Judge the nine new cases against expected.json; expected_outcomes lists
allowed outcomes for distinct-period/scope cases, but required multi-claim outcomes for the
additive and multi-claim cases. An additional outcome must have no alleged transcript match.
A mere review warning is not proof of a correct comparison. Consistent classifications cannot
hide explicit uncertainty. Preserve all qualifiers in both accounts. Inspect both stages'
corrections/failures, not just selected outputs. Written requests may stay exact source prose.

Acceptance requires every agreed case/repetition complete, no critical missed/invented conflict,
no commitment completeness regression, correct source separation, and reviewer judgment of
useful context. Report per-case scores, request counts by stage/arm, correction count, timeouts,
failures, review incidence and measured latency. One repetition on familiar cases does not
establish reliability or isolate causal improvements. No tuning, selective reruns or dropping
failed cases. Replay every selected proposed output including warnings using wrapper 9 and
confirm all prior manifests unchanged. Current synthetic Obsidian manual acceptance remains a
separate gate; M10 stays unbuilt until both pass and merging is authorized.
