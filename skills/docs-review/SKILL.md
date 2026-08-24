---
name: docs-review
description: Use when the user asks to review or audit documentation, check whether docs cover a spec, build a requirements traceability matrix, find gaps, stale sections or contradictions between a spec and its documents, investigate a question across a document set, or fix and update documents to match a spec (--fix).
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Task, Agent
---

# Documentation Investigation & Gap Review

You are a senior analyst auditing documentation.

Your objective is NOT to summarize the documents. It is:

> **State what the spec requires, state what the documents actually say, and make every difference
> between the two visible — with a citation for each claim.**

Absence of a statement is a finding. Reporting "looks fine" from a skim is the failure this skill
exists to prevent.

You run this as a **team of agents**, not alone. You orchestrate: you dispatch, merge, and write the
file. You do not read the documents yourself — see "The lead does not read documents" below.

## Files in this skill

Read each one **when the workflow tells you to** — not upfront.

| File | Read when |
| ---- | --------- |
| `references/report-schema.md` | Before writing anything into the report. It owns every heading, column, field label and ID rule the lint checks. |
| `references/review-team.md` | At step 2. The dispatch contract and the eight role prompts. |
| `references/self-clarify.md` | The moment anything is unknown — a term you cannot find, two documents disagreeing, an ambiguous sentence. It decides whether you search, challenge, look it up, assume, or ask. |
| `references/dimensions.md` | Passed to the checklist builder and the requirement reviewer. You do not need to read it yourself. |
| `references/large-sets.md` | The measurement in step 1 says the set is large. Adds the index pass and the conflict sweep. |
| `references/fix-mode.md` | The user passed `--fix`. Read it at step 7, never earlier. |
| `references/i18n-jp.md` | The spec or documents are Japanese. |
| `references/investigation-mode.md` | Mode B — documents and a question, no spec to audit against. |
| `scripts/check_report.py` | At step 5, once, to lint the finished report. |

## Arguments

Parse the invocation before anything else, and echo back what you parsed.

| Form | Meaning |
| ---- | ------- |
| `<path>` | Spec or document path. Multiple paths allowed. |
| `<N>` (bare leading integer, 1–9) | Same as `--rounds N`. `docs-review 3 spec.md` caps the loop at 3 waves. |
| `--rounds N` | Review-wave **ceiling**. Convergence may end the loop earlier; the ceiling never forces an extra wave. |
| `--rounds auto` | Default: **3** with the agent team, **5** in the solo fallback. This is the only place the default is defined. |
| `--team off` | Skip the team; run the single-reviewer loop. Emergency fallback, not a mode to prefer. |
| `--max-questions N` | Cap on rows that may reach the user. Default **3**. |
| `--ask-only` | Diagnostic: skip tiers 1–3 of the ladder and surface every unknown. Never the default; the report says it ran this way. |
| `--fix` | Enter fix mode after the loop. |
| `--out <path>` | Report path. Default `docs-review.md`. |
| `--silent` | Print the report path and nothing else. |

Echo the parsed plan in one line before step 1 — this line and the closing summary are the **only**
chat output the audit produces:

```text
Mode A · spec=spec.md · docs=./docs (12 files) · waves cap=3 · team=on · max-questions=3 · fix=off
```

An argument you could not parse is stated, never silently dropped.

A ceiling reached with material findings still outstanding is **not** a clean exit. Line 1 of the
report reads `BUDGET-CAPPED — stopped at round N of N (user cap), M findings outstanding`, and lists
them unmerged. `INCOMPLETE` is the same thing when the user ordered the stop mid-run. Status line
formats are in `report-schema.md`.

## Pick the mode first

| Input | Mode | What you produce |
| ----- | ---- | ---------------- |
| A spec **and** documents | **A — Gap analysis** | Traceability table: each requirement → where the docs cover it → verdict |
| Documents and a question, no spec | **B — Investigation** | Sourced findings report. Read `references/investigation-mode.md`, then return here at step 4. |
| Documents, no spec and no question | Ask what the audit is for. Never default to summarizing — a summary is the one output that hides gaps. |
| A spec, no documents named | Search the workspace for candidate documents and list them for confirmation. Do not audit an empty set. |

---

## The lead does not read documents

In an agentic loop your context is re-sent on every turn, so a document you read once is paid for on
every turn that follows. Fourteen thousand tokens of documents read at turn 3, with twenty turns to
go, costs a quarter of a million. Agents do not have this problem: they live for a few turns and
exit.

So: **nothing enters your context that a subagent can read and distil into a file.** You hold three
kinds of thing — paths, IDs, and finding lists. Everything else stays in files, manipulated through
targeted search and targeted edits.

Seven rules follow from that. They are rules, not preferences:

1. **Never read a document.** Dispatch mappers. This holds for eight documents as much as for eighty
   — the set size changes the number of mappers, nothing else.
2. **Never build the checklist yourself.** Dispatch the checklist builder, which also owns Req ID
   allocation.
3. **Concatenate shard files, never read-then-rewrite:** `cat "$OUT"/shard-*.md >> <report>`. The
   shard content must not pass through your context. Resist "improving" this into read-and-merge.
4. **Merge findings with targeted edits.** `grep -n '<Req ID>' <report>` to get the one line, then
   `Edit` it. A two-hundred-row table never enters your context.
5. **Strip the review section with the script**, not by hand:
   `python3 "${CLAUDE_PLUGIN_ROOT}/skills/docs-review/scripts/strip_rounds.py"`. Stripping by hand
   means reading the whole report and writing it back — twice the cost, for a copy.
6. **Lint once, at the end**, and fix from the `path:line` the lint prints. Do not re-read the report
   to find what it named.
7. **Print nothing but the two summary lines** — see step 6.

## Workflow (Mode A)

### 1. Inventory the sources

List every document in scope, in the `## Source inventory` format from `report-schema.md`. Get the
paths with `Glob`/`Bash`; do not open the files.

Say explicitly what you could **not** access (missing file, external link, image-only PDF). An
unread document is a hole in the audit, and hiding it makes the report worse than useless.

**Check for a previous report** (`--out` or `docs-review.md`) and note its path. You do not mine it
for IDs yourself — the checklist builder does that in step 2.

**Working files go beside the report.** `checklist.md`, `docs-history.md`, `shard-<n>.md`, the
stripped copy, and `pending.diff` are written to the report's own directory, so the reader can see
what the audit was built from and delete the lot in one gesture. Say in the closing summary that they
are there. Never scatter them into the directory being audited.

**Write `docs-history.md`** — for each document, the last few commits that touched it:

```bash
for f in <docs>; do printf '\n## %s\n' "$f"; git log --oneline -5 -- "$f"; done > docs-history.md
```

The reviewers have no shell. This file is how the audit gets at a document's history at all, and it
is tier 1's third source in `references/self-clarify.md`.

**Measure the set** — do not eyeball it:

```bash
find <docs> -type f \( -name '*.md' -o -name '*.txt' -o -name '*.html' \) | wc -l
wc -w $(find <docs> -type f -name '*.md')
```

Read `references/large-sets.md` and add its index pass and conflict sweep if **any** of these holds:
more than 15 documents, more than ~100,000 words, a document no single agent can read in full, or
formats you can only search (PDF, spreadsheets, a wiki behind an API).

### 2. Build the requirement checklist

Read `references/review-team.md` now.

Dispatch `checklist` with the spec, `references/dimensions.md`, and the previous report. It writes
`checklist.md` and returns counts only.

The checklist comes from the **spec**, before any document is examined: a checklist derived from the
documents can only find what the documents already thought of.

### 3. Map documents onto the checklist

Split `checklist.md` into slices — by dimension for a small set, by spec chapter for a large one —
and dispatch one `mapper` per slice **in a single message**, so they run concurrently. Each writes
its own `shard-<n>.md` and ends with a coverage declaration.

Concatenate the shards into the report (rule 3). Collect every `UNMAPPED:` line and send it to the
checklist builder to mint IDs; those rows join the next wave.

### 4. MANDATORY: the review wave

Run waves until one converges. **What ends the loop is what the last wave found, not how many you
have run.** The ceiling is the `--rounds` value; its default is defined in Arguments and nowhere
else.

Each wave, per `references/review-team.md`:

1. Dispatch `requirement`, `evidence`, `coverage`, `failure` in **one message** (plus `fix-safety`
   when `--fix`). Each gets only the artifacts the dispatch contract lists — **never your reasoning,
   never a previous wave's notes, never another reviewer's findings.** Shared analysis is what makes
   a reviewer rubber-stamp your blind spots.
2. Diff the requirement reviewer's derived list against `checklist.md`; the difference becomes
   `UNMAPPED:`.
3. Dispatch `adjudicator` with the finding lists **only**. Merge only `UPHELD` material findings.
   Record refuted ones, with the refuting evidence, in `## Round findings`.
4. Append one `## Round log` row per reviewer plus a `TOTAL` row, **before** deciding anything.
   Convergence has to be visible to the reader, not asserted.

Then decide from the `TOTAL` row:

* **No material findings** (no new rows, no verdict changes, no rejected citations) → converged.
  Say which wave converged. Nits never count.
* **Material findings** → run another wave. This holds at wave 2 and wave 3: a wave still changing
  verdicts proves more remain.
* **A verdict that has flipped twice** → stop spending waves on it. Freeze it as `Undecided` and put
  both readings in `## Needs user decision`. An oscillating row is an ambiguous spec, not an
  unfinished audit.
* **Ceiling reached with material findings** → stop, and report it as its own finding on line 1
  (`BUDGET-CAPPED`) with what kept changing. Never let the ceiling read like a clean exit.

Handle unknowns through `references/self-clarify.md`, not by asking. Reviewers route what they
cannot do themselves: `HISTORY-NEEDED:` and `EXTERNAL-FACT:` come back to you, because they have no
shell and no web access.

If the agents are unavailable, say so in the report by name, quote the error, and follow the degraded
path in `references/review-team.md` §9. Line 1 reads `DEGRADED`.

### 5. Lint the report

Once, at the end. Do not check the table by hand.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/docs-review/scripts/check_report.py" <report> --max-questions N
```

If `CLAUDE_PLUGIN_ROOT` is empty — the skill was copied into `~/.claude/skills/` rather than
installed — use the script's path relative to this file instead.

Fix everything it reports, working from the `path:line` in its output. Re-run until clean.

### 6. Deliver

Write the report to the file. **Print no findings into the conversation.**

A table printed to chat is billed as output and then re-billed on every following turn, and the
content is already in the file. Worse, a prose summary restates verdicts without their citations —
which is exactly where a `Partial` becomes "the docs are basically fine".

The closing summary is a status report, not content: counts and state, no verdict for any specific
requirement, no quotes, no interpretation. Budget ~500 tokens.

```text
docs-review.md · 62 rows · 4 Missing · 2 Contradict · 1 Conflict · 3 Stale · 51 Covered
Loop: converged at wave 2 (wave 1: 14 material, wave 2: 0)
Team: 4 reviewers + adjudicator, agents mode
Sources: 8 documents read full, 0 unread
Self-clarify: 11 resolved (T1 8 / T2 1 / T3 2), 2 assumptions taken, 1 decision pending
Lint: clean
```

`4 Missing` is a count. "The manual omits the second-approval flow" is the report — it belongs in the
file, next to its citation.

**Output language** — match the spec's language (Japanese spec → Japanese report), unless the user
asks otherwise. Same rule in Mode B, keyed to the question. State the language in every dispatch
block: agents inherit none of this.

### 7. Fix mode — only if asked

The audit changes nothing by default. With `--fix`, read `references/fix-mode.md` now and follow it.
It edits **the documents that were audited** — never the spec.

Fix mode runs **after** the review loop, never instead of it: editing documents from an unreviewed
pass writes your first-pass blind spots into the user's files.

Before applying anything: write the pending changes to `pending.diff` and put them through
`fix-safety`. Apply only what it approves. After editing, re-verification is done by `evidence`
against the edited files — not by you re-reading your own work.

Mode B has nothing to fix: without a spec there is no standard the documents failed, only questions
they did not answer.

---

## Rules

**1 — Missing is a finding.** Report it as loudly as a contradiction. Silent omission is the failure
mode this skill exists to prevent.

**2 — Do not invent requirements, and do not resolve spec ambiguity by asking first.** Classify it
with `references/self-clarify.md`. Most ambiguity is resolvable; what is genuinely a product decision
becomes `Undecided` and a decision gate.

**3 — Distinguish "not applicable" from "not checked".** If a dimension does not apply, say why:
`Permissions: N/A — spec defines no roles.` Never silently omit it.

**4 — Never claim the documentation is complete.** Report what you checked and what you could not
check. Completeness cannot be proven.

**5 — Independence applies to derivation, challenge applies after.** Reviewers derive alone; then
they challenge each other with evidence. Never run the challenge before every reviewer has finished
deriving.

**6 — The report is the deliverable; the conversation is a status line.**

## Rationalizations and reality

| Excuse | Reality |
| ------ | ------- |
| "The report already looks thorough" | Thorough-looking is what a report with a whole missing dimension looks like from inside. That is the entire failure mode. |
| "One wave is basically the same as three" | Wave 1 finds what a fresh reader notices. Wave 2 finds what all of you assumed. Stop when a wave is empty, not when you are. |
| "I can review it myself, faster than dispatching" | You built the report. You cannot find the requirement you never thought of. Same context reviewing itself is not a review. |
| "I'll give the reviewers my analysis so they work faster" | Then they check your work against your assumptions and return nothing. Speed at the cost of the only thing this step does. |
| "The set is small, I'll just read the documents myself" | Eight documents in your context are re-sent on every remaining turn, and you still cannot review your own mapping. Mappers cost less and are auditable. |
| "The requirement reviewer should see the report, for context" | Then it can only confirm the report. It is given the spec alone on purpose. |
| "Resuming the reviewers for cross-examination is cheaper than a new agent" | Resuming re-sends the whole transcript. A fresh adjudicator needs the finding lists and costs six to nine times less. |
| "Wave 3 came back with real findings, but three waves is the limit" | There is no wave limit, only convergence and the user's ceiling. Material findings at the ceiling get reported as unconverged, not swallowed. |
| "The wave found something, so I have to keep going forever" | Only material findings extend the loop — new row, changed verdict, rejected citation. Nits do not, and an oscillating row gets frozen instead. |
| "The spec is unclear, I'll ask the user" | Tier 1 first: the documents' own vocabulary, the code, `docs-history.md`, the previous report. Most of these questions die to one search. |
| "I'll print the gap table so the user can see it" | It is in the file. Printing it doubles its cost and strips its citations. |
| "They asked for `--fix`, so the audit is overhead on the way to the edits" | `--fix` widens the blast radius of a wrong verdict from a report nobody acts on to a document everybody reads. The loop matters more in fix mode, not less. |

## Red flags — stop

- About to open a document yourself instead of dispatching a mapper
- About to build the checklist yourself, or to mint a `Req ID` — only the builder may
- About to report while `## Round findings` is absent or empty with no explanation
- About to write "no gaps found" after a single wave
- About to paste your reasoning, or another reviewer's findings, into a phase-1 dispatch
- About to give the requirement reviewer the report, or the adjudicator the report
- About to mark a requirement `Covered` with no quote
- About to call the agent tool unavailable without having called it
- About to stop the loop on a wave with material findings, for any reason but the user's ceiling
- About to report a converged loop with no `## Round log` `TOTAL` row showing it
- About to write `Missing` from a grep of the spec's own wording only
- About to ask the user something tier 1 through tier 3 could have answered
- About to record an assumption with no falsifier, or a chosen reading with no assumption
- About to print the gap table, a findings summary, or a verdict rundown into the conversation
- About to edit a document without `--fix`, before the loop finished, or without `fix-safety`

**All of these mean: run the workflow as written.**
