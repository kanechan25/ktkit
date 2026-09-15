<!-- group: Understand | order: 21 -->
# ktkit:rca — a bug report becomes a root cause, by evidence rather than guesswork

`superpowers:systematic-debugging` Phases 1 to 3, with a rule attached: **every why needs a line of
code, not a theory**. It maps the symptom to code, traces backward to the original trigger, states
one hypothesis and proves it with a **failing test**, classifies the failure and sizes the blast
radius.

It fixes nothing. The test it leaves behind is red on purpose — `/ktkit:bug-fix-execute` confirms it
is red for the stated reason before it changes any code.

```
/ktkit:rca <bug-report.md | "described symptom">
```

## The cases

```bash
# a written bug report
/ktkit:rca .claude/claude/prompts/bugs/duplicate-refund.md

# no file — describe the symptom
/ktkit:rca "share link still opens after it expired, but only for the owner"

# a stack trace and nothing else is still a valid input
/ktkit:rca "NullReferenceException in ExportService.Resolve, line 88, only on retry"
```

## What you get

```
.claude/claude/analyze/<rel>/<base>.analyze.md
```

An evidence chain where each step cites a file and a line, one hypothesis with the failing test that
proves it, a classification of the failure, and the blast radius. Read it before approving a fix.

## Do not

| Anti-pattern | Why |
| ------------ | --- |
| Skip it and go straight to the fix | The fix then targets the symptom, and the bug comes back wearing a different message. |
| Accept a why with no citation | An uncited why is a guess with a number in front of it. |
| Expect a fix | `/ktkit:bug-fix-specs` writes the fix plan; `/ktkit:bug-fix-execute` applies it. |
| Carry two hypotheses forward | One at a time. A second stacked on the first means neither gets tested. |

## See also

`/ktkit:help bug-fix-specs` — the next step. `/ktkit:help chain` with `--bug` — runs the whole bug arm
in one line.
