<!-- group: Specify | order: 31 -->
# ktkit:bug-fix-specs — a diagnosed bug becomes a reviewed fix spec, then it stops

The forensic pipeline — memory, explore, reproduce, blast radius, root cause — then it writes the fix
spec and **hard stops**. Nothing is changed until you approve.

```
/ktkit:bug-fix-specs <bug-report.md | "described symptom"> [--no-speckit]
```

## The cases

```bash
# the ordinary case
/ktkit:bug-fix-specs .claude/claude/prompts/bugs/duplicate-refund.md

# no file — describe the symptom
/ktkit:bug-fix-specs "share link still opens after it expired, but only for the owner"

# a repository with no speckit scaffolding
/ktkit:bug-fix-specs bug-report.md --no-speckit
```

## Flags

| Flag | Default | When you need it |
| ---- | ------- | ---------------- |
| `--no-speckit` | — | Take this skill's internalised path even where speckit is installed. It **selects a path, it does not relax a check**. |

## What you get

```
.claude/claude/specs/<rel>/<base>/…      the fix spec, with the reproduction and the root cause
```

Then it stops. Approve, then run `/ktkit:bug-fix-execute`.

## Do not

| Anti-pattern | Why |
| ------------ | --- |
| Approve a spec whose root cause has no citation | An uncited root cause is a guess, and the fix inherits it. |
| Expect the fix itself | That is `/ktkit:bug-fix-execute`. |

## See also

`/ktkit:help rca` — if you want the diagnosis on its own first. `/ktkit:help chain` with `--bug` — the
whole arm in one line.
