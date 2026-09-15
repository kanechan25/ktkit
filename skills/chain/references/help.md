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

# pick up a run that was interrupted, without re-minting IDs
/ktkit:chain requirement.md --resume

# start over; the old run directory is renamed, never deleted
/ktkit:chain requirement.md --fresh

# put a ceiling on the run; it stops at a step boundary, never mid-step
/ktkit:chain requirement.md --budget 400000
```

## Flags

| Flag | Default | When you need it |
| ---- | ------- | ---------------- |
| `--bug` / `--cr` / `--nr` / `--trivial` | read from `type:` at step 00, else asked | Names the lane outright. Nothing overrides it. Passing two is an error. `--feature` is an alias for `--nr`. |
| `--trivial` | — | The only lane with no analysis and no spec. All four conditions in `references/lanes.md` must hold, and it requires `--execute`. Crossing its 50,000-token ceiling escalates to CR with the reason recorded — it never extends the ceiling. |
| `--to A\|B\|C` | `C` | Stop after analysis (`A`), spec (`B`) or plan (`C`). |
| `--plan yes\|no` | asked at step 00 | Answers the plan question up front instead of being asked. |
| `--execute` | **off** | Runs phase D — the change itself. Off by default on purpose. |
| `--resume` | — | Restart at the first step marked `missing` or `partial`. Rows marked `complete` are never re-run: their ID allocations are cited downstream. |
| `--fresh` | — | Start at step 00. Deletes nothing — the old run directory is renamed `<base>.<timestamp>/`. |
| `--budget <token>` | **asked, never assumed** | ⭐ Ceiling for the run, checked at every phase boundary against `cost.jsonl` — what agents actually reported. Omit it and step 00 stops for your answer: nothing has measured this skill yet, so it will not pick a number for you. |
| `--budget-execute <n>` | what A–C cost | A separate ceiling for phase D, whose cost tracks the size of a change rather than the number of questions. ⛔ If the remainder is under that figure, phase D does not start — a half-changed repository is worse than an unchanged one. |
| `--contract` *(on `deviation.py`)* | — | Marks a divergence that changes what the spec **promises** — an acceptance criterion, an API shape, a dropped requirement. It becomes a gate at step 06 rather than syncing on its own. |
| `--ledger-scope run\|dir` | `run` | `dir` also reads sibling runs' ledgers in the same `prompts/<rel>/` and reports a match as **`FOREIGN`, exit 2** — a lead for a resolver, never a conclusion. |
| `--rounds N` | `2` | Self-clarify rounds per phase. |

## ⭐ What it costs, and where it stops

Four files land beside the ledger, and every figure in them is what an agent reported:

```
cost.jsonl · cost.md         what each phase and each agent cost
budget.jsonl                 the gate's verdict at every boundary
dispatch.jsonl · dispatch.md what each agent was sent, against what it spent
lookup.jsonl                 every ledger lookup, and what it saved
```

`quota.py --gate 80` runs before anything is spent; `budget.py` decides `GO` or `STOP` after every
phase. On `STOP` the run stops **at a boundary** — and a boundary here is worth more than in a
reconnaissance run, because each phase ends on a *complete artifact*: stopping after phase B leaves
you a finished spec, not half an evidence set.

⛔ **It will not choose a ceiling for you.** `ktkit:spec-recon` defaults to 4,000,000 because it
measured 453,571 tokens per agent; this skill has a different shape and no measurement yet, so
step 00 prints what a comparable run cost and waits.

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
| Treat a `FOREIGN` row as an answer | It is a lead. Last week's conclusion may be stale, and a wrong `HIT` is worse than a `MISS` — the chain cites an answer to a question nobody asked now and stops looking. |
| Start `--execute` on the last of the budget | Phase D costs by the size of the change. Out of budget mid-implementation leaves the repository half-changed. |
| Delete the run directory to "start clean" | IDs are re-minted from 001 and every citation in the old artifacts silently repoints. Use `--fresh`. |
| Pass `--execute` on the first run of an unfamiliar requirement | Read the spec first. The flag is off by default for that reason. |
| Re-run without `--resume` after an interruption | Completed steps are re-run and their IDs re-minted. |

## See also

`/ktkit:help spec-recon` — when the requirement needs measuring, not just reading, before a spec is
worth writing. `/ktkit:help docs-review` — when the question is about documents rather than a change.
