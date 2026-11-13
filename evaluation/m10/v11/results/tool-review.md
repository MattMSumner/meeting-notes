# Evaluation reporting tools

The owner approved all forty frozen synthetic pairs once per arm: caps 160 baseline,
116 proposed, 276 total. Approval and actual execution metadata live in `run.json`;
the frozen settings, prompts, runtime, cases and expectations remain unchanged.

Separate Codex implementation and read-only review agents worked in isolated Herdr
worktrees. The Chief integrated the accepted verifier and owns final verification and
assessment. Review covered the reporting tools, not live model quality.

Independent review found and resolved these issues before scoring:

- Failed/stale verifier reports could permit a quality pass. Analysis now checks evidence
  integrity, completion, exact captured input hashes and preparation provenance.
- Opaque labels did not establish an exact slot bijection, and keys were not locked with
  the packets. Preparation/locking hashes and packet reconstruction bind every label to
  its source, raw attempts and selected output, with all eighty slots required.
- Baseline parse failures and selected attempts were absent from diagnostics. Replay
  observers delegate to the unchanged frozen parser/figure checks, record object identity,
  and restore functions in `finally`. Corrected/fallback success remains complete.
- Baseline packets lost truncation/failure metadata. Packets now retain ordered parsing,
  transport, response, warning and selection diagnostics alongside raw response metadata.
- Extra scorer fields could overwrite the verified arm/case/repetition during joining.
  Scores now require exact protocol fields and joined identity comes exclusively from
  the verified key.

Final reviewed tools: commit `795c38db2aafd125ab6ffe91836e59cf8156d423`.
The verifier is byte-for-byte identical to worker commit
`54bb1c3c3d031ac563037f4883b844a140471f16`. The final independent verdict was **PASS**,
with 23 focused checks. A synthetic eighty-slot in-memory transport capture replayed
exactly: 41 complete, 39 blocked, verified evidence integrity and failed completion.
These are authored engineering probes, not fresh model outcomes or held-out evidence.

The Chief also passed twelve logical helper probes, formatting, lint, strict pyright and
978 offline tests; six model/hardware integration tests stayed excluded. All 396
historical and 67 V11 manifest entries, plus seventeen prior wrapper-9 replays, verified.
No additional inference was used for tool implementation or review. Final live-run
verification and semantic assessment are recorded separately in this results directory.
