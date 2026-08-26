# The solo loop — `--team off`

Read this when the user passed `--team off`. One context does the audit; one blind reviewer attacks
it each round. This is the shape the skill had before the agent team existed, restored because it is
the only configuration that produces **one transcript**, and because a run that must not spend the
team's quota still has to be able to happen.

It is **not** the degraded path. If the agents are not registered at all, that is
`review-team.md` §9 — a different situation with a different report header.

| | `--team off` | degraded (`review-team.md` §9) |
| --- | ------------ | ------------------------------ |
| Cause | the user chose it | the agents could not be dispatched |
| Reviewer | `ktkit:docs-review-solo-reviewer` | `general-purpose`, because nothing else is available |
| Line 1 of the report | normal | `DEGRADED — ...` |
| `## Review team` | `Mode=solo` | `Mode=degraded` |

## Modes this supports

**Mode A and Mode B only.**

Mode C is **not** available with `--team off`. Say so and stop:

```text
--team off is not available in Mode C. Critiquing a single document needs the claims/verify split:
verify must not be given the document, and one context cannot un-read it. Run without --team off,
or pass a spec to audit against for Mode A.
```

That is not a limitation to work around by improvising. The whole content of Mode C is that the role
settling a claim has never seen the argument for it (`critique-mode.md` §3). A solo context settling
its own claims is the failure the mode exists to prevent, and it would produce a report shaped
exactly like a real one.

## What stays exactly as it is

Everything outside the dispatch shape. Do not treat solo as a licence to skip:

* `SKILL.md` steps 1, 5 and 6 — inventory, lint, deliver. Unchanged, including `docs-history.md`.
* `report-schema.md` — same sections, same columns, same verdict sets.
* `check_report.py` and `verify_citations.py` — both, at step 5. The scripts are the cheapest part
  of the audit and the only part that never gets tired.
* `self-clarify.md` — the whole ladder, including `--max-questions`.
* `dimensions.md` — read it at step 2 as always.
* `large-sets.md` — its threshold still applies, and it matters **more** here: a large set is exactly
  what a single context cannot hold.
* `fix-mode.md` — after the loop, never instead of it. With no `fix-safety` role, you check the six
  rules yourself against `fix-mode.md`, and say in the report that nobody independent reviewed the
  edits.

`--rounds auto` is **5** here, not 3 (`SKILL.md` Arguments). One reviewer per round finds less per
round than four specialists, so the loop needs more of them to converge.

## The procedure — replaces `SKILL.md` steps 2, 3 and 4

### S2. Build the checklist from the spec

Read `dimensions.md`, then decompose the spec into atomic, checkable requirements — **before**
reading the documents closely. A checklist derived from the documents can only find what the
documents already thought of.

One requirement per row, each answerable yes/no against a document. `Req ID` format
`REQ-<area>-<3 digits>`. Keep IDs from a previous report, append new ones at the end, mark removed
ones `[OBSOLETE]` rather than deleting. Never renumber — the previous report's IDs are cited
elsewhere by now.

You are the checklist's only writer here, which is the cost of this mode: nothing separates the hand
that wrote the requirement from the hand that judges whether it is covered. The round loop is the
only thing standing in for that separation, so it is not optional.

### S3. Map the documents onto the checklist

Read every document in full, then for each requirement record what you actually found, in the
`## Requirements` columns from `report-schema.md`.

Two rules carry most of the weight:

* **Evidence is mandatory for every verdict except the ones `report-schema.md` exempts.** Doc plus
  section or line, plus a short verbatim quote. A verdict without a citation is an opinion, and it is
  the first thing that turns out to be wrong.
* **Before writing `Missing`, expand the search terms.** Search the spec's wording *and* every
  synonym, abbreviation and field name the **documents** use for the concept — a spec saying "second
  approver" will not match a manual saying "dual sign-off". Record the expanded list in the Note. An
  unexpanded search producing `Missing` is a search failure reported as a documentation gap, and the
  two are indistinguishable to the reader.

Never paraphrase a document into agreement with the spec. Quote it and let the gap show.

### S4. MANDATORY: the round loop

Repeat until a round converges. What ends the loop is what the last round found, not how many you
have run.

```text
ROUND n
 1. Bash: strip_rounds.py <report>   → the stripped copy the reviewer gets
 2. Dispatch ktkit:docs-review-solo-reviewer with ONLY:
      the spec path, the document paths, the stripped report,
      the path to dimensions.md, and the output language
    NOT: your reasoning, your checklist rationale, or any earlier round's notes
 3. Merge its findings. Record every one under `## Round findings` with the
    round number, what was missed, and why it was missed
 4. Append the `## Round log` row BEFORE deciding anything
 5. Decide from the row
```

**Never give the reviewer your analysis.** Shared analysis is what makes a reviewer rubber-stamp your
blind spots — including your own notes on what a previous round caught. You built the checklist; you
cannot find the requirement you never thought of, and neither can anything that has read your
reasoning.

Deciding, from the `## Round log` row:

* **No material findings** → converged. Say which round.
* **Material findings** → another round. This holds at round 3, 4 and 5 — a round still changing
  verdicts proves more remain.
* **A verdict that has flipped twice** → freeze it as `Undecided`, both readings into
  `## Needs user decision`. An oscillating row is an ambiguous spec, not an unfinished audit.
* **Ceiling reached with material findings** → stop and report it on line 1 as `BUDGET-CAPPED`, with
  what kept changing. Never let the ceiling read like a clean exit.

Material means: a row added, a verdict changed, or a citation rejected. Wording and formatting nits
are not material and never justify another round.

A deadline is not a stop condition. If the user orders you to stop early, line 1 reads `INCOMPLETE`
and lists what the last round returned unmerged.

## Two things to say in the report

`## Review team` carries `Mode=solo`, one row for the reviewer per round.

And the closing summary line says it, because the reader cannot tell otherwise:

```text
Team: solo loop (--team off) · 1 reviewer × 3 rounds
```

A solo run that does not announce itself reads exactly like a team run, and the two are not the same
audit. What is missing is named rather than implied: no independent requirement derivation, no
citation sweep by a role that was denied the spec, no adjudication of the reviewer's own findings.

## The cost, so the choice is informed

Solo is not the cheap option, and picking it for that reason is picking it wrong. One context pays
for its whole prefix on **every** tool call it makes, and that prefix holds the spec, every document
and every result it has read. The team pays a large fixed cost per agent and then nothing for
carrying the material, because the lead never holds it.

Measured on this harness, a lean role's base is ~6.6k tokens and a subagent's real cost tracks its
**tool call count**, not its prompt length. What makes solo expensive is the opposite quantity: the
number of turns multiplied by a prefix that only grows. The larger the context window, the worse that
trades — a bigger window does not bound the prefix, it lets it grow.

`.claude/claude/analyze/solo-vs-team-arch-20260826.md` in this repo has the full comparison. Its
conclusion, in one line: solo wins on latency and on having a single transcript to debug, roughly
ties on token for a small set, and loses badly on a large one.
