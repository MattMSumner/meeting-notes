# Offline V5 → V6 replay

No inference. All 14 saved V5 responses were replayed after verifying the V5 input and result
manifests. The adapter only renames the original task field and moves explicitly supplied
external timing/context references into timing_updates. It preserves selected IDs, quotes,
prose and conflicts. It does not reverse incorrect links, recover omitted tasks or infer
relationships from shared prose. Output creation is exclusive.

11 responses compile and three block, covering 11 of 13 cases. The two sparse-note attempts
still cite handwriting as spoken evidence. The revised-timing response still selects the
correction as its task; its backwards link now blocks instead of publishing a misleading
checkbox. This is a stricter failure, not a recovered commitment.

Targeted changes:

- Empty notes: the independent release-Friday decision survives. The rollback task has no
  assigned deadline and no unrelated release-date review; the tagging task retains Friday.
- Shared numbers: the monitoring cost of 120 survives as an attributed quote. The disputed
  support amounts remain unresolved in Conflicts; neither is promoted to a settled key point.
- Later timing: the explicitly linked Friday answer remains visible in review, with no due.
- Revised timing: T2 pointing backwards to T1 fails. A separate unit test uses the correct
  original T1 and later T2 link and retains the original task with both dates under review.

Other limitations remain: an omitted task cannot be recovered from this replay; source-ID
validity does not establish commitment semantics; undated actions can still get needless
review if the model supplies a non-timing quote. These results are not quality scores.

Reproduce without network or model access:

```sh
uv run python scripts/replay-v5-enhancement.py --output /tmp/m10-v6-replay.jsonl
```

Unit tests forbid network connection, check the targeted outcomes and reject overwriting output.
