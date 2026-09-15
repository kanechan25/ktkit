---
name: cr-delta
description: "Use when a change request arrives against a feature that already has an approved spec, and especially when implementation has already started. Reads the CR's old-behaviour and new-behaviour sections, the current spec, and the run's task-state ledger, then reports what changed, which finished work it invalidates, and what to append to spec.md, plan.md and tasks.md. Never re-reads the repository to find out what a task touched -- the task recorded that when it finished. Stops outright on a contradiction, on an invalidation nothing can explain, and on a change large enough to be a new requirement. Trigger on /ktkit:cr-delta <cr-file>, or when the user asks what a change request breaks."
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Purpose

A change request is not a feature request in different words. A feature starts
from nothing. A CR starts from a spec somebody approved, a plan somebody made,
and tasks somebody may already have built — and the expensive question is not
*what do we want now* but **what did we already do that this undoes**.

Answering that by re-reading the repository costs a full pass over the code for a
change that may touch two files. This skill does not. Every task that finished
recorded which requirements it satisfied and which paths it changed, at the
moment it finished; this reads that and asks the ledger, not the tree.

⛔ **It changes nothing.** It produces a report and a patch plan, then stops. The
patch is applied by the lane's spec and execute skills, after you have read it.

## Arguments

```
/ktkit:cr-delta <cr-file>
    [--spec <path>]       the current spec.md. Default: resolved from the CR's
                          own sub-path, the same way every other skill resolves it
    [--ledger <path>]     the run's resolved.md. Default: the chain run for this
                          base. `task-state.md` sits beside it
    [--threshold <0..1>]  word overlap above which two statements are the same
                          requirement reworded. Default 0.45
    [--json]              machine-readable output instead of the report
```

## STEP 0 — PREFLIGHT

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py" \
  --groups artifacts,speckit --repo "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
```

Exit 1 ⇒ ⛔ **STOP**. Nothing has been read and nothing spent.

## STEP 1 — THE INPUT MUST BE A CR

The file must carry `type: CR` and must have **both** `§2` (old behaviour) and
`§3` (new behaviour). That pair is what makes a CR a delta; without it there is
nothing to subtract from.

⛔ **Missing `§2` ⇒ STOP, and do not reconstruct it from the code.** Reading the
current behaviour out of the repository is exactly the expensive pass this skill
exists to avoid, and a reconstruction is this skill's opinion of the old
behaviour rather than the reporter's. Send it back to `/ktkit:raise-issue`.

## STEP 2 — RUN THE DELTA

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cr_delta.py" \
  --cr <cr-file> --spec <spec.md> --ledger <resolved.md>
```

Three sections come back, and never more:

| Section | What it holds |
| ------- | ------------- |
| `delta` | added · modified · removed · contradicted · ambiguous |
| `impact` | requirements, files, and tasks split into invalidated / superseded / untouched |
| `patch` | what to append to `spec.md`, `plan.md`, `tasks.md` |

**`invalidated` and `superseded` are not synonyms**, and the difference decides
what happens next:

- `invalidated` — the task was **done**, against a requirement that no longer
  says that. There is work in the tree that is now wrong, and something has to
  unwind or rework it.
- `superseded` — the task was **not** done and its definition changed underneath
  it. Nothing was built; the row is stale and its replacement is appended.

`impact.files` comes from the ledger's `touched` column and from nowhere else.
⛔ Never verify it by searching the repository: that is the pass this skill
exists to avoid, and a task that finished already said what it changed.

## STEP 3 — THE THREE STOPS

They are exit codes, not advice. Each one ends the run and hands the question to
a person.

| Exit | Name | Why a script must not decide it |
| ---- | ---- | ------------------------------- |
| 1 | `contradicted` | Two requirements cannot both hold. Picking one is a product decision wearing a diff's clothes. |
| 2 | `uncitable-invalidation` | A `done` task is being killed and no requirement id explains why. The ledger is missing `spec_refs`, so nothing can show what killed it — and an invalidation nobody can justify is indistinguishable from a mistake. |
| 3 | `not-a-change-request` | More than 60% of tasks are reached. This is a new requirement wearing a change request's clothes; route it as NR and get the analysis a new requirement earns. |

On any of them: print the report, state which stop fired, and **wait**. ⛔ Do not
apply the patch, and do not soften the threshold to get past it.

Exit 2 has one extra obligation: say **which** tasks lack `spec_refs`. That is a
gap in how the run recorded its work, and it will happen again on the next CR
unless somebody fixes the recording.

## STEP 4 — HAND THE IMPACT BACK, DO NOT WRITE IT

⛔ **This skill does not write to the ledger.** The ledger belongs to
`/ktkit:chain`, which owns the run directory and every row already in it, and a
second writer is how an append-only file gains two orderings.

Report the reached tasks, split into invalidated and superseded, and say which
requirement reached each. The chain records them, one transition per task, from
the state each task was already in — that state is the fact that separates *built
and now wrong* from *never built*, and it is already written down.

⛔ **Append-only, whoever writes it.** Nothing is deleted and no row is rewritten.
A task that was built and is now wrong stays in the history as having been built;
that is how the next reader knows there is code to unwind.

## STEP 5 — HAND OFF

```
patch.spec.md   → /ktkit:feat-req-specs, as an amendment to the existing spec
patch.plan.md   → /ktkit:feat-req-execute STEP 6
patch.tasks.md  → appended, never renumbered
```

⛔ **Requirement ids are never reused or renumbered.** A modified requirement
keeps its id and gains a revision note; a withdrawn one is marked withdrawn and
left in place. Everything that already cites `FR-14` — tasks, the ledger, a
review comment in a pull request — keeps pointing at the same thing.

## HARD STOP

Report the three sections, the stop if one fired, and what you wrote to the
ledger. Then stop. ⛔ This skill never edits `spec.md`, `plan.md`, `tasks.md` or
any code.

## Unknown handling

Whenever anything is unknown — a requirement id that appears in the CR and not in
the spec, two readings of a changed statement — **invoke skill
`/ktkit:escalation-ladder`** and follow it. The `cited_but_absent` list in the
report exists so that question is asked with the evidence already attached.
