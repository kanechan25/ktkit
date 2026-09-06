<!-- group: Survive | order: 61 -->
# ktkit:ccontinue — resume from a checkpoint, with the file outranking the summary

Runs on the far side of a memory wipe. The compaction summary in context is lossy and possibly wrong;
the checkpoint file is the authority. It reconstructs the binding decisions, compares the recorded
branch and HEAD against the current ones, prints a self-audit, and **waits** before touching anything.

```
/ktkit:ccontinue <compact-file>
```

## The cases

```bash
# the ordinary case, right after pasting /compact
/ktkit:ccontinue .claude/claude/compacts/share-links/expiry-rules.compact.md

# a checkpoint written by a parallel session
/ktkit:ccontinue .claude/claude/compacts/share-links/expiry-rules.frontend.compact.md
```

## What it prints

A self-audit block: the goal, the binding decisions, what is in progress, the traps, and the git
comparison. **Every conflict between the compaction summary and the file is reported, and the file
wins.** Then it stops and waits for you to confirm.

## Do not

| Anti-pattern | Why |
| ------------ | --- |
| Trust the compaction summary over the file | That is the exact failure this skill exists to catch. |
| Stitch older rounds together | The highest `## Round N` is self-contained. Older rounds are history. |
| Let it edit, run or commit before you confirm | It stops for a reason: the context it just rebuilt has not been checked by a human yet. |

## See also

`/ktkit:help ccompact` — the half that runs before `/compact`.
