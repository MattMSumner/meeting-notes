# M10 evaluation freeze v2 — not run

This revision addresses the failed v1 conflict qualification and conditional deadline
checks. Only the proposed prompt and schema descriptions change. The five synthetic pairs,
baseline source at `199dd62`, model, settings, numeric checks and bounded retries are
unchanged. The v1 inputs, results and scoring remain preserved in the parent folder.

The proposed instructions now put competing values in Conflicts, refer to unresolved
topics from core sections, and require complete alternative/conditional wording in each
action item's due field. They also discourage unsupported document/deployment specificity,
duplicating tasks as decisions without a separate agreement, and copying emphasis cues as
meeting facts. These changes are candidates, not a demonstrated quality fix.

`rubric.md` is copied verbatim from the v1 scoring contract. Success still requires no
critical failures, no spoken-commitment regression, and useful written context. In
particular, a conflict section does not excuse settled claims elsewhere, and a conditional
task does not excuse a shortened due field. The same cases now serve as regression
material after being inspected; this is not an unseen generalization evaluation.

Use `scripts/evaluate-enhancement.py --freeze v2` with the chosen arm, repetitions, request
budget, exclusive output path and `--run`. The default remains v1 so old commands keep
selecting their original inputs. `runner.py` archives the runner version for provenance;
invoke the script in `scripts/` so its repository-relative paths resolve correctly.

Proposed budget for separate approval: three repetitions of each of five cases for both
arms, with at most 60 requests per arm (120 total, including corrections). Rerun the
baseline as a contemporaneous control rather than spending its allocation on tuning.
Record Ollama version and model digest before and after; preserve outputs outside the
repository until reviewed. Do not call the models as part of unit verification.

The manifest covers the exact inputs, prompt, schema, source, rubric, settings, and runner
snapshot. Do not modify this freeze after inference starts. Any further revision requires
a new version. M10 remains unbuilt until quality acceptance passes; the user previously
reported the manual Obsidian workflow complete.
