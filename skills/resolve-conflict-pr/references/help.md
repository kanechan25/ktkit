<!-- group: Publish | order: 46 -->
# ktkit:resolve-conflict-pr — a conflicted PR, merged with its base and pushed back without losing a line

Takes a PR that conflicts with its base branch, reads which branch goes into which **from the PR
itself**, merges the base into the head in a temporary detached worktree, explains every conflict
from the commits on both sides, resolves it, proves nothing either side added was lost, runs your
verify command, then commits and pushes. ⛔ Your checkout is never touched, and it never rebases,
force-pushes or creates a branch.

```
/ktkit:resolve-conflict-pr <#N | url>
```

## The cases

```bash
# the ordinary case: fix the conflicts and push, from whatever branch you are on
/ktkit:resolve-conflict-pr 412

# a PR in another repository — run it from inside a clone of that repository
/ktkit:resolve-conflict-pr https://github.com/<owner>/<repo>/pull/412

# first time on a PR you do not trust yet: resolve and verify, push nothing
/ktkit:resolve-conflict-pr 412 --dry-run

# keep a record of how each hunk was resolved
/ktkit:resolve-conflict-pr 412 --report
```

## Flags

| Flag | What it does |
| ---- | ------------ |
| `--report [<file.md>]` | Also writes the resolution table to a file. Off by default — the result is in the chat only. Bare: `.claude/claude/resolve-conflict-pr/pr-<N>-<head branch>.conflict.md`; with a path, that path. |
| `--dry-run` | Resolves and runs every gate, then stops: no commit, no push. The worktree is kept and its path printed. |

## When it stops and asks

Only for an **intent conflict** — one side deletes or replaces what the other side changed, or both
set the same thing differently on purpose. All of them come in one block. Your answer is also the
approval to commit and push: the run does not stop again unless a gate goes red.

Once per repository it also asks for the **verify command**, and keeps it in
`.claude/claude/resolve-conflict-pr/verify.cmd` — one shell line per check, run from the worktree
root. It must install dependencies itself when the check needs them; write `none` to skip building.

## The three gates before anything is committed

1. No unresolved path is left.
2. `line_survival.py` finds every line each side added still present, or each missing one has a
   written reason: carried over in a changed form, or removed by your answer.
3. The verify command is green — or red on the base branch too, which makes it pre-existing.

A third red on gate 3 stops the run with the worktree kept. Nothing is pushed.

## Do not

| Anti-pattern | Why |
| ------------ | --- |
| Expect a rebase | It rewrites reviewed commits and needs a force push. This skill only merges. |
| Expect a force push when the push is rejected | A rejection means somebody pushed. It starts over from the fetch, once. |
| Run it from a clone of a different repository | It finds the remote by the PR's `owner/repo` and stops when none matches. |
| Skip the verify command because the merge was textually clean | Textually clean is where a renamed symbol still called by the PR hides. |

## See also

`/ktkit:pr-writeup` rewrites the PR's description afterwards, from its commits.
