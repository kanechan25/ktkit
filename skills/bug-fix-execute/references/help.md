<!-- group: Execute | order: 41 -->
# ktkit:bug-fix-execute — an approved fix plan becomes the fix, red test first

> ⛔ **Not an entry point.** `/ktkit:chain --bug --execute` runs this as part of the BUG lane, with the ledger, the budget gate and step 07's convergence check that a direct run does not get. Running it directly still works and writes the same files.

Picks up where `/ktkit:bug-fix-specs` stopped. It does **not** re-investigate: the root cause is
already settled and cited. Red test → fix → verify → document.

```
/ktkit:bug-fix-execute [<fix-plan-path>]
```

**Prerequisite:** an approved fix plan under `.claude/claude/specs/`. Resolved by `basename`, in
order: `<base>/fix.md`, then `<base>/spec.md` from before the rename, then a legacy flat
`*.spec.md`. The older two are read, never renamed.

## The cases

```bash
# the ordinary case: the fix plan was just written and approved
/ktkit:bug-fix-execute

# name the plan outright when several are in flight
/ktkit:bug-fix-execute .claude/claude/specs/bugs/duplicate-refund/fix.md
```

## What you get

The fix itself, plus:

```
.claude/claude/implemented/<rel>/bug-<name>.implt.md     what changed, and how it was verified
```

## Do not

| Anti-pattern | Why |
| ------------ | --- |
| Run it before the root cause is cited | The fix then targets the symptom. |
| Expect a re-investigation | That was `/ktkit:rca`, once. |
| Change code before the test is red | STEP 4.95 refuses. A fix written first can only confirm itself. |
| Try a fourth fix | Three failed attempts is an architectural signal, not bad luck. The skill stops and says so. |

## See also

`/ktkit:help bug-fix-specs` — the step before. `/ktkit:help chain` with `--bug --execute` — the whole
arm in one line.
