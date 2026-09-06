<!-- group: Execute | order: 41 -->
# ktkit:bug-fix-execute — an approved fix spec becomes the fix, verified and recorded

Picks up where `/ktkit:bug-fix-specs` stopped. It does **not** re-investigate: the root cause is
already settled and cited. Fix → verify → document.

```
/ktkit:bug-fix-execute [<spec-path>]
```

**Prerequisite:** a fix spec under `.claude/claude/specs/` that you have read and approved. The skill
searches recursively — do not assume a flat folder or a `bug-` prefix.

## The cases

```bash
# the ordinary case: the fix spec was just written and approved
/ktkit:bug-fix-execute

# name the spec outright when several are in flight
/ktkit:bug-fix-execute .claude/claude/specs/bugs/duplicate-refund.spec.md
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
| Expect a re-investigation | That was `/ktkit:rca` and `/ktkit:bug-fix-specs`. |

## See also

`/ktkit:help bug-fix-specs` — the step before. `/ktkit:help chain` with `--bug --execute` — the whole
arm in one line.
