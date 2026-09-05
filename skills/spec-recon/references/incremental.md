# Incremental runs

When `recon.py` is given `--prior <report>` and finds one, `--incremental` turns on by default. The
run then analyses what changed rather than the whole set, which is the single largest cost lever
available — wave 1 is roughly two thirds of a full run's spend.

## What counts as changed

An input is in scope when **any** of these hold:

| Signal | Source |
| ------ | ------ |
| mtime newer than the prior report | `recon.json` `stale_risk` |
| a revision marker higher than the one the prior report recorded | `revision_markers[*].max` |
| a commit touching it since the prior report | `last_commit` |
| an md5 differing from the one the prior report recorded | `md5` |

Anything else is out of scope for extraction — but **not** out of scope for the report. Its rows are
carried forward verbatim, marked as inherited, with the run that produced them.

## What is never inherited

Three kinds of row are re-derived every time, however unchanged the inputs look:

1. **Rows citing a changed input.** A verdict about document A that quotes document B is invalidated
   when B moves, even though A did not.
2. **Absence verdicts.** `UPHELD` means "a search did not find it"; a codebase that has moved makes
   that a claim about a state that no longer exists. Every absence verdict goes back through
   `arbiter-impl`.
3. **Anything the prior report marked `not-accessed`.** That was a gap, not a finding. Re-attempt
   it — the capability that was missing may now be present, which is often the reason for the
   re-run.

## ID stability

Requirement IDs and claim IDs come from registries — `checklist.md` and `claims.md` under `<base>/`.
**Never delete them to force a clean run.** The next run re-mints from 001, and every ID in the
previous report silently points at a different row. That is not a cosmetic problem: someone reading
both reports side by side has no way to see it happened.

An incremental run appends to the registries. Retired requirements are marked retired, not removed.

## What the report must say

Line 1, before anything else:

```markdown
INCREMENTAL — 3 of 11 inputs changed since `spec-recon.md` (2026-08-14). Rows for the other 8 are
inherited from that run and marked accordingly; every absence verdict was re-checked.
```

And in the source inventory, per row:

```markdown
| Source | Kind | Read |
| ------ | ---- | ---- |
| `docs/design.md` | document | fully (changed: 5版-l → 5版-n) |
| `docs/api.md` | document | inherited from 2026-08-14, unchanged |
```

An incremental run that does not announce itself is indistinguishable from a full one, and the
person acting on it will assume every row was checked today. That assumption is the entire risk of
running incrementally, and stating it is the whole mitigation.

## When to force a full run

- The prior report is `DEGRADED`, or was produced with a narrower `--probe` than this one.
- The prior report's registries are missing.
- More than about half the inputs changed — the bookkeeping costs more than it saves.
- The question changed. `--scope` is not an input `recon.json` can diff, and a new question makes
  every inherited row an answer to a different one.
