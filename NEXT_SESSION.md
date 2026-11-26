# M10 handoff — 2026-11-25, work-retention experiment incomplete

Continue `m10/notes-guided-enhancement`, [PR #16](https://github.com/MattMSumner/meeting-notes/pull/16).
Read AGENTS.md, `.chief/CHIEF.md`, the reviewable-draft section of plan.md and the
[runtime investigation](evaluation/m10/reviewable-draft/runtime-investigation-1/report.md).
Use the [current Chief workflow](.chief/README.md) for delegated work: `hc` children
with an explicit verified Chief parent and `codex --no-daemon`, in the existing
desktop tab/space. Legacy `herdr` pane IDs in old evidence are not core addresses.
Keep local coordination in ignored `.chief/STATE.md`; close out accepted worker
checkouts after preserving their work and handoffs.

## Latest outcome and authorization

The owner-approved four-case work-retention experiment is **INCOMPLETE and fails
quality acceptance**. It stopped after **three generation requests in 15.868 seconds**:
two rendered drafts, one literal-selection rejection and one unsent case. No retries,
timeouts, overruns or artifact errors. The independent capture audit passes; source
meaning assessment finds one critical defect, one criterion met with noncritical burden,
and two incomplete cases. See the [report](evaluation/m10/reviewable-draft/retention-probe-1-analysis/report.md)
and [assessment](evaluation/m10/reviewable-draft/retention-probe-1-analysis/assessment.json).

| Case | Outcome |
| --- | --- |
| Partial withdrawal | **Critical:** invoice sending survives, but the suggested action also includes cancelled draft review. Both full turns are visible; this is not an omission. |
| Replacement task | Meets criterion: inline retraction preserves independent sending and attribution, no invented due. Broad selection/repeated review adds noncritical burden. |
| Qualified timing | Incomplete: combined T1/T2 quote attributed to T1 is rejected as quote_absent; no draft. Full timing qualifier is present in attempted content, not proven omitted. |
| Additional undertakings | Unsent after case three; no model quality evidence. |

No semantic assessment completed during capture. The first detected in-run failure
was the third case's literal rejection, which stopped before the fourth request.
The later critical finding does not imply earlier detection or authorize more calls.
**The once-only allowance is closed: no retry, resumption, unused-slot transfer or
further inference is authorized.** Keep the existing baseline and production behavior.

The owner said “Great, run the experiment” to one repetition in fixed order of
`partial_coordination_retracted`, `cancellation_with_new_task`,
`qualified_external_timing`, `additional`; Qwen3.5 thinking false/streaming true,
unchanged prompt/schema/decoder/renderer, temperature0, context32768. Limits were
four requests / 900 seconds overall / 180 seconds per generation / no retries.
Preparation/review/freeze/publication preceded execution; in-run validation, metadata,
loading, capture, saving and cleanup count toward the shared deadline.

Exact collector source `af210c01b803bc885d24c2ed78f7c7fb725108b4` is integrated
unchanged as an ancestor. Independent source review passed with no findings or repair
rounds; format/lint/strict types and **1555 offline tests pass**, six integration tests
excluded, 66 new tests. Worker and Chief full suites used the same pinned source;
post-freeze static checks also pass. Production and historical code are unchanged.

The [48-artifact freeze](evaluation/m10/reviewable-draft/retention-probe-1/manifest.json)
was committed/pushed at `9dba7187037592d2898f773932d48f7a70c9fd76` before inference;
SHA256 `24676d89c8a68db18a9d78d732a3089caffd85c74dc6526f07a560c511f1fdbd`,
generation `retention-probe-8c62fdd2301f4b8695e81a55c5424188`. The
[prospective criteria](evaluation/m10/reviewable-draft/retention-probe-1-analysis/criteria.json)
were committed at `e96d48b` before outputs; SHA256
`4c9f4f238b0a57470d0cd9ba1134db4c002a4acf0565ab8a41c4210f40a7fecb`.

All six before/after gates match Ollama0.40.13/model digest/thinking/defaults. Exactly
21 HTTP200 exchanges account for three generation calls and eighteen metadata calls;
zero thinking characters, no child kill/error/timeout, all children reaped. The
[capture manifest](evaluation/m10/reviewable-draft/retention-probe-1/results/manifest.json)
contains 171 artifacts plus itself; SHA256
`64b673d748447c087d4d58254f113f25d435ec370a1d2c6f39366892458d6943`.
All 1347 prior tracked evaluation/prototype files remain byte-exact.

Use the [collector contract](prototypes/reviewable_draft/RETENTION_PROBE.md).
Capture manifest accounting equals the returned accounting exactly: incomplete,
literal-failure stop, zero overrun. Its elapsed boundary is15.867515917s; post-seal
observation15.867707959s; independent full-call wall15.867782917s. `final.json` is a
non-authoritative pre-save snapshot. All later meaning/report/launch/final-seal
artifacts live in the sibling analysis directory; never alter or add to either
strict freeze/capture inventory. No historical result or grade changed.

## Completed streaming runtime probe — earlier allowance consumed

The owner-approved runtime probe is **complete**, using exactly **two generation
requests in 104.676 seconds**, no retries, failures, unsent slots or overruns. The
[result report](evaluation/m10/reviewable-draft/runtime-probe-1-analysis/report.md)
records the independent capture audit and meaning assessment. Both outputs meet the
narrow availability/no-action criterion. The false arm adds two unnecessary review
passages; the true arm adds none. **No further inference is authorized.** The unused
wall-time allowance authorizes no new case, retry or repetition.

| Thinking | HTTP seconds | Model load seconds | Thinking characters | Actions |
| --- | ---: | ---: | ---: | ---: |
| false, first | 11.539 | 9.384 | 0 | 0 |
| true, second | 91.687 | 0.003 | 13,509 | 0 |

The true arm spends 91.566 seconds in returned evaluation time versus 0.864 seconds
for false, with 3110 versus 33 returned output tokens. These are observed costs for
one ordered negative-control pair. False loads cold; true is warm with 416 cached
prompt tokens versus zero. Returned prompt counts differ (418 versus 420). This is
not a reliability estimate or proof that useful work/timing would be retained.

Preparation metadata found installed Ollama **0.40.13**, versus historical 0.40.9.
The same model digest and boolean thinking support remain. This was disclosed to the
owner and pinned with relevant model defaults for the fresh pair; no service or model
change was made. All four captured identity/default gate sets match. The historical
timeout did not recur with this new version and streaming setup; its cause remains
unproven. No historical grades changed and no model switch follows.

The isolated collector is implemented and independently reviewed at
`58bf14f216aa642bc3ab4d14022b17469724f787`: no remaining findings after two repair
rounds. Format/lint/strict types and 1489 offline tests pass, six integration tests
excluded; 103 tests cover the new profile. Existing production and historical files
remain unchanged. All 1182 prior tracked evaluation/prototype hashes verify exact.

The [36-file freeze](evaluation/m10/reviewable-draft/runtime-probe-1/manifest.json)
has SHA256 `d459841b61df3ed2ecdab8e9866b7da280b2744707c56b4d2b574e7d1e4b22f2`
and generation `runtime-probe-956c51abc1a849aa9eeccee33793ceb7`. Its source, wire
hashes, selected complete snapshot and new identity/defaults independently verify.
The exact freeze was committed/pushed at `a5f0e64e00adb8e09be61834b8bfa8d0351d57d6`
before inference. Its 36 artifacts plus manifest remain exact. The single-use results
now contain 114 artifacts plus manifest, all independently verified and replayed.
Fourteen HTTP200 exchanges account for two generation calls and twelve metadata calls.

Use the [collector contract](prototypes/reviewable_draft/RUNTIME_PROBE.md). Results are
single-use. `results/manifest.json.accounting` is authoritative at its explicit boundary;
`final.json` is only a labeled pre-save snapshot. Preserve the returned envelope's
separate post-seal observation and independently measured full call wall time outside
capture. Sealed, post-seal and independent full-wall observations all pass. Keep later
analysis/review/launch artifacts outside both strict inventories, as in the sibling
`runtime-probe-1-analysis/`. Do not rerun the collector or alter captured bytes. Its
sealed stop reason correctly refers to the then-pending separate semantic assessment;
the later passing assessment lives in the sibling report and assessment.json.

## Completed offline investigation

The owner asked to start the recommended timeout investigation. The offline audit
rechecked eleven saved replies/attempts and 505 overlapping manifest entries, with no
new Ollama requests, live service inspection or configuration changes. Neither timeout
has headers/body bytes or server timings, so the cause remains unproven. The completed
Qwen3.5 request generated 17,084 thinking characters for 37 answer characters; older
successful baseline replies also have long traces. Prompt caching and runtime residency
metadata limit comparisons. The 4096 reply reserve is not a sent output-token cap.

The [proposal](evaluation/m10/reviewable-draft/runtime-investigation-1/proposal.json)
is one fresh Qwen3.5 availability pair, false then true, with streaming fixed for both:
two generation requests, 180 seconds each, seven minutes overall, no retries. Exact
proposed request bodies are saved. That proposal was subsequently approved, independently
reviewed, frozen and executed as recorded above. Its historical report remains unchanged.
The new run tests a prospective setting; it does not prove the historical cause.

## Earlier local-model screen — unchanged

The owner said “Do it!” to the fixed-task local-model screen: two installed alternatives,
six cases each, at most twelve new requests / thirty minutes, no retries; reuse the Qwen3
baseline and hide model names during meaning assessment. Preparation/review/freeze preceded
execution. The approved once-only run is complete with an **INCOMPLETE comparison**:

| Configuration | Complete replies | Criteria met | Other outcomes |
| --- | ---: | ---: | --- |
| Cached Qwen3 30B | 6/6 | 5 | One critical surviving-invoice omission, unchanged. |
| Qwen3.5 9B Q4_K_M | 1/6 | 1 | Availability case timed out; four cases unsent. |
| Gemma4 12B IT Q4_K_M | 2/6 | 2 | Partial-withdrawal case timed out; three cases unsent. |

Actual run: **five requests, three complete replies, two 600-second client timeouts and
seven unsent cases in 1381.014 seconds (23m01s)**, no retries or arm/global overrun.
Qwen3.5 arm elapsed719.438s; Gemma4 arm661.250s. All three returned challenger outputs
are negative controls. There is no challenger evidence of surviving-work/timing coverage
and no basis for a model switch. Timeout is not proof of incorrect missing answers.
**The seven unused slots authorize no resumption, retry, configuration change or new run.**
No further inference is authorized. Old unused allowances also authorize nothing.

## Fixed controls and evidence

Only request model varied: same prompt, complete speech input, response schema,
temperature0, thinktrue, context32768 and unchanged actions decoder/renderer. Both models'
boolean thinking support was checked in local metadata before freezing. Original writing
stayed outside model input, retained separately in complete snapshots and drafts.

- Source candidate `3275c1d380fbda9d2fd76f429c4c6014dfd03843`.
- Freeze committed/pushed before inference `91157d4645452ddf92ebfc3fbf076acafc8c9f6b`.
- [Thirty-entry freeze](evaluation/m10/reviewable-draft/model-comparison-1/manifest.json), SHA256
  `0c08baba4e1a1524f7ba8fa8b8c74e1a2b4b38fb8cc6798dd3c28c356d450c7d`.
- Ollama0.40.9; Qwen3.5 digest
  `56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`, Gemma4 digest
  `6114515d63c17436a7c0417d82820ac65ad643e2806c5a3c89cb62846436ed0b`.
- All five attempted slots' before/after version/model/digest gates match. Five chat POSTs
  and twenty captured metadata GETs; twenty GETs and three returned POSTs are HTTP200.
  Three replies are done/stop and replay exactly. Two timeouts retain empty raw bodies
  without response headers; failed replies are not fabricated. No source/config drift.
- compare.py reuses existing hardened HTTP/time helpers; no real-execution global patching,
  baseline inference, warm-up, semantic validator or correction/retry was added.
- results/manifest.json is an **exact capture inventory**. Never add launch/analysis/review
  files inside results/. They live in sibling analysis/ and review/. Preserve capture bytes.
- All913prior entries and40original inputs remain exact, plus30current frozen artifacts;
  all179baseline artifacts verify/replay. A final seal covers new capture/review/analysis.

## Model-name-hidden assessment

Exactly eighteen randomized opaque records covered six cached baseline outputs and all
twelve challenger slots, including failed/unsent cases. A fresh read-only assessor received
only packet+criteria+SHA, not names/keys/raw thinking/timings/paths/old reports. All eighteen
grades locked before joining identities; original packet/key pins and final model/source
attribution were checked. Baseline grades remain5pass/1critical; challengers1pass/5incomplete
and2pass/4incomplete. No grade changed after reveal. Original terminal evidence is retained.

PacketSHA `3cd56589ca6c865912aa6ea0e46eedfd83142edd0dc77c5c8389cc396f0fe195`;
scoreSHA `07ff222b51a21b77587df25dc1246076dc5deaa0ca3e8ee59a81cce4b3c3082f`;
lockSHA `6208522433d95b66a998f504753679b70a8640911b07f7465f80f45009e5a3f3`.
See review/packet.json, grades/lock.json, analysis/joined.json and assessment.json.
Names hidden does not guarantee perfect blinding. Familiar inputs/one repetition/incomplete
coverage establish no reliability, full regression, summary/decision quality, editing-time
benefit or current Obsidian usefulness.

## Checks and next decision

The latest collector passed source review and all required engineering checks, but
its work-retention run did not qualify the model configuration. Reassess source
selection before another call: cancelled work must be excluded from current action
spans, and supporting turns must remain separate from a primary-source quotation.
Do not add more literal validators for the currentness failure: that quote already
passes literal checks. No decoder relaxation, quote repair or selective rerun follows.
Any new experiment needs separately agreed scope and budget.

Earlier model-screen CI fixture fix `0e349218915d722c14e9d5e9385f826899dd7ab3`
reads committed frozen baseline files instead of missing historical Git objects.
Its depth-one collection passed; latest collector also has depth-one fixture coverage.
No old frozen source or model request changed. Final-head CI status is in PR/local ledger.

The owner still values useful drafts requiring review and approved the authored normal/
incomplete presentation. That product direction remains unchanged. Current app behavior
is V11; M10 unbuilt. Fresh examples/repeated tests, full40regression, production snapshot/
persistence/edit safeguards and current synthetic Obsidian usefulness remain required.
Numerical latency/review-effort targets are unagreed. Only owner `shipit` authorizes
`git shipit`; never merge on GitHub. No real-meeting pilot is authorized.

## Immutable earlier checkpoints

Never rewrite prior captures, frozen declarations, scores or verdicts. Do not run old
mutating verify/analyze tools. All historical details remain in their reports:

- [Action-only diagnostic](evaluation/m10/reviewable-draft/diagnostic-3/results/report.md):
  six requests/247.310s;5criteria met,1criticalretentionfailure. Twenty freeze+157result
  entries. Source287d85b; freeze7381d8e; manifest
  `472027ef8be047233a3a8cf75630c922afe28c96b73911b844619c16b33e8bd3`.
- [Quoted diagnostic](evaluation/m10/reviewable-draft/diagnostic-2/results/report.md):2requests,
  one compiled, one reference-validation rejection,4unsent; nineteen freeze+56result
  entries remain exact. Old4unused slots authorize nothing. Source9e369ad/freeze77fd9d3.
- [First draft diagnostic](evaluation/m10/reviewable-draft/diagnostic-1/results/report.md):
  six requests/5m13s;4meet,1inventedwork,1noncriticalsurviving-work failure with facts still
  visible in Summary. Eighteen freeze+157result entries. Source2934d10/freeze1a3aceb.
- [V11](evaluation/m10/v11/results/report.md): proposed34/40,6blocked,1falseunitconflict;
  baseline40/40with8criticalcases.109requests/98m46s;167unusedauthorize nothing. Sourcefb3b130/
  freezee866b10.34wrapper10+17wrapper9generations replay;486historical entries preserved.

## Separate follow-up

Leave /private/tmp/meeting-notes-safeguards and the unrelated recovery issue alone.
Processing-spawn failure after confirmed orphan shutdown can clear a pending session;
repair separately with synthetic regression. This task changes no capture/recovery behavior.
Never read/publish real meeting content in prompts/logs/reports.
