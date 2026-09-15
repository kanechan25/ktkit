# Lanes

Four lanes, one input, and the lane is chosen **before** anything is spent. The mechanism is in
`SKILL.md` step 00 and does not change here: a lane flag, else the `type:` frontmatter, else ask.
This file holds what a lane *is* and, for TRIVIAL, what must be true before it may be named.

| Lane | The request is | 01 | 03 | 05 |
| ---- | -------------- | -- | -- | -- |
| BUG | something that exists and does **not** behave as designed | `/ktkit:rca` | `/ktkit:bug-fix-specs` | `/ktkit:bug-fix-execute` |
| CR | something that exists, behaves **as designed**, and must behave differently | `/ktkit:analyze-feat` | `/ktkit:feat-req-specs` | `/ktkit:feat-req-execute` |
| NR | something that does not exist yet | `/ktkit:analyze-feat` | `/ktkit:feat-req-specs` | `/ktkit:feat-req-execute` |
| TRIVIAL | a change small enough that a spec would cost more than the change | — | — | test-driven, directly |

CR runs the NR column until a dedicated `cr-delta` skill exists (C3). The lane is recorded separately from the
first day so that the manifest says which one ran, and so the split costs one table edit later
instead of a migration.

## BUG is not CR

`skills/raise-issue/references/form-bug.md` and `form-cr.md` draw the line and this file follows it:
**does the thing behave as its own design says it should?** No → BUG, and there is a root cause to
find. Yes, but the design is now wrong → CR, and there is nothing to diagnose.

The expensive mistake is routing a CR into BUG. `/ktkit:rca` will look for a root cause, find none,
and the run will either stall or invent one. The reverse is cheaper: a BUG sent to CR produces a
delta that the bug's own failing test immediately contradicts.

⛔ When an investigation in the BUG lane proves the code matches the spec and the **spec** is what is
wrong, that is a CR. Re-route, and record it in the ledger as a reclassification with the finding
that caused it. It is never a quiet edit: the artifacts already written under the BUG lane stay, and
the reclassification is the reason the next reader can tell why they stop there.

## TRIVIAL — all four conditions, not three

The other three lanes produce a document somebody reads before any code changes. TRIVIAL does not.
It is the only lane where a wrong call ships a change nobody reviewed, so its entry is a conjunction,
never a judgement call:

1. **One file.** Not "one file plus a small change next door".
2. **No contract change.** No public signature, no API shape, no wire format, no exported name.
3. **No schema change.** No migration, no column, no index, no stored-data shape.
4. **The area already has tests.** Test-driven means there is somewhere to put the failing test.

Fail any one → the request is not TRIVIAL. The lane is **never inferred**: not from the frontmatter,
not from the size of the diff, not from the wording. `--trivial` names it, and nothing else does.

`--trivial` also requires `--execute`. The lane has no 01 and no 03, so without it the chain would
write a trace directory with nothing in it and report success.

### The ceiling

**50,000 tokens**, measured the same way every other budget in this skill is measured — against
`cost.jsonl` at a step boundary.

Crossing it means the estimate was wrong, and the honest reading of a wrong estimate is that the
change was never trivial. So:

⛔ **Crossing the ceiling escalates to CR. It does not extend the ceiling, and it does not push
through.** Write the reason into `manifest.md` — what was believed, what it actually cost, and which
of the four conditions turned out to be false — then stop. A half-finished change with no spec and no
analysis behind it is the worst artifact this skill can produce.

The escalation is recorded even when the user then asks to continue anyway. The record is what makes
the next TRIVIAL estimate better than this one.

## BUG does not touch SDD

The BUG lane runs `/ktkit:rca` on `superpowers:systematic-debugging`, then a failing test
through `superpowers:test-driven-development`, then the fix, then
`superpowers:verification-before-completion`. It does **not** run `speckit-specify`,
`speckit-plan`, `speckit-tasks`, `speckit-analyze` or `speckit-converge`.

The reason is not economy. A bug is a disagreement between the code and a specification that already
exists; writing a second specification to describe the disagreement adds a document that has to be
kept true, and the failing test says the same thing in a form that cannot drift. SDD answers "what
should this do"; a bug has already answered that, and the open question is "why does it not".

⛔ The single exception: an investigation that proves the code matches the spec and the **spec** is
what is wrong. That is a CR, and it is re-routed as one — see above.
