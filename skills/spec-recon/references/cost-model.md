# Cost model

> ⚠️ **This file estimates; it does not enforce.** The multiple below was measured on one run and
> understated a later one by **4.2×** — that run spent 15.2M tokens and returned no verdict.
> Enforcement lives in `references/budget.md`: a ceiling checked at every step boundary against what
> agents actually reported. Read this to understand where the money goes; read that one to keep a run
> inside a number.

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

## ⚠️ What drives the cost — fitted, and mostly unexplained

A later 24-agent run recorded tokens and tool calls per agent, which is enough to test the models
this file had been reasoning with. They do not survive.

| Candidate driver | R² over 24 agents |
| ---------------- | ----------------: |
| `sqrt(calls)` | 0.476 |
| `calls` (linear) | 0.421 |
| **`calls(calls+1)/2` (quadratic)** | **0.298** — the worst of the three |
| output tokens written | 0.145, slope negative |
| output × calls | 0.025 |

⛔ **The quadratic-in-tool-calls model is refused by the data**, and a proposed cap of six tool calls
per agent rested on it. That proposal is withdrawn: `cost-model.md` was already right to reject a
hard cap for a different reason — an agent out of quota concludes early — and the saving it was
supposed to buy is not there.

**What the data does show is a large per-agent floor.** The cheapest agent in that run cost
**123,460 tokens at four tool calls**; 24 × that floor is 2,963,040, or **55%** of the whole run.
Agents making ≥40 calls averaged 269,243 against 149,564 for those making ≤6 — **1.8×**, not the
order of magnitude a quadratic implies.

⭐ **So the lever with measured support is fewer agents, not fewer calls.** Dropping one agent saved a
mean of 222,713 tokens; halving an agent's calls is weakly related at best.

And the floor itself is unexplained. Wave 1 was handed 852,260 bytes of document — ~213,000 tokens,
9.7% of what it spent. One term was never measured: the prompt the lead composes and sends, which is
written nowhere and is re-sent on every internal turn a subagent takes.
`scripts/dispatch_log.py` records it. Until `dispatch.md` from a real run pairs payload against
spend, the floor stays `[unexplained]` — and nothing should be cut on the strength of a guess about
it.

## The cost file, and the per-wave line

Cost is an **artifact of the run**, not a line of chat. It used to be only the line, which meant the
only record of a multi-million-token run was whatever survived in scrollback — and a compaction ends
that. Two files, in the run directory:

```
<base>/cost.jsonl      append-only, one row per agent, the source of every figure
<base>/cost.md          rendered view, regenerated on each append
```

Written by `scripts/cost_log.py`, in **one call per wave**:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/spec-recon/scripts/cost_log.py" wave \
    --base <base> --wave N \
    --row 'probe-code,A,148200,3100,14,96' \
    --row 'probe-artifact,B,92400,2050,9,61' \
    --row 'probe-vcs,B,,,,,no usage returned'
```

`agent,toolset,tokens_in,tokens_out,tool_calls,seconds[,note]` — an empty field means that number
was not reported.

### The tracking must not cost what it tracks

This is why the call is per wave and not per agent, and the difference was measured rather than
assumed. Wave 1 of a real 62-document corpus is 43 agents:

| Shape | Calls | Command chars | Output chars | ~Tokens | Share of a 2,754,748-token run |
| ----- | ----: | ------------: | -----------: | ------: | -----------------------------: |
| one call per agent | 43 | 8,557 | 2,709 | ~4,106 | 0.149% |
| **one call per wave** | **1** | **1,903** | **63** | **~521** | **0.019%** |

Batching is **13%** of the per-agent cost and one round trip instead of 43. Character counts are
`[measured]`; the token figures are `[derived]` at four characters per token plus 120 characters of
Bash-call envelope, and are stated as approximate for that reason.

Half a thousand tokens to know what a two-million-token run cost is about the most this is worth
spending.

If even that is unwelcome, the answer is not to log approximately. A cost file that is partly guessed
is worse than none, because it gets quoted. The answer is a smaller run: `--incremental`, a narrower
`--probe`, or `--handoff off`.

`append` takes one agent with named flags and accepts `--usage-json`, which stores the harness usage
object verbatim. It is for a single late-returning agent or for debugging — not the hot path.

Then print what the script returns. It is computed from the file, not from memory:

```text
Wave 2: 5 agents · 339,925 tokens · 11m · running 1,205,844
```

This is stricter than `docs-review`, which prints only after wave 1. The reason is the size of the
runs: a review that costs 200k does not need a running total, one that can reach several million
does. The line is **progress, not report**, so it does not count against the two-line chat budget.

### What the file may and may not contain

Take the numbers from the `usage` field each agent returns. Never estimate a figure that was
actually reported — a `[derived]` total that could have been `[measured]` breaks the same rule the
evidence files are held to.

| Rule | |
| ---- | - |
| Missing is missing | An agent that reported no usage is written down as having reported none. The total then names how many agents it excludes and reads as a **floor**. ⛔ Never an average, never an interpolation. |
| Append only | A re-run wave appends. What the failed attempt cost is part of the record; a correction is `cost_log.py correct --reason <why>`, never an edit. |
| The lead is not in it | An agent cannot measure the session that dispatched it. `cost.md` says so out loud, because a total that silently omits the largest term is worse than no total. |
| One label per number | `[measured]` for what an agent reported, `[derived]` for the base floor computed from tool sets. Nothing else appears. |

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
