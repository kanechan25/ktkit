<!-- group: Chain | order: 10 -->
# ktkit:chain — a requirement in, a reviewed spec and plan out, as one run

Four skills in a row — analyse, self-clarify, spec, plan — with one thing none of them has alone:
an append-only **ledger**. A question settled in analysis is never asked again in the spec, because
the spec reads the ledger instead of re-deriving. Implementation is **off** unless you ask for it.

```
/ktkit:chain <requirement.md | "described request"> [flags]
```

## The cases, in the order you will meet them

```bash
# the ordinary case: a requirement file in, a reviewed spec and plan out
/ktkit:chain .claude/claude/prompts/share-links/expiry-rules.md

# no file yet — describe it instead, in quotes
/ktkit:chain "expiring share links: 24h default, owner can override to 7d"

# a bug report — name the arm rather than letting step 00 ask
/ktkit:chain .claude/claude/prompts/bugs/duplicate-refund.md --bug

# a feature, but the request reads ambiguously — say so outright
/ktkit:chain requirement.md --feature

# stop at the spec; you will produce the plan some other way
/ktkit:chain requirement.md --plan no

# stop even earlier — after analysis, before any spec is written
/ktkit:chain requirement.md --to A

# go all the way and apply the change
/ktkit:chain requirement.md --execute

# pick up a run that was interrupted, without re-minting IDs
/ktkit:chain requirement.md --resume

# start over; the old run directory is renamed, never deleted
/ktkit:chain requirement.md --fresh

# a repository with no speckit scaffolding, and you do not want to install it
/ktkit:chain requirement.md --no-speckit

# put a ceiling on the run; it stops at a step boundary, never mid-step
/ktkit:chain requirement.md --budget 400000
```

## Flags

| Flag | Default | When you need it |
| ---- | ------- | ---------------- |
| `--bug` / `--feature` | inferred at step 00 | Names the arm outright. Nothing overrides it. Passing both is an error. |
| `--to A\|B\|C` | `C` | Stop after analysis (`A`), spec (`B`) or plan (`C`). |
| `--plan yes\|no` | asked at step 00 | Answers the plan question up front instead of being asked. |
| `--execute` | **off** | Runs phase D — the change itself. Off by default on purpose. |
| `--resume` | — | Restart at the first step marked `missing` or `partial`. Rows marked `complete` are never re-run: their ID allocations are cited downstream. |
| `--fresh` | — | Start at step 00. Deletes nothing — the old run directory is renamed `<base>.<timestamp>/`. |
| `--budget <token>` | no ceiling | Stop cleanly at a step boundary. A cost line prints after every step regardless. |
| `--no-speckit` | — | Take the internalised path even where speckit is installed. It **selects a path, it does not relax a check**. |
| `--rounds N` | `2` | Self-clarify rounds per phase. |

## What you get

Artifacts stay exactly where each skill already put them. The chain adds only a trace directory.

```
.claude/claude/chain/<rel>/<base>/
    manifest.md          ← the index: one row per step, and the resume instruction
    resolved.md          ← the ledger: every question, its answer, and who settled it
    steps/               ← 00-route.md · 01-analyze.md · … · 06-syncback.md

.claude/claude/analyze/<rel>/<base>.analyze.md         A
.claude/claude/specs/<rel>/<base>/spec.md              B
.claude/claude/specs/<rel>/<base>/plan.md              C
.claude/claude/implemented/<rel>/<base>.implt.md       D  (only with --execute)
```

`<rel>` and `<base>` mirror the input's sub-path under `prompts/`. Read `manifest.md` first if a run
stopped — it is the index, and `--resume` reads the same file.

## Where it stops

A question reaches you only when a resolver could not settle it **and** being wrong would be
expensive. Everything else is answered from the repository and written to the ledger. If the run
stops, the manifest says at which step and why.

## Do not

| Anti-pattern | Why |
| ------------ | --- |
| Delete the run directory to "start clean" | IDs are re-minted from 001 and every citation in the old artifacts silently repoints. Use `--fresh`. |
| Pass `--execute` on the first run of an unfamiliar requirement | Read the spec first. The flag is off by default for that reason. |
| Re-run without `--resume` after an interruption | Completed steps are re-run and their IDs re-minted. |

## See also

`/ktkit:help spec-recon` — when the requirement needs measuring, not just reading, before a spec is
worth writing. `/ktkit:help docs-review` — when the question is about documents rather than a change.
