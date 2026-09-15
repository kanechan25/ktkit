<!-- group: Specify | order: 31 -->
# ktkit:bug-fix-specs — a finished diagnosis becomes a reviewed fix plan, then it stops

> ⛔ **Not an entry point.** `/ktkit:chain --bug` runs this as part of the BUG lane, with the ledger, the budget gate and step 07's convergence check that a direct run does not get. Running it directly still works and writes the same files.

Reads the `.analyze.md` that `/ktkit:rca` wrote — it does **not** investigate again — and turns it
into `fix.md`, graded against a checklist it writes itself. Then it **hard stops**. Nothing is
changed until you approve.

No speckit on this lane: a bug is a disagreement with a specification that already exists, so the
artifact is a fix plan, not a second spec.

```
/ktkit:bug-fix-specs <bug-report.md | "described symptom">
```

## The cases

```bash
# the ordinary case
/ktkit:bug-fix-specs .claude/claude/prompts/bugs/duplicate-refund.md

# no file — describe the symptom
/ktkit:bug-fix-specs "share link still opens after it expired, but only for the owner"

```

## Flags

| Flag | Default | When you need it |
| ---- | ------- | ---------------- |

## What you get

```
.claude/claude/specs/<rel>/<base>/fix.md              what changes, and why
.claude/claude/specs/<rel>/<base>/checklists/bugfix.md the grading it gave itself
```

Then it stops. Approve, then run `/ktkit:bug-fix-execute`.

## Do not

| Anti-pattern | Why |
| ------------ | --- |
| Approve a plan whose root cause has no citation | An uncited root cause is a guess, and the fix inherits it. |
| Expect the fix itself | That is `/ktkit:bug-fix-execute`. |
| Run it without `/ktkit:rca` first | It stops. One bug, one investigator — a second pass can only disagree with the first, with nothing to say which is right. |

## See also

`/ktkit:help rca` — if you want the diagnosis on its own first. `/ktkit:help chain` with `--bug` — the
whole arm in one line.
