# The execution layer

`tasks.md` says **what**. It is spec-kit's file, it is what `/speckit-converge`
appends to, and it is the one artifact a later reader treats as canonical.

How each task gets built — which mode, which executor, what review it earns — is
a different question with a different lifetime, and writing it into `tasks.md`
makes the canonical file carry decisions that change every run. So it lives
beside it.

```
<feature-dir>/tasks.md            WHAT  — canonical, append-only, speckit's
<chain-dir>/execution.yml         HOW   — this run's decisions, rewritable
```

The idea of splitting them comes from `superspec`. The dependency does not: that
repository is one author against a spec-kit that releases roughly weekly, and a
closed loop that stops when somebody else stops pushing is not closed.

## `execution.yml`

One entry per task id, and the ids are `tasks.md`'s. ⛔ Never renumber them here:
this file points at that one, and a renumbering breaks every pointer including
the ledger's.

```yaml
T03:
  mode: inline | subagent          # who does the work
  executor: worker | trivial       # which discipline it runs under
  tier: R0 | R1 | R2               # how much review it earns -- see below
  parallel_group: g1               # tasks in one group may run concurrently
  review: minimal-diff-guard, requesting-code-review
  brief: steps/briefs/T03.md       # written when the task becomes READY
```

⛔ **This file never contradicts `tasks.md`.** A task id present here and absent
there is a stale entry, not a new task — the chain reports it and stops rather
than executing something the canonical file does not list.

## The brief is written when the task is READY, and not before

A task's brief is the thing a worker actually reads: exact paths, the interfaces
it consumes and produces, the acceptance criterion, the test, and the command
that verifies it.

The methodology comes from `superpowers:writing-plans` — the five slots below are
its task template, and they are what makes a plan usable by somebody with no
context. What is deliberately **not** taken is its timing. That skill writes every
task's detail up front, because it is producing a plan for a human to read.

Here the detail is produced for a worker to execute, and a change request can
kill a third of the plan before the worker reaches it. Writing thirty briefs and
having twelve invalidated is paying twice for the same tasks: once to write them,
once to work out which survived.

⛔ **A brief is written when its task transitions to `ready`, from the state
`ledger.py --task-state` already records.** Not at planning time, not in a batch.

| Slot | What it holds | Why a worker cannot proceed without it |
| ---- | ------------- | -------------------------------------- |
| **files** | exact paths to create, modify (with line ranges) and test | "the export module" is four files, and a worker with fresh context cannot know which |
| **interfaces** | what this task consumes from earlier tasks, and produces for later ones — exact names and types | the worker sees only this task; this block is the only way it learns the names its neighbours use |
| **acceptance** | the one condition that makes this task done | without it, done means "I stopped" |
| **test** | the failing test to write first, and where it goes | the BUG lane's rule applies here too: a test written after the code can only confirm it |
| **verify** | the command that proves it, read from the repository | ⛔ never guessed — see the free gate in step 05 |

Five slots, all of them, every brief. A brief missing one is not a short brief,
it is a brief that will be answered with a question.

## The worker gets the brief and nothing else

⛔ **A worker never inherits the conversation.** It receives its brief, the files
that brief names, and nothing further.

Two reasons, and the second is the one people forget:

1. **Cost.** A conversation carried into every worker is paid again on every
   spawn, and it grows all run.
2. **Correctness.** A worker that can see the discussion can see the options that
   were rejected, the half-formed version of the design, and the reasoning that
   was later overturned. It will occasionally build one of them. A brief carries
   the decisions; a transcript carries the decisions *and everything that lost*.

This is `superpowers:subagent-driven-development`'s discipline, applied to the
briefs this file defines.

## Tiers — how much review a task earns

Assigned at routing, written into `execution.yml`, and never raised by the worker
that would be reviewed by it.

| Tier | What it covers | Review |
| ---- | -------------- | ------ |
| **R0** | no contract, no schema, no shared state — one file, and the test already exists | the free gate only |
| **R1** | ordinary work inside one subsystem | free gate → `ktkit:minimal-diff-guard` |
| **R2** | a contract, a schema, a migration, or anything another subsystem depends on | free gate → `ktkit:minimal-diff-guard` → `superpowers:requesting-code-review` |

### The agent each tier adds

| Role | Agent | Tools | Model |
| ---- | ----- | ----- | ----- |
| minimal-diff-guard | `ktkit:minimal-diff-guard` | `Read, Grep, Glob` | haiku |

⛔ **Read-only, and it reports rather than fixes.** It answers one narrow
question — is this the change that was asked for — and it answers it before any
reviewer is dispatched, because a diff that wandered outside its brief wastes a
reviewer's whole pass on files nobody asked about. It is `haiku` because the
question is a comparison against a list of paths, not a judgement about code, and
every finding it makes carries a `path:line` a person can check in a second.

⛔ **The ratchet turns one way**, as it does for the three paths in
`/ktkit:analyze-feat`: torn between two tiers, take the heavier; something
surfacing mid-task that belongs to a heavier tier raises it and says so. A tier
is never lowered, and never by the work it governs.

## ⚠️ Batching: not decided, because it has not been measured

An obvious saving would be to hand several small tasks to one worker. Whether
that saves anything is **unknown**, and this file will not guess.

What is recorded: a spawn was measured at roughly 6,619 base tokens for a
three-tool agent, and a large-bodied four-tool agent at 23,375 — the cost of a
worker tracks its tool set and prompt size far more than the size of its task. If
that holds, three trivial tasks in three workers can cost more than three trivial
tasks inline, and batching would be worth having.

⛔ **No threshold is written here until `cost.jsonl` shows one.** The data needed
is already collected — `cost_log.py` records the model and the tokens per agent
per wave since 4.5.0 — so this is a measurement waiting to be read, not a design
question waiting to be argued. Writing a number now would make it look settled.

Until then: one task, one worker, and the tier decides the review.
