# The convergence loop

Everything before step 07 compares one document with another. Analysis against request, spec against
analysis, plan against spec, deviations against spec. All of it is documents agreeing with documents,
and a set of documents can agree perfectly with each other while the code does something else.

`/speckit-converge` is the only step that opens the delivered code and asks whether it satisfies the
spec. That question is what makes this a loop rather than a pipeline.

## Where it sits

```
01 analyse → 02 clarify → 03 spec → 04 plan → 05 implement → 06 sync back → 07 converge
                                                    ▲                            │
                                                    └──── appended tasks ────────┘
                                                         at most twice
```

07 runs **after** 06, not before it. 06 writes down what diverged while the code was being written —
facts the author still remembers. 07 reads the finished code cold. Running them the other way round
would have converge measure against a spec that was about to change.

## What it is, and what it is not

| | |
| - | - |
| **Is** | an assessment of the present state of the code against `spec.md`, `plan.md`, `tasks.md` |
| **Is not** | a diff, a branch comparison, or anything that reads git history |
| **Writes** | one new `## Phase N: Convergence` section appended to `tasks.md` — nothing else |
| **Never writes** | `spec.md`, `plan.md`, application code, or any existing task |

When the code already satisfies everything, it leaves `tasks.md` byte-for-byte unchanged and reports
clean — no empty header. A run whose `tasks.md` mtime did not move is a run that converged, not a run
that failed to write.

⛔ **Append-only is its property, not ours to enforce.** It is in that skill's own operating
constraints. What this plugin has to do is not break it: never renumber, reorder or delete what it
appended, and never let a later step rewrite `tasks.md` wholesale.

## The cap is two rounds

```
round 1   converge → gaps → append → implement → converge
round 2   converge → gaps → append → implement → converge
round 3   ⛔ does not exist
```

Round 3 is not a third attempt at the same problem. It is evidence of a different one.

Two full rounds of *find the gap, build the gap, look again* that still leave work outstanding means
the gap is not in the code. It is in the spec: something is wrong, or something is ambiguous enough
that each pass reads it differently and builds a different thing. Appending a third round of tasks
pays model usage to chase a target that moves every time it is reached.

At the cap, in this order:

1. ⛔ **Append nothing.** Round 2's convergence section stands as the record of where it stopped.
2. Write into `manifest.md`: which gaps survived both rounds, what each round appended, and — the
   part only this run can supply — which reading of the spec each surviving gap implies.
3. Escalate through `/ktkit:confirm-with-me`, naming the spec section believed wrong or ambiguous.

That escalation does **not** count against the run's two-question budget, for the same reason a
contract-level deviation does not: it reports something that happened rather than asking what to do.

## Which lanes run it

| Lane | 07 | Why |
| ---- | -- | --- |
| NR · CR | yes | they have a `spec.md`, a `plan.md` and a `tasks.md` to converge against |
| BUG | no | no plan phase and no `tasks.md`. What a bug converges against is its failing test, and `/ktkit:bug-fix-execute` turned that green before the run got here |
| TRIVIAL | no | no spec at all — the ceiling is its only gate |

## The free gate is a different thing, and it comes earlier

`05` runs build, test, lint and typecheck before any reviewer is dispatched. That is not convergence
— it asks whether the code *works*, not whether it is the code that was asked for. Both are needed,
they answer different questions, and the cheap one runs first so the expensive one is never spent on
code that does not compile.
