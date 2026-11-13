# M10 V8 — compact complete requests

No inference has run. V8 changes the request representation to address the PR review's
meeting-size regression. It retains V7's prompt, model-facing output contract, compiler,
validation rules, 13 synthetic pairs, rubric, baseline `199dd62`, model/settings and retries.

Source-ID enums now live once in shared JSON-schema definitions; every reference field uses
those definitions through `$ref`. Generic prose sources reference the union of transcript and
handwritten IDs. Empty notes still disable notes/context conflicts. Unknown IDs and source-kind
violations remain subject to runtime validation. Live model behavior under the new grammar has
not been evaluated; passing structural tests is not a quality pass.

Source material is explicitly labelled by kind. Transcript rows contain `[ID, speaker, exact
text]`; handwritten rows contain `[ID, exact text]`. Source text and ordering are unchanged;
there is no silent truncation or chunking. Metadata remains separate. Saved audits still contain
full passage records, requests and replies. The existing conservative complete-request estimate
counts schema, source material, metadata, system prompt, correction history and reply allowance
before every send. Context remains 32768 by default; genuinely oversized requests still fail.

Production-path tests send every source in 5,202-word and 10,402-word synthetic transcripts to
a fake transport at default context. The latter request is about 79,000 serialized characters
(about 30,500 estimated tokens including reply allowance). These are capacity regression tests,
not a universal maximum duration: vocabulary, sentence count, notes and retries affect fit.

The production transport suite now covers malformed/truncated/missing replies, source labels,
settings, initial and correction context limits, audit records and failed correction retention.
Legacy transport tests remain explicitly identified as compatibility tests. All published V7
saved generations still validate; output compilation and wrapper version 6 remain unchanged.

Related application fixes keep orphaned capture in a retryable stopping phase until helper exit
is confirmed, and skip corrupt chooser entries individually. These do not invoke models.

V1–V7 frozen inputs and results remain unchanged. V7's single-run pass does not establish V8
quality. Repetitions and budget remain unset; evaluation and current manual acceptance are
pending. M10 remains unbuilt. Select this freeze with `scripts/evaluate-enhancement.py --freeze v8`
only after agreeing the run budget. No private meeting material is included.
