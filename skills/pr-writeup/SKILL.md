---
name: pr-writeup
description: "Rewrite the title and description of an EXISTING pull request so it reads like an engineering write-up instead of a list of commits. Triggers '/ktkit:pr-writeup <#N|url>', 'viết lại description cho PR', 'sửa title + mô tả PR', 'rewrite this PR description'. Reads the full body of every commit on the PR plus the changed-file stat — NEVER the code diff. Free-form text passed as an argument (a ticket, a bug report, notes) is a first-class source alongside the commit bodies. Detects the repository's own PR template and commit conventions, so it works on any repository. Writes English prose and keeps business-domain nouns verbatim in their original script when the sources use them. NEVER creates a PR, commits, pushes, merges, comments, labels or touches an issue — the only write it makes is the PR's title and body. Not a PR creator, and not a code review. /ktkit:create-pr calls it when the PR it was asked for already exists."
argument-hint: "[<#N> | <url> | empty = the current branch] [--out [<file.md>]] [--apply] [--follow-refs] [--no-emoji] [free-form context: ticket, notes]"
user-invocable: true
---

# Rewrite a PR's title and description — `/ktkit:pr-writeup $ARGUMENTS`

```text
$ARGUMENTS
```

Turn an existing PR's commits into a write-up a reviewer can act on.

## 🎯 Identity — read before anything else

**This skill NARRATES what the author already wrote in the commits. It does not EXPLAIN code.**

| Activity | Owner | This skill |
|---|---|---|
| Rewriting an **existing** PR's title and body from its commit bodies | **`/ktkit:pr-writeup`** | ✅ **the entire product** |
| Grouping commits into work items, each one Impact → Cause → Fix | **`/ktkit:pr-writeup`** | ✅ yes |
| Creating a PR, rebasing, pushing, linking issues | your forge workflow | ❌ FORBIDDEN |
| Judging whether the code is correct, safe or well-written | `/ktkit:docs-review`, a code review | ❌ FORBIDDEN |
| Framing a problem, diagnosing a cause, writing a spec | `/ktkit:raise-issue`, `/ktkit:rca`, `/ktkit:feat-req-specs` | ❌ FORBIDDEN |

⛔ **The quality ceiling is the commit bodies.** That is a deliberate design decision, not a defect
to work around. If the commits are thin, the output is thin **and says so** (§Step 6).

## ⛔ Hard guardrails (NEVER break)

1. **Never read the code diff.** Not to "verify", not to "enrich", not for one file, not for one
   hunk. File names and per-file line counts are metadata and are allowed; diff *content* is not.
   No Read on source files, no grep of the working tree, no running tests or builds.
2. **The only write is the PR's title and body.** Never commit, push, merge, comment, label, close,
   touch an issue, or edit a file in the repository. With `--out`, not even that — the file is the
   only artifact and the PR is left alone.
3. **Never fabricate.** Every number, file name, identifier, table, column, endpoint and claim must
   come from a commit body, the stat, or the context the user pasted. Missing → say it is missing.
4. **Never invent an issue link.** Preserve existing `Closes` / `Part of` / `Related PRs` lines
   verbatim; never add one, never change one, never guess one.
5. **One generation pass.** No drafting-then-self-reviewing in loops, no subagents.
6. **Never ask a follow-up question** about thin commits. Warn and continue (§Step 6).

## Arguments

```
/ktkit:pr-writeup [<#N> | <url>] [free-form context]
    [--out [<file.md>]]    write the result to a file; leave the PR untouched
    [--apply]              skip the confirm gate (batch use)
    [--follow-refs]        allow opening the docs or issues the commits point at
    [--no-emoji]           replace the marker set with text prefixes
```

| Flag | What it actually means |
|---|---|
| `--out` | The one way this skill produces no forge write at all. With a path, that path verbatim; bare, `<repo-root>/.claude/claude/implemented/pr-<N>.writeup.md`. Step 8 stops there. |
| `--apply` | ⛔ Skips **the confirm gate only**. It does not skip Step 9's render check, and it does not license reading the diff. Meant for a batch run where a human already agreed to the rewrite. |
| `--follow-refs` | Off by default because a commit pointing at a design document invites an unbounded read. On, the referenced document may be opened — a diff still may not. |
| `--no-emoji` | For repositories that forbid emoji. ⛔ → `NOTE:`, ⚠️ → `WARNING:`, 🎯 → `VERIFIED:`, 🔴 → `IMPORTANT:`. The rules themselves do not change. |

No argument at all → the PR of the current branch. Everything not matched above is **free-form
context** and is treated as a source of equal standing to a commit body.

If the user passes `--code`, `--deep` or `--level 2`: print one line — *"there is no code-reading
tier; this skill reads commit bodies only"* — and continue. Never silently swallow the flag, and
never go read the diff because of it.

## Step 00 — Preflight

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py" \
  --groups forge --repo "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
```

Exit 1 → STOP and report; nothing has been read and nothing has been spent. With `--out` and no
explicit path, add `artifacts` to the groups so `<repo-root>/.claude/claude/implemented/` exists
before Step 8 writes into it. That layout is a rule of this plugin, not a discovery: never probe
for an alternative and never write outside `<repo-root>/.claude/`.

⚠️ `gh auth status` is **not** a usable gate — the preflight proves the token with a real API
request instead, for the reason written at the top of `preflight.py`. Do not substitute your own
check for it.

## Step 1 — Resolve the repository and the PR

Never hardcode a repository. In order:

1. The argument is a URL → parse `owner`, `repo` and `N` out of the URL itself.
2. The argument is a number → `gh repo view --json nameWithOwner -q .nameWithOwner` in the cwd.
3. No argument → `gh pr view --json number,url`.

```bash
gh pr view <N> --json number,title,body,headRefName,baseRefName,additions,deletions,changedFiles,state,url
```

⚠️ **Two transports.** Prefer the GitHub MCP tools (`pull_request_read`, `update_pull_request`) when
they are present; `gh` is the fallback. On some machines `gh` fails inside the sandbox with a
certificate error from a corporate proxy while working fine outside it — on that error, retry the
same command outside the sandbox. Do not conclude the PR is unreachable.

A `merged` or `closed` PR is edited **normally** — no extra confirmation beyond Step 7's gate.

## Step 2 — Fetch the material

⛔ **Never assume the PR's branch is checked out.** `git log <base>..HEAD` silently returns **0
commits** when HEAD is some other branch — and 0 commits looks identical to an empty PR. Prefer the
API, which is correct regardless of the working tree:

```bash
gh pr view <N> --json commits \
  -q '.commits[] | "=== \(.oid[0:8]) \(.messageHeadline)\n\(.messageBody)"'
```

Use git only after confirming the right branch is out:

```bash
HEAD_REF=$(gh pr view <N> --json headRefName -q .headRefName)
[ "$(git branch --show-current)" = "$HEAD_REF" ] || echo "not on the PR branch — use the API path"
BASE=$(gh pr view <N> --json baseRefName -q .baseRefName)   # never assume the default branch
git fetch origin "$BASE" && MB=$(git merge-base "origin/$BASE" HEAD)
git rev-list "$MB"..HEAD --count               # how many commits
git log "$MB"..HEAD --format='%s%n%b' | wc -c  # how big — measure BEFORE reading
git log "$MB"..HEAD --format='=== %h %s%n%b'   # SUBJECT + FULL BODY, every commit
```

**The changed-file stat.** ⛔ `gh pr diff --stat` does not exist. Get per-file counts from the API:

```bash
gh api --paginate 'repos/<owner>/<repo>/pulls/<N>/files' \
  --jq '.[] | "\(.additions)\t\(.deletions)\t\(.filename)"' | sort -rn
```

`--paginate` is required — the endpoint pages at 30 files, so a large PR silently truncates without
it. ⛔ Do not request the `patch` field: that is diff content, and guardrail 1 forbids it.

**Read every commit body in full.** No sampling, no pre-summarising: this is the only place the
information lives.

**The budget is a function of the PR, never a constant.** Use the two measurements above:

| Measured material | Behaviour |
|---|---|
| small (a handful of commits) | read everything, one pass |
| moderate | read everything, but group commits by theme before composing |
| very large (a long-lived branch, hundreds of commits) | ⛔ do not swallow it all — group by theme from the subjects first, open the full bodies of the representative commits per group, and **say in the output that grouping happened** |
| near-empty | → Step 6 |

## Step 3 — Split the file list

From the per-file counts fetched in Step 2, separate **authored** files from noise:

- generated files (designer/`*.g.*` output, generated clients, snapshots), lockfiles, minified or
  bundled output, vendored trees
- files whose change is one byte, a trailing newline, or pure formatting

This feeds rule **S8** (the misleading-diff warning) and the "skip this file" line in Notes for
Reviewers. ⛔ It does not license opening any of them.

## Step 4 — Detect the repository's conventions

| What | How | Fallback |
|---|---|---|
| **PR template** | `.github/PULL_REQUEST_TEMPLATE.md`, `.github/pull_request_template.md`, `.github/PULL_REQUEST_TEMPLATE/*.md`, `docs/PULL_REQUEST_TEMPLATE.md`, `PULL_REQUEST_TEMPLATE.md` | a generic skeleton: `## Summary` · `## Changes` · `## Testing` · `## Risks & follow-ups` · `## Notes for reviewers`, no emoji |
| **Commit type and scope** | 🎯 infer from **the PR's own commits**, already in context, at zero extra cost. ⛔ Do not read `CLAUDE.md`, a commitlint config, or the base branch | plain Conventional Commits |
| **Ticket or API code** | a recurring `[A-Z]{2,4}[- ]?\d{3,5}` in the branch name, the commits, or the paths | omit it |
| **Issue links** | ⛔ resolve none — preserve what the old body already has | — |

The **section frame belongs to the repository**; the **writing style (S1–S9) belongs to this skill**.
Never force one repository's frame onto another.

### Language

Prose is **English**, always, in every repository — including in a repository whose other ktkit
artifacts are written in Vietnamese. A PR body is read by the forge, so it follows the forge rule.

Scan the PR's own sources (commit bodies, file paths, pasted context) for non-Latin script
(CJK, Hangul, Cyrillic, Thai):

- **Found** → keep domain nouns **verbatim, in their original script**. The sentence around them is
  English. ⛔ Do not translate them, ⛔ do not add a gloss the source did not have.
- **Not found** → plain English, and ⛔ do not import a foreign term from anywhere.
- A commit written entirely in another language → **summarise the sentences into English**, keep the
  domain nouns. The line is: *domain noun = keep · descriptive sentence = translate*.
- ⛔ Identifiers (class, method, file, column, endpoint, enum) are never translated, in any mode.

## Step 5 — Compose

Read `references/style-guide.md` now — it carries the nine rules S1–S9 with worked right/wrong
examples. `references/exemplar.md` holds an annotated example of a finished body; open it when you
want to see the shape end to end.

The two things that decide whether this is any good:

1. **Group commits into work items, not a commit list.** The exemplar has 11 commits and 7 items.
   ⛔ The body is never a 1:1 rendering of `git log`.
2. **Each item answers Impact → Cause → Fix**, with a heading that states the symptom, and carries
   a measurement whenever a commit body provides one.

**Title**: `<type>(<scope>): <symptom>` — scope lowercase, comma-separated when several parts of the
system are touched, and a subject stating what was wrong and how much, never "fix bug".

## Step 6 — Thin commits: warn, then carry on

If the commit bodies are largely empty (subjects only, or almost no prose):

1. Use the free-form context from the arguments as an equal source, if the user gave one.
2. Compose the best body the material allows.
3. Mark the thin spots inline with `<!-- TBD: what is missing -->`.
4. Print the warning:

```text
⚠️ Thin source: items 3, 5 have no measured impact in their commit bodies.
   Marked <!-- TBD --> in the body — fill them in, or amend the commits and rerun.
```

⛔ Do not ask the user anything. Do not stop. Do not read code to compensate. A thin commit is an
input, not a reason to halt.

Equally: ⛔ never write a number, a count, a percentage or a "verified" claim the sources do not
contain. Line counts are **not** record counts, test counts, or user impact.

## Step 7 — Confirm gate 🔴

Updating a PR is outward-facing — people are reading it. Unless `--apply`:

1. Print the **full** proposed title and body, not a summary.
2. Print what changes against the current body, and call out everything preserved verbatim.
3. List the items marked `<!-- TBD -->`.
4. BLOCK until the user replies `confirm` / `abort` / `modify: <change>`.

⛔ Never drop or rewrite: existing `Closes #N` / `Part of #N` / `**Related PRs:**` lines, checkboxes
the author ticked by hand, embedded images, and any block a reviewer has already quoted.

No backup file is written — the forge keeps the description's edit history, and the diff printed
above is the pre-write check.

## Step 8 — Write

- `--out` → write the file, report the path, **stop. The PR is untouched.**
- otherwise → update the PR's title and body (MCP `update_pull_request`, or
  `gh pr edit <N> --title ... --body-file ...`).

The body must be a **real multi-line string**: no literal `\n`, no HTML entities, no extra wrapping
quotes. Checkboxes need `[x]` / `[ ]` at the start of their own line.

## Step 9 — Verify the render

Re-fetch the PR and check the body contains real `## ` headings and no escaped sequences. If it is
malformed, fix it with one more update, then report. Print the final line as:

```text
<url> — title updated, body rewritten (N items, M TBD)
```

## Edge cases

| Case | Handling |
|---|---|
| No argument and the branch has no PR | STOP and say so. Do not create one — creating a PR is not this skill. |
| The PR is merged or closed | Edit normally. The gate in Step 7 is the only approval needed. |
| 0 commits returned by `git log` | Almost always the wrong branch is checked out. Re-fetch through the API before believing it. |
| Commit bodies are empty | → Step 6. Warn, mark `<!-- TBD -->`, continue. Never ask, never read code. |
| The stat is dominated by generated files | → S8. Say so in the body before the reviewer opens the diff. |
| The old body has hand-ticked checkboxes or a quoted block | Preserve verbatim. Step 7 must call out what was preserved. |
| `gh` fails with a certificate error inside the sandbox | Retry the same command outside it. Not evidence the PR is unreachable. |
| The user asks for a code-reading tier | Print the one-line refusal in §Arguments and continue. |
