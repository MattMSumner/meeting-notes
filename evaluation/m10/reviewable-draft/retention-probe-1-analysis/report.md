# Work-retention experiment — 2026-11-25

**INCOMPLETE: three generation requests in 15.868 seconds; two drafts rendered,
one literal-selection rejection, one case unsent.** The collector stopped on the
first detected failure, with no retries, timeouts or overruns. No further inference
or resumption is authorized. **Quality acceptance fails:** independent source-based
assessment finds one critical cancelled-work error, one criterion met with noncritical
review burden, and two incomplete cases. Successful transport and literal decoding
are not semantic acceptance.

## Case outcomes

| Case | Capture / publication | Meaning assessment |
| --- | --- | --- |
| Partial cancellation | Complete stream and rendered draft | **Critical: cancelled review remains inside the suggested action.** Sending survives and withdrawal context is visible; this is not an omission. |
| Cancellation with replacement | Complete stream and rendered draft | Meets criterion; broad quotation and redundant focused review add editing burden. |
| Qualified timing | Complete stream; rejected by unchanged literal check; no draft | Incomplete: selected quotation joins text from two source passages under one primary source. |
| Additional undertakings | Unsent after the preceding failure | Incomplete; no reply or quality evidence. |

The first draft places the complete original compound undertaking under Suggested
actions, including draft review that a later source explicitly withdraws. Sending
is discoverable and both whole turns are available. The defect is presenting the
cancelled review within the still-positive suggested-action selection; the later
context and generic draft warning do not remove that component. Supported attribution
and absence of invented timing do not excuse this currentness error. The reader must
reconcile a contradiction across action, context and excerpt.

The replacement case differs: its selected complete utterance includes the explicit
inline retraction before the surviving sending undertaking. It preserves the actual
revocation, relevant context and supported attribution, without inventing a due date.
Repeating the same clear passage under focused review and selecting the whole utterance
add noncritical review burden. Chief's source-based assessment agrees with the
independent reviewer. See [assessment.json](assessment.json).

The third response supplies a primary-source quotation spanning the sending passage
and a separate later timing passage. The combined text is not a contiguous quotation
in the named primary source. The unchanged decoder records `quote_absent`. Answer text
remains in `observed.json` and the raw stream in `response/body.raw`; `result.json`
retains the issue and both review references. The collector
publishes no `actions.md` for that failed case. The attempted response does contain
the full not-before/next-Friday/unless-finance qualifier; this is not proof of omitted
timing or an invented deadline. Do not repair the quotation or treat the backend
result as a completed user-facing draft.

Capture stopped on the literal failure in case three. No semantic assessment had
completed during the 15.9-second run; the newly identified post-run critical defect
does not imply earlier in-run detection. All already-captured outputs are preserved.
The unsent fourth case is not a semantic failure and
does not authorize using its unused slot in another invocation.

## Runtime observations

| Metric | Partial cancellation | Replacement | Qualified timing |
| --- | ---: | ---: | ---: |
| HTTP worker seconds | 7.062032 | 3.274215 | 3.628994 |
| Whole slot seconds | 7.696512 | 3.896789 | 4.212311 |
| Server total seconds | 6.985156 | 3.225823 | 3.575648 |
| Server load seconds | 4.897089 | 0.001607 | 0.001583 |
| Server prompt-evaluation seconds | 1.096115 | 1.071445 | 1.097402 |
| Server output-evaluation seconds | 0.980444 | 2.144315 | 2.466291 |
| Returned prompt tokens / cached tokens | 428 / 0 | 394 / 0 | 425 / 0 |
| Returned output tokens | 37 | 81 | 93 |
| First content seconds | 6.007961 | 1.084329 | 1.112060 |
| Thinking characters | 0 | 0 | 0 |
| Answer characters | 139 | 222 | 255 |
| Raw response bytes | 5,168 | 7,731 | 8,808 |
| Complete events / logged chunks | 37 / 37 | 56 / 56 | 64 / 64 |

All three returned streams have valid UTF-8/NDJSON and one terminal `done=true` /
`done_reason=stop`, with no trailing bytes. Received-event timings are relative to
each HTTP child's monotonic origin, not GPU production time. Character counts are
not token counts. These familiar, ordered cases and one repetition establish no
reliability or general performance estimate. The first request incurs model load;
later requests are warm. This is not a historical timeout reproduction or diagnosis.

## Approval, freeze and integrity

The owner's “Great, run the experiment” approved one repetition in fixed order:
partial cancellation, replacement, qualified timing, additional undertakings. Limits
were four generation requests, 900 seconds overall, 180 seconds per generation and
no retries. Preparation/review/publication preceded the run clock. See
[authorization.json](authorization.json).

Prospective [criteria.json](criteria.json) was committed at
`e96d48b7a2393f1000a45ffcedc2d8c60761064f` before inference; SHA256
`4c9f4f238b0a57470d0cd9ba1134db4c002a4acf0565ab8a41c4210f40a7fecb`.
It preserves the existing source-based work/currentness/timing requirements and
allows supported suggestions or focused review. Generic warnings/transcript dumps
alone do not satisfy useful retention. Assessment is not blinded or held out.

Exact independently reviewed collector source:
`af210c01b803bc885d24c2ed78f7c7fb725108b4`, integrated without changing its bytes or
rewriting its commit. The [48-artifact freeze](../retention-probe-1/manifest.json)
was committed and pushed at `9dba7187037592d2898f773932d48f7a70c9fd76` before inference;
manifest SHA256 `24676d89c8a68db18a9d78d732a3089caffd85c74dc6526f07a560c511f1fdbd`.
Generation: `retention-probe-8c62fdd2301f4b8695e81a55c5424188`.

The run pins Ollama0.40.13 and `qwen3.5:9b-q4_K_M`, digest
`56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`.
Thinking is false, streaming true, temperature0, context32768. Prompt, speech input,
schema and decoder/renderer are unchanged. Writing remains outside model input and
separately preserved in complete snapshots/drafts. Three preparation metadata calls
made no generations; no warm-up, baseline call or service/model/config change ran.

All six before/after identity/default gates match. **21 HTTP200 exchanges** account
for three generation POSTs and eighteen metadata calls (twelve GETs, six model-show
POSTs). All child processes were reaped normally; no kill, timeout or overrun occurred.
The failed third case has a complete response and all post-generation metadata; the
fourth has its frozen request/bindings and unsent outcome, with no attempt/response.

The [capture manifest](../retention-probe-1/results/manifest.json) has 171 artifact
entries plus itself; SHA256
`64b673d748447c087d4d58254f113f25d435ec370a1d2c6f39366892458d6943`.
Its authoritative accounting equals the preserved returned accounting exactly.
Sealed elapsed time is 15.867515917 seconds at the pre-manifest-write boundary;
separate post-seal time is 15.867707959 seconds and independent full `run()` wall
time is **15.867782917 seconds**. All report zero overrun. `final.json` remains a
labeled non-authoritative pre-save snapshot; the saved literal-failure stop reason
is not rewritten by later meaning assessment.

Chief and independent read-only audit verify exact freeze/capture inventories, all actual wire/attempt/snapshot/
generation bindings, raw/chunk/progress/observed replay, unchanged decoder results
and the two rendered draft byte sequences. All 1347 prior tracked evaluation/prototype
files remain exact. See [verification.json](verification.json), [launch.json](launch.json)
and the reviewed single-call [launch script](launch-script.txt). Analysis and the
final [seal](seal.json) remain outside both strict freeze and capture inventories.

Engineering review found no necessary corrections or repair rounds. Format/lint/
strict types and **1555 offline tests pass**, six integration tests excluded; 66 new
tests cover the profile. Worker and Chief full runs used the same pinned source;
post-freeze formatting/lint/type checks also pass. These checks establish no model
quality. Production, historical evidence and earlier grades are unchanged.

## Next decision

This experiment does not qualify the configuration for broader integration. Fast
completion did not establish safe selection of current work or a usable timing draft.
Keep the existing baseline; preserve these failures and reassess the source-selection
contract before another model run: current action spans must exclude cancelled work,
and supporting passages must remain separate from a primary-source quotation.
Do not add more literal validators to address the currentness failure: its quotation
already passes literal checks. No source/decoder relaxation, quotation repair,
retry or selective rerun follows automatically. New experiments need separately
agreed scope and budget. Broader cases/repetitions, full40 regression, full-draft
quality, production persistence/edit protection and current synthetic Obsidian
usefulness remain pending. M10 stays unbuilt and PR #16 is not ready to merge.
