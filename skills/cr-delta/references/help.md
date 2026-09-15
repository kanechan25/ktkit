<!-- group: Understand | order: 25 -->
# ktkit:cr-delta — what a change request breaks, read from the ledger not the repo

A change request starts from a spec somebody approved and tasks somebody may
already have built. The expensive question is **what did we already do that this
undoes** — and answering it by re-reading the repository costs a full pass over
the code for a change that may touch two files.

Every task recorded what it satisfied and what it touched when it finished. This
reads that.

```
/ktkit:cr-delta <cr-file> [--spec <path>] [--ledger <path>] [--threshold 0..1] [--json]
```

## The cases

```bash
# the ordinary case: a CR against a feature that is already specified
/ktkit:cr-delta .claude/claude/prompts/2472-share-links/owner-override.md

# a run whose artifacts are not where they would be resolved from
/ktkit:cr-delta cr.md --spec .claude/claude/specs/2472-share-links/expiry/spec.md

# feed it to something else
/ktkit:cr-delta cr.md --json
```

## Flags

| Flag | Default | When you need it |
| ---- | ------- | ---------------- |
| `--spec <path>` | resolved from the CR's sub-path | The spec is somewhere the usual resolution would not find. |
| `--ledger <path>` | the chain run for this base | Several runs exist for the same feature and you mean a particular one. |
| `--threshold <0..1>` | `0.45` | Word overlap above which two statements are the same requirement reworded. Raise it when the CR restates a lot of context; lower it when a rewrite is being read as a brand-new requirement. |
| `--json` | — | Machine-readable output instead of the report. |

## What you get

```
delta    added · modified · removed · contradicted · ambiguous
impact   requirements · files · tasks (invalidated / superseded / untouched)
patch    spec.md · plan.md · tasks.md
```

**`invalidated` is not `superseded`.** Invalidated means the task was *done*, and
done against a requirement that has changed — there is work in the tree that is
now wrong. Superseded means it was never built and its definition moved. One
needs code unwound; the other needs a row rewritten.

## It stops rather than deciding

| Exit | Why |
| ---- | --- |
| `1` contradicted | Two requirements cannot both hold. Choosing is a product decision. |
| `2` uncitable invalidation | A done task is being killed and no requirement id explains why — the ledger is missing `spec_refs`. |
| `3` not a change request | Over 60% of tasks reached. This is an NR in a CR's clothes. |

## Do not

| Anti-pattern | Why |
| ------------ | --- |
| Run it on a CR with no `§2` old behaviour | There is nothing to subtract from, and reconstructing the old behaviour from the code is the expensive pass this skill exists to avoid. |
| Verify `impact.files` by searching the repository | That is the pass. The task said what it touched when it finished. |
| Lower `--threshold` to clear a `contradicted` stop | The stop is the finding. |
| Renumber a requirement the CR modified | Everything already citing it — tasks, the ledger, a review comment — would keep pointing at the old meaning. |

## See also

`/ktkit:help raise-issue` — where the CR comes from, with `§2` and `§3` already
separated. `/ktkit:help chain` with `--cr` — the whole lane in one line.
