# Frozen M10 comparison — not run

Implementation is not quality acceptance. No model output or score is claimed here.
Decide the inference budget and repetition count separately before running anything.
Do not tune prompts, compare models, or use real meetings in this evaluation.

`pairs.json` contains five synthetic pairs: empty notes, sparse notes, additional written
context, conflicting facts and ambiguous dates. Every pair uses the same transcript and
meeting metadata in both arms. The baseline receives only the transcript; the proposed
arm also receives the handwritten text. Criteria are human-written reference facts, not
fabricated model outputs. There are no baseline model outputs yet.

`baseline/` preserves the relevant source and prompt exactly from commit `199dd62`
(full revision in `settings.json`), before the enhancement change. It does not use the
rejected quoted-figures experiment. `proposed/` freezes this implementation's model,
prompt, schema and numeric checks. Each arm includes `schema.json`. `sha256.json` locks
all comparison inputs and implementations. No live handwritten files are involved.
Both use qwen3:30b, temperature zero, thinking enabled, context 32768, and the existing
bounded retry structure (one format correction per attempt, one number correction).

## Running later

After agreeing on repetitions and a maximum request count, run each arm separately with
`scripts/evaluate-enhancement.py`. It requires `--arm baseline|proposed`, `--repetitions N`,
`--max-requests B`, `--output /absolute/path/results.jsonl`, and `--run`. The output path
must not already exist. Choose budgets to cover the same repetitions in both arms; the
maximum is four requests per case per repetition. Every correction counts against the
budget. A run stopped by the budget is incomplete, not a quality failure or pass. Record
the installed Ollama version and exact local model digest with the output before scoring.
Do not invoke the runner during implementation verification.

The runner imports the frozen source, verifies hashes, contacts only localhost, and writes
results as each case finishes. Keep outputs outside the repository until reviewed for
publication. A valid first result may survive an exhausted correction budget, matching
production fallback; review request counts before declaring a comparison complete.

## Manual scoring rubric

Blind the arm labels and score each case/repetition independently. Use 0 (incorrect or
missing), 1 (partly correct), 2 (correct) for each dimension. Record exact evidence spans
and errors, not just totals. Score baseline for transcript-supported behavior; do not
penalize it for lacking information never supplied to it.

| Dimension | What earns 2 | Critical failure |
|---|---|---|
| Commitment completeness | Every important spoken commitment and agreed decision retained | Notes omissions erase a commitment |
| Source attribution | Spoken core sections; written-only context/tasks visibly separated | Written-only task promoted into a spoken agreement |
| Conflicts | Both accounts explicitly identified and unresolved | Chooses a disputed fact as settled |
| Numbers | Correct amount, unit, source and meaning | Invented calculation, wrong attribution or false agreement |
| Dates and owners | Relative/conditional wording preserved; only supported owners | Invented precise deadline or owner |
| Useful emphasis | Concise useful priorities without losing important spoken content | Notes overwhelm or distort the discussion |

Numeric presence warnings are supporting evidence only: they do not establish correct
meaning, attribution, agreement, or resolve conflicts. Inspect owners, units and claims
even when there is no warning. Retained warnings are not themselves evidence of success.

Acceptance requires all five pairs completed for the agreed repetitions, no critical
failures, no regression in spoken commitment completeness versus baseline, and a reviewer
judgment that notes improve useful emphasis/context when present. Report scores per case
and repetition, variability and any warning/correction failures. Do not mark M10 built
until the evaluation and the manual workflow below pass. Revisions require a new explicitly
versioned freeze; never silently replace a scored arm.

## Manual Obsidian acceptance (pending)

1. Record a synthetic meeting through the start shortcut. Verify a new handwritten tab,
   correct summary/transcript links, and the original writing's byte hash.
2. Stop. Verify transcription only and “ready to enhance”; inspect no-speech behavior too.
3. Cancel the enhancement chooser: verify no job or result. Select the completed meeting,
   verify enhancement notification and a new summary tab, with correct backlinks.
4. Verify spoken commitments, written-only tasks, unresolved conflicts and relative dates.
   Verify original writing bytes are unchanged.
5. Edit the generated summary and enhance again. Verify the new result is saved internally,
   the edit remains, and no old summary is opened as a new result.
6. Change/move original writing after successful generation and render. Verify saved
   evidence remains authoritative. Re-enhancement should require restoring the associated
   path and then take a fresh snapshot. Verify logging and explicit crash retry messaging.
