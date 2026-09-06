<!-- group: Decide | order: 71 -->
# ktkit:confirm-with-me — gate one irreversible step on an explicit yes

Not a skill you usually invoke. It is a **marker**: write the literal phrase `confirm with me` next
to a step — in a message, a spec, a plan, a workflow, another skill's body — and that step blocks
until you answer.

```
… delete the old migration table   confirm with me
```

Active for every session while this plugin is installed, via its SessionStart hook.

## What happens when it fires

Execution stops **before** the marked step and a five-field block is posted: what is about to happen,
what it touches, what it cannot be undone by, what the alternative is, and what silence means.
It then waits for one of:

```
confirm              → the step runs
abort                → it does not
modify: <change>     → the step is changed, and the gate re-arms
```

## The rules that make it a gate rather than a hint

| Rule | Why |
| ---- | --- |
| One marker is one gate for **one step** | Approving a larger task never covers a step that carries its own marker. |
| Silence is not consent | Neither is an unrelated "ok, go on". |
| Markers are never batched | Two markers are two gates, answered separately. |

## Turning it off

Say so for the session: *"stop confirm-with-me"*.

## Do not

| Anti-pattern | Why |
| ------------ | --- |
| Put the marker on a whole workflow | It gates a step. On a workflow it fires once and covers nothing. |
| Read prior approval as covering a marked step | That is precisely what the marker denies. |

## See also

`/ktkit:help escalation-ladder` — the other stop: an unknown that could not be resolved.
