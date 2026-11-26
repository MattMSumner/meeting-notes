# Offline V6 → V7 replay

All 15 saved V6 replies were parsed without adaptation and replayed through V7 after checking
V6's input and result hashes. No model or network access. Output creation is exclusive.

13 attempts compile; two block. Across 13 cases, 12 have at least one compiled attempt.
This is not live retry selection: both recorded later-timing responses are replayed independently,
even though V7 would accept the first. No new correction response is invented for additional.

- Both later_timing attempts now retain the Sam rollback task and full Friday source under
  unverified review, due null. The first also has an explicit update; the second does not.
  Repeating the relationship in initial timing no longer prevents conservative publication.
- Additional now blocks with “Possible omitted commitment T3: I will review it next week.”
  No task is fabricated. A later model run must test whether bounded correction fixes it.
- Sparse's first draft retains its original wrong-kind notes error; its recorded correction
  compiles. Unknown/wrong-source validation remains active.
- Empty, revised_timing and shared_numbers preserve their V6 outcomes. Conflicting still
  includes unrelated delivery text in the budget conflict: this change does not fix topic
  grouping or claim that valid references prove meaning.

Unit tests cover absent/repeated/non-date/backwards timing quotes, unknown and handwritten
sources, unrelated task timing without due assignment, unchanged drafts, retry retention,
omission detection even when prose mentions the task, successful/failed bounded correction,
and negative coverage examples (negation, conditional, tentative, quoted and non-task speech).
Tests also preserve all published V6 saved wrappers and forbid network access during replay.

```sh
uv run python scripts/replay-v6-enhancement.py --output /tmp/m10-v7-replay.jsonl
```
