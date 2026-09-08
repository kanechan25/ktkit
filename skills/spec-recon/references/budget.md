# The ceiling, the boundary, and the gate that narrows the reading

A run of this skill spent **15,200,000 tokens across 34 agents**, hit the session limit inside its
final wave, and produced **no verdict at all**. Every one of the 12.7M spent on extraction was still
on disk as evidence; the thing the run existed to produce — `REFUTED` / `UPHELD` / `GAP` — was not.

Nothing in the skill could have prevented it, because nothing in the skill measured anything until
it was over. The cost model printed a floor and a multiple; the multiple was measured on one run and
turned out to understate this one by **4.2×**.

Three mechanisms now stand between a run and that outcome. None of them forecasts.

| | What it does | Measured effect |
| - | ------------ | --------------- |
| `quota.py` | reads the subscription window before the run starts | opens or closes the gate |
| `relevance.py` | reads only the inputs the question occurs in | **48 mapper agents → 20** |
| `budget.py` | at every step boundary, asks whether another step fits | stops **at a boundary**, work banked |

## 1. Why prediction was the wrong instrument

The obvious design is to estimate the run and compare it with what is available. Two rounds of this
work tried, and both were wrong in the same way.

The first tried to predict from the corpus. But an agent's cost is dominated by its tool results, not
by the bytes it was given: a 96 KB shard is ~24,600 tokens of content, and the agents on that run
averaged **453,571 tokens each** — **18.2×** the shard. What drives it is the number of tool calls,
because an agentic loop re-sends everything accumulated so far on every call.

The second tried to predict from the quota, by converting the window's percentage into tokens. That
requires knowing how many tokens one percent buys, which is only true for the account and tier it
was measured on — and signing in with a different account moved the window from **94% used to 6%**
while the work was in progress. A stored ratio would have survived that silently and been wrong.

⭐ So nothing is predicted. **What the last step actually cost is the only estimate the next step
needs, and it is an observation.**

## 2. The ceiling — `budget.py`

Called at every step boundary: after each dispatch batch, after each arbitration, after each wave.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/spec-recon/scripts/budget.py" \
    --base <base> --budget 4000000 --quota-gate 85 --step <name>
```

```
spent + last_step × 1.5  >  budget            -> STOP (the ceiling)
window_headroom < last_step_pct × 1.5         -> STOP (the session)
```

`spent` comes from `cost.jsonl` — what each agent reported. `last_step` is the difference since the
previous boundary, recorded in `budget.jsonl` beside it. Both are `[measured]`.

`1.5` is the only tunable, and it is a margin rather than a model: a step may cost more than the one
before it, so the check asks for that much again plus half. Lower and a run dies inside a step;
higher and it stops with budget unspent.

A boundary checked twice sees no difference, and a zero difference would switch the lookahead off
while still printing `GO`. The estimate therefore falls back to **the last step that actually cost
something**, and names it. That failed silently in the first version, which is the failure mode this
whole file exists to remove.

### Raising the ceiling — and knowing whether the window can hold it

The default is a default. `--budget 8000000` for a large corpus, `--budget 2000000` for a quick
check. Measured, same spend, four ceilings:

```
spent 2,908,000 · last step 2,908,000 · a step like that needs 4,362,000

  --budget 2000000   STOP    --budget 6000000   STOP
  --budget 4000000   STOP    --budget 8000000   GO    (5,092,000 left)
```

Once a step has reported both tokens and a window percentage, the run knows its **own rate** and says
what the remaining window allows:

```
window allows about 14,505,000 tokens in total, at this run's own rate of
151,166 per 1%  [measured here, not stored]
  ⇒ the 20,000,000 ceiling will not be reachable in this window;
    raise it only if you also wait for the reset
```

⛔ **That rate is never stored and never carried between runs.** It is two observations from the run
in front of you. An earlier design measured the same ratio once and persisted it — and signing in
with a different account moved the window from 94% used to 6% while the work was in progress, which
would have left the stored figure silently wrong. Measuring it inside the run costs nothing and
cannot go stale, because it is discarded with the run.

### A cheap step passes where an expensive one does not

This ordering is the point, not a side effect. Measured on the gate:

```
after 03-extract b3   spent 3,172,500 / 4,000,000   last step 927,500
                      ⛔ STOP: 827,500 left, a step like that needs 1,391,250

after 05-arbitrate    spent 3,477,500 / 4,000,000   last step 305,000
                      ✅ GO: 522,500 left, a step like that needs 457,500
```

Extraction is refused and arbitration proceeds. Arbitration is what turns evidence into an answer, so
it is the last thing that should be starved — a run that stops with evidence and no verdicts has
spent everything and delivered nothing, which is exactly what happened.

### Stopping is a result

On `STOP`: write `partial` into `manifest.md` naming precisely what was not reached, print the reset
time, print the resume command. Everything finished is on disk and is never re-run —
`step-protocol.md` explains why re-minting a completed step's IDs silently repoints every citation.

⛔ **Never dispatch a further step after `STOP`.** The ceiling is the user's number.

## 3. The narrowing — `relevance.py`

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/spec-recon/scripts/relevance.py" <base>/recon.json \
    --scope "<verbatim>" --threshold 0.01 --add <term>... \
    --report <base>/steps/01b-relevance.md --out <base>/recon-relevant.json
```

`--scope` becomes a search vocabulary; each input is scored in hits per kilobyte; inputs below the
threshold are excluded. On a real 64-file corpus this took wave 1 from **48 agents to 20**.

**Density, not presence.** A 456 KB reference table with two incidental matches looks relevant to a
keyword filter and is not. Giving it an agent to find those two matches is how a run reaches fifteen
million tokens.

**Meta-words are stopped.** A scope sentence names *where to look* as well as *what to look for* —
`code`, `spec`, `docs`, `implementation`. Measured: leaving `code` and `spec` in the vocabulary moved
the exclusion from 54 files to 17 on the same corpus, because they occur nearly everywhere.

### Three rules, and the first is what makes it safe

1. **Narrowing is never silent.** `steps/01b-relevance.md` lists every excluded file with its size
   and hit count; the report carries a `## Not read` section.
2. ⭐ **An absence claim from an excluded file is `not-accessed: cut by the relevance gate`, never
   `UPHELD`.** Without this rule the gate turns *"I did not read it"* into *"it does not exist"* —
   the `R-ARTIFACT` failure in a new place.
3. **The gate declines rather than guess.**

### Declining, and rescuing

Two signals mean the vocabulary itself is wrong, and either one makes the gate keep everything:

| Signal | Why |
| ------ | --- |
| **script mismatch** | most of the corpus is in a writing system no term covers |
| **too much was cut** | past ~85% of the corpus by size, the vocabulary probably does not fit |

Measured, and the reason this exists: a scope written in Vietnamese and English produced the four
terms `EXP-021 EXP-030 EXP-033 export` against a corpus that is **68% Japanese**, and would have
excluded the two main specification documents — 729 KB and 223 KB, zero hits each, because the
question says `export` and the document says `出力`. A gate that removes the specification because
the question was asked in another language is worse than no gate.

```
GATE-DECLINED  nothing excluded · terms: EXP-021 EXP-030 EXP-033 export
  - script mismatch: 68% of the corpus is CJK and no term is
  ⇒ every input is read; add a term in the corpus's own language with --relevance-add
```

A third case is narrower and gets a narrower answer. A document carrying revision markers is a
specification, and cutting a specification on a question about the specification is almost always
the gate being wrong — but declining the whole gate over one file out of fifty-six throws away the
saving to fix a single row. So specifications are **rescued**: kept regardless of density, named as
rescued in the report, while the reference tables that cost the tokens are still excluded.

⭐ Neither `GATE-DECLINED` nor a rescue is a failure. Both are the gate refusing to be the reason a
finding was missed.

## 4. What a ceiling actually buys — stated plainly

At the measured **453,571 tokens per agent**, a **4M** budget is about **8–9 agents**. The relevance
gate takes wave 1 of that corpus from 48 agents to 20, which is still roughly **9M**.

⛔ **So the ceiling does not make a 20-agent wave fit in 4M.** What it guarantees is different, and
worth being exact about:

- the run **stops at a boundary** rather than dying inside a wave;
- everything finished is **on disk**, and `--resume` continues from there;
- the stop names the reset time, so the remainder is one wait away rather than one re-run away.

Making the run *fit* needs the agents to be fewer or cheaper. The remaining levers, in order of
measured or expected effect:

| Lever | Effect | Status |
| ----- | ------ | ------ |
| `probe_index.py` — grep in a script, not in an agent | **~109x** on the read `[measured]`; zero-hit identifiers need no agent | shipped |
| `--relevance` when the vocabulary fits | 48 → 20 agents `[measured]` | shipped |
| ~~A cap on tool calls per agent~~ | ~~×0.36 from the quadratic~~ | ⛔ **WITHDRAWN** — the quadratic fitted worst of three models (R² 0.298 over 24 agents); calls explain under half the variance |
| **Fewer agents** — the only lever with measured support | dropping one agent saved a mean of **222,713** tokens `[measured]` | shipped, via the two gates above |
| Measure the dispatch payload | unknown; it is the one unmeasured term and the floor is 55% of a run | `dispatch_log.py` records it; nothing cut yet |
| Verdict per question rather than per run | a partial run keeps its verdicts | ⛔ architecture change |
| `--rounds 2` on a small set | one fewer review wave | shipped |
| `--probe code,artifact` | one set-B agent and the whole forge preflight | shipped |
| `--handoff off` | stops after evidence; no verdicts | shipped |

The full analysis, including what has not been measured, is in
`.claude/claude/analyze/spec-recon-budget-architecture.md`.

## 5. Where each number comes from

| Claim | Label | Source |
| ----- | ----- | ------ |
| 15.2M tokens, 34 agents, no verdict | `[measured]` | the run, 07/09/2026 |
| 453,571 tokens per agent | `[measured]` | 12.7M / 28 |
| tool results are 18.2× the shard given | `[derived]` | (453,571 − 6,619) / 24,576 |
| 48 mapper agents → 20 | `[measured]` | `plan_fleet.py` before and after the gate |
| 54 of 64 files carry zero scope hits | `[measured]` | the same corpus |
| adding `code`/`spec` moved the cut 54 → 17 | `[measured]` | the same corpus |
| corpus is 68% CJK by bytes | `[measured]` | `recon.json` language field |
| the window moved 94% → 6% on sign-in | `[measured]` | `quota.py`, same session |
| cost is quadratic in tool calls | `[derived]` ⚠️ | a model, **not yet measured** |
