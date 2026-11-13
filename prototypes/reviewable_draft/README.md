# Reviewable meeting draft — offline prototype

This is a rendering/design experiment inside M10. Inputs and responses are synthetic;
no model, recording, vault, production CLI, pipeline, store, prompt or saved wrapper is
used. Authored examples demonstrate intended behavior, not model capability, a passing
quality evaluation or owner usefulness acceptance. V11's failed results remain unchanged.

The owner approved the normal and incomplete preview format on 2026-11-13. That is format
feedback; generated quality and actual editing effort remain untested. The next
[six-case diagnostic](EXPERIMENT.md) has a transport-free request builder and
decoder in `generation.py`. The `diagnostic.py` driver freezes exact source, original
inputs, snapshots, requests and model identity into a new directory. Its explicit `run`
entry claims one results directory, verifies the reviewed manifest hash, enforces child
process deadlines and keeps raw responses/errors before decoding. No inference runs on
import or freeze, and no automatic retry/resume exists. A timed-out client cannot guarantee
server-side compute cancellation; elapsed overruns are recorded honestly.

Only offline fake-response checks have run. The owner has approved six local requests /
fifteen minutes for the declared diagnostic; independent review and the exact freeze
precede execution, with no further permission needed. The approval string supplied to
the runner is audit context, not an authentication mechanism. Existing app behavior,
production persistence and protected vault files are unaffected by this diagnostic.

## Try the previews

Start with the [normal draft](previews/additional.md), the
[incomplete comparison with a retained invoice suggestion](previews/multi_claim_notes.md),
or [all ten examples](previews/index.md). Shared source excerpts appear once below the
suggestions; original handwritten text stays separate. Every preview identifies itself
as an authored offline example.

From the repository root:

```sh
uv run python -B -m prototypes.reviewable_draft --case multi_claim_notes
uv run python -B -m prototypes.reviewable_draft --output-dir /tmp/reviewable-draft-previews
```

The export directory must be new; existing files and edits are never overwritten.
The exporter reads only frozen synthetic inputs and authored fixture JSON, then renders
saved in-memory drafts. Its separate preview manifest records captured-input/fixture and
output hashes; it is not a production persistence format or a quality-score report.
Checked-in previews are reproducible with the same command in a fresh directory.

## Prototype contract

Use a small immutable in-memory vocabulary, independent of production models:

- `Snapshot`: title, started_at, attendees, my_name, complete transcript and handwritten
  text. Empty writing is valid; missing/non-string inputs are errors. Fingerprint every
  input/context field. Generate transcript passage IDs `T1…` and written passage IDs
  `N1…` in input order, retaining complete original strings. Transcript passages are whole
  timestamped speaker turns, without semantic sentence/claim splitting. Written passages
  are nonblank lines; preserve the full original writing separately, including gaps.
- `Item(text, sources)`: readable authored text with one or more existing passage IDs.
  References establish literal provenance only; they do not prove the text's meaning.
- `Section(kind, state, snapshot_id, generation_id, items, notice, review_sources)`:
  kind is summary, decisions, actions or review. State is draft, needs_review or unavailable.
  Summary/decision/action items and their focused review evidence cite speech only;
  review passages can cite either source. Written notes are rendered verbatim by code,
  not rewritten into generated spoken claims.
- `Draft(snapshot, generation_id, sections)`: contains exactly one of each section kind.
  All sections bind to the same snapshot fingerprint and generation; reject mixing,
  missing/duplicate kinds, unknown references or inappropriate source kinds.
- `render(draft) -> str`: pure Markdown output from this saved in-memory object only.
  No input-file reads, network, inference or persistence during rendering.

Use tuples/frozen objects for nested collections. A section marked unavailable contains
no accepted items: it needs a specific user-readable notice and focused source passages.
Needs-review sections also need a notice and focused evidence; independent usable items
can remain. Draft does not mean verified; all generated sections require human review.
States are caller-supplied outcomes in this authored experiment, not model confidence.

Render a clear AI-draft header and an incomplete banner whenever a section is unavailable.
Use readable titles and speaker/time labels, with source excerpts readily available.
Suggested actions/decisions use ordinary bullets, never executable checkboxes or claims
of automatic acceptance. The user can promote suggestions while editing in Obsidian.
Review items present passages without declaring agreement, conflict or resolution.
Escape generated Markdown/HTML so item text cannot inject headings, checkboxes or hidden
content. Quote original source text safely as literal data, preserving its wording.
Do not expose fingerprints, generation IDs, wire fields or error codes as product prose.

This prototype validates shape, bindings and provenance. It has no semantic verifier,
commitment classifier, arithmetic inference, note-claim coverage engine, retry loop or
transport. Wrong facts, unsupported obligations, lost conditions and misleading review
remain defects even when all references validate. Do not rebuild the V11 compiler here.

## Authored diagnostic set

Read these ten inputs unchanged from `evaluation/m10/v11/pairs.json`:

| Case | Authored behavior to inspect |
| --- | --- |
| empty | Both spoken undertakings and the independent release agreement remain discoverable. |
| additional | Spoken draft/review suggestions retain owners and timing; written-only requests/capacity stay writing. |
| unit_equivalence | Both literal price passages are available without an invented conflict or computed claim. |
| multi_claim_notes | Unavailable optional written comparison leaves invoice checking with full not-before timing available; rejected comparison prose is absent. |
| tentative_confirmed | Tentative speech remains tentative; the written confirmation is visibly a separate account. |
| accepted_status_answer | An affirmative availability answer does not produce an action suggestion. |
| accepted_request_retracted | The accepted sending request and withdrawal are retained together for review, not as a current sending obligation. |
| cancellation_with_new_task | The new invoice-sending undertaking survives cancellation of draft review; no immediate deadline is invented. |
| partial_coordination_retracted | Keep the whole original and withdrawal in focused review, making remaining invoice sending easy to find. |
| qualified_external_timing | Keep the full later not-before/next/finance condition with its original undertaking. |

All ten are familiar development cases. All forty original inputs/expectations and every
historical verdict stay unchanged. Fixtures are explicitly authored, not adapted model
responses presented as new results. Checked-in Markdown previews should reproduce from
the same snapshots and fixture data. They are sketches for owner review, not accepted
meeting notes or production generations.

## Prospective acceptance and persistence

Before any model experiment, declare draft-specific criteria on the unchanged inputs:
no critical wrong meaning/numbers/owners/timing, no invented or cancelled current work,
separate sources, meaningful access to independent undertakings/agreements, focused
uncertainty and honest unavailable states. A transcript dump or generic warning alone
does not satisfy useful retention. An honestly incomplete artifact can demonstrate graceful
degradation without passing overall quality/usefulness acceptance.

The owner must judge whether reviewing/editing a draft saves effort; no numerical review
time or generation-latency target is agreed. Authoring these fixtures is no evidence
that a local model can produce them. A later experiment needs separate exact scope,
repetitions, request/time limits, settings, stopping rule and fresh-case provenance.

Production persistence remains out of scope. Before integration, specify a distinct draft
artifact bound to its complete input snapshot/generation and each section's outcome.
An incomplete new draft must coexist with prior successful/accepted output and protected
edits; never splice generations or overwrite prior results with a rejected partial result.
Missing/unreadable associated notes stop input capture, unlike optional analysis failure.
Atomic saving, old wrapper semantics, crash recovery and user-edit preservation require
separate integration design/tests. This prototype performs no save/migration or vault edit.
