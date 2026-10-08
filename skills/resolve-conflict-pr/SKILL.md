---
name: resolve-conflict-pr
description: "Resolve the merge conflicts of an EXISTING pull request against its base branch and push the result back to the PR, without touching the branch you have checked out. Triggers '/ktkit:resolve-conflict-pr <#N|url>', 'PR này đang bị conflict, fix đi', 'merge dev vào PR này', 'resolve conflict cho PR', 'this PR has conflicts with its base'. Reads the PR's head and base from the forge, never from the local checkout. Works in a detached temporary worktree, merges the base into the head, explains why each hunk conflicts from the commits on both sides, and resolves it by taking one side, both, or a rewrite that keeps both intents. Proves with a script that no line either side added was lost, runs the repository's own verify command, then commits and pushes with a plain push. Stops to ask only when the two sides contradict each other's intent. Never rebases, never force-pushes, never creates a branch."
argument-hint: "<#N | url> [--report [<file.md>]] [--dry-run]"
user-invocable: true
disable-model-invocation: true
---

# Resolve a PR's conflicts — `/ktkit:resolve-conflict-pr $ARGUMENTS`

```text
$ARGUMENTS
```

## 🎯 Identity

The PR says which branch goes into which. This skill reads that, merges the base into the head in a
place of its own, understands every conflict before touching it, and pushes a merge commit that
loses nothing either side wrote. **Your checkout, your working tree and your stash are never
touched** — you can run it while standing on any branch, with uncommitted work.

## ⛔ Hard guardrails (NEVER break)

1. **Never create, switch or delete a branch.** All work happens in a `git worktree add --detach`
   under `$TMPDIR`. No `-b`, no `checkout <branch>`, no `switch`, no `stash`, in any repository.
2. **Merge, never rebase. Plain push, never `--force` and never `--force-with-lease`.** A rebase
   rewrites commits reviewers have commented on; a force push can erase somebody else's push.
3. **Never resolve a hunk you have not explained.** Every hunk gets a class from §Step 6 and a
   reason that cites a commit on each side before it is edited.
4. **Never push past a red gate.** §Step 8's three gates all pass, or nothing is committed.
5. **Never `git checkout --ours/--theirs` on a directory or on `.`** It silently discards the other
   side's clean merges in every file beneath it. Per file, only for the generated-file class.
6. **The only question this skill asks is an intent conflict** (§Step 7) — plus, once per
   repository ever, the verify command (§Step 8c). Everything else is decided and reported.
7. Commit messages are English.

## Arguments

```
/ktkit:resolve-conflict-pr <#N | url>
    [--report [<file.md>]]   also write the resolution table to a file
    [--dry-run]              resolve and verify, then stop: no commit, no push
```

| Flag | What it actually means |
|---|---|
| `--report` | Off by default — the result is printed in the chat and nothing is written. Bare: `<repo-root>/.claude/claude/resolve-conflict-pr/pr-<N>-<head>.conflict.md`, where `<head>` is the head branch name verbatim, so `feat/x/y` becomes the directories `pr-<N>-feat/x/` and the file `y.conflict.md`. With a path, that path verbatim. |
| `--dry-run` | Runs §Step 1–8, prints everything, and leaves the worktree in place with its path printed so you can inspect it. Nothing is committed, nothing is pushed. |

No PR argument → STOP and ask for one. The current branch is never assumed to be the PR's.

## Step 00 — Preflight

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py" \
  --groups runtime,vcs,forge,artifacts --repo "$(git rev-parse --show-toplevel)"
```

Exit 1 → STOP and report. An SSH `SKIP` is not a failure: fetch and push over SSH are retried
outside the sandbox, which denies the SSH agent socket.

## Step 1 — Read the PR from the forge

URL → `owner`, `repo`, `N` from the URL. Number → the repository of the cwd. Prefer the GitHub MCP
`pull_request_read`; `gh` is the fallback (retry outside the sandbox on a certificate error):

```bash
gh pr view <N> -R <owner>/<repo> --json number,url,state,headRefName,headRefOid,baseRefName,isCrossRepository,headRepository,headRepositoryOwner,maintainerCanModify,mergeable
```

| Read | Then |
|---|---|
| `state` is not `OPEN` | STOP — nothing to push to. |
| `isCrossRepository` and not `maintainerCanModify` | STOP — the head lives in a fork you cannot push to. |
| anything else | continue. `mergeable` is a hint only — §Step 5's local merge is the truth. |

## Step 2 — Find the remote

The remote is the one whose URL names `<owner>/<repo>` (`git remote -v`) — not necessarily
`origin`. None matches → STOP: this is not a clone of the PR's repository. Call it `R`. For a fork
head, the push target is the head repository's URL in the same scheme as `R`'s.

## Step 3 — Fetch, and pin both sides to SHAs

```bash
git fetch R <base>                     # then BASE_SHA=$(git rev-parse R/<base>)
git fetch R <head>                     # same-repo head: HEAD_SHA=$(git rev-parse R/<head>)
git fetch R pull/<N>/head              # fork head instead: HEAD_SHA=$(git rev-parse FETCH_HEAD)
```

`HEAD_SHA` ≠ the PR's `headRefOid` → fetch once more; still different → STOP (the PR moved while
you read it). Every later step uses the two SHAs, never a branch name.

## Step 4 — A worktree of its own

```bash
WT="$TMPDIR/ktkit-rcp-<N>"
git worktree list --porcelain | grep -q "^worktree $WT$" && git worktree remove --force "$WT"
git worktree add --detach "$WT" "$HEAD_SHA"
MB=$(git merge-base "$HEAD_SHA" "$BASE_SHA")
```

`--force` is used on that path only, and only because it is this skill's own leftover from an
interrupted run. Any other path is never removed.

## Step 5 — Trial merge

```bash
git -C "$WT" -c merge.conflictStyle=zdiff3 merge --no-ff --no-commit "$BASE_SHA"
git -C "$WT" status --porcelain     # UU AA DU UD AU UA DD = the conflicted paths
```

`zdiff3` needs git ≥ 2.35; older → `diff3`. Both show the merge base between the two sides, which
is what tells you who actually changed what.

- Clean, and the forge said `CONFLICTING` → the forge's view was stale; go to §Step 8.
- Clean otherwise → `git -C "$WT" merge --abort`, clean up (§Step 11), print "no conflict" and stop.

## Step 6 — Understand each conflict before touching it

Per conflicted file:

```bash
git log --format='%h %an %s' "$MB..$BASE_SHA" -- <file>   # what the base side did, and why
git log --format='%h %an %s' "$MB..$HEAD_SHA" -- <file>   # what the PR did, and why
git show -s --format=%B <sha>                             # the body, for the commits behind a hunk
```

Then read each hunk's three versions (ours / base / theirs) and give it **exactly one** class:

| Class | Recognised by | Resolution |
|---|---|---|
| **one-sided** | Against the base, only one side changed meaning; the other only reformatted, reordered or touched whitespace | That side's version, with the other side's formatting where it is the base branch's convention |
| **additive** | Both sides added independent entries at the same spot — imports, enum members, routes, DI registrations, config keys, list items | **Both**, ordered by the file's own convention (sorted stays sorted) |
| **convergent** | Both sides changed the same logic, the two intents are compatible | A rewrite that carries both intents. Say which line of each side it carries |
| **generated** | Lockfiles, generated clients, migration snapshots, build output | Never merge text. Lockfile: take the base side, then regenerate from the merged manifest with the package manager's own lock-only command. Snapshot: keep every migration from both sides, then rebuild the snapshot so it reflects both |
| **intent** | One side deletes or replaces what the other side changed; both sides set the same value differently on purpose | → §Step 7. Never guess |

A file deleted on one side and modified on the other (`DU`/`UD`) is **intent** unless the deleting
side's commit says where the code moved — then it is **convergent**: apply the change at the new home.

## Step 7 — Intent conflicts: the one question

All of them, in **one** block, once: per hunk the file, both versions, the commit on each side and
what each was for, and your recommendation. Wait for the answer. Apply it. **From here the run does
not stop again** for anything but a red gate — the answer is the approval for commit and push.

## Step 8 — Three gates, all green before commit

**a. Nothing unresolved.** `git -C "$WT" diff --name-only --diff-filter=U` prints nothing, and every
resolved file is `git add`-ed.

**b. Nothing lost** — every line either side added since `MB` is still there:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/resolve-conflict-pr/scripts/line_survival.py" \
  --repo "$WT" --base "$MB" --ours "$HEAD_SHA" --theirs "$BASE_SHA"
```

`MARK` → fix, always. Each `LOST` line is restored unless it is one of exactly two things, written
down next to it: the line was carried over in a changed form (cite the line that replaced it), or the
user's answer in §Step 7 removed it. "It looked redundant" is not one of them. Re-run until exit 0
or every remaining `LOST` has one of those two reasons.

**c. Still builds.** The command lives in
`<repo-root>/.claude/claude/resolve-conflict-pr/verify.cmd` — one shell line per check, run from the
worktree root. Missing → ask once, write the file, continue; `none` in the file → skip, and say so in
the output. A fresh worktree has no installed dependencies, so the file must install them itself if
the check needs them (`npm ci && npx tsc --noEmit`). A network failure inside the sandbox → retry
outside it.

Red → is the merge the cause? Run the same line on `BASE_SHA` in a second detached worktree. Red
there too → pre-existing, record it and continue. Otherwise fix it in `$WT` — a symbol the base side
renamed that the PR still calls is the usual one — and re-run b and c. **Third red → STOP**, keep the
worktree, print its path and the failure. Nothing is pushed.

`none` means no build ran, so look for that usual one by hand: every declaration the base side
removed or renamed (`git diff "$MB" "$BASE_SHA"`) must have no remaining use in `$WT`.

`--dry-run` stops here: print §Step 12's output and the worktree path.

## Step 9 — Commit

```bash
git -C "$WT" commit -F <msgfile>
```

```text
Merge branch '<base>' into <head>

Resolve conflicts with <base> at <BASE_SHA short>.

- <path>: kept both sides (additive: <what each side added>)
- <path>: took <side> (one-sided: <why>)
- <path>: rewrote to keep both intents (convergent: <what each carried>)
- <path>: regenerated (generated: <command>)
```

## Step 10 — Push

```bash
git -C "$WT" push R HEAD:refs/heads/<head>     # fork head: the head repository's URL instead of R
```

The merge commit descends from `HEAD_SHA`, so this is a fast-forward. **Rejected → somebody pushed
meanwhile:** start over from §Step 3 once. Rejected twice → STOP and say so. SSH failure → retry
outside the sandbox. ⛔ A rejection is never answered with `--force`.

## Step 11 — Confirm, then clean up

Re-read the PR: `headRefOid` must equal the pushed SHA. `mergeable` right after a push is often
`UNKNOWN` while the forge recomputes — report that as it is; claim "no conflicts" only on
`MERGEABLE`. Then `git worktree remove "$WT"` (plus the base worktree from §Step 8c, if one was made).

## Step 12 — Output

In the chat, always:

```text
PR #<N>  <head> ← <base>   merge base <MB short>
| File | Hunk | Class | Taken | Why (base commit · PR commit) |
gates: unresolved 0 · lost 0 (2 justified) · verify <command> green
pushed <sha short> → <head>   mergeable: <state>
```

With `--report`, the same content goes into the file too. Nothing is written otherwise.

## Red flags — stop and re-read the guardrails

| Thought | Reality |
|---|---|
| "Rebase gives a cleaner history" | It rewrites reviewed commits and needs a force push. Merge. |
| "Push was rejected, `--force-with-lease` is safe" | It overwrites the push that just landed. Start over from §Step 3. |
| "This side's version is obviously right, take it for the whole file" | The clean hunks of the other side die with it. Hunk by hunk. |
| "The LOST line looked redundant" | Not one of the two reasons. Restore it. |
| "Build is slow, the merge is textually clean, push" | Textually clean is where renamed-symbol breakage hides. Gate c, or `none` and the manual check. |
| "I'll quickly check out the PR branch locally" | Your checkout is the user's. The worktree is yours. |

## Edge cases

| Case | Handling |
|---|---|
| The cwd is not a clone of the PR's repository | STOP at §Step 2 and say which repository is needed. |
| The PR is a draft | Resolve normally — a draft can still be pushed to. |
| The base side force-pushed and `MB` is odd | The merge still uses the SHAs fetched in §Step 3; say in the output that the base history was rewritten if `MB` is not on `R/<base>`'s first-parent chain. |
| Many conflicted files of the generated class only | Regenerate each; gate b ignores nothing, so report its LOST lines as "regenerated". |
| A pre-push or commit hook fails | It is a red gate. Fix and retry; never `--no-verify`. |
