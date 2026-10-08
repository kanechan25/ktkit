<!-- group: Publish | order: 44 -->
# ktkit:create-pr — a branch's commits become an open PR, conflicts with its target already resolved

Opens a pull request from a branch into its target and writes the title and body from the **full
bodies of the commits** it carries — plus the issue it is for, related issues, your free-form text and
what the current session already established. ⛔ It never reads the code diff. After the PR exists it
always hands it to `/ktkit:resolve-conflict-pr`.

```
/ktkit:create-pr [free-form context] [--from <branch>] [--to <branch>]
```

Source: `--from`, else the branch you are on. Target: `--to`, else `dev`, else `develop` — both
present is asked once, neither is a stop, and the default branch is never picked by inference.

## The cases

```bash
# the branch you are on → dev (or develop, whichever the repository has)
/ktkit:create-pr

# another branch → dev, whatever is checked out
/ktkit:create-pr --from bugfix/inline-note-wording

# a release PR: what dev carries into main, summarised per bundled PR
/ktkit:create-pr --from dev --to main

# the PR is for an issue: its body is read too, linked as Part of
/ktkit:create-pr this resolves https://github.com/<owner>/<repo>/issues/123

# the same, closing the issue on merge, plus a related one
/ktkit:create-pr --issue 123 --closes --related 98

# a Japanese PR, opened as a draft to look at first
/ktkit:create-pr --lang ja --draft
```

## Flags

| Flag | What it does |
| ---- | ------------ |
| `--from <branch>` | The source branch. Unpushed → pushed with `-u`; ahead → pushed; diverged → stop. Never a force push. |
| `--to <branch>` | The target branch. Must exist on the remote. |
| `--mode simple\|full` | `simple` is the default. `full` is reserved and stops with "not implemented yet". |
| `--lang en\|ja` | The PR's language, `en` by default. Vietnamese is never used — `vi` falls back to `en`. |
| `--issue <#N\|url>` | The issue this PR is for: read in full, linked as `Part of #N`. Repeatable. An issue link in the free-form text counts as one. |
| `--related <#N\|url>` | A related issue: read for context, linked, never closed. Repeatable. |
| `--closes` | Links every `--issue` as `Closes #N` instead. |
| `--draft` | Opens the PR as a draft. The conflict step still runs. |

## Where the body comes from

| Source | Weight |
| ------ | ------ |
| full commit bodies | the main source |
| the `--issue` body, labels, comments | the problem and its acceptance criteria |
| free-form text you pass | equal to a commit body |
| this session | equal to a commit body — only what was actually said or run here |
| changed-file names and line counts | to warn when generated files make the diff look bigger than the work |

What no source states is marked `<!-- TBD -->` and listed in the output. Nothing is invented.

## Do not

| Anti-pattern | Why |
| ------------ | --- |
| Expect it to read the code to fill a thin commit | It never opens the diff. The fix is a commit body that says why. |
| Run it when a PR for the same branches is already open | It prints that PR's URL and stops; `/ktkit:pr-writeup` rewrites a body. |
| Rely on it to aim at `main` when there is no `dev` | It stops instead. Pass `--to`. |
| Expect `--mode full` to do something | Not built yet. |

## See also

`/ktkit:resolve-conflict-pr` runs at the end of every run. `/ktkit:pr-writeup` rewrites the body of a
PR that already exists.
