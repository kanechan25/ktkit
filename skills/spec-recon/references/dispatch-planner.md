# Dispatch planner

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/spec-recon/scripts/plan_fleet.py" \
    <base>/recon.json --probe code,artifact,vcs --baseline <paths> --rounds 3
```

## The boundary

**The planner decides structure. You decide content.**

Structure — how many agents, of which roles, in which wave — is deterministic, comes out of
`recon.json`, and is locked by `test_plan_fleet.py`. Content — what each agent is actually asked, in
the words of `--scope` — is yours.

The reason for drawing it here: a fleet that comes out differently on every run is not dynamic, it
is unreproducible, and two runs over one input set that dispatch different agents cannot be compared
or debugged. The falsifier is written into the test: *if two runs over one `recon.json` produce
different plans, this boundary is wrong.*

## Sharding

| Source | Rule | Cap |
| ------ | ---- | --: |
| text document | one agent per ≤700 lines, or per top-level section, whichever is smaller | 12/wave |
| HTML document | one agent, and **strip tags to a temp file first** — an agent reading raw markup spends its budget on markup | 1 |
| baseline document | one agent per document, **never split**: a change surface needs continuity | 1/doc |
| binary artifacts | one agent for the whole group; measuring in bulk is cheaper than per file | 2 |
| code questions | one agent per **topic cluster**, never one per identifier | 4 |
| vcs | exactly one agent — the rate limit is shared | 1 |

**Hard cap: twelve agents per message.** More than that runs in batches inside the same wave.

## Three rules inherited from large sets, not to be reinvented

1. **The same roles at every size.** Document count changes *how many* agents run, never *which*
   ones.
2. **An index is mandatory above ~15 documents**, and its `Values asserted` column — every number,
   threshold, state name, format and ID pattern — feeds a separate conflict sweep. That sweep finds
   the disagreements no requirement row would ever have caught.
3. **Shard waves do not count against `--rounds`.** Only cross-shard waves do. After the shard waves,
   run exactly one cross-shard wave looking for the four things a shard boundary hides: a
   requirement falling between two slices, one requirement with two different verdicts, a conflict
   no shard reflected, and a shard whose coverage declaration is weaker than the verdicts it
   produced.

## Routing: evidence type to probe

| The question is | Probe |
| --------------- | ----- |
| "the spec requires X — does the code have it?" | `probe-code`, then `arbiter-impl` if the answer is no |
| "does the shipped template match the published form?" | `probe-artifact` — **and the deployed copy too** when a fallback blob exists |
| "what state is this issue / PR / milestone in?" | `probe-vcs` |
| "what does the real data look like?" | `probe-runtime` — **off by default**. Not enabled means the verdict is `needs-runtime-probe` plus the command to turn it on. Never answer it from seed files or fixtures. |
| "do documents A and B contradict each other?" | no probe — `ktkit:docs-review-coverage` |
| "is this citation real?" | `verify_citations.py` first; the `evidence` reviewer sees only the failures |

## Runtime is never inferred

`plan_fleet.py` cannot schedule `probe-runtime`. It appears only when `runtime` is in `--probe`,
which only happens when a human typed it. A planner able to infer it from the inputs would
eventually infer it wrongly, against a live system.

## Print the plan, then go

One line. No question, no pause:

```text
Recon: 6 docs (2 stale-risk) · 3 baselines · 3 binary · git+forge · prior report: none
Plan:  wave1 = 6 doc-extract + 3 state-extract + 1 artifact + 2 code + 1 vcs = 13 agents (2 batches)
       wave2 = 4 reviewers + 1 arbiter · cap 3 waves
```

## Batching

When a wave exceeds twelve agents, split it into batches **inside the same wave** — all of batch one
in a single message, then all of batch two. Do not turn a batch into a round: rounds are the
convergence counter, and inflating them makes a run look like it converged when it only ran out of
ceiling.
