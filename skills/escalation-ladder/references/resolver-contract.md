# The resolver's contract

One agent, one question, one verdict. The ladder decides *whether* to ask; this
file says what the thing it asks is allowed to be.

| Role | Agent | Tools | Model |
| ---- | ----- | ----- | ----- |
| escalation-resolver | `ktkit:escalation-resolver` | `Read, Bash` | inherit |

## Why `Read, Bash` and not `Read, Grep, Glob`

A resolver answers questions the repository can settle, and some of them are not
file questions: what a command prints, whether a script exits zero, what a lock
file resolves a version to. `Bash` covers those and `Read` covers the rest.

⛔ It is never given `Grep` or `Glob` alongside `Bash`. The harness collapses that
combination to `Read, Bash` and drops the others **silently**, so an agent asking
for four tools would run with two and nothing would say so.

## Why the model is `inherit`, and what that costs

`inherit` means the resolver runs on whatever model the session is running. Every
other agent in this plugin that writes something nobody re-reads has been pinned,
for one reason: a session switched to a cheaper model silently weakens exactly
the steps where a mistake is not caught.

This one is not pinned, and that was decided rather than overlooked — see the
model routing section of the README. It is recorded here so the next person to
ask the question finds the answer instead of re-deriving it.

⚠️ The exposure is real and worth naming: a resolver's verdict goes into the
ledger, and **the ledger has no reviewer**. A wrong line is not caught later; it
is *cited* by every phase that reads the ledger instead of re-deriving. That is
the same argument that pinned the five judgement agents to `opus`, and the reason
this row is worth revisiting with a measurement rather than an opinion.

## What the agent may and may not do

- It is given **one** question, and never the caller's reasoning. Reasoning is
  what produces a resolver that agrees with the caller.
- It returns a verdict with a `file:line`, or it states which sources it
  exhausted and with which search terms. "Not found" without the search terms is
  not a finding, it is a shrug.
- It never draws a conclusion about the product, only about the repository.
