# V3-to-V4 offline replay

No inference was performed. All 25 V3 proposed attempts were adapted independently:
23 compile, one retains an invalid cross-source conflict reference, and one has an
unmappable nonexistent `null` claim. Seven compiled attempts contain action review evidence.
These are attempt counts, not 13-case acceptance scores or model quality measurements.

The adapter locates original passages monotonically in each exact saved input, then maps
valid unique quotes to overlapping new statement IDs. Old task labels and owner proposals
are discarded because V4 derives those fields. Same-statement timing quotes remain proposals;
cross-statement timing becomes review context. Claim references become direct source IDs.
No original task selection or missing relationship is repaired. Output is exclusively created.

Ordinary dated tasks no longer fail because the old task text repeats the date. Both facts
on the single handwritten conflict line map separately. Coordinated tasks remain grouped;
later and front-loaded timing become visible review evidence. These outcomes demonstrate
reduced representational brittleness, not complete semantic preservation.

**Known semantic failure:** revised_timing attempt 1 selects “Actually, Monday instead.” as
the task. The compiler leaves its due unset and flags review, but cannot reconstruct the
unselected sending commitment. “I will send the draft Friday.” remains an unqualified key
point because the model did not identify it as the action or timing context. This fails the
frozen revised-timing criteria. The earlier attempt also contains a nonexistent `null` claim.
Some old overview/decision content disappears because task prose is now confined to Action
items. Replay cannot establish that all independent spoken decisions remain selected.

Tentative_task attempt 0 retains an invalid notes reference to spoken evidence and stays
blocked. The later attempt retains only the actual checklist commitment. A separate unit
test documents that selecting a tentative source as an action can still compile: reference
checks do not prove agreement, and such an output must fail semantic evaluation.

Reproduce with `uv run python scripts/replay-enhancement.py --output <new-path>`.
The frozen adapter is `../replay.py`; current compiler inputs are included in the V4 manifest.
The historical V3 raw responses remain unchanged. Do not interpret this report as permission
for inference or as successful quality acceptance.
