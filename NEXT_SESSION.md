# M10 handoff — 2026-11-13, local-model screen incomplete

Continue `m10/notes-guided-enhancement`, [PR #16](https://github.com/MattMSumner/meeting-notes/pull/16).
Read AGENTS.md, `.chief/CHIEF.md`, the reviewable-draft section of plan.md and the
[latest report](evaluation/m10/reviewable-draft/model-comparison-1/analysis/report.md).
Use Herdr for delegated work; keep local coordination in ignored `.chief/STATE.md`.

## Latest outcome and authorization

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

Engineering review passed without findings/formal repairs. Format/lint/strict types and
**1386 offline tests pass**, six integration tests excluded, capture unchanged. CI exposed
a test collector using historical Git objects missing in shallow checkouts; fixture-only
commit `0e349218915d722c14e9d5e9385f826899dd7ab3` reads committed frozen baseline files.
A real depth-one checkout collects all51newtests; full checks pass. Runtime, model packets
and frozen source were unchanged by this repair. Final-head CI status is in PR/local ledger.

Keep the existing baseline. A small generation/runtime configuration investigation should
precede another quality comparison or pipeline changes. Thinking mode is one possible
variable; the timeout cause is unproven. No new configuration, model requests or experiment
is approved by this recommendation. Do not add quote validators or rerun automatically.

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
