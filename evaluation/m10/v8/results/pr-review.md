# Independent maximum-effort PR review

Reviewed commit: `2e0455996c80aae196d7c5ef2f25082d15fc89bf` (PR #16).
A fresh subagent reviewed the full diff independently while the parent ran V8 evaluation.
It did not inspect V8 results. No model calls, recordings, private meeting inspection,
file edits or GitHub posts were performed by the reviewer.

## Findings

1. **P1 — Corrupt sessions cannot be claimed for recovery.** `cli.py:251` compares a fresh
   session read with the orphan snapshot. `session.py:82` returns a new `datetime.now()`
   in its fallback Session each time malformed JSON is read, so the equality check fails.
   Synthetic reproduction: `session.json` contains `{"pid":`; `notes stop` returns 0,
   calls stop_capture zero times and leaves the session present. A subsequent start launches
   another recording. A malformed session needs stable identity for recovery claims.

2. **P1 — Corrupt meeting metadata prevents helper shutdown.** `cli.py:258` reads the title
   before stopping capture. With a valid orphan session and `meeting.json` containing `{`,
   stop raises JSONDecodeError, makes no shutdown attempt and restores the orphan session.
   Stop capture independently of metadata needed for notifications; use a fallback ID label.
   Both recovery defects are regressions against main.

3. **P2 — Partial timing quotes lose qualifiers.** `compiler.py:145` expands a limited set
   of preceding date modifiers. For `I will send the draft after Friday.` with timing quote
   `Friday`, validation emits task `I will send the draft after`, due `Friday`, and no review
   or warnings. `not before Friday` and `at least one week after Friday` similarly become
   unqualified Friday deadlines. Preserve the full qualifier or leave timing unassigned.
   This is deterministic compiler behavior given a partial quote allowed by the schema.

## Verification and limits

All three findings were reproduced separately with synthetic directories/drafts. The reviewer
ran 180 targeted offline tests successfully; those existing tests do not cover these cases.
The selected suite excluded the test that invokes the real default calendar adapter and the
real-ps locale test. Real hardware, Shortcuts/Obsidian interaction and live transport were not
verified by this review. The parent evaluation assesses live model behavior separately.

These findings remain unfixed in this frozen evaluation. No candidate changes or retuning were
made during the run. They block merging regardless of the synthetic model-quality score.
