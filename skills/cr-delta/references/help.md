<!-- group: Understand | order: 25 -->
# ktkit:cr-delta — what a change request breaks, read from the ledger not the repo

A change request starts from a spec somebody approved and tasks somebody may
already have built. The expensive question is **what did we already do that this
undoes** — and answering it by re-reading the repository costs a full pass over
the code for a change that may touch two files.

Every task recorded what it satisfied and what it touched when it finished. This
reads that, and writes one analysis document.

```
/ktkit:cr-delta <cr-file> [--spec <path>] [--ledger <path>] [--threshold 0..1] [--probe] [--json]
```

It is **phase 01 of the CR lane** — the slot `/ktkit:rca` fills for a bug and
`/ktkit:analyze-feat` fills for a new requirement — and it produces the same kind
of artifact they do.

## The cases

```bash
# the ordinary case: a CR against a feature that is already specified
/ktkit:cr-delta .claude/claude/prompts/2472-share-links/owner-override.md

# a run whose artifacts are not where they would be resolved from
/ktkit:cr-delta cr.md --spec .claude/claude/specs/2472-share-links/expiry/spec.md

# the feature was built before any of this existed — measure the code as well
/ktkit:cr-delta cr.md --probe

# feed the delta to something else; the document is still written
/ktkit:cr-delta cr.md --json
```

## Flags

| Flag | Default | When you need it |
| ---- | ------- | ---------------- |
| `--spec <path>` | resolved from the CR's sub-path | The spec is somewhere the usual resolution would not find. |
| `--ledger <path>` | the chain run for this base | Several runs exist for the same feature and you mean a particular one. |
| `--threshold <0..1>` | `0.45` | Word overlap above which two statements are the same requirement reworded. Raise it when the CR restates a lot of context; lower it when a rewrite is being read as a brand-new requirement. |
| `--probe` | off | Measures tier E4 with `/ktkit:spec-recon` — the code itself. ⛔ Costs a real reconnaissance run, and it never turns itself on. |
| `--json` | — | Also prints the machine-readable delta to stdout. |

## What you get

```
.claude/claude/analyze/<rel>/<base>.analyze.md
```

Eight sections: the delta in one sentence · old behaviour · new expected
behaviour · the requirement delta · **the finished work this negates** ·
backward-compatibility questions · the proposed patch · what still needs you.

The chat gets the path, the stop if one fired, and one metric line — never the
document itself.

**`invalidated` is not `superseded`.** Invalidated means the task was *done*, and
done against a requirement that has changed — there is work in the tree that is
now wrong. Superseded means it was never built and its definition moved. One
needs code unwound; the other needs a row rewritten.

## Where "already built" comes from

Five tiers, ordered by trust. Every row of the section says which one answered it.

| Tier | Source | Present when |
| ---- | ------ | ------------ |
| `E1` | the run's `task-state.md` | the feature went through `/ktkit:chain` |
| `E2` | `implemented/<rel>/<base>.implt.md` | it went through `/ktkit:feat-req-execute` |
| `E3` | **the CR's own §2 and §5** | **always** — §2 is a mandatory slot |
| `E4` | `/ktkit:spec-recon` | only with `--probe` |
| `E5` | not measured | — |

E3 is the floor, so the section is never empty — a feature built by hand, or
before this toolkit existed, is still describable. ⛔ The `[VERIFIED]` and
`[UNVERIFIED]` labels `/ktkit:raise-issue` attached pass through unchanged.

## It stops rather than deciding

| Exit | Why |
| ---- | --- |
| `1` contradicted | Two requirements cannot both hold. Choosing is a product decision. |
| `2` uncitable invalidation | A done task is being killed and no requirement id explains why — the ledger is missing `spec_refs`. |
| `3` not a change request | Over 60% of tasks reached. This is an NR in a CR's clothes. |

The document is written **before** the stop, with `stop:` in its frontmatter. A
contradiction is the most review-worthy thing here; it does not vanish into chat.

## Do not

| Anti-pattern | Why |
| ------------ | --- |
| Run it on a CR with no `§2` old behaviour | There is nothing to subtract from, and reconstructing the old behaviour from the code is the expensive pass this skill exists to avoid. |
| Verify the touched files by searching the repository | That is the pass. The task said what it touched when it finished. |
| Reach for `--probe` by habit | It buys a real reconnaissance run. E1, E2 and E3 are free and answer most CRs. |
| Lower `--threshold` to clear a `contradicted` stop | The stop is the finding. |
| Read an `E3 UNVERIFIED` row as fact about the code | It is what somebody said. Only `E1`, `E2` and `E4` were recorded or measured. |
| Renumber a requirement the CR modified | Everything already citing it — tasks, the ledger, a review comment — would keep pointing at the old meaning. |

## See also

`/ktkit:help raise-issue` — where the CR comes from, with `§2` and `§3` already
separated, and where `§5`'s evidence labels are attached. `/ktkit:help chain`
with `--cr` — the whole lane in one line.
