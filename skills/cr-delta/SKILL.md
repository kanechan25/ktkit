---
name: cr-delta
description: "Use when a change request arrives against a feature that already has an approved spec, and especially when implementation has already started. Reads the CR's old-behaviour and new-behaviour sections, the current spec, and the run's task-state ledger, then writes one analysis document saying what changed, which finished work it invalidates, and what to append to spec.md, plan.md and tasks.md. Never re-reads the repository to find out what a task touched -- the task recorded that when it finished. Records a contradiction, an invalidation nothing can explain, and a change large enough to be a new requirement as stops in the document, then halts. Trigger on /ktkit:cr-delta <cr-file>, or when the user asks what a change request breaks."
argument-hint: "<cr-file> [--spec <path>] [--ledger <path>] [--threshold 0..1] [--probe] [--json]"
user-invocable: true
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

This is **phase 01 of the CR lane**, the position `/ktkit:rca` holds for BUG and
`/ktkit:analyze-feat` holds for NR. Like both of them it produces exactly one
artifact — `.claude/claude/analyze/<rel>/<base>.analyze.md` — and like both of
them it stops there.

⛔ **It changes nothing else.** One analysis document is the only write. The patch
it proposes is applied by the lane's spec and execute skills, after you have read
it.

## Arguments

```
/ktkit:cr-delta <cr-file>
    [--spec <path>]       the current spec.md. Default: resolved from the CR's
                          own sub-path, the same way every other skill resolves it
    [--ledger <path>]     the run's resolved.md. Default: the chain run for this
                          base. `task-state.md` sits beside it
    [--threshold <0..1>]  word overlap above which two statements are the same
                          requirement reworded. Default 0.45
    [--probe]             measure tier E4 with `/ktkit:spec-recon`. Off by
                          default, and it never turns itself on
    [--json]              print the machine-readable delta to stdout as well.
                          The document is written either way
```

## STEP 0 — PREFLIGHT

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py" \
  --groups artifacts,speckit --repo "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
```

Creates `<repo-root>/.claude/claude/{prompts,analyze,specs,pipeline,implemented,compacts}`
when the repository does not have them, so STEP 4 has somewhere to write.
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

## STEP 3 — THE EVIDENCE LADDER FOR "WHAT WAS ALREADY BUILT"

The ledger is the best source and it is not the only one. A CR can land on a
feature built before this toolkit existed, built by hand, or built by somebody
else — and in every one of those cases a person still knows what shipped.

Five tiers, ordered by **trust**, not by search order: recorded-by-a-machine-at-
the-moment beats remembered-by-a-person, and remembered beats nothing measured.

| Tier | Source | Written by | When | Present |
| ---- | ------ | ---------- | ---- | ------- |
| **E1** | `task-state.md` — `spec_refs`, `touched` | machine | the moment a task turns `done` | after a `/ktkit:chain` run |
| **E2** | `implemented/<rel>/<base>.implt.md` | machine | the moment implementation finished | after `/ktkit:feat-req-execute` |
| **E3** | **the CR's own `§2` and `§5`** | a person; paths verified by `/ktkit:raise-issue` | at raise time | **always** — `§2` is mandatory |
| **E4** | `/ktkit:spec-recon` | measured from code | on demand | only with `--probe` |
| **E5** | `NOT-MEASURED` | — | — | — |

**E3 is the floor, and it is why this section is never empty.** It also costs
nothing: the CR file is already the one file this skill reads.

⛔ **The labels `/ktkit:raise-issue` attached pass through unchanged.**
`[UNVERIFIED]` in is `[UNVERIFIED]` out. What a person says exists is evidence
about the claim, never about the code, and nothing here may launder one into the
other.

**E2 is one `test -f`, never a search.** The path is derived by the same
`<rel>/<base>` mirror everything else uses. When the file is there, read
`## Files Changed` and `Acceptance Criteria` and stop — ⛔ not the prose of
`## What Was Built`.

**E4 runs only when `--probe` was typed.** Without it, write `[E5] NOT-MEASURED`
and carry on. ⛔ It never enables itself, not even when E1, E2 and E3 are all
empty.

Every row in §5 of the document carries the tier that answered it:

```
[E1 ledger]           INVALIDATED  T-07  FR-14  <path the ledger recorded>
[E2 implt]            BUILT        feature <name> · 4 of 12 files match CR §5
[E3 CR§5 VERIFIED]    BUILT        <path:line raise-issue confirmed>
[E3 CR§5 UNVERIFIED]  CLAIMED      <what ops described, unchecked>
[E4 probe]            REFUTED      <path:line spec-recon opened>
[E5]                  NOT-MEASURED
```

E5 across the whole section means the CR left `§2` and `§5` empty — a malformed
CR worth reporting, not an ordinary outcome.

## STEP 4 — WRITE THE ANALYSIS

```
.claude/claude/analyze/<rel>/<base>.analyze.md
```

`<rel>` and `<base>` mirror the CR file's sub-path under `prompts/`, exactly as
`/ktkit:analyze-feat` resolves them. `mkdir -p` the directory if it is missing.
⛔ Never derive `<base>` from anything but the input's own name.

> **Language**: the document is written in **Vietnamese**. Code snippets, file
> paths, symbol names, requirement ids and technical names stay exactly as they
> are — only the descriptive prose is Vietnamese.

```markdown
---
type: CR-ANALYSIS
cr: <path to the CR file>
spec: <path to spec.md>
stop: none | contradicted | uncitable | not-a-cr
evidence: E1 | E2 | E3 | E4 | E5        # the highest tier that answered §5
---

# §1. Delta trong một câu
# §2. Behavior CŨ            — cite CR §2; write only what the delta touches
# §3. Behavior MỚI kỳ vọng   — cite CR §3, with the reason and the requester
# §4. Delta theo requirement — rendered from cr_delta.py
# §5. Công việc đã làm bị phủ định — the ladder table from STEP 3
# §6. Backward-compat        — questions from CR §7, never answers
# §7. Patch đề xuất          — rendered from cr_delta.py
# §8. Chưa biết / cần quyết  — from /ktkit:escalation-ladder
```

`§6` inherits the rule `raise-issue`'s CR form already states: backward
compatibility is a business decision. ⛔ State the options and who must choose.
Never choose.

The conversation gets the path, the stop if one fired, and one metric line.
⛔ **Never print the document into the chat.** A table printed to chat is billed
as output and then re-billed on every following turn, and the content is already
in the file.

## STEP 5 — THE THREE STOPS

They are exit codes, not advice. Each one ends the run and hands the question to
a person.

| Exit | Name | Why a script must not decide it |
| ---- | ---- | ------------------------------- |
| 1 | `contradicted` | Two requirements cannot both hold. Picking one is a product decision wearing a diff's clothes. |
| 2 | `uncitable-invalidation` | A `done` task is being killed and no requirement id explains why. The ledger is missing `spec_refs`, so nothing can show what killed it — and an invalidation nobody can justify is indistinguishable from a mistake. |
| 3 | `not-a-change-request` | More than 60% of tasks are reached. This is a new requirement wearing a change request's clothes; route it as NR and get the analysis a new requirement earns. |

⛔ **A stop does not swallow the artifact.** STEP 4 runs first, the stop is
recorded in the `stop:` frontmatter field and in its own section, and only then
does the run halt. A `contradicted` result is the most review-worthy thing this
skill produces; leaving no trace of it is how the same argument gets had twice.

Then: state which stop fired and **wait**. ⛔ Do not apply the patch, and do not
soften the threshold to get past it.

Exit 2 has one extra obligation: say **which** tasks lack `spec_refs`. That is a
gap in how the run recorded its work, and it will happen again on the next CR
unless somebody fixes the recording.

## STEP 6 — HAND THE IMPACT BACK, DO NOT WRITE IT

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

## STEP 7 — HAND OFF

```
§7 patch.spec.md   → /ktkit:feat-req-specs, as an amendment to the existing spec
§7 patch.plan.md   → /ktkit:feat-req-execute STEP 6
§7 patch.tasks.md  → appended, never renumbered
```

⛔ **Requirement ids are never reused or renumbered.** A modified requirement
keeps its id and gains a revision note; a withdrawn one is marked withdrawn and
left in place. Everything that already cites `FR-14` — tasks, the ledger, a
review comment in a pull request — keeps pointing at the same thing.

## Cost ceilings

This skill is cheap because of what it is forbidden to do, not by accident.

**One file reaches the model.** `cr_delta.py` opens `--cr`, `--spec` and
`--ledger` itself.

```
the model reads:       the CR file (§2 · §3 · §5) and cr_delta.py's output
the model never reads: spec.md · task-state.md · resolved.md · any source file
```

⛔ `spec.md` never enters the model's context — the script has read it, and
reading it a second time pays twice for one fact. That is what keeps the input
roughly constant however large the spec grows.

| ⛔ Forbidden | |
| ------------ | - |
| Grep or scan the repository to "verify" `impact.files` | that is the pass this skill exists to avoid |
| Dispatch a subagent to analyse | it has never needed one |
| Print the document into the conversation | billed as output, then re-billed every later turn |
| Import a Scan/Peek/Full-Read phase, a code graph, or a docs-retrieval tool | those belong to `/ktkit:analyze-feat` at NR phase 01 |

**The document cites; it does not copy.** `§2` and `§3` reference the CR's own
sections and write only the delta — the reviewer has both files. Per-section
ceilings:

```
§1  one line
§2  ≤ 5 bullets, each citing CR §2 or a spec requirement id
§3  ≤ 5 bullets
§4  a table rendered from cr_delta.py, never written by hand
§5  a table, every row tagged [E1|E2|E3|E4|E5]
§6  ≤ 3 questions, no answers
§7  rendered from cr_delta.py
§8  ≤ 3 rows — the cap /ktkit:escalation-ladder already enforces
```

§4 and §7 are rendered, so the prose actually generated is §1–§3, §6 and §8.

## HARD STOP

Write the document, print its path, the stop if one fired, and the metric line.
Then stop. ⛔ This skill never edits `spec.md`, `plan.md`, `tasks.md`, the ledger,
or any code.

## Unknown handling

Whenever anything is unknown — a requirement id that appears in the CR and not in
the spec, two readings of a changed statement — **invoke skill
`/ktkit:escalation-ladder`** and follow it. The `cited_but_absent` list in the
delta exists so that question is asked with the evidence already attached.
