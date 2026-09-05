# Cost model

A run of this shape measured **2,754,748 tokens across 15 agents and 302 tool calls**. That is not a
reason to avoid it — it replaced a week of manual reading — but it is a reason to make the spend
visible while it is happening rather than afterwards.

## Base cost per spawn, measured on this harness

| Tool set | `tools` | Base tokens | Used by |
| -------- | ------- | ----------: | ------- |
| A | `Read, Grep, Glob` | 6,619 | `probe-code`, `arbiter-impl`, every `docs-review` reviewer |
| B | `Read, Bash` | 11,353 | `probe-artifact`, `probe-vcs`, `probe-runtime` |
| C | `Read, Write, Grep, Glob` | 6,875 | `state-extract`, mappers |

Set B costs about **4,700 more per spawn** than set A, and that difference is the schema of `Bash`,
which carries the whole sandbox description. It is why only three roles have a shell, and why
`arbiter-impl` — which would have been convenient to give one — does not.

Two other numbers worth holding on to:

- **Base cost is dominated by body length, not tool count.** A four-tool agent with a long body
  measured 23,375 against a three-tool agent with a short one at 6,619. Hence the ≤800-word budget:
  a 3,000-word role prompt costs ~4,400 extra **on every spawn**.
- **Base cost is the floor, not the estimate.** Tool results dominate everything. A wave of ten
  agents at ~7k base is 70k before a single file has been read; the actual bill for that run was an
  order of magnitude higher.

## The per-wave line

After **every** wave, print one line. Do not ask, do not stop:

```text
Wave 2: 5 agents · ~340k tokens · 11m · running ~1.2M · 1 wave left in the cap
```

This is stricter than `docs-review`, which prints only after wave 1. The reason is the size of the
runs: a review that costs 200k does not need a running total, one that can reach several million
does. The line is **progress, not report**, so it does not count against the two-line chat budget.

Take the numbers from the `usage` field each agent returns. Never estimate a figure that was
actually reported — a `[derived]` total that could have been `[measured]` breaks the same rule the
evidence files are held to.

## Where the money goes

From the measured run:

| Wave | Agents | Tokens | Tool calls |
| ---- | -----: | -----: | ---------: |
| 1 — extract and probe | 10 | 1,721,594 | 125 |
| 2 — uncovered areas | 2 | 339,925 | 65 |
| 3 — verify | 3 | 693,229 | 112 |

Wave 1 is roughly two thirds of the spend, and it is the wave whose size the planner controls. The
levers, in order of effect:

1. **`--incremental`** when a prior report exists — analyse the delta, not the set.
2. **Fewer, larger document slices.** 700 lines per mapper is a ceiling, not a target; a 900-line
   document as one agent beats two agents plus a cross-shard wave to reconcile them.
3. **Topic clusters for code probes, not identifiers.** Four agents answering twelve questions each
   beats twelve answering one.
4. **`--probe code,artifact`** when the forge is not part of the question. It removes an entire
   set-B agent and the whole forge preflight group.
5. **`--rounds 2`** when the document set is small. Convergence usually arrives before the ceiling
   anyway; the ceiling never forces an extra wave.

What does *not* work as a lever: shortening role prompts below the point where they still carry
their rules. The prompts are already at ~700 words, and the rules in them are what stop the
expensive mistakes — a wrongly upheld absence claim costs more than every token this skill will ever
spend on a run.

## What was deliberately not done

Three cheaper designs were considered and rejected. They are recorded here because each looks
attractive from a cost table and each fails the same way — by losing something no later check can
detect.

| Rejected | Why |
| -------- | --- |
| One slice per agent, agent dies after writing | Keeps every word but breaks the *thread*: the fourth agent inherits none of the first one's reasoning, and cross-slice contradictions stop being visible to anyone |
| A hard cap on tool calls | An agent out of quota concludes early rather than declaring itself unfinished, and a shallow answer reads exactly like a complete one |
| Passing a 5% distillate downstream instead of the extract | Compression at that ratio drops qualifying clauses, the link between distant passages, and anything the extracting agent could not tell was load-bearing — invisibly |

Together they would have saved perhaps another 15% over what is implemented, in exchange for two
failure modes that no reviewer, lint or convergence recount can see. This skill exists to stop
confident wrong conclusions; a saving that makes them likelier is not a saving.

## Estimating before you start

`plan_fleet.py` prints a floor:

```text
floor ~176k base tokens (bodies and tool results on top)
```

Treat it as a floor and say so. A measured run came in roughly **fifteen times** its base floor. If
that multiple would take a run past what the session can afford, say it in the plan line **before**
dispatching, and offer `--incremental`, a narrower `--probe`, or a smaller document set — rather
than starting and stopping halfway, which is the one outcome that pays full price for nothing.
