# M10 handoff — 2026-11-13, quoted-selection diagnostic stopped

Continue on `m10/notes-guided-enhancement`, [PR #16](https://github.com/MattMSumner/meeting-notes/pull/16).
Read AGENTS.md, `.chief/CHIEF.md`, the reviewable draft section of plan.md and the
[latest report](evaluation/m10/reviewable-draft/diagnostic-2/results/report.md).
Use the Herdr skill for delegated work. Keep local task state in ignored `.chief/STATE.md`.

## Current outcome and authorization

The owner approved “six requests” for the frozen quoted-selection candidate: the same
six synthetic cases, at most six local qwen3:30b requests / fifteen minutes, no retries.
That once-only run **stopped after two requests in 184.814 seconds (3m05s)**. One draft
compiled; the second response failed with `Source references must be unique`; four cases
were unsent. Both replies and all metadata/errors remain captured. No retry or resumption
followed. **The four unused slots authorize neither restart nor another experiment.**

Overall outcome is **INCOMPLETE**, not a quality pass. The
[completed additional-context draft](evaluation/m10/reviewable-draft/diagnostic-2/results/01-additional/draft.md)
retains both undertakings, owners and timing, with original writing separate, but repeats
content heavily. The rejected price response duplicates speech references, selects a
price fact as an action/decision and puts a written price in its speech-only summary
with speech-only citations. Those raw defects were not published as a compiled draft.
No price conflict or calculated relationship was asserted.

Availability, cancellation/replacement, partial cancellation and qualified timing were
never reached. Do not claim that source quotations fixed the original invented-work or
surviving-work failures. Literal wording constrains prose, not admissibility, relevance,
qualifier coverage or completeness. Do not normalize the rejected reply and regrade it.

## Product direction and next work

The owner confirmed that a useful draft requiring review saves time, and approved the
normal/incomplete authored presentation (“Yeah these look good!”). Keep that direction.
Suggested actions remain ordinary Markdown; the user promotes them while editing in
Obsidian. Writing stays separately attributed. Automatic conflict classification is
deferred. Draft labels still permit no wrong facts, unsupported obligations or lost work.

The faithful-action-extraction successor is implemented offline and its approved bounded
experiment is now accounted for. Application behavior still follows V11; M10 is unbuilt.
Before another model run, reassess the smallest model-facing task: reduce avoidable
protocol burden and inspect whether work extraction should be evaluated separately from
summary generation. This is a recommendation, not an implemented replacement or approved
new experiment. Do not add semantic validators or repeatedly rerun the same six cases by
reflex. Any next candidate needs concrete criteria, independent review, exact freeze and
fresh request/time approval. Do not ask again for the completed run's approval.

Full forty-case regression, honest fresh-case provenance, production persistence and
current synthetic Obsidian usefulness acceptance remain required before Built. Numerical
latency/review-effort targets are not agreed. Production integration must bind sections
to complete snapshots/generations, preserve prior successful output/protected edits and
use atomic saving; incomplete optional analysis differs from missing associated input.
Only explicit owner `shipit` authorizes `git shipit`; never merge on GitHub.

## Current source and evidence

- Source candidate: `9e369ad51b55ed324a5377463e76822a5951def6`.
- Freeze committed/pushed before inference: `77fd9d3526ce8759ab9915c852209be820d84c0b`.
- [Nineteen-entry freeze](evaluation/m10/reviewable-draft/diagnostic-2/manifest.json), SHA256
  `0cbaafa34c9f538eaa6b5cc43158d1f21429e7e85c197fc79372bc0f24ad28bf`.
- `extraction.py` accepts unique literal speech selections plus full selected context for
  actions/decisions; code supplies attribution/notices. Known-source literal failures
  retain independent valid items and explicit incomplete status. Unknown/structural
  failures reject the response. Summary/review prose remains generated.
- `quoted_diagnostic.py` preserves the first generator/driver and uses single-use results,
  exact request/source hashes, raw capture, identity checks and bounded child deadlines.
  No retry/resume exists. A killed client cannot prove server compute cancellation.
- Two POSTs plus eight metadata GETs, all HTTP 200. Both replies have `done=true` and
  `done_reason=stop`; no transport/truncation errors, overrun or identity drift. Ollama
  0.40.9 / qwen3:30b digest
  `ad815644918f0eaab341c12b67837cc6dd4562342cdaf118f83d5d554cb37226`, temperature zero,
  thinking enabled, context 32768. One saved draft and the failed decode replay exactly.
- [Results](evaluation/m10/reviewable-draft/diagnostic-2/results/report.md) include every
  raw response, request, status, before/after identity, launch/final, independent assessment,
  Chief verification and a separate result manifest. Frozen/runtime bytes were unchanged.
- Formatting, lint, strict types and **1234 offline tests pass**; six model/hardware
  integration tests excluded. Capture is unchanged. Engineering review at `9e369ad`
  passed independently with no findings/formal repairs. Accounting/replay is no quality
  proof. Independent post-capture assessment was read-only and not blinded.

[Six authored quoted previews](prototypes/reviewable_draft/quoted-previews/index.md) show
intended behavior, with zero inference. All six first-contract replies are incompatible
with the new wire contract; incompatibility is not semantic improvement. Six familiar
cases, only two captured once, establish no reliability, full regression, measured owner
editing-time benefit or current Obsidian acceptance.

## Immutable earlier checkpoints

Never rewrite prior captures, assessments, frozen declarations or failed verdicts.
All **486 historical/sealed entries + 18 first-freeze + 157 first-result entries** verify;
all forty original regression inputs and six first-diagnostic drafts remain exact.

The [first draft diagnostic](evaluation/m10/reviewable-draft/diagnostic-1/results/report.md)
used all six requests in 5m13s: four cases meet criteria, one invents meeting-rescheduling
work from availability, one fails useful surviving-work handling without changing facts.
No transport/format failures or unsent cases. Source `2934d1004fb592d5ff0708fa2068532c7d51b543`,
freeze `1a3acebc8192647aa114ec16728264cba414ab93`, manifest SHA256
`8c1b2ee279047f3c751311c73e0c9ff4680b0e5cc0afbd7fc4b147d283680168`. All six saved drafts
replay. No further allowance transfers from that completed run.

The [V11 evaluation](evaluation/m10/v11/results/report.md) failed quality: baseline40/40,
proposed34/40, six blocked and one published false unit-conversion conflict. Baseline has
eight critical failure cases. The approved forty-pair/arm run used109requests in98m46s;
167unused requests authorize nothing. Source `fb3b130fb0d6a48859b96c7e9e74ffbd6152c878`,
freeze `e866b10e23ebf4c359c0c7e643f92cb8a3640c37`;34wrapper-10 and17wrapper-9 generations
replay faithfully, including historical mistakes. Reporting tools passed separate review
at `795c38db2aafd125ab6ffe91836e59cf8156d423`; never rerun historical mutating verifiers.

## Separate follow-up

Leave `/private/tmp/meeting-notes-safeguards` and the unrelated recovery issue alone.
The processing-spawn failure after confirmed orphan shutdown can clear a pending session;
repair it separately with a synthetic regression. This evaluation changes no capture or
recovery behavior. Never read or publish real meeting content in prompts/logs/reports.
