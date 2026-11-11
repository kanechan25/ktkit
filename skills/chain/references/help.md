<!-- group: Chain | order: 10 -->
# ktkit:chain — a requirement in, a reviewed spec and plan out, as one run

Four skills in a row — analyse, self-clarify, spec, plan — with two things none of them has alone.

An append-only **ledger**: a question settled in analysis is never asked again in the spec, because
the spec reads the ledger instead of re-deriving.

And a **closing step**. Everything up to 06 compares one document with another, and documents can
agree perfectly with each other while the code does something else. Step 07 runs `/speckit-converge`,
the only step that opens the delivered code and asks whether it satisfies the spec — capped at two
rounds, because work still missing after two is a spec problem, not a code one.

Implementation is **off** unless you ask for it. `--full` goes all the way: implement, commit each
task with a body built from the run's own files, and open the PR through `/ktkit:create-pr`.

```
/ktkit:chain <requirement.md | "described request"> [flags]
```

## The cases, in the order you will meet them

```bash
# the ordinary case: a requirement file in, a reviewed spec and plan out
/ktkit:chain .claude/claude/prompts/share-links/expiry-rules.md

# no file yet — describe it instead, in quotes
/ktkit:chain "expiring share links: 24h default, owner can override to 7d"

# a bug report — name the lane rather than letting step 00 ask
/ktkit:chain .claude/claude/prompts/bugs/duplicate-refund.md --bug

# something that exists and works as designed, but must work differently
/ktkit:chain requirement.md --cr

# something that does not exist yet (--feature is the old name for this)
/ktkit:chain requirement.md --nr

# one file, no contract, no schema, tests already there — skip analysis and spec
/ktkit:chain requirement.md --trivial --execute

# stop at the spec; you will produce the plan some other way
/ktkit:chain requirement.md --plan no

# stop even earlier — after analysis, before any spec is written
/ktkit:chain requirement.md --to A

# go all the way and apply the change
/ktkit:chain requirement.md --execute

# further still: commit each task, then open the PR (from the branch you are on — check it out first)
/ktkit:chain requirement.md --nr --full

# the same, into a named target, as a Japanese draft
/ktkit:chain requirement.md --full --pr-to release/2.4 --draft --lang ja

# pick up a run that was interrupted, without re-minting IDs
/ktkit:chain requirement.md --resume

# start over; the old run directory is renamed, never deleted
/ktkit:chain requirement.md --fresh

# a hard ceiling on measured spend; reaching it winds the run down and pauses it
/ktkit:chain requirement.md --budget 400000

# wind down earlier than the default 96% of any session or weekly window
/ktkit:chain requirement.md --execute --wind-down 90
```

## Flags

| Flag | Default | When you need it |
| ---- | ------- | ---------------- |
| `--bug` / `--cr` / `--nr` / `--trivial` | read from `type:` at step 00, else asked | Names the lane outright. Nothing overrides it. Passing two is an error. `--feature` is an alias for `--nr`. |
| `--trivial` | — | The only lane with no analysis and no spec. All four conditions in `references/lanes.md` must hold, and it requires `--execute`. Crossing its 50,000-token ceiling escalates to CR with the reason recorded — it never extends the ceiling. |
| `--to A\|B\|C` | `C` | Stop after analysis (`A`), spec (`B`) or plan (`C`). |
| `--plan yes\|no` | asked at step 00 | Answers the plan question up front instead of being asked. |
| `--execute` | **off** | Runs phase D — the change itself. Off by default on purpose. Nothing is committed. |
| `--full` | **off** | `--execute`, then one commit per task the moment it passes review, then `/ktkit:create-pr` with the run's context. Checked at step 00 before anything is spent: on `dev`/`develop`/the default branch, a dirty tree or a detached HEAD is a stop — ⛔ the chain never creates a branch for you. |
| `--pr-to <branch>` | `dev`, else `develop` | With `--full`: the PR's target. Not `--to`, which names the phase to stop after. |
| `--draft` | — | With `--full`: open the PR as a draft. |
| `--lang en\|ja` | `en` | With `--full`: the PR's language. Commits are always English. |
| `--resume` | — | Restart at the first step marked `missing` or `partial`. Rows marked `complete` are never re-run: their ID allocations are cited downstream. |
| `--fresh` | — | Start at step 00. Deletes nothing — the old run directory is renamed `<base>.<timestamp>/`. |
| `--budget <token>` | none | Optional hard ceiling on what agents reported in `cost.jsonl`. Reaching it — not being forecast to reach it — runs the wind-down. Without it the window watch alone guards the run. |
| `--wind-down <pct>` | `96` | Any session or weekly window at this percentage — read every 100 s — stops new work: agents finish the sub-step in hand, `--full` commits what passed, `checkpoint.md` is written and the run pauses. The last 4% are the room for that. |
| `--contract` *(on `deviation.py`)* | — | Marks a divergence that changes what the spec **promises** — an acceptance criterion, an API shape, a dropped requirement. It becomes a gate at step 06 rather than syncing on its own. |
| `--ledger-scope run\|dir` | `run` | `dir` also reads sibling runs' ledgers in the same `prompts/<rel>/` and reports a match as **`FOREIGN`, exit 2** — a lead for a resolver, never a conclusion. |
| `--rounds N` | `2` | Self-clarify rounds per phase. |

## ⭐ What it costs, and where it stops

Four files land beside the ledger, and every figure in them is what an agent reported:

```
cost.jsonl · cost.md         what each phase and each agent cost
budget.jsonl                 the gate's verdict at every boundary
checkpoint.md                every milestone of every agent, stamped to the minute, and the run's status
dispatch.jsonl · dispatch.md what each agent was sent, against what it spent
lookup.jsonl                 every ledger lookup, and what it saved
```

### ⭐ The gate that costs nothing runs first

```
worker finishes ──► build · test · lint · typecheck        0 tokens
                              │
                        FAIL ─┴─ PASS
                          │        │
                   back to worker  superpowers:requesting-code-review
```

A reviewer dispatched over code that does not compile returns findings about a file the compiler
would have rejected in a second — and the run pays usage to be told something free. The test command
comes from the repository (`preflight --groups testcmd` says which file states it); when no file
does, the chain asks **once** and records the answer. ⛔ It never guesses `npm test`: a green from
the wrong command is worse than no gate.

### ⭐ Where it stops — measured, never forecast

`window_watch.py` runs in the background for the whole run and reads every session and weekly window
every 100 seconds. Nothing stops while all of them are under `--wind-down` (96%). The first one to
reach it trips the run into **wind-down**:

1. nothing new is dispatched;
2. each agent in flight finishes the sub-step it is in, marks it in `checkpoint.md`, and returns;
3. with `--full`, every task that passed its gate is committed; a task still running is not, and its
   last milestone and touched files are in the checkpoint;
4. the run writes `paused` into the checkpoint and the manifest, and prints the resume line.

`checkpoint.md` is **one file per run** — a section per agent, a line per sub-step, each stamped
`YYYY-MM-DD HH:MM` — and it is written as each sub-step finishes, not at the end. A window that runs
out mid-wind-down loses at most the sub-step in flight. `--resume` continues each task from its last
milestone.

⛔ No phase is refused on a forecast. An earlier gate would not start phase D because the window left,
converted to tokens, was less than phases A–C had cost — with 44% of the session unspent.

### What the ledger lookup saved

```bash
/ktkit:chain … --ledger-scope dir        # sibling runs as leads, never answers
```

```
lookups=34 · hits=19 (56%) · misses=15
spawns avoided=19  ⇒  ~125,761 tokens NOT spent   [derived: 19 x 6,619 base]
⚠️ base only — a resolver costs more once it reads anything, so this is a FLOOR
```

`self-loop.md` had always listed the lookup as one of five places the tokens are saved, with the
arithmetic; nothing counted the hits, so it was an assertion. Now it is a number, labelled as a floor
because it is one. The metric also lists near-misses between 0.45 and 0.60 — the only evidence for
whether `--threshold` sits where it should.

## ⭐ The spec still matches the code afterwards

A specification that disagrees with the code is worse than no specification: it reads as
authoritative and is quietly wrong. So every divergence is recorded **the moment it happens**, while
the reason is still known, and written into the spec at a boundary:

```
during implement   deviation.py add   → <chain-dir>/deviations.jsonl   ⛔ spec untouched
step 06            deviation.py lint  → exit 1 stops the sync
                   deviation.py render ┬→ spec.md block  (upsert, end of file)
                                       └→ .implt.md table
```

⭐ **Both come from one source, so they cannot disagree — reading `spec.md` alone is enough.** A
hand-written table in each file would be two authorings, and a reader finding them different has no
way to tell which is true.

⛔ **The spec is not edited during implement.** It would stop being a stable reference during the
phase that reads it, and an aborted run would leave a spec describing code that was rolled back —
worse than a stale spec, which was at least true of its own moment.

Three things the lint refuses, and each is a stop rather than a warning:

| Refused | Why |
| ------- | --- |
| a reason that is empty, `n/a` or `tbd` | ⭐ A diff shows *that* the code differs; it never shows *why*. Nobody can reconstruct it later. |
| an anchor whose line is gone | It reads as verified and is not. A line that merely *moved* is re-resolved and marked. |
| nothing recorded at all | Silence is not "nothing diverged". Say `deviation.py none` and it is stated, with when. |

**A contract-level change is a gate**, not a sync: mark it `--contract` and step 06 stops for
`confirm-with-me`. ⛔ "It could not be done" is not "it did not need doing" — that substitution, made
quietly, is how a requirement disappears without anyone deciding to drop it.

## What you get

Artifacts stay exactly where each skill already put them. The chain adds only a trace directory.

```
.claude/claude/chain/<rel>/<base>/
    manifest.md          ← the index: one row per step, and the resume instruction
    resolved.md          ← the ledger: every question, its answer, and who settled it
    steps/               ← 00-route.md · 01-analyze.md · … · 06-syncback.md · 07-converge.md

.claude/claude/analyze/<rel>/<base>.analyze.md         A
.claude/claude/specs/<rel>/<base>/spec.md              B
.claude/claude/specs/<rel>/<base>/plan.md              C
.claude/claude/implemented/<rel>/<base>.implt.md       D  (only with --execute)
```

With `--full`, also: one commit per task on the branch you are on (`Why:` · `What:` · deviations ·
`Verified:` · `Part of #N`, plus `Chain-Run` / `Chain-Task` trailers so a resume never commits twice),
`pr-context.md` in the run directory, and the PR. ⛔ Nothing under `.claude/claude/` is committed.

`<rel>` and `<base>` mirror the input's sub-path under `prompts/`. Read `manifest.md` first if a run
stopped — it is the index, and `--resume` reads the same file.

## Where it stops

A question reaches you only when a resolver could not settle it **and** being wrong would be
expensive. Everything else is answered from the repository and written to the ledger. If the run
stops, the manifest says at which step and why.

## Do not

| Anti-pattern | Why |
| ------------ | --- |
| Treat a `FOREIGN` row as an answer | It is a lead. Last week's conclusion may be stale, and a wrong `HIT` is worse than a `MISS` — the chain cites an answer to a question nobody asked now and stops looking. |
| Delete or hand-edit `checkpoint.md` between a pause and `--resume` | It is where each task restarts. A missing milestone re-runs a sub-step; a wrong one skips it. |
| Delete the run directory to "start clean" | IDs are re-minted from 001 and every citation in the old artifacts silently repoints. Use `--fresh`. |
| Pass `--execute` on the first run of an unfamiliar requirement | Read the spec first. The flag is off by default for that reason. |
| Run `--full` from `dev` or `main` and expect a branch to appear | Step 00 stops. Check out the feature branch first — the chain never creates one. |
| Run `--full` over uncommitted work of your own | Step 00 stops: a per-task commit would sweep it in. |
| Re-run without `--resume` after an interruption | Completed steps are re-run and their IDs re-minted. |

## See also

`/ktkit:help create-pr` — what `--full` hands the PR to. `/ktkit:help spec-recon` — when the requirement needs measuring, not just reading, before a spec is
worth writing. `/ktkit:help docs-review` — when the question is about documents rather than a change.
