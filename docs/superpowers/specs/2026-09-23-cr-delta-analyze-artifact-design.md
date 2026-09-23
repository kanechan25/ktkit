# cr-delta writes the analysis its lane position already promised

Date: 2026-09-23 · Status: awaiting review · Scope: `skills/cr-delta`, `skills/chain/references/lanes.md`, `README.md`

## The problem

`/ktkit:cr-delta` sits at phase 01 of the CR lane and produces no file. Its two
siblings at the same position — `/ktkit:rca` for BUG and `/ktkit:analyze-feat`
for NR — each write `.claude/claude/analyze/<rel>/<base>.analyze.md`. A CR is the
only lane whose analysis phase leaves nothing to review.

That is not a preference. Three places in the repository already say the artifact
should exist:

1. **`skills/chain/SKILL.md:64-72`** — the artifact map lists
   `.claude/claude/analyze/<rel>/<base>.analyze.md` as row `A` with **no lane
   qualifier**, while every row below it is tagged (`B CR · NR`, `B BUG`,
   `C CR · NR only`). Row `A` is written by all three lanes; CR does not deliver it.
2. **`scripts/help.py` index** — `cr-delta` is in group `Understand` at order 25,
   between `analyze-feat` (20) and `rca` (21). Same group, same lane position,
   different contract.
3. **`skills/chain/references/lanes.md:9,14`** — still lists CR phase 01 as
   `/ktkit:analyze-feat` and says *"CR runs the NR column until a dedicated
   `cr-delta` skill exists (C3)"*. That sentence is stale: the skill shipped in
   5.2.0 (README, *"Upgrading to 5.2.0 - the CR lane knows what it undoes"*) and
   `chain/SKILL.md:183` already routes CR to it. Two files in
   the same skill disagree about which skill runs at phase 01.

The skill's own body is explicit about the current contract — *"⛔ It changes
nothing. It produces a report and a patch plan, then stops"* (`SKILL.md:26`) — so
this is a deliberate design being revisited, not a bug being fixed.

## What must not be lost

`cr-delta` is cheap on purpose, and the reason is written down:

> Answering that by re-reading the repository costs a full pass over the code for
> a change that may touch two files. This skill does not. — `SKILL.md:20-24`

Measured against its siblings, that cheapness is structural:

| Skill | SKILL.md lines | Reading discipline |
| ----- | -------------- | ------------------ |
| `analyze-feat` | 741 | Scan → Peek → Full Read, hard cap 3 files, graph and docs-retrieval tools |
| `rca` | 417 | two conditional branches "costing no model tokens" |
| `cr-delta` | 147 | reads three known paths, runs one deterministic script |

The failure mode of this change is importing `analyze-feat`'s exploration
machinery "to make it a proper sibling". Section 7 exists to forbid that.

## Design

### 1. Position and output

`cr-delta` keeps its name and its place as CR lane phase 01, and writes

```
.claude/claude/analyze/<rel>/<base>.analyze.md
```

`<rel>` and `<base>` mirror the input's sub-path under `prompts/`, by the same
resolution `analyze-feat` uses and `chain/SKILL.md:78` already specifies.
Downstream needs no change: `feat-req-specs` reads the file it already reads.

⛔ No lane-specific suffix such as `.cr.md`. A lane that produces a differently
named artifact is exactly what the unqualified row `A` avoids.

### 2. Document shape

Vietnamese prose, matching `analyze-feat` and `rca`; identifiers, paths and code
stay as written. Every section's material already exists in the CR file that
`raise-issue` produced against `references/form-cr.md`.

| Section | Source | Answers |
| ------- | ------ | ------- |
| §1 Delta in one sentence | CR §1 | what becomes what |
| §2 Old behaviour | CR §2, plus the `modified`/`removed` rows `cr_delta.py` derived from `spec.md` | what it did before |
| §3 New expected behaviour | CR §3 (reason, requester) | what is expected after |
| §4 Requirement delta | `cr_delta.py` | added · modified · removed · contradicted · ambiguous |
| §5 Finished work this negates | the evidence ladder (§3 below) | impact against the old state |
| §6 Backward compatibility | CR §7 | raised as a question, never decided |
| §7 Proposed patch | `cr_delta.py` | spec.md · plan.md · tasks.md |
| §8 Unknowns | `escalation-ladder` | what still needs a human |

§6 inherits the rule `form-cr.md` already states: backward compatibility is a
business decision, and the model states the options without choosing one.

### 3. The evidence ladder for §5

Five tiers, ordered by **trust**, not by search order. Machine-recorded at the
moment of the event outranks human recollection; human recollection outranks
nothing measured at all.

| Tier | Source | Written by | Written when | Always present? |
| ---- | ------ | ---------- | ------------ | --------------- |
| **E1** | `task-state.md` (`spec_refs`, `touched`) | machine | the moment a task is marked `done` | only after a `chain` run |
| **E2** | `implemented/<rel>/<base>.implt.md` | machine | the moment implementation finished | only after `feat-req-execute` |
| **E3** | **CR §2 + §5** | human, paths verified by `raise-issue` | at raise time | **yes** — §2 is a mandatory slot |
| **E4** | `spec-recon --probe` | measured from code | on demand | opt-in only |
| **E5** | `NOT-MEASURED` | — | — | — |

E3 is the floor and the reason §5 is never empty. It costs nothing extra: the CR
file is already the one file the model reads (§7.1). `raise-issue` labels each
row of CR §5 `[VERIFIED]` / `[UNVERIFIED]` / `[LOCATED …]`.

⛔ **Labels pass through unchanged.** `[UNVERIFIED]` in is `[UNVERIFIED]` out. A
human's statement about what exists is evidence about the claim, never about the
code, and nothing in this skill may launder one into the other.

Every row carries the tier that answered it:

```
[E1 ledger]           INVALIDATED  T-07  FR-14  src/…/DepotAllocation.cs
[E2 implt]            BUILT        feature `depot-code` · 4 of 12 files match CR §5
[E3 CR§5 VERIFIED]    BUILT        src/…/depotCodeOf.ts:142
[E3 CR§5 UNVERIFIED]  CLAIMED      "the depot configuration screen"
[E4 probe]            REFUTED      src/…/ExportService.cs:88
[E5]                  NOT-MEASURED
```

E5 now means the CR left §2 and §5 empty — a malformed CR worth reporting, not an
ordinary state.

### 4. A stop no longer swallows the artifact

Today the three stops print to chat and end the run, leaving nothing to review:
exit `1` contradicted, `2` uncitable invalidation, `3` not a change request.

After this change the document is written **first**; the stop becomes a section
plus a frontmatter field, and only then does the run stop.

```yaml
stop: contradicted        # none | contradicted | uncitable | not-a-cr
```

A `contradicted` result — two requirements that cannot both hold — is the single
most review-worthy output this skill produces, and it is currently the only one
that leaves no trace. The stop still blocks the lane; it now blocks it with the
evidence on disk.

### 5. What does not change

- `scripts/cr_delta.py` is untouched. It stays the measurement; its stdout and
  `--json` become §4 and §7 of the document.
- "Read the ledger, not the repository" stays the **default**. E4 is opt-in.
- `--json` still prints to stdout and writes no file, for callers piping it on.
- `--spec`, `--ledger`, `--threshold` keep their exact meanings.

### 6. Wiring that must change with it

| File | Change | Why it is mandatory |
| ---- | ------ | ------------------- |
| `skills/cr-delta/SKILL.md` | writing step, §2 template, evidence ladder, `--probe` | the change itself |
| `skills/cr-delta/references/help.md` | document `--probe`; "What you get" becomes the file path | `test_help.py` H3 fails on an undocumented flag |
| `skills/chain/references/lanes.md:9,14` | CR 01 becomes `cr-delta`; delete the "until a dedicated cr-delta skill exists" sentence | it contradicts `chain/SKILL.md:183` |
| `README.md` | restate cr-delta in the summary table | it describes the old contract |
| `.claude-plugin/plugin.json` | version `6.2.0` | behaviour extended, no existing interface broken |

### 7. Cost ceilings — binding on every section above

**7.1 The model reads one file.** `cr_delta.py` already opens `--cr`, `--spec` and
`--ledger` itself.

```
model reads:      the CR file (§2/§3 for the narrative) + cr_delta.py stdout
model never reads: spec.md · task-state.md · resolved.md · any source file
```

⛔ `spec.md` never enters the model's context. The script has read it; reading it
again pays twice for the same fact, and it is what keeps input roughly constant
however large the spec grows.

**7.2 Four absolute prohibitions**, each already the practice of some skill here:

| ⛔ | Already stated in |
| -- | ----------------- |
| No grep or scan of the repository to "verify" `impact.files` | `cr-delta` help — *"That is the pass. The task said what it touched when it finished."* |
| No subagent dispatch for analysis | `cr-delta` has none today |
| Never print the document into the conversation | `escalation-ladder` — *"a table printed to chat is billed as output and then re-billed on every following turn"* |
| No Scan/Peek/Full-Read, no graph or docs-retrieval tooling | those belong to `analyze-feat` at NR phase 01 |

The conversation receives the file path, the stop if one fired, and one metric
line. Nothing else.

**7.3 The document cites; it does not copy.** §2 and §3 reference `CR §2` / `CR §3`
and write only the delta. The reviewer has both files open. Per-section ceilings,
checkable by eye:

```
§1  one line
§2  ≤ 5 bullets, each citing CR §2 or a spec FR id
§3  ≤ 5 bullets
§4  a table rendered from cr_delta.py, never written by hand
§5  a table, every row tagged [E1|E2|E3|E4|E5]
§6  ≤ 3 questions, no answers
§7  rendered from cr_delta.py
§8  ≤ 3 rows — the cap escalation-ladder already enforces
```

§4 and §7 are rendered, so the prose the model actually generates is §1–§3, §6
and §8.

**7.4 The two expensive doors are both locked.**

- **E2** is one `test -f` on a path derived by the same `<rel>/<base>` mirror — no
  search. When present, only `## Files Changed` and `Acceptance Criteria` are
  read, never the prose of `## What Was Built`.
- **E4** runs only when `--probe` is typed. Absent, §5 records `[E5]
  NOT-MEASURED` and the run continues. ⛔ It never enables itself, not even when
  E1, E2 and E3 are all empty.

**7.5 `scripts/budget.py` is deliberately not wired in.** It expects `--base` to be
a run directory carrying `cost.jsonl` and `budget.jsonl` — the accounting built
for `spec-recon`'s agent fleet. A skill that reads one file and runs one script
has nothing to account for, and the counter would cost more than what it guards.
The ceiling here is structural (7.1–7.4) and is checked by reading `SKILL.md`,
not by running anything.

## Cost, before and after

| | Today | After |
| - | ----- | ----- |
| Model input | CR file + script stdout | the same, plus `implt.md` only when E2 exists |
| Model output | a report printed into the conversation | a document written to a file, and **not** printed |
| Re-billed every later turn | yes — the report sits in context | no — one path line remains |

The genuine increase is the output tokens of §1–§3, §6 and §8, bounded by 7.3. It
is offset by 7.2 removing the per-turn re-billing of today's chat-printed report.

⚠️ **Not measured.** No token measurement of a real `cr-delta` run exists. The
table above is reasoned from the number of files opened and the printing rules,
not observed. Measuring it means running one real CR and reading `/context`
before and after.

## Open questions

None outstanding. The ledger-absent case, raised in review, is resolved by tier E3.

## Rejected alternatives

- **`analyze-feat` runs first and `cr-delta` appends to its file.** Maximum reuse,
  but it runs two skills at one phase, and `analyze-feat` has no notion of CR §2
  or §3 — the old-behaviour half of the delta would be reconstructed rather than
  read.
- **A new `analyze-cr` skill wrapping `cr_delta.py`.** Clean separation of
  responsibility, at the price of a nineteenth skill and two confusingly similar
  names at the same lane position.
- **Falling back to a repository scan when no ledger exists.** This is the full
  code pass the skill was created to avoid. Available deliberately as E4 behind
  `--probe`, never as a default.
