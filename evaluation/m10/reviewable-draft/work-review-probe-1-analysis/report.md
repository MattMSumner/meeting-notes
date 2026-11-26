# Seven-case passage-selection experiment — stopped on critical omission

The once-only experiment is **incomplete and fails its prospective quality criterion**.
It stopped after **one generation request in 27.252 seconds**, including
the Chief agent's review wait. The first model reply selected no passages despite surviving
invoice-sending work in the input. All six later cases remain unsent; no retries or overruns.
Independent saved-evidence audit passes; source-meaning review independently confirms
the critical omission and six incomplete cases. See [assessment](assessment.json),
[verification](verification.json), [criteria](criteria.json) and [final seal](seal.json).

## Source meaning and stopping decision

The complete first snapshot has a compound undertaking in T1 and a withdrawal of only draft
review in T2. Invoice sending survives. The accepted contract requires complete original and
withdrawal context in focused neutral passages for a person to resolve current work.
The actual model answer was `{"groups": []}`: structurally valid, with zero selected turns.
The [rendered result](../work-review-probe-1/results/01-partial_coordination_retracted/work-review.md)
therefore offers no work passages. The empty-selection notice and preserved full snapshot do
not satisfy useful selected-work coverage. This is a **critical omission of surviving work**.
No invented action, owner or deadline was observed.

The unchanged decoder and renderer accepted and faithfully displayed that empty selection.
Answer text is saved in [observed.json](../work-review-probe-1/results/01-partial_coordination_retracted/observed.json);
the raw stream is in [response/body.raw](../work-review-probe-1/results/01-partial_coordination_retracted/response/body.raw).
The bound [result.json](../work-review-probe-1/results/01-partial_coordination_retracted/result.json)
retains the complete source snapshot and zero groups. The Chief agent identified the defect
at the first in-run review gate and recorded a [critical verdict](../work-review-probe-1/results/01-partial_coordination_retracted/meaning-review.json)
before any second request. Capture accounting marks the first slot failed due to that
meaning verdict; its transport/stream/decode completed normally.

| Case | Result |
| --- | --- |
| partial_coordination_retracted | **Critical: empty selection omits surviving work.** |
| cancellation_with_new_task | Unsent / incomplete; no model answer. |
| qualified_external_timing | Unsent / incomplete; no model answer. |
| additional | Unsent / incomplete; no model answer. |
| accepted_status_answer | Unsent / incomplete; no model answer. |
| unit_equivalence | Unsent / incomplete; no model answer. |
| authored_longer_context | Unsent / incomplete; no model answer. |

The six unsent outcomes retain their frozen snapshot/generation/request bindings and have
only outcome artifacts. They provide no evidence about replacement, complete timing,
additional undertakings, negative controls or longer-context selection. No missing answer
is graded as a semantic error. The experiment did not reach a seven-case feasibility result.

## Observed runtime

| Metric, first returned case | Value |
| --- | ---: |
| Generation HTTP seconds | 6.715 |
| Slot seconds, including Chief review | 27.162 |
| Returned server total seconds | 6.631 |
| Returned load seconds | 5.614 |
| Returned prompt-evaluation seconds | 0.845 |
| Returned output-evaluation seconds | 0.160 |
| Returned prompt tokens | 324 |
| Returned cached prompt tokens | 0 |
| Returned output tokens | 6 |
| First content receive seconds | 6.475 |
| Answer characters | 14 |
| Thinking characters | 0 |
| Raw generation stream bytes | 998 |
| Complete NDJSON events | 6 |
| Raw receive chunks | 6 |

Receive times are measured from the HTTP child's monotonic origin, not GPU time. Returned
server durations and token counts are separate measurements; characters/bytes are not
tokens. Most generation HTTP time is returned loading time. The full-call wall includes
validation, metadata, rendering, explicit Chief review wait and finalization. This one
cold-load observation establishes neither performance reliability nor why selection failed.

## Binding, accounting and preservation

- Reviewed source: `67f025148778d6d62dcdde2f76ad770800dc9fda`, exactly five additions,
  independently accepted without findings or repairs. Both source-identical full offline
  suites pass: Chief 1725 tests / six excluded in454.81s; worker 1725 / six in461.32s;
  targeted104, formatting/lint/strict types pass. No production source/configuration changed.
- Published freeze: `a81f7ddb16ef13a05290208de6873791526074f4`, before inference; all75
  artifacts plus [manifest](../work-review-probe-1/manifest.json) remain exact. Manifest
  SHA256 `52f0dca1b62063ba09bd0ca0f7d50eca588dc07bdacd2ca1b5d5c99f6c3fa0b7`; generation
  `work-review-probe-d4a32d0153d94bb1a9e2a746da0fd2b4`.
- Exact capture:66artifacts plus [seal manifest](../work-review-probe-1/results/manifest.json),
  SHA256 `74f7d1b164dd21b1fa3901cb259ea71cdb5ba4b4360f88e6d3fb5551c806c6c1`. One conservative attempt and one actual
  pinned chat body; all seven initial bindings retained. No further attempt/retry/resumption.
- Seven recorded HTTP200 exchanges: one generation and six metadata exchanges. Both
  before/after identity gates match Ollama0.40.13, the pinned Qwen3.5 digest/capabilities/
  thinking/defaults. No identity change, timeout, child error, kill, overrun or artifact error.
- Saved stream/progress/observed/result/render replay exactly; terminal done/stop at EOF.
  Zero thinking characters. All1610prior tracked evaluation/prototype hashes remain exact.
- `results/manifest.json.accounting` equals [launch.json](launch.json)'s returned accounting.
  Its authoritative pre-manifest-write elapsed boundary is27.251692459s; post-seal observation
  is27.252203959s, sealed with no deadline reached. Independent full-call wall is27.252280959s.
  [final.json](../work-review-probe-1/results/final.json) is explicitly non-authoritative.
  Capture remains incomplete because the identified critical verdict stopped the run.

[Authorization](authorization.json) preserves the owner's “Ok, run those examples and fix CI!”:
seven requests, one pass,1500seconds overall,180seconds each, no retries, required Chief review
before advancing. The reviewed [launcher](launch-script.txt) calls the collector once,
uses an exclusive execution claim and retains the full return plus independent wall outside
strict inventories. Verdict input rejects duplicate keys and missing/invalid verdicts; audit
storage failure cannot report completion. Chief assessment is agent review, not owner/human
approval. **This allowance is closed; unused slots permit no retry, resume or new requests.**

## CI and limits

The original [CI run](https://github.com/MattMSumner/meeting-notes/actions/runs/45827573292)
failed to acquire a hosted macOS runner: no runner assignment or executed Python steps;
GitHub annotated runner capacity constraints. Rerunning it succeeded for both Python and
Swift. No workflow change was justified. The current PR separately checks the published
collector/data/doc descendants.

Six inputs are familiar development cases and the seventh is Chief-authored, not held out.
Only the first was executed once. This identifies one failure on the new source-review task;
it cannot estimate reliability, identify a historical failure cause or justify a model
switch. Presentation acceptance and offline engineering integrity stand; source/reference
integrity cannot guarantee useful retrieval. Existing action-extraction failures and grades
remain unchanged. No summary/decision/full40 quality, saved effort, persistence/edit
protection, current Obsidian usefulness, production integration, M10 Built or merge follows.
