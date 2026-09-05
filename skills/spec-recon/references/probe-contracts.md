# Probe contracts

What each `spec-recon-*` agent is handed, what it must return, and the tool grant it runs on. The
lead dispatches from this file; `check_agent_table.py spec-recon` enforces the last table against
the agent files, so the two cannot drift.

## 1. Roles, models, tools

| Role | Agent | `tools` | Model |
| ---- | ----- | ------- | ----- |
| probe-code | `ktkit:spec-recon-probe-code` | `Read, Grep, Glob` | sonnet |
| probe-artifact | `ktkit:spec-recon-probe-artifact` | `Read, Bash` | sonnet |
| probe-vcs | `ktkit:spec-recon-probe-vcs` | `Read, Bash` | sonnet |
| probe-runtime | `ktkit:spec-recon-probe-runtime` | `Read, Bash` | sonnet |
| state-extract | `ktkit:spec-recon-state-extract` | `Read, Write, Grep, Glob` | sonnet |
| arbiter-impl | `ktkit:spec-recon-arbiter-impl` | `Read, Grep, Glob` | inherit |
| gap-design | `ktkit:spec-recon-gap-design` | `Read, Grep, Glob` | inherit |

Only three tool sets appear, and that is not tidiness. Tool grants on this harness are **not
monotonic**: a role declaring `Read, Grep, Glob, Bash` receives `Read, Bash`, with `Grep` and `Glob`
removed and no warning. Only three sets were ever probed directly, so only three are used:

| Set | `tools` | Base tokens per spawn |
| --- | ------- | --------------------: |
| A | `Read, Grep, Glob` | 6,619 |
| B | `Read, Bash` | 11,353 |
| C | `Read, Write, Grep, Glob` | 6,875 |

Three consequences worth stating before someone tries to improve on this:

1. **Set B costs ~4,700 more tokens per spawn** than set A. That is the schema of `Bash`, which
   carries the whole sandbox description. Three roles pay it; they pay it because they genuinely
   need a shell, not because a shell is convenient.
2. **A set B role has no `Grep` or `Glob` tool.** It searches through the shell, where two local
   traps apply: `grep` is a `ugrep` shim that honours `.gitignore` unless told otherwise, so a file
   that is git-ignored will not appear; and the shell is zsh, where an unmatched glob aborts the
   whole command line, so glob patterns used as flag values must be quoted.
3. **`arbiter-impl` deliberately has no `Bash`.** It is the role that refutes absence claims, which
   is search work, and granting it a shell would have taken away the tools it lives by. Git history
   it needs is precomputed by the lead into a file it can `Read` — the same arrangement
   `docs-review` uses for `docs-history.md`.

`probe-runtime` never receives MCP tools. MCP names inside an agent's `tools` frontmatter have never
been probed on this harness, and an unrecognised name is dropped in silence. Anything needing MCP
belongs to the lead, which already has it; the agent reads a file the lead wrote.

## 2. Dispatch blocks

The shape differs by kind, and getting it wrong wastes the entire agent. A reviewer handed a
`Write to:` line will spend its budget and be unable to deliver — that has happened, and it cost two
agents and roughly half a million tokens.

**Producer** — `state-extract`, `probe-artifact`, `probe-vcs`, `probe-runtime`:

```text
Read: <path> offset=<n> limit=<n>     # one range per agent; see §2b
Scope: <the caller's own words, verbatim>
Output language: <language>
Write to: <base>/evidence/probe-<kind>-<topic>.md
Return: the file path and a one-line count, nothing else
```

**Reviewer** — `probe-code`, `arbiter-impl`:

```text
Read: <path> offset=<n> limit=<n>
Items: <the identifiers or verdict ids, one per line>
Output language: <language>
# reviewers return rows in the reply; they have no Write and must not be asked for a file
```

### 2b. Ranges, and the escape hatch that keeps them honest

`plan_fleet.py` sizes shards in **bytes** and emits an explicit `offset`/`limit` per agent. Pass them
through. Two reasons, and the second is the expensive one:

1. **A line is not a unit of cost.** One line of minified markup can carry 50 KB while a line of
   prose carries 60 bytes, so a line-based shard billed anywhere from 20 KB to 2 MB for the same
   nominal size.
2. **An agent given a range reads once.** An agent given only a file gropes toward what it needs --
   grep, read, grep again -- and every earlier result rides along in its context for the rest of its
   life. The range does not change *what* it sees, only *how many times it pays to see it*.

⚠️ **A range without `NEEDS-WIDER` is not an optimisation, it is a defect.** An agent that cannot
find something inside its slice must return

```text
NEEDS-WIDER  <path>  <what it searched for>  <why it likely lies outside>
```

and the lead widens the range and dispatches again. Absence inside a slice is a fact about the
slice. Every reading role's body carries this; if you write a new one, carry it too.

**HTML**: strip tags to a temp file **first**, then apply the ranges to the stripped file. Measured
on a real 729 KB page, stripping removed 29%; the planner already accounts for that when sizing.

Never put the lead's reasoning in a dispatch block. A prober told what answer is expected finds it.

## 3. Return contracts

| Role | Returns | Never |
| ---- | ------- | ----- |
| probe-code | `EXISTS <id> <path>:<line> <line>` / `NOT_FOUND <id> tried: …` / `PARTIAL` | any statement about what it means |
| arbiter-impl | `REFUTED <vid> <path>:<line> <line>` / `UPHELD <vid> searched: … unsearched: …` / `UNSAFE <vid> <why>` | re-arguing the requirement |
| probe-artifact | a measurement table + a reproduce command, written to a file | a conclusion about correctness |
| probe-vcs | a state table + the endpoint per row, written to a file | any write to the forge |
| probe-runtime | raw rows + the exact query, written to a file | substituting seed or fixture data |
| state-extract | baseline + change surface + stated-as-future + gaps, written to a file | comparing against a spec |
| gap-design | `GAP` + `ANCHOR <path>:<line>` + `SHAPE` + `NEIGHBOUR` + `UNKNOWN` | an anchor it did not read; effort estimates; code |

## 4. Rules every probe carries

**`R-NOFAB`** — never name a table, column, function, endpoint, config key, file or enum value that
was not read off a line in a real file. If something must be mentioned before it is verified, mark
it `[unverified]` in the same sentence, never in an identifier column.

**`R-DERIVED`** — every number carries exactly one label: `[measured]` (read from the thing),
`[quoted]` (copied from a document), `[derived]` (computed). Two labels in one unlabelled sentence
is a defect `check_evidence.py` catches. The rule exists because a derived figure once got read as
an observation and had to be retracted mid-run.

**`R-ARTIFACT`** — absence in a derived source is not absence in the artifact. No probe may state
that something does not exist outside the region it actually searched, and the region must be named.

**`R-PARTIAL`** — running short of budget means returning **fewer items fully settled**, plus the
names of the ones not reached. Never half-settle everything: a report where each row is
half-checked cannot be told apart from a finished one by the person reading it.

**`R-BINARY`** — never regex a binary file. `.xlsx` and friends are ZIP archives of XML: use
`zipfile` plus `xml.etree.ElementTree`, resolve namespaces, resolve `sharedStrings`. `openpyxl` is
not installed and must not be assumed.

**`R-SANDBOX`** — `gh` cannot reach the network here and `git` cannot use an SSH remote here. Use
`gh auth token` for credentials and `urllib` for transport; treat a blocked command as
`not-accessed`, never as evidence that the thing is missing. `timeout` does not exist on macOS.
