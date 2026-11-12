# Chief workflow

One Codex session owns the objective, delegates bounded tasks through Herdr, reviews
evidence, and integrates accepted work on the milestone branch. Workers implement or
investigate in separate worktrees. The owner still authorizes merging with `shipit`.
For small changes, work directly without workers.

## Start or resume

The official [Herdr skill](https://github.com/herdrdev/herdr/tree/master/skills/herdr)
is installed in `~/.codex/skills/herdr/`. New Codex turns can discover it. Herdr must
already be running; check `HERDR_ENV=1` before using its control commands. If the skill
is absent on another machine, install it from that official source first.

Tell the main Codex session:

> Act as Chief using .chief/CHIEF.md and the Herdr skill. Read the current handoff,
> then plan the next authorized task before launching workers.

Add the objective when starting new work. Activating the workflow alone does not
authorize implementing a milestone or running model evaluations.

Initialize local state once per Chief checkout, without overwriting existing files:

```sh
mkdir -p .chief/tasks .chief/results .chief/runs
test -e .chief/STATE.md || cp .chief/templates/state.md .chief/STATE.md
test -e .chief/DECISIONS.md || cp .chief/templates/decisions.md .chief/DECISIONS.md
```

Read AGENTS.md, NEXT_SESSION.md and the relevant section of plan.md. Reconcile the
ledger with `git status`, `git worktree list` and live Herdr agents on every restart.
If `herdr pane current --current` reports `pane_not_found`, inherited caller IDs may
be stale. Rediscover the matching checkout with `herdr agent list` and use its live,
explicit IDs; never fall back to whichever pane happens to be focused.
Ignored state and result files exist only in the Chief checkout; they are not copied
or synchronized by Git worktrees. Worker assignments must include the task contract
itself or an explicit absolute path to it.

## Delegate and verify

1. Define acceptance criteria and dependencies. Copy [the task template](templates/task.md)
   into `.chief/tasks/<id>.md`; fill every field before dispatch. Record the base commit,
   allowed writes and required checks. Serialize overlapping write sets.
2. Check the installed CLI with `herdr --help`, `herdr worktree` and `herdr agent`.
   Create one worktree per implementation worker from the Chief's current milestone
   commit, not automatically from main. Commit needed inputs first: worktrees cannot see
   the Chief's uncommitted edits. Use a unique branch such as `agent/<run>/<task>` and
   an absolute path under the ignored `.chief/worktrees/` directory. Record the actual
   worktree path, workspace/pane IDs and agent name in STATE.md.
3. Use `herdr worktree create --cwd <chief-checkout> --branch <branch> --base <sha>
   --path <absolute-path> --label <task> --no-focus`. Parse the returned JSON IDs;
   never guess pane identifiers. Start a named Codex agent in the returned shell pane
   with `herdr agent start <name> --kind codex --pane <pane-id> -- --sandbox
   workspace-write --ask-for-approval on-request -c sandbox_workspace_write.network_access=false`.
   Use `--sandbox read-only` for investigation/review. Inherit the configured model;
   change models or reasoning effort only when requested or agreed for the task.
4. Submit the filled contract with `herdr agent prompt <name> <task-text>`. Dispatch
   independent assignments before waiting. Use bounded waits (at most 60 seconds per
   call), then inspect state/output and keep the owner updated. `done`/`idle` is a
   terminal state, not evidence that acceptance criteria passed. On a timeout, inspect
   before retrying; a prompt may already have been delivered. Never answer an approval
   dialog by blindly sending keys.
5. Collect the worker's response using `herdr agent read <name> --source
   recent-unwrapped --lines 160`, then record it using [the result template](templates/result.md)
   in `.chief/results/<id>.md`. If output cannot be recovered, ask for a file handoff
   in the worker's temporary directory and copy it into the Chief's results. This
   avoids granting workers write access to the Chief checkout.
6. Independently inspect `git diff <base>...<worker-commit>`, including changed paths,
   test evidence and uncommitted/untracked files. For nontrivial work, assign
   [the reviewer contract](templates/review.md) against that exact commit in a separate
   review worktree. A reviewer does not share a checkout with an active implementer.
7. After acceptance, the Chief cherry-picks or merges the worker commits into the
   milestone branch and runs the required repository checks from AGENTS.md. Run Swift
   tests if capture changed; model evaluations require their own agreed budget. Update
   the existing milestone PR (or open one when appropriate), with `🤖 Codex:` first in
   every posted body. Only the owner's `shipit` authorizes `git shipit`.
8. Record verification and the PR/commit references. Remove only worktrees/panes created
   for this run after checking handoffs and commits are retained and no work would be
   lost. Do not force-remove dirty worktrees or delete unrelated branches/sessions.

Start with at most three implementers and one reviewer. Use fewer when tasks overlap,
and stop for a decision after two failed revision cycles. No orchestration daemon is
needed; the Chief manages the ledger and Herdr supplies the runtime.

## Durable knowledge and local evidence

| Location | Responsibility |
| --- | --- |
| `AGENTS.md` | Shared repository rules and checks |
| `plan.md` | Milestone decisions and Built notes, in separate `Plan: ...` commits |
| `NEXT_SESSION.md` | Current milestone handoff and authorization limits |
| `.chief/CHIEF.md`, `.chief/templates/` | Committed workflow and reusable contracts |
| `.chief/STATE.md`, `.chief/DECISIONS.md` | Ignored local coordination state |
| `.chief/tasks/`, `.chief/results/`, `.chief/runs/` | Ignored contracts, handoffs and evidence |
| `.chief/worktrees/` | Ignored worker checkouts |

Promote durable decisions into plan.md or NEXT_SESSION.md before concluding a milestone;
the ignored ledger is not a substitute for a committed handoff. Keep credentials and real
meeting data out of all agent context, even ignored files. Git isolation and task ownership
are coordination conventions, not credential isolation or enforcement of allowed paths.

Command syntax was checked against Herdr 0.9.5 and Codex CLI 0.167.2. Learn updated
syntax from the installed CLI and [Herdr documentation](https://herdr.dev/tui/docs/).
The worker launch uses the sandbox/approval controls described in the
[official OpenAI documentation](https://learn.chatgpt.com/docs/sandboxing).
