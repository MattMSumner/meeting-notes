# M10 V10 — bounded conflict-completeness candidate

Frozen offline before inference. **No model run, repetitions or request budget are authorized.**
M10 remains unbuilt; this candidate has no quality result. V1–V9 inputs/results and baseline
199dd62 remain unchanged. provenance.json identifies the implementation commit; sha256.json
covers source, prompts, schemas, fixtures, expectations, settings, rubric and runner.

## Placement and contract

A separate comparison stage runs before summary generation when handwritten passages exist.
It receives every saved transcript and note passage, with stable T/N IDs, plus meeting context.
It partitions each note passage into ordered atomic claims. Exact note quotes concatenate to
the entire passage, including punctuation and whitespace. A sentence containing multiple facts
or a fact plus a request must split into multiple claims. Code assigns N1.C1, N1.C2, etc.
within a passage, in returned order. Nonfactual context, headings and requests also receive
explicit coverage; they cannot silently disappear.

Every claim has a note account, zero or more transcript accounts, one outcome and a reason.
Accounts contain source ID, exact quote, kind (fact/commitment/context/request) and structured
subject, quantity, unit, period, scope and epistemic status. Missing dimensions are null.
Outcomes are consistent, additional, conflicting or uncertain. Consistent/conflicting require
spoken accounts; additional is unmatched and has no transcript accounts. Uncertain may be
unmatched or matched. Request/context notes cannot be factual conflicts. Source kinds, exact
quotes, duplicate accounts and the exact note partition are checked mechanically.

Matching, atomic splitting, qualifier preservation and classification remain model work.
A whole passage incorrectly called one claim can pass text coverage. An incorrect consistent
or additional classification can pass validation. Shared numbers/keywords never mechanically
establish subject identity, agreement or conflict. The evaluation must expose such failures;
reference integrity, structured dimensions and complete text coverage are not proof of semantic
completeness. Different periods, units, scopes and statuses can explain different values.

## Compilation and review

The comparison is fixed after validation and supplied to summary generation alongside all
original sources and context. The summary draft's conflicts array must be empty; it cannot
silently replace or add to the comparison. Code assembles each conflicting account from the
exact quotes. Disputed source references in core prose become unresolved references; unaffected
sources in mixed prose remain attributed quotes. For a partly disputed transcript statement,
its full text remains an attributed quote explicitly marked as containing an unresolved account.
Additional and consistent note claims are copied into From your notes. Written-only requests
never create spoken actions. Uncertain claims show both available accounts and the model's
unverified explanation in a persistent review warning, rather than an agreement or hard conflict.
Uncertainty alone does not consume a summary correction.

Independent commitments/decisions retain the existing code assembly and omission diagnostics.
Factual disputes do not automatically dispute actions from adjacent sources. Only comparison
accounts explicitly classified as commitments cause commitment review; a genuinely disputed
commitment is retained with its original timing for review. Relative dates and uncertainty are
never converted to an invented calendar date. The model still has to cite the right sources.

## Bounds, failures and context

With notes: at most **four** requests, two initial and two corrections: comparison initial plus
at most one correction, then summary initial plus at most one correction. Without note passages:
comparison is skipped, at most two summary requests. There are no transport retries, chunking,
truncation, hidden passes or selective reruns. Malformed JSON or failed coverage/references can
use the comparison correction. A valid uncertain result is final comparison evidence. Failure
of either comparison attempt blocks summary generation. Transport/length/missing-message errors
stop that stage immediately. Existing numeric-warning fallback can retain the first validated
summary if a summary correction fails, with warnings visible and comparison unchanged.

Both stages use qwen3:30b, temperature zero, thinking enabled, context 32768 and transport timeout
600 seconds. Each added initial comparison incurs sequential inference latency; correction adds
another request. Four sequential request timeouts could nominally take about 40 minutes; this
is not a measured latency estimate or a strict overall wall-clock bound.

For EVERY initial/correction request, code constructs the full JSON body first, including model,
settings, complete schema, full sources/context and that stage's entire correction history.
Summary requests additionally contain the entire selected comparison. The same conservative
estimate is used: ceil(len(json.dumps(body, ensure_ascii=False)) / 3) + 4096 reply/thinking tokens.
If that exceeds num_ctx, the attempt is saved as unsent and fails. This accounts for all request
characters; it is not an exact tokenizer measurement. Nothing is silently dropped to fit.
proposed/request-schemas.json records both actual stage schemas for each case. Generic draft,
comparison, published summary and wrapper schemas are separate artifacts.

Wrapper 9 / grounding-v8 saves source snapshots, both stages' requests/replies/findings/selections,
summary and compilation warnings together via atomic summary.json replacement. Failed attempts
are also recorded in attempts/. Audit-save or summary-save failure preserves the previous
successful generation and its evidence. Abrupt process death can still prevent attempt archival.
Rendering validates and recompiles only saved inputs/replies; no original note read or inference.
Wrappers 1–8 retain their historical compilers and validators, including V9's known missed conflict.

## Evaluation gate still requires approval

The 13 original pairs are unchanged; nine new synthetic pairs discriminate units, periods,
scope, epistemic status, additive context and multiple claims in one passage. expected.json
freezes expected behavior before any output is viewed. Neither the familiar cases nor the
implementer's new cases are independent held-out evidence. A separately authored unseen set
would improve confidence; it is outside this freeze and any future run must identify it first.

Agree case count, repetitions, per-arm ceilings and total budget before invoking the runner.
For reference, all 22 cases in both arms for one repetition have an upper bound of 176 requests
(88 per arm); the proposed bound is actually 74 because seven cases skip comparison.
The baseline retains its historical four-request ceiling; the proposed arm has four with notes.
Using the fixture-specific proposed ceiling of 74 plus baseline 88 gives 162 total.
These ceilings are cost calculations, **not approval**. The unused V9 allowance cannot be reused.

Use rubric.md and expected.json, score every selected result, record all stage attempts and
failures, and replay every selected proposed result as wrapper 9 from saved evidence. A hard
missed/invented conflict, silent agreement over uncertainty, incomplete output or spoken
commitment regression fails the gate. No tuning or selective reruns inside a scored run.
After a passing quality gate, current synthetic Obsidian acceptance must cover publication,
links, protected writing, failures/review warnings and later rendering. Do not merge or add a
Built note before both gates and merge authorization.
