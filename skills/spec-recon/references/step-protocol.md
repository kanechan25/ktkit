# Step protocol — every large step ends in a file

**No step takes its input from the previous step's conversation.**

The run this skill was modelled on lost two agents mid-flight. One of them had gathered everything
in context and planned to write at the end; it lost **100%** of its work. The other had been writing
as it went and lost only the tail. That difference is the whole reason this protocol exists.

Three things fall out of it, and only the first is obvious:

1. **A crashed run resumes** from the last completed step instead of from the beginning.
2. **Every conclusion is traceable** back to the step that produced it.
3. **The lead's context stays small**, because steps are concatenated rather than read and rewritten.

## Layout

```
<dir>/<base>.md                     the report
<dir>/<base>/
    steps/00-preflight.md           the gate
         01-recon.md                freshness, surface, and recon.json beside it
         02-fleet-plan.md           what the planner decided, and why that many
         03-extract-<slice>.md      one per mapper
         04-state-<doc>.md          one per baseline document
         05-collect.md              the merged inventory
         06-handoff.md              the package given to docs-review
         manifest.md                the index of all of the above
    evidence/probe-<kind>-<topic>.md
    recon.json
    scratch/
```

`<base>` comes from `--out`: a report at `<dir>/<base>.md` puts everything under `<dir>/<base>/`.
This is the same convention `docs-review` uses. Do not invent a second one.

## Rules

| Rule | |
| ---- | - |
| Write | Each completed step writes `steps/NN-<name>.md` before the next begins. |
| Read | Step `NN+1` receives the **file** `NN` plus a list of paths. Never the lead's reasoning. |
| Manifest | Every step appends a row: step · file · status · which step consumes it. |
| Citation | Every statement in a step file carries a `path:line` or a command that regenerates it. |
| Labels | Every number carries exactly one of `[measured]`, `[quoted]`, `[derived]`. |
| Append | Never rewrite a completed step file. A correction is a new row, with the reason. |

## manifest.md

```markdown
| Step | File | Status | Consumed by |
| ---- | ---- | ------ | ----------- |
| 00 | steps/00-preflight.md | complete (2 SKIP) | 01 |
| 01 | steps/01-recon.md | complete | 02 |
| 02 | steps/02-fleet-plan.md | complete | 03, 04 |
| 03 | steps/03-extract-ch1.md | complete | 05 |
| 03 | steps/03-extract-ch2.md | **missing** | 05 |
| 04 | steps/04-state-design.md | complete | 05 |
```

The manifest is the resume instruction. A row marked `missing` names exactly one agent to re-run.

## Resuming

1. Read `manifest.md`. Do not read the step files themselves.
2. The first row that is `missing` or `partial` is where the run restarts.
3. Re-dispatch only that step's agents, with the same inputs the manifest records.
4. Append the re-run to the manifest rather than editing the failed row. What failed, and when, is
   part of the record.
5. Never re-run a step marked `complete` because it would be "safer". A completed step's ID
   allocations — requirement IDs, claim IDs — are referenced by every later row, and re-minting them
   silently repoints every citation in the previous report at a different thing.

## Partial work is preferable to complete-looking work

If budget runs out mid-step, write what exists and mark the row `partial`, naming precisely what was
not reached:

```markdown
| 03 | steps/03-extract-ch4.md | partial: sections 4.1–4.3 only, 4.4–4.9 not accessed | 05 |
```

A step file that covers half its slice while looking whole is worse than a missing one: a reader
cannot tell it apart from a finished step, and neither can the next agent.
