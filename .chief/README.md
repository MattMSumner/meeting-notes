# Chief workflow

One Codex session owns the objective, delegates bounded tasks through Herdr, reviews
evidence, and integrates accepted work on the milestone branch. Workers implement or
investigate in separate Git worktrees. The owner still authorizes merging with `shipit`.
For small changes, work directly without workers.

## Start or resume

Read the installed Herdr skill at `~/.codex/skills/herdr/SKILL.md`. The installed
manuals, not the older TUI documentation, define the current desktop workflow:

```sh
hc --skill
hc --help
hc run --help
herdr-app --skill
herdr-app commands
```

`hc` / `herdr-core` manages terminals and agents. `herdr-app` manages desktop spaces,
tabs, panes and focus. The older `herdr` CLI has a separate backend; its workspaces,
sessions, pane IDs and `HERDR_*` variables do not address desktop/core terminals.
If PATH lacks the current CLIs, use `~/.local/bin/herdr-core` for `hc` and, on this
Mac, `/Applications/Herdr.app/Contents/MacOS/Herdr` for `herdr-app`. Do not start the
app, an interactive picker, or a server just to inspect state. For desktop details,
read `~/.config/herdr-app/AGENTS.md` (or `$HERDR_APP_HOME/AGENTS.md`) and any
`AGENTS.local.md` beside it; do not edit generated guides/types or desktop settings
as part of orchestration.

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
ledger with `git status`, `git worktree list` and live core state on every restart:

```sh
herdr-app ls
herdr-app status
hc ls --json
hc get <candidate-chief-terminal-id> --json
```

Codex must run with `--no-daemon`, including templates and desktop launches, so
commands retain Herdr context. An existing daemon-backed session can lack
`HC_TERMINAL_ID` or use another terminal's identity. Verify the requesting Chief's
terminal using desktop space/tab membership and core foreground cwd, process,
title and labels; core `cwd` is only the launch directory. Focus alone, `HERDR_ENV=1`,
and legacy pane IDs do not identify the Chief. If necessary, inspect a candidate
with `hc read <id> --lines 0`; if it remains ambiguous, resolve the parent before
launching. Do not restart existing sessions to repair context.

Record the verified Chief terminal address explicitly. Ignored state and result files
exist only in the Chief checkout; Git worktrees do not synchronize them. Assignments
must include the filled task text or its explicit absolute path and the Chief's
report-back address. A child's `HC_TERMINAL_ID` identifies the child itself.

## Delegate and verify

1. Define acceptance criteria and dependencies. Copy [the task template](templates/task.md)
   into `.chief/tasks/<id>.md`; fill every field before dispatch. Record the base commit,
   allowed writes and required checks. Serialize overlapping write sets.
2. Create a separate Git worktree from the Chief's explicit milestone commit, not
   automatically from main. Commit needed inputs first: workers cannot see uncommitted
   changes in the Chief checkout. Use a unique branch and an absolute path under the
   ignored `.chief/worktrees/` directory:

   ```sh
   git worktree add -b <agent/run/task> <absolute-worker-path> <base-sha>
   ```

3. Inspect `hc templates`; use a fitting template only if its command preserves the
   intended model/settings and includes `--no-daemon` for Codex. Otherwise launch
   interactive Codex directly. Use a unique name and an explicit verified parent:

   ```sh
   hc run --bg --parent <verified-chief-terminal-id> --json --name <worker-name> \
     --cwd <absolute-worker-path> -- codex --no-daemon --sandbox workspace-write \
     --ask-for-approval on-request -c sandbox_workspace_write.network_access=false \
     "<filled contract, including hc send <verified-chief-terminal-id> reporting instructions>"
   ```

   Use `--sandbox read-only` for investigation/review. Inherit configured model and
   reasoning settings unless the owner agrees otherwise. Children appear beneath the
   Chief in the Agents list and belong to its existing tab/space without a pane.
   Do not add desktop labels or create a space, tab or split merely for delegation.
   Create a separate space only when requested; keep the person's focus unchanged.
4. Put the first assignment in the launch, then check the returned terminal address
   and `first_message.sent`. Creation does not prove readiness or delivery. Inspect
   `hc get <worker-id> --json` and `hc read <worker-id> --lines 160` before recovering
   failed delivery or retrying. Dispatch independent assignments before waiting.
   Use `hc wait <worker-id> --timeout 60` or
   `hc wait <verified-chief-terminal-id> --children all --timeout 60`.
   Timeouts are seconds and leave programs running; messages/timeouts can end a wait
   before all workers finish. Inspect the reason and continue useful work or wait
   again. Do not sleep/poll, blindly resend, or answer approval dialogs for the owner.
   Use `hc send --wait <worker-id> "<follow-up>" --timeout 60` for later turns.
5. Read the actual handoff with `hc read <worker-id> --lines 160`, then record it using
   [the result template](templates/result.md) in `.chief/results/<id>.md`. A worker
   reports done or stuck with `hc send <verified-chief-terminal-id> "<status>"`.
   While working/blocked/error, history reads return the screen marked incomplete;
   `done`/`idle` alone is not proof that acceptance criteria passed. If output cannot
   be recovered, ask for a file handoff in the worker's temporary directory and copy
   it into the Chief's results, without granting writes to the Chief checkout.
6. Independently inspect `git diff <base>...<worker-commit>`, including changed paths,
   test evidence and uncommitted/untracked files. For nontrivial work, assign
   [the reviewer contract](templates/review.md) against that exact commit in a separate
   read-only review worktree. A reviewer never shares an active implementer's checkout.
7. After acceptance, the Chief cherry-picks or merges the worker commits into the
   milestone branch and runs required AGENTS.md checks. Run Swift tests if capture
   changed; model evaluations require their own agreed budget. Update the existing
   milestone PR (or open one when appropriate), with `🤖 Codex:` first in every posted
   body. Only the owner's `shipit` authorizes `git shipit`.
8. Record verification and PR/commit references, then close out completed workers as
   described below. Keep worktrees only for active work, pending review/integration,
   or a specific recorded reason to retain them.

Start with at most three implementers and one reviewer. Use fewer when tasks overlap,
and stop for a decision after two failed revision cycles. The Chief manages the ledger;
Herdr Core supplies the runtime.

## Visibility, parenting and cleanup

An unlabeled worker with no pane or visible parent ancestry stays outside the desktop.
`herdr.space` / `herdr.tab` labels opt into desktop placement; missing/unknown tab or
space IDs can create layout. Labels are not parenting. When the owner requests a
view, use `herdr-app commands` to choose `terminal.peek`, `agent.focus` or
`terminal.keep` with an explicit child address. These change the display; preserve
focus unless the requested presentation requires changing it. `terminal.park` removes
a pane while leaving the terminal running. Desktop keep/park do not reparent it.
For requested new spaces/tabs, give useful names and use `--focus false` when they
should remain in the background; `pane.split` has no such focus option.

Parentage is set once at launch. The installed core schema and desktop command list
have no reparent command; correcting a wrong parent requires a safe relaunch after
preserving work. Children normally end with their parent's program. Do not default
to `--no-parent` or `--outlive-parent`, and never stop/restart shared cores or apps.

After acceptance, retain the result and confirm commits are integrated. Check for
running processes, staged/unstaged changes, untracked files and valuable ignored
logs/data before removing a worktree. For dirty work, preserve a verified private
archive with HEAD/branch, binary patches, source/untracked files and required local
evidence. Rebuildable compiler caches need not be retained. Keep worker branches
while needed for recovery. Stop/remove only the finished worker terminals being
cleaned up (`hc kill <worker-id>`, then `hc rm <worker-id>`), then use
`git worktree remove <path>`. Use `--force` only when the remaining dirty files have
been preserved and verified, or their discard was explicitly authorized. Record the
archive/disposition in STATE.md. Never delete unrecovered work or unrelated checkouts,
branches, terminals or databases; do not let completed checkouts accumulate indefinitely.

## Durable knowledge and local evidence

| Location | Responsibility |
| --- | --- |
| `AGENTS.md` | Shared repository rules and checks |
| `plan.md` | Milestone decisions and Built notes, in separate `Plan: ...` commits |
| `NEXT_SESSION.md` | Current milestone handoff and authorization limits |
| `.chief/CHIEF.md`, `.chief/templates/` | Committed workflow and reusable contracts |
| `.chief/STATE.md`, `.chief/DECISIONS.md` | Ignored local coordination state |
| `.chief/tasks/`, `.chief/results/`, `.chief/runs/` | Ignored contracts, handoffs, archives and evidence |
| `.chief/worktrees/` | Ignored active worker checkouts |

Promote durable decisions into plan.md or NEXT_SESSION.md before concluding a milestone;
the ignored ledger is not a substitute for a committed handoff. Keep credentials and real
meeting data out of agent context and committed artifacts. Git isolation and task ownership
are coordination conventions, not credential isolation or enforcement of allowed paths.
Historical `herdr` IDs in old results are evidence, not current desktop targets. Verify
syntax with installed manuals/help and `codex --help`; never launch samples or change
desktop settings to validate instructions.
