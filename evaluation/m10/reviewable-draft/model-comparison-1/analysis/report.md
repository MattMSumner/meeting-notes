# Local-model action screen — 2026-11-13

**INCOMPLETE: neither challenger completed the screen; no replacement is justified.**
Qwen3.5 returned one case and timed out on the second. Gemma4 returned two and timed out
on the third. The three returned outputs meet their scoped criteria, but they cover only
negative controls. No challenger supplied evidence of surviving-work or qualified-timing
coverage. Timeout is operational incompleteness, not proof of wrong missing answers.

The owner approved twelve new requests / thirty minutes, no retries, after preparation,
review and freeze. The single serial run used **five requests in 1381.014 seconds (23m01s)**:
three complete replies, two client timeouts and seven unsent slots, with zero retries or
arm/global overrun. Each timed-out request hit its fixed 600-second limit; the affected
arm stopped. All failed/unsent cases remain represented. The seven unused slots authorize
no resumption, retry, configuration repair or new experiment.

## Comparison

| Configuration | Complete replies | Criteria met | Critical defects | Incomplete cases | Measured run time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qwen3 30B, cached baseline | 6/6 | 5 | 1 | 0 | 4m07s, prior run |
| Qwen3.5 9B Q4_K_M | 1/6 | 1 | 0 observed in returned output | 5 | 11m59s |
| Gemma4 12B IT Q4_K_M | 2/6 | 2 | 0 observed in returned outputs | 4 | 11m01s |

Incomplete cases include both timeouts and unsent slots. These counts do not establish
relative accuracy on the missing cases, a speed ranking, or reliability. The old baseline
was reused, with no baseline inference. Its five passes and critical surviving-invoice
omission remain unchanged under the fresh masked assessment and in historical evidence.

| Case | Cached Qwen3 | Qwen3.5 | Gemma4 |
| --- | --- | --- | --- |
| unit_equivalence | Meets criterion | Meets criterion, 117.6 s | Meets criterion, 28.0 s |
| accepted_status_answer | Meets criterion | Timeout, 601.5 s slot elapsed | Meets criterion, 31.7 s |
| partial_coordination_retracted | Critical retention omission | Unsent | Timeout, 601.5 s slot elapsed |
| cancellation_with_new_task | Meets criterion | Unsent | Unsent |
| qualified_external_timing | Meets criterion | Unsent | Unsent |
| additional | Meets criterion, minor presentation notes | Unsent | Unsent |

The completed challenger price cases produce no price-derived action or computed relation.
Gemma4's completed availability case produces no action or rescheduling. The cached partial
withdrawal case still omits current invoice work and focused review; a generic notice and
backend snapshot do not satisfy useful retention. No historical rating is rewritten.

## Controls and assessment

The prompt, complete speech input, JSON schema, temperature zero, thinking enabled,
context 32768 and unchanged decoder/renderer were fixed. Only the request model field
varied. Both challengers advertised boolean thinking support before configuration freeze.
Writing stayed outside model input and was retained separately in snapshots and drafts.
No semantic validator, correction, warm-up inference or selective rerun was added.

Technical auditing preceded meaning review. Exactly eighteen records—six cached baseline,
twelve challenger slots including failed/unsent cases—were canonicalized and randomized
with unpredictable IDs. A fresh independent assessor received only the packet, its SHA256
and fixed source-based criteria. Model names, arm labels, raw thinking, timings, paths,
generation IDs, old reports and the key were withheld by task contract.

All eighteen grades locked before joining identities. The original packet/key pins were
checked before lock, and model-to-artifact attribution was checked after joining. No grade
or evidence changed after reveal. Terminal visual wrapping was folded to JSON whitespace
when recovering the grades; the original terminal handoff is preserved.

- [Masked packet](../review/packet.json), SHA256
  `3cd56589ca6c865912aa6ea0e46eedfd83142edd0dc77c5c8389cc396f0fe195`.
- [Locked original grades](../review/grades/scores.json), SHA256
  `07ff222b51a21b77587df25dc1246076dc5deaa0ca3e8ee59a81cce4b3c3082f`.
- [Lock](../review/grades/lock.json), SHA256
  `6208522433d95b66a998f504753679b70a8640911b07f7465f80f45009e5a3f3`.
- [Joined grades](joined.json), [assessment](assessment.json),
  [assessor handoff](assessor-terminal.txt) and [verification](verification.json).

Names hidden does not guarantee perfect blinding. The inputs are familiar development
material, one repetition with incomplete coverage; no held-out/full-regression, summary/
decision, full-draft usefulness, owner editing-time or Obsidian acceptance claim follows.

## Capture and engineering evidence

- Reviewed source `3275c1d380fbda9d2fd76f429c4c6014dfd03843`; freeze committed/pushed at
  `91157d4645452ddf92ebfc3fbf076acafc8c9f6b` before inference.
- [Thirty-artifact freeze](../manifest.json), SHA256
  `0c08baba4e1a1524f7ba8fa8b8c74e1a2b4b38fb8cc6798dd3c28c356d450c7d`.
- All 913 prior hashed entries and all forty original inputs remain exact; the 179 pinned
  baseline artifacts replay and verify. New requests match frozen bytes and host bindings.
- Ollama 0.40.9; exact model digests/configurations are frozen. All five attempted slots'
  before/after version/model/digest gates match. No source/request/settings/baseline drift.
- The audit contains five chat POSTs and twenty metadata GETs. All twenty GETs and three
  returned POSTs have HTTP 200; all three replies have `done=true`, `done_reason=stop`
  and exact raw/result/render reproduction. Neither timeout yielded response headers or
  body bytes. Empty raw/error records are preserved, not converted into model answers.
- [Final accounting](../results/final.json), exact [capture inventory](../results/manifest.json)
  and every request/attempt/outcome/raw/metadata record remain immutable. Launch, analysis
  and review files live outside results/ to preserve its exact capture inventory.
- Returned load/evaluation timings are retained separately. The first Qwen3.5 case reports
  eval_count 4080 / evaluation 110.346 s; Gemma4's first two report 551 /13.957 s and
  1184 /28.528 s. These records and the [runtime metadata](runtime-metadata.json) do not
  establish the root cause of either timeout. No thinking trace is supplied for a timeout.
- Client processes were killed/reaped at timeout. Server compute cancellation cannot be
  guaranteed; no server or configuration was changed to continue this screen.

Independent engineering review passed without findings or formal repairs. Formatting,
lint, strict types and **1386 offline tests pass**; six model/hardware integration tests
excluded, capture unchanged. CI exposed a test collector's assumption of full Git history;
fixture-only commit `0e349218915d722c14e9d5e9385f826899dd7ab3` reads frozen baseline source
files instead. A real depth-one clone collects all 51 new tests; the full suite passes.
Experiment runtime, frozen requests and model configuration were unchanged by that fix.

## Next decision

Keep the existing baseline; this screen supplies no evidence for a model switch. Both
alternatives were tested only with thinking enabled and the fixed structured-output
contract. A small investigation of generation/runtime configuration should precede another
quality comparison or further pipeline changes. Thinking mode is one possible variable
to isolate; the cause of these timeouts is unproven. This recommendation grants no new
requests, configuration changes or follow-up run.

Application behavior remains V11; M10 is unbuilt. Fresh examples/repeated tests, broader
regression, production persistence, current synthetic Obsidian usefulness and owner shipit
remain pending. No real-meeting pilot, production model switch, Built note or merge occurred.
