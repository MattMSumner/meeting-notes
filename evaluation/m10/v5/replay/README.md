# Offline replay of V4 responses

No inference was performed. Of V4's 23 saved attempts, **11 compile, nine remain blocked,
and three cannot be mapped unambiguously**. Four compiled attempts contain review items.
These are compiler outcomes, not model quality scores. No best attempt is synthesized or
semantic selection repaired, and constraints in a future model request cannot alter an old reply.

The adapter renames commitment to commitment_id without changing its value or any context
reference. A timing quote is mapped to its original commitment when that valid ID contains
it exactly once; otherwise it requires exactly one matching transcript statement. Ambiguous
or nonexact quotes remain unmappable. This provides provenance for the new timing object,
not proof that the statement applies to the selected task. Notes cannot supply a timing source.
The source-ID enum mechanism cannot be evaluated by replay because no request is sent.

Observed targeted repairs:

- The corrected empty case assigns Friday to tagging, keeps rollback due null and removes
  its spurious review. Same-speaker sending and the tentative-case checklist also regain
  their straightforward due values after redundant self-context is ignored.
- The later-timing review retains both the question and the actual Friday answer, with no
  assigned due. The new explicit timing source and source-evidence preservation prevent
  the previously observed loss; no relation is presented as verified.
- Corrected shared_numbers and status_conflict now compile. Code neutralizes their redundant
  handwritten references in core prose while preserving the full conflict accounts and tasks.
  Unit negatives still reject unknown references and unrelated written facts in core sections.

Remaining problems are intentionally visible:

- Both revised_timing attempts still use the literal word Monday as commitment_id and block.
  Other first attempts still contain task prose instead of an ID. The enum-constrained request
  is intended to reduce this in future responses, but no backend behavior has been measured.
- Both ambiguous_dates timing quotes omit a comma and cannot be mapped exactly. The first
  empty attempt has an invalid prose commitment reference and a Friday quote matching two
  statements. The adapter does not normalize punctuation or invent a choice.
- The additional-context result still cross-links two unrelated tasks as timing context;
  both remain review-only. Sparse still omits the monitoring cost. No missing facts are added.
- A model can select a wrong-but-valid source ID or a tentative statement as a commitment.
  Tests expose that semantic boundary rather than treating reference validity as agreement.

Reproduce with `uv run python scripts/replay-v4-enhancement.py --output <new-path>`.
The tool verifies V4 input/result hashes and creates its output exclusively. A test forbids
network connections during replay. The archived adapter is `../replay.py`; invoke the script
under `scripts/` for correct repository-relative paths. Raw V4 responses remain unchanged.
