# Chief state

Updated: <date/time and timezone>
Chief checkout: <absolute path>
Milestone branch / PR: <branch and link>
Integration HEAD: <commit>
Objective: <current authorized objective>
Acceptance: <observable completion criteria>
Authorization limits: <inference budget, manual acceptance and merge gates>

Read AGENTS.md, NEXT_SESSION.md and plan.md before using this ledger. Reconcile it
against Git and live Herdr state after a restart. This file is local to the Chief checkout.

| Task | Status | Depends on | Owned paths | Base / worker commit | Worktree | Workspace / pane / agent | Revisions | Contract / evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

Statuses: queued, running, blocked, review, revision, accepted, rejected, integrated, verified.
Use `verified` only after integration checks pass. Preserve failure/block reasons below.

## Next actions

<What can run now, what is waiting, and what evidence or owner decision is needed.>

## Verification and handoff

<Exact commits checked, commands/results, reviewer findings, PR/CI state, remaining gates.>
