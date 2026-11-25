# Chief state

Updated: <date/time and timezone>
Chief checkout: <absolute path>
Chief core terminal: <verified address; never infer from focus or legacy pane IDs>
Desktop context: <verified space/tab IDs if applicable; child workers need no pane>
Milestone branch / PR: <branch and link>
Integration HEAD: <commit>
Objective: <current authorized objective>
Acceptance: <observable completion criteria>
Authorization limits: <inference budget, manual acceptance and merge gates>

Read AGENTS.md, NEXT_SESSION.md and plan.md before using this ledger. Reconcile it
against Git and live Herdr state after a restart. This file is local to the Chief checkout.

| Task | Status | Depends on | Owned paths | Base / worker commit | Worktree | Child terminal / parent terminal / name | Revisions | Contract / evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

Statuses: queued, running, blocked, review, revision, accepted, rejected, integrated, verified.
Use `verified` only after integration checks pass. Preserve failure/block reasons below.

## Next actions

<What can run now, what is waiting, and what evidence or owner decision is needed.>

## Worker cleanup

<Active or intentionally retained checkouts; accepted workers retired; removed paths;
verified recovery archive and retained branches for any dirty work. Historical IDs
are not current runtime targets.>

## Verification and handoff

<Exact commits checked, commands/results, reviewer findings, PR/CI state, remaining gates.>
