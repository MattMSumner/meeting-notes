# Task <id>: <short objective>

Role: implementer | investigator
Chief checkout: <absolute path; read context only, do not write here>
Worker checkout: <absolute path>
Worker branch: <agent/run/task>
Base commit: <full SHA>
Dependencies: <accepted prerequisite commits, or none>

## Objective and context

<One bounded objective and why it matters. Include relevant files/decisions and
the applicable handoff limits. Use synthetic material only.>

## Ownership and constraints

- Allowed writes: <explicit files/directories; none for an investigator>.
- Read AGENTS.md and the supplied context; ask the Chief if another write is needed.
- Work only in the assigned checkout. Do not delegate or launch other workers.
- Do not push, open PRs, merge, run `git shipit`, change credentials/configuration or
  spend model evaluation budget. No real meeting data, frozen-evidence changes or
  unrelated cleanup. Carry over any task-specific exceptions explicitly agreed by the owner.
- Revision limit: two cycles. Report blocked if scope, evidence or permission is missing.

## Acceptance criteria

<Specific observable behaviors, including compatibility and failure behavior where needed.>

## Validation

<Exact targeted commands and required checks. Implementation workers run all applicable
AGENTS.md checks before committing. No inference unless separately and explicitly budgeted.>

## Handoff

Reply with STATUS (PASS, BLOCKED or FAIL), acceptance results, changed files, exact
commands and results, risks and decisions needed from the Chief. Implementers commit
their accepted scope on the worker branch and report the SHA plus any uncommitted or
untracked files. Keep plan.md changes in separate `Plan: ...` commits. Investigators
return file/line evidence without changes. PASS is a worker claim pending Chief review.
