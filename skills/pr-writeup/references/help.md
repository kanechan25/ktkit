<!-- group: Publish | order: 45 -->
# ktkit:pr-writeup — an existing PR's commits become a write-up a reviewer can act on

Rewrites the **title and description of a PR that already exists**. It reads the full body of every
commit on the PR plus the changed-file stat, groups the commits into work items, and writes each one
as Impact → Cause → Fix. ⛔ It never reads the code diff, and the only write it makes is the PR's
title and body.

```
/ktkit:pr-writeup [<#N> | <url>] [free-form context]
```

No argument → the PR of the current branch. Anything that is not a number, a URL or a flag is
**free-form context** — a ticket, a bug report, your own notes — and it counts as a source of equal
standing to a commit body.

## The cases

```bash
# the ordinary case: a PR number, in the repository you are standing in
/ktkit:pr-writeup 412

# a PR in another repository — the URL carries owner, repo and number
/ktkit:pr-writeup https://github.com/<owner>/<repo>/pull/412

# the PR of the branch you are on, with the ticket pasted in as context
/ktkit:pr-writeup "ABC-123: slips print the wrong depot code on every depot"

# draft it into a file and leave the PR completely alone
/ktkit:pr-writeup 412 --out

# a batch run where the rewrite was already agreed — no confirm gate
/ktkit:pr-writeup 412 --apply

# the commits point at a design document, and you want it opened
/ktkit:pr-writeup 412 --follow-refs

# a repository whose review culture forbids emoji
/ktkit:pr-writeup 412 --no-emoji
```

## Flags

| Flag | What it does |
| ---- | ------------ |
| `--out [<file.md>]` | Writes the write-up to a file and **leaves the PR untouched**. Bare, the file is `.claude/claude/implemented/pr-<N>.writeup.md`; with a path, that path verbatim. |
| `--apply` | Skips the confirm gate. Nothing else — the render check after the write still runs. |
| `--follow-refs` | Permits opening the documents or issues the commits point at. Off by default; a diff is still forbidden, on or off. |
| `--no-emoji` | ⛔ → `NOTE:`, ⚠️ → `WARNING:`, 🎯 → `VERIFIED:`, 🔴 → `IMPORTANT:`. The rules do not change, only the markers. |

`--code`, `--deep` and `--level` are **not** flags of this skill. Passed anyway, they get one line
saying there is no code-reading tier, and the run continues.

## What you get

```
the PR's title and body, rewritten          the default — one forge write, nothing else
.claude/claude/implemented/pr-<N>.writeup.md   with a bare --out; the PR is untouched
```

Both go through the same confirm gate first: the full proposed title and body are printed, together
with what changes against the current body and what is preserved verbatim.

## The ceiling, stated plainly

**The output can only be as good as the commit bodies.** That is the design, not a defect. A branch
of `fix: update` subjects produces a thin body — and the skill says so, marks the thin spots with
`<!-- TBD -->`, and carries on. It will not ask you to fill the gaps, and it will not go read the
code to cover them.

The fix is upstream: write the body of the commit while you still remember why.

## Do not

| Anti-pattern | Why |
| ------------ | --- |
| Expect it to create a PR | It only edits one that exists. Creating, rebasing, pushing and linking issues are somebody else's job. |
| Expect a code review | It narrates what the author wrote in the commits. It never opens the diff, so it cannot judge the code. |
| Pass it a PR whose branch is not checked out and then trust `git log` | It fetches through the API for exactly this reason: on the wrong branch, `git log` returns 0 commits and an empty PR looks identical. |
| Ask it to "verify" a claim by reading the source | Every number must come from a commit body, the stat, or your pasted context. There is no tier that reads code. |
| Add an issue link through it | `Closes #N` and `Part of #N` are preserved verbatim and never invented. |
| Use `--apply` to move faster on a PR people are already reviewing | The gate is the only thing standing between a bad rewrite and an outward-facing page. |

## See also

`/ktkit:raise-issue` frames a problem before any work starts; this skill narrates the work after it
is finished. `/ktkit:feat-req-execute` and `/ktkit:bug-fix-execute` write the in-repository record of
what was implemented — the write-up here is the forge-facing half of the same story, in English
because the forge is read in English.
