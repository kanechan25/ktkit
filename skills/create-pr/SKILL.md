---
name: create-pr
description: "Open a pull request from a branch into its target and write its title and body from the full bodies of the commits it carries — never from the code diff. Triggers '/ktkit:create-pr', 'tạo PR', 'tạo PR từ nhánh này vào dev', 'create a PR for this branch', 'open a PR from dev to main'. Source is the current branch or --from; target is --to, else `dev`, else `develop`. Also reads the issue the PR is for, related issues, free-form text in the arguments and what the current session already established. Writes English by default, Japanese with --lang ja, never Vietnamese. Pushes an unpushed source branch with a plain push. After the PR exists, always hands it to /ktkit:resolve-conflict-pr so a conflict with the target is resolved at once. Works in any repository; nothing about one repository is assumed."
argument-hint: "[free-form context, issue #N or URL] [--from <branch>] [--to <branch>] [--mode simple|full] [--lang en|ja] [--issue <#N|url>] [--related <#N|url>] [--closes] [--draft]"
user-invocable: true
disable-model-invocation: true
---

# Open a PR from its commits — `/ktkit:create-pr $ARGUMENTS`

```text
$ARGUMENTS
```

## 🎯 Identity

The commits on the branch already say what was done and why. This skill turns them — plus the issue
the work is for and whatever this session already knows — into a PR a reviewer can act on, opens it,
and makes sure it does not sit there conflicting with its target.

| Activity | Owner |
|---|---|
| Opening the PR, composing its title and body | **this skill** |
| Resolving a conflict with the target | `/ktkit:resolve-conflict-pr`, called by this skill |
| Rewriting the body of a PR that already exists | `/ktkit:pr-writeup` |
| Judging the code | a code review — not this skill |

## ⛔ Hard guardrails (NEVER break)

1. **Never read the code diff.** Not a hunk, not "to verify". File names and per-file line counts
   (`--numstat`) are metadata and allowed; diff content is not. No reading source files either.
2. **Never fabricate.** Every number, identifier, behaviour and claim in the body comes from a commit
   message, an issue, the user's arguments, or something this session actually established. Missing
   → `<!-- TBD -->`, never a guess.
3. **Never invent an issue link.** Links come only from `--issue`, `--related`, the arguments, the
   session, or the commit messages.
4. **Never create or switch a local branch**, never check anything out. Pushing an existing local
   branch to the remote is the only ref this skill makes.
5. **Plain push only.** Never `--force`, never `--force-with-lease`. Diverged → STOP.
6. **PR prose is English or Japanese.** Never Vietnamese, whatever language the session, the
   commits or the issue are written in.
7. The only writes are: the push of the source branch, the PR itself, and what
   `/ktkit:resolve-conflict-pr` does. No issue is edited, commented on, labelled or closed.

## Arguments

```
/ktkit:create-pr [free-form context]
    [--from <branch>]       the source branch; default the branch checked out now
    [--to <branch>]         the target branch; default `dev`, else `develop`
    [--mode simple|full]    default simple; full is reserved and not built yet
    [--lang en|ja]          the PR's language; default en
    [--issue <#N|url>]      the issue this PR is for; repeatable
    [--related <#N|url>]    a related issue, linked only; repeatable
    [--closes]              link --issue as `Closes #N` instead of `Part of #N`
    [--draft]               open the PR as a draft
```

| Flag | What it actually means |
|---|---|
| `--from` | Named → that branch, from the remote, whatever is checked out. Absent → `git branch --show-current`; a detached HEAD is a STOP. |
| `--to` | Named → that branch, and it must exist on the remote. Absent → `pr_material.py base` picks `dev`, else `develop`; both → ask once; neither → STOP. Never the default branch by inference. |
| `--mode full` | Prints `full mode is not implemented yet — run without --mode, or with --mode simple` and stops before anything is read. |
| `--lang` | `en` or `ja`. `vi` (or any other value) → one line saying the PR is written in English instead, and the run continues in `en`. |
| `--issue` | Read in full — body, labels, comments — and linked as `Part of #N`. A same-repository issue is `#N`; another repository's is its full URL. |
| `--related` | Body read for context, linked under a related line, never as closing. |
| `--closes` | Applies to every `--issue`. A forge closes the issue only when the PR merges into the default branch. |
| `--draft` | The way to look at the result before reviewers are notified. |

**Free-form text** is everything that is not a flag: a ticket, notes, an instruction. It is a source
of equal standing to a commit body. An issue URL or `#N` inside it is an `--issue`, unless the
sentence presents it as related ("related to", "see also", "liên quan") — then it is `--related`.

## Step 00 — Preflight

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py" \
  --groups runtime,vcs,forge --repo "$(git rev-parse --show-toplevel)"
```

Exit 1 → STOP. An SSH `SKIP` is not a failure: fetch, `ls-remote` and push over SSH are retried
outside the sandbox, which denies the SSH agent socket.

## Step 1 — Repository and remote

`owner/repo` from `gh repo view --json nameWithOwner -q .nameWithOwner`. The remote `R` is the one
whose URL names it (`git remote -v`) — not necessarily `origin`. None → STOP.

## Step 2 — The source branch, on the remote

```bash
git fetch R
git rev-parse --verify -q "refs/heads/<from>"      # local copy?
git rev-parse --verify -q "R/<from>"               # remote copy?
```

| Local | Remote | Action |
|---|---|---|
| exists | missing | `git push -u R <from>` |
| ahead of remote | exists | `git push R <from>` |
| equal, or behind | exists | nothing to push; a behind local copy is said in the output |
| diverged | exists | ⛔ STOP — pushing would need a force or a merge, and neither is this skill's call |
| missing | exists | use the remote copy |
| missing | missing | STOP — no such branch |

Uncommitted changes in the working tree are not in the PR; say so in the output when `<from>` is the
checked-out branch. `FROM_SHA=$(git rev-parse R/<from>)` after any push.

## Step 3 — The target branch

```bash
git ls-remote --heads R | sed 's#.*refs/heads/##' > "$TMPDIR/heads"
python3 "${CLAUDE_PLUGIN_ROOT}/skills/create-pr/scripts/pr_material.py" base \
  [--to <to>] --heads $(cat "$TMPDIR/heads")
```

Exit 0 → its output is `<to>`; with `--to`, check it is in the list, else STOP. Exit 3 → ask once
which of `dev` / `develop`. Exit 4 → STOP and ask for `--to`. `TO_SHA=$(git rev-parse R/<to>)`.

`<from>` = `<to>` → STOP.

## Step 4 — Is there a PR already?

```bash
gh pr list -R <owner>/<repo> --head <from> --base <to> --state open --json number,url
```

One exists → print its URL, point at `/ktkit:pr-writeup` for rewriting its body, and STOP. Never
open a second one.

## Step 5 — The commits, measured before read

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/create-pr/scripts/pr_material.py" commits \
  --repo . --to "$TO_SHA" --from "$FROM_SHA" > "$TMPDIR/material.json"
git diff --numstat "$TO_SHA...$FROM_SHA"            # names and counts only — never the patch
```

`stats.commits` = 0 → STOP: nothing to merge. Entries of kind `sync-merge` carry no work — leave them
out of the body. `stats.message_bytes` decides how to read:

| Measured | Behaviour |
|---|---|
| small | read every message in full, one pass |
| large (a release PR, hundreds of commits) | read every subject; open full bodies per `pr-merge` / `squash-pr` entry; children only where the merge body is thin. Say in the output that grouping happened |

## Step 6 — Every other source

| Source | Read | In the body |
|---|---|---|
| `--issue` | body, labels, comments | the problem statement, acceptance criteria, `Part of` / `Closes` |
| `--related` | body | a related line |
| `issue_refs` from the commits | not read | linked under related, unless already linked above |
| free-form text | as written | equal to a commit body |
| this session | decisions, reasons, measurements, runs actually done here | equal to a commit body — only what was really said or run, never what was planned |

Issues are read with the GitHub MCP `issue_read`, `gh issue view` as fallback (retry outside the
sandbox on a certificate error). An issue that cannot be read is linked anyway and said in the output.

## Step 7 — The repository's conventions

| What | How | Fallback |
|---|---|---|
| PR template | `.github/PULL_REQUEST_TEMPLATE.md`, `.github/pull_request_template.md`, `.github/PULL_REQUEST_TEMPLATE/*.md`, `docs/PULL_REQUEST_TEMPLATE.md`, `PULL_REQUEST_TEMPLATE.md` | `## Summary` · `## Changes` · `## Testing` · `## Risks & follow-ups` · `## Notes for reviewers` |
| Title type and scope | from the commits already read | plain Conventional Commits |

The section frame belongs to the repository; the writing inside it belongs to
`references/style-guide.md`.

## Step 8 — Compose (simple mode)

Read `references/style-guide.md` now. `references/exemplar.md` shows a finished body end to end.

**A feature PR** (mostly `commit` entries): group commits into work items, each Impact → Cause → Fix
with a heading that states the symptom. ⛔ Never a 1:1 rendering of the log.

**A release PR** (mostly `pr-merge` / `squash-pr` entries): one line per bundled PR — `#N` and what it
delivered, from its merge body or its children — grouped by kind (features, fixes, other). Every ⚠️
caveat a bundled PR's messages state is collected into one `Risks & follow-ups` section.

**Links**, at the top of the body: `Part of #N` (or `Closes #N` with `--closes`) per `--issue`, then
`Related: …` for the rest. Nothing else is linked.

**Thin sources** — commit bodies near empty and nothing else to draw on: compose what the material
supports, mark the gaps `<!-- TBD: what is missing -->`, and print which ones. Do not ask, do not
read code to compensate.

**Title:** `<type>(<scope>): <symptom>`, per the style guide, in the PR's language.

## Step 9 — Open the PR

GitHub MCP `create_pull_request` (head `<from>`, base `<to>`, `draft` per `--draft`), or:

```bash
gh pr create -R <owner>/<repo> --head <from> --base <to> --title "<title>" --body-file <file> [--draft]
```

The body is a real multi-line string — no literal `\n`, no HTML entities. Re-fetch the PR; if the
body did not render (`## ` headings missing, escaped sequences), fix it with one update.

## Step 10 — Conflicts, always

Invoke `/ktkit:resolve-conflict-pr <PR url>` — every time, not only when the forge says
`CONFLICTING`: the forge's answer right after creation is usually `UNKNOWN`, and that skill's local
trial merge is the real test. It stops by itself when there is nothing to resolve.

## Step 11 — Output

```text
PR #<N>  <from> → <to>   <url>   [draft]
title: <title>
sources: <k> commits (<m> entries, <s> sync merges left out) · issues <list> · free-form · session
pushed: <nothing | -u <from> | <from> ahead by <n>>
TBD: <items, or none>
conflict: <none | resolved and pushed <sha> | stopped: <reason>>
```

## Red flags

| Thought | Reality |
|---|---|
| "The commit is vague, one look at the diff would settle it" | Guardrail 1. Mark it TBD. |
| "There is surely an issue for this, I'll link #N" | Guardrail 3. Only links a source gave. |
| "No dev or develop — main is obviously the target" | Exit 4 is a STOP. A PR into `main` by accident is the expensive mistake. |
| "The local branch diverged, a force push fixes it" | Guardrail 5. STOP and say so. |
| "The session is in Vietnamese, write the PR the same way" | Guardrail 6. English, or Japanese with `--lang ja`. |
| "The forge says mergeable is UNKNOWN, skip the conflict step" | Step 10 runs every time. |
