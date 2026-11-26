# Runtime investigation — offline checkpoint, 2026-11-25

**The saved evidence does not establish either timeout's cause.** Thinking mode is
a useful first variable to test. Prepare a small instrumented comparison before another
quality screen; do not increase timeouts, switch models or change the production pipeline
based on this analysis.

The owner asked to start the recommended investigation. This checkpoint uses committed
synthetic captures and source at `920ef107188d79f2e07a6ffefb71edd1c5121029` only:
**zero new local-model requests, no live service inspection and no configuration changes**.
Historical captures, scores and verdicts remain unchanged. The application remains V11;
M10 is unbuilt.

## Observations

[evidence.json](evidence.json) records the source paths, request/response hashes, exact
nanosecond timings, Unicode character counts and failure metadata for eleven saved replies
or attempts. Independently hashing the two comparison manifests, its final seal and the
two baseline manifests verifies 505 entries, with overlap between inventories. This is
an integrity check of those five inventories, not a new model-quality evaluation.
Repository formatting, lint, strict types and all 1386 offline tests pass; six
integration tests are excluded. Capture code is unchanged.

All requests explicitly set `think=true`, `stream=false`, temperature zero and
`num_ctx=32768`, with the same two-field action schema. Neither `num_predict` nor
`keep_alive` is specified in the requests. Model defaults and scheduler state are not
fully captured by the version/tags gates.

The 4096 reply reserve in
[`actions.py`](../../../../prototypes/reviewable_draft/actions.py) is a pre-send size
guard. It does not send a generation-token limit to the server.

### Completed challengers

Times below are seconds; HTTP elapsed excludes before/after metadata and local replay.
Thinking and answer sizes are characters, **not separately measured token counts**.

| Model / case | HTTP elapsed | Server total | Load | Prompt tokens | Output tokens / evaluation seconds | Thinking / answer characters |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5 / unit_equivalence | 115.990 | 115.910 | 4.595 | 384 | 4080 / 110.346 | 17084 / 37 |
| Gemma4 / unit_equivalence | 26.575 | 26.507 | 10.773 | 384 | 551 / 13.957 | 2024 / 43 |
| Gemma4 / accepted_status_answer | 30.254 | 30.165 | 0.002 | 418 | 1184 / 28.528 | 4472 / 43 |

For Qwen3.5's completed request, evaluation accounts for about 95% of returned server
time; loading accounts for about 4%. This demonstrates substantial generation work on
that request, not a diagnosis of the later failure. Gemma4's first request also has
material loading cost. Neither observation rules out loading or contention on a timeout.

### Timeouts

| Model / case | HTTP elapsed | Complete slot elapsed | Saved headers | Body bytes | Returned timing/token fields |
| --- | ---: | ---: | --- | ---: | --- |
| Qwen3.5 / accepted_status_answer | 600.012 | 601.487 | Absent | 0 | Absent |
| Gemma4 / partial_coordination_retracted | 600.004 | 601.503 | Absent | 0 | Absent |

The parent subprocess deadline expired at the declared 600 seconds. Slot time includes
metadata and local work, explaining its roughly 1.5-second difference. These are not
measured server generation times. No thinking trace, output-token count, load duration,
prompt timing or server error is available for either failure.

[`_http.py`](../../../../prototypes/reviewable_draft/_http.py) opens `body.raw` before
sending, then saves headers only after `getresponse()` returns. It writes body chunks
incrementally. An empty file with no headers therefore records lack of an observed
response, not proof that the server did no work. Non-streaming requests give no
intermediate thinking/answer progress. The
[parent transport](../../../../prototypes/reviewable_draft/action_diagnostic.py) kills
and reaps the HTTP child at deadline; it does not establish server-compute cancellation.
Version/tags success after a timeout establishes metadata availability, not runner idleness.

### Cached Qwen3 baseline

The six older baseline replies also contain substantial thinking and all completed.
They ran on another occasion and are not concurrent controls for challenger speed.
Their returned prompt-cache counts become nonzero (277–352), while all three completed
challenger replies report zero cached prompt tokens. This is another comparison limit;
reuse of saved baseline artifacts is distinct from the server's prompt cache.

| Case | HTTP elapsed seconds | Load seconds | Prompt / output tokens | Thinking / answer characters |
| --- | ---: | ---: | ---: | ---: |
| unit_equivalence | 31.447 | 15.420 | 375 / 1085 | 4960 / 37 |
| accepted_status_answer | 22.143 | 0.002 | 409 / 1510 | 7123 / 37 |
| partial_coordination_retracted | 19.085 | 0.002 | 417 / 1304 | 5771 / 37 |
| cancellation_with_new_task | 46.168 | 0.002 | 383 / 3051 | 14037 / 109 |
| qualified_external_timing | 65.912 | 0.003 | 414 / 3930 | 16989 / 120 |
| additional | 59.151 | 0.002 | 416 / 3317 | 14364 / 204 |

Long thinking alone is not evidence of a loop: the baseline's largest trace is close
in character count to the completed Qwen3.5 trace. Completion also is not accuracy:
the baseline partial-withdrawal output still has its critical surviving-work omission.

## Hypotheses and limits

- **Thinking or its interaction with structured generation:** worth isolating because
  the completed Qwen3.5 reply spends substantial time generating a very small answer.
  No failed trace or `think=false` control exists, so a thinking loop is unproven.
- **Output budget:** the requests impose no explicit token cap. Current
  [Ollama parameter documentation](https://docs.ollama.com/modelfile#valid-parameters-and-values)
  describes `num_predict` as the output-token limit and documents a default of -1.
  That does not prove the historical effective limit: model/server defaults were not
  fully saved. A future token cap must count as another deliberate configuration change;
  reaching it is incomplete generation, not a valid empty-action answer.
- **Loading, queueing, memory or runner behavior:** still possible. Completed prompt
  counts are small and completed loading times measurable, but neither is available
  for failed requests. The saved process metadata reports both models resident and a
  Gemma4 size of 742,318,406 bytes versus an on-disk tag size of 8,021,618,941 bytes.
  These are different fields. The snapshot has no accompanying collection timestamp or
  exchange envelope tying it to a failure; it is not a time series, busy-state record,
  proof of full GPU offload, or sufficient evidence of a memory problem.
- **Capture visibility:** a confirmed limitation, not a confirmed cause. Current
  [streaming documentation](https://docs.ollama.com/api/streaming) describes NDJSON
  progress; the [thinking API](https://docs.ollama.com/capabilities/thinking) exposes
  thinking and answer chunks separately. Streaming would make progress observable
  during a prospective request; it cannot recover the missing historical traces.

The linked official documentation was checked on 2026-11-25. It is current documentation,
not a pinned account of every Ollama 0.40.9 implementation detail. Frozen metadata says
both challengers support boolean thinking, including false. Recheck identity and supported
controls before any future freeze; do not silently substitute a different service/model.

## Proposed next probe — not approved or executed

Start with **one Qwen3.5 case, two new generation requests, seven minutes overall,
180 seconds per generation, no retries**. Use the previously timed-out availability
case (`accepted_status_answer`). A single model/case keeps the first probe small;
Gemma4 and quality comparisons would be separate follow-ups.

[proposal.json](proposal.json) and the proposed
[false](proposed-requests/01-think-false.json) /
[true](proposed-requests/02-think-true.json) requests are concrete preparation inputs.
They are not an execution freeze. Relative to the old
request, both enable streaming for observation; within the fresh pair, **only `think`
differs**. Run false first, true second. Preserve the model/digest, complete messages,
schema, temperature, context and unspecified token/keep-alive settings. Do not use the
cached true request as a substitute for the fresh control. Streaming changes the
historical configuration, so this pair tests a prospective setting effect; it cannot
prove the cause of an earlier non-streaming timeout.

Before asking to execute, prepare and independently review a separate streaming capture
adapter, test it against authored local/fake responses, and freeze its exact source,
requests, identities and accounting. It must:

1. Record request bytes, headers, timestamped raw chunks, first byte/thinking/content
   timing, final counters and all errors. Preserve partial bytes on timeout. Decode a
   draft only after a complete valid terminal response; never fabricate an answer.
2. Enforce a shared 420-second wall deadline including validation, metadata, loading,
   capture and cleanup, plus the 180-second generation deadlines. Record every attempted
   and unsent slot. Stop the entire probe at the first timeout, transport/identity drift,
   structural/literal failure, identified critical semantic defect or deadline; do not
   start another request behind uncertain server compute. No warm-up, unload/restart,
   automatic retry or configuration repair.
3. Retain the unchanged action decoder and manually check the unchanged availability
   criterion. Report completion, timing and any semantic defect separately. Keep raw
   thinking out of owner-facing notes; aggregate sizes/timing suffice for this diagnosis.

A completed false reply followed by sustained thinking in the true arm would support
testing that setting further on this case. No first event would leave queue/load/prefill/
runner causes unresolved. A completed pair with comparable timings would weaken the
simple thinking hypothesis. A timeout without chunks would remain inconclusive. Do not
infer missing-answer correctness or use this negative control to claim work retention.

One ordered pair cannot establish causation, reliability, a general speed ranking or
product quality. False-first cold loading and true-second cache effects remain order
limits; report returned load/prompt timings and observed conditions. Repetition, reverse
order, other cases, a token-cap experiment or a Gemma4 probe need separately agreed scope.

No new model call or runtime setting has been applied for this proposal. The owner's
request to investigate is not a specified inference allowance; the old unused slots do
not transfer. Production integration, full regression, current Obsidian usefulness,
Built and owner `shipit` remain pending.
