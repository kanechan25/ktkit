# The ledger

One file per chain run: `.claude/claude/chain/<rel>/<base>/resolved.md`.

It answers one question, asked thousands of times across a run: **has anyone already settled this?**

## Why a file and not context

The chain's phases are separate skills, and several run as subagents. A subagent cannot see the
lead's conversation, and the lead must not carry the phases' findings in its own context — that is
what makes a long run collapse. A file is the only channel every participant can read.

It is also the only channel that survives a crash, a compaction, and a `--resume` three days later.

## Columns

| Column | Rule |
| ------ | ---- |
| `ID` | `Q01`, `Q02`, … Minted **only** by `ledger.py --next-id`, and only in the lead. Two subagents minting concurrently would both get the same number. |
| `Question` | The unknown, in the words it was first asked. Not rewritten later — the lookup depends on the original vocabulary being present. |
| `At` | When the row was settled, ISO. Stamped by `--add`. |
| `Head` | The short commit the answer was drawn from, from `git rev-parse` at the moment of writing. A conclusion is only as current as the tree it came from, and without this there is no way to ask whether a row citing code survived forty commits. |

⚠️ A ledger written before these columns existed has seven, not nine. It is read as having no
provenance rather than refused: crashing a `--resume` on an older run would be worse, and skipping
the rows would silently re-open questions somebody settled.
| `Tier` | `T1` `T2` `T3` `T3.5` `T4`, per `/ktkit:escalation-ladder`. |
| `Conclusion` | What was settled. `OPEN` means the row reached T4 and is waiting on the user. Only a T4 row may be `OPEN`. |
| `Evidence` | `path:line` for anything the repository settled. For a T4 row the user answered, say so: `user answered at the gate`. |
| `Falsifier` | **Mandatory for T3.5.** What observation would prove the chosen reading wrong. A T3.5 row without one is a guess wearing a label, and `ledger.py` refuses to write it. |
| `Phase` | `A` `B` `C` `D` — which phase settled it. Answers "when did we learn this". |

## Append-only, and what that buys

A conclusion that changes writes a **new row with the same ID**. The old row stays where it is.

```
| Q02 | soft delete or hard delete for archived records | T3.5 | soft | migrations/004.sql:12 | any row removed by a real DELETE | A |
| Q02 | soft delete or hard delete for archived records | T1   | hard, since the 004 migration | migrations/011.sql:4 | — | C |
```

Reading the file top to bottom shows the belief and the correction. `ledger.py` treats the **last**
row for an ID as current, so nothing needs to be deleted for the newer answer to win.

This is also the sync-back trail: the second row above is exactly what step 06 writes into the
spec's `chain` block.

## Lookup

```bash
ledger.py <path> --lookup "who owns the retry policy" [--threshold 0.6]
```

Matching is a Jaccard overlap of content words — deliberately crude, and deterministic. Exact-string
matching would miss almost every time, because the phase that asks second phrases the question its
own way; anything cleverer would start deciding which questions "mean the same", which is a judgement
call this file must not make.

- `HIT` (exit 0) — cite the row and **do not spawn a resolver**.
- `MISS` (exit 1) — queue the question.

Two rules the implementation enforces rather than documents:

1. **An `OPEN` row never hits.** It is a question, not an answer; returning it would let the chain
   answer itself with its own unanswered question.
2. **The best match wins, then the threshold is applied.** A near-miss is reported with its score,
   so a caller tuning `--threshold` can see how close it came.

### Recording what the lookup saved

Pass `--record` and every lookup is appended to `lookup.jsonl` beside the ledger. Then:

```bash
ledger.py <path> --cache-metric
```

```
lookups=34 · hits=19 (56%) · misses=15
spawns avoided=19  ⇒  ~125,761 tokens NOT spent   [derived: 19 x 6,619 base]
⚠️ base only. A resolver costs more than its base once it reads anything.
```

⛔ **The figure is a floor and says so.** Multiplying the hits by what a resolver *really* costs would
read better and has never been measured, so it is not written.

Near-misses between 0.45 and 0.60 are listed too. They are the only evidence for where
`--threshold` belongs — and moving it on a hunch is how a wrong `HIT` gets shipped.

### Sibling runs — `--ledger-scope dir`

Two runs on related requirements re-derive the same answers, and the ledger is per-run. `dir` reads
the `resolved.md` of other runs in the same `prompts/<rel>/` and reports a match as **`FOREIGN`,
exit 2** — deliberately neither `HIT` (0) nor `MISS` (1).

⛔ **A `FOREIGN` row is a lead, not a conclusion, and may not close anything.** It is printed with the
run it came from, when it was settled and against which commit; the caller dispatches a resolver
*with that as a starting point*, which is cheaper than a blind search and still a search. Last week's
answer may be stale — the code moved, the decision changed — and a wrong `HIT` is worse than a
`MISS`, because the chain then cites an answer to a question nobody asked now and stops looking.

Raise `--threshold` when the run has many similar questions about different subjects. Lowering it
below ~0.5 starts merging unrelated questions, and a wrong `HIT` is worse than a missed one: the
chain cites an answer to a different question and stops looking.

## The metric

```bash
ledger.py <path> --metric [--min-ratio 0.70]
```

```
self_resolve_ratio=0.86 · self_resolved=6 · needs_user=1 · assumptions=2
```

Recomputed from the rows every time. ⛔ Never print a ratio an agent asserted — that is precisely how
the number stopped meaning anything the last time it was trusted.

Two ways to fail, and both are reported in the same run so a caller does not fix one and discover
the other on the next round-trip:

| Failure | Meaning |
| ------- | ------- |
| `BELOW-FLOOR` | Ratio under 0.70 ⇒ tiers 1–3 were not exhausted. Dispatch more resolvers. ⛔ Do not open the gate. |
| `TOO-MANY-OPEN` | More than 3 `OPEN` rows. That is not a gate, it is the interview the chain exists to remove: merge them into one representative row and say the requirement is missing a section. |

## What closes a row

A row is closed when its current `Conclusion` is not `OPEN`. Once a T4 row has been answered **by the
user**, no later phase may re-open it — not to re-check it, not because a resolver could now settle
it. Re-deciding a question somebody answered on purpose overwrites their decision silently, which is
the single worst thing this file could be used for.

If new evidence genuinely contradicts an answered T4 row, that is not a re-decision: it is a conflict
for step 06 to sync back and, if it changes the outcome, a new row at the next gate.
