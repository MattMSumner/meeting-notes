# Offline passage-review prototype

This isolated work-section prototype implements the accepted focused-passage/manual-task
workflow. Review the complete selected turns, decide what is current, then write or promote
tasks. It produces no task claims, owners, deadlines, semantic titles or currentness
decisions. Production remains V11; M10 remains unbuilt. Existing actions, captured replies,
failures and grades are unchanged. No inference, live metadata or transport runs here.

```python
from prototypes.reviewable_draft import work_review

prepared = work_review.prepare(saved_snapshot, "host-generation")
payload = prepared.payload()  # fresh messages/schema data; no sender or model settings
result = work_review.decode(prepared, '{"groups":[["T1","T2"]]}')
markdown = work_review.render_result(result)
```

`prepare`, `payload`, `decode` and `render_result` are pure. Importing the new modules
does not read fixture inputs, connect to services or write files. The complete immutable
`Snapshot` contains title, start, attendees, author, transcript and writing. The model-neutral
payload includes minimal meeting context and every complete speech turn with its ID, text,
recorded speaker and time; writing stays outside it. The saved snapshot retains writing
unchanged. Payload copies are fresh, and the prepared canonical payload is rechecked against
its snapshot and contract. There are no model, thinking, streaming or options defaults,
HTTP/stream statuses, callbacks, senders, collector or persistence layer.

The wire contract is exactly `{"groups":[["T1","T2"]]}`. `groups: []` is valid. Inner
groups must be nonempty arrays of speech references in this snapshot. Extra fields,
duplicate JSON keys, nonfinite constants, malformed JSON/shapes, wrong types and
unknown/written references reject the whole selection. No rejected/truncated content is
silently converted to accepted partial output. Strict parsing reuses only the existing
pure JSON helpers; rendering reuses only literal/metadata escaping helpers.

Every supplied reference is validated before normalization. Then duplicate references
within a group collapse, references follow original snapshot order (T2 before T10), exact
duplicate normalized groups collapse, and groups sort by their first source. Groups
sharing the same first source retain their supplied relative order. Nonidentical overlapping
groups remain separate, so a turn can appear more than once. This preserves distinct
grouping without claiming one task, owner or semantic relationship. Repetition can still
be a review-burden defect; deduplication does not infer which overlap is useful.

`Prepared`, `Group` and `Result` are distinct frozen records. Their deterministic bindings
cover the complete snapshot identity, host generation and their respective payload,
references or result state/groups. Nested groups carry both originating identities.
Construction, decoding and rendering revalidate them, including after `dataclasses.replace`
or object-level mutation. Copying a group into another snapshot or generation fails, even
with coincident turn IDs. Changed writing, metadata or transcript cannot silently reinterpret
an earlier result. These checks detect inconsistent records; they are not signatures or an
adversarial security boundary. Fully reconstructing a new consistent record is host work.

Ordinary structurally valid content always decodes to a `draft` result. Two explicit
host-owned routes model selection failure without giving the model state/notice fields:

- `host_incomplete(prepared, valid_content)` retains independent, completely valid groups
  and displays a prominent incomplete-selection notice. It uses the same strict validation
  as `decode`; it cannot salvage malformed, truncated or unknown-reference content.
- `host_unavailable(prepared)` accepts no groups and displays a prominent unavailable
  notice. Both routes retain the complete saved snapshot and original writing. The host
  must decide when either route is warranted; this layer implements no transport status.

An empty ordinary selection says no passages were selected, not that no work exists.
The selected view copies each whole turn separately with recorded speaker/time labels
and group boundaries. It preserves literal whitespace, line breaks and conditions, handles
embedded fences and escapes inline metadata. Original writing has its own author-attributed
section. No full transcript is dumped into the normal selected view. Implementation IDs
are not added as product prose; arbitrary identifiers in source text remain untouched.

The prompt's relevance/context/coverage criteria are prospective instructions, not code
guarantees. Unit counterexamples mechanically accept a group missing its withdrawal/timing
and an irrelevant fact-only group. Those remain quality defects. No semantic classifier
or quality grade is supplied. Missing work, misleading groups, excessive selection and
actual review effort need separate empirical evaluation. A full-source annex or warning
cannot rescue omitted selected work.

## Authored previews

`work_review_examples.load_examples()` explicitly reads the seven existing authored mappings
from `work-review-proposal/examples.json`, the forty-input synthetic fixture and the separate
Chief-authored longer input. It verifies pinned input/mapping/annex/original-preview hashes,
all seven complete snapshot identities, text hashes and selected-source hashes. For the
longer input it also checks every redundant saved source and field. Six inputs are familiar;
the seventh is Chief-authored, not held out. No old model reply is adapted.

`preview(result)` is pure. `failure_examples(results)` purely authors two additional host
failure demonstrations: the longer input retains only its independent T11 group in an
incomplete result, and the additional input has unavailable selection with writing retained.
These are not passing coverage examples or repaired failed replies.

```sh
UV_PROJECT_ENVIRONMENT=/Users/matthewsumner/development/meeting-notes/.venv \
UV_CACHE_DIR=/private/tmp/work-review-prototype-uv-cache PYTHONDONTWRITEBYTECODE=1 \
uv run --no-sync python -m prototypes.reviewable_draft.work_review_examples \
  --case authored_longer_context

UV_PROJECT_ENVIRONMENT=/Users/matthewsumner/development/meeting-notes/.venv \
UV_CACHE_DIR=/private/tmp/work-review-prototype-uv-cache PYTHONDONTWRITEBYTECODE=1 \
uv run --no-sync python -m prototypes.reviewable_draft.work_review_examples \
  --output-dir /private/tmp/new-work-review-previews
```

`write_previews(output)` validates/renders before exclusively creating a new directory
under an existing ordinary parent. It refuses existing files/directories, edits, symlinks,
symlink parents and parent traversal. It never overwrites or resumes; an interrupted export
must be retained and a fresh destination chosen. It performs no vault writes. This is a
local authored exporter, not a hardened concurrent filesystem transaction.

The checked-in [preview index](work-review-previews/index.md) and its nine selected views,
complete synthetic source annex, result JSON and manifest reproduce byte for byte. Every
artifact is explicitly authored, not model-generated or model-quality/saved-effort evidence.
The longer normal preview manually selects four of sixteen turns in two groups. The JSON
retains complete snapshots, generation/result/group bindings; the manifest records input,
mapping and output hashes. The manifest inventories every other output; it does not hash
itself. This is authored preview provenance, not production persistence or a runtime freeze.

Model evaluation/budget/freeze, full-draft summary/decisions, full40 regression, production
integration/edit protection and current Obsidian usefulness remain separate gates.
