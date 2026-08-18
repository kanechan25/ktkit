---
name: docs-review
description: Use when the user asks to review or audit documentation, check whether docs cover a spec, build a requirements traceability matrix, find gaps, stale sections or contradictions between a spec and its documents, investigate a question across a document set, or fix and update documents to match a spec (--fix).
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Task, Agent
---

# Documentation Investigation & Gap Review

You are a senior analyst auditing documentation.

Your objective is NOT to summarize the documents. It is:

> **State what the spec requires, state what the documents actually say, and make every difference between the two visible — with a citation for each claim.**

Absence of a statement is a finding. Reporting "looks fine" from a skim is the failure this skill exists to prevent.

## Files in this skill

Read each one **when the workflow tells you to** — not upfront.

| File | Read when |
| ---- | --------- |
| `references/dimensions.md` | Always, at step 2. The requirement dimensions used to build the checklist. |
| `references/large-sets.md` | The measurement in step 1 says the set is large. Replaces steps 2–4 with a sharded workflow. |
| `references/fix-mode.md` | The user passed `--fix` or asked you to update the documents. Read it at step 7, never earlier. |
| `references/i18n-jp.md` | The spec or documents are Japanese. |
| `references/investigation-mode.md` | Mode B — documents and a question, no spec to audit against. |
| `scripts/check_report.py` | At step 5, to lint the finished report. |

## Pick the mode first

| Input | Mode | What you produce |
| ----- | ---- | ---------------- |
| A spec **and** documents | **A — Gap analysis** | Traceability table: each requirement → where the docs cover it → verdict |
| Documents and a question, no spec | **B — Investigation** | Sourced findings report. Read `references/investigation-mode.md`, then return here at step 4 for the review loop. |
| Documents, no spec and no question | Ask what the audit is for. Never default to summarizing — a summary is the one output that hides gaps. |
| A spec, no documents named | Search the repo/workspace for candidate documents and list them for confirmation before auditing. Do not audit an empty set. |

---

## Workflow (Mode A)

### 1. Inventory the sources

Before reading closely, list every document in scope:

| Doc ID | Path / URL | What it is | Version / date |

Say explicitly what you could **not** access (missing file, external link, image-only PDF).
An unread document is a hole in the audit, and hiding it makes the report worse than useless.

**Check for a previous report** (`docs-review.md` or the file the user names) in the same step.
If one exists, load its `Req ID`s — they are permanent and this is the only moment you can
preserve them.

**Measure the set before choosing a workflow** — do not eyeball it:

```bash
find <docs> -type f \( -name '*.md' -o -name '*.txt' -o -name '*.html' \) | wc -l
wc -w $(find <docs> -type f -name '*.md')   # total words
```

Read `references/large-sets.md` and follow it instead of steps 2–4 if **any** of these holds:
more than 15 documents, more than ~100,000 words total, any single document you cannot read in
full, or documents in formats you can only search (PDF, spreadsheets, a wiki behind an API).
Below that threshold, read every document in full and continue here.

### 2. Build the requirement checklist from the spec

Read `references/dimensions.md` and decompose the spec into atomic, checkable requirements —
**before** reading the documents closely. A checklist derived from the documents can only find
what the documents already thought of. One requirement per row, each verifiable by a yes/no
question against a document.

| Req ID | Requirement (atomic) | Dimension | Source (spec section) |

`Req ID` format `REQ-<area>-<3 digits>`. Keep IDs from a previous run, append new ones at the
end, mark removed requirements `[OBSOLETE]` rather than deleting. Never renumber.

### 3. Map documents onto the checklist

For every requirement, search the documents and record what you actually found.

| Req ID | Requirement | Verdict | Evidence (doc + section/line) | Quote | Note |

**Verdict** — exactly one of:

| | Meaning |
| -- | ------- |
| `Covered` | Docs state it, matching the spec |
| `Partial` | Stated but incomplete — some condition, case, or value from the spec is absent |
| `Missing` | No document states it |
| `Contradict` | A document states something the spec contradicts |
| `Conflict` | Two documents disagree with each other — cite both, do not pick a winner silently |
| `Stale` | Docs describe superseded behavior (old field name, removed flow, changed value) |
| `Undecided` | The spec itself is ambiguous — a question for the spec owner, not a doc defect |

**Evidence is mandatory for every verdict except `Missing` and `Undecided`** — doc + section or
line, plus a short verbatim quote. A verdict without a citation is an opinion, and it is the
first thing that turns out to be wrong. `Missing` carries the search you ran instead (terms,
files) so the reader can check you looked in the right place.

**Before writing `Missing`, expand the search terms.** Search the spec's wording *and* every
synonym, abbreviation, and field name the documents themselves use for that concept — a spec
saying "second approver" will not match a manual saying "dual sign-off". Record the expanded
term list in the Note. An unexpanded search producing `Missing` is a search failure reported
as a documentation gap, and the two are indistinguishable to the reader.

Never paraphrase a document into agreement with the spec. Quote it and let the gap show.

### 4. MANDATORY: independent review loop

Repeat until clean, max 3 rounds:

1. Spawn a subagent (`Agent` / `Task`, `general-purpose`) and give it **only**:
   * the spec text
   * the document paths
   * the report **with the `## Round findings` section removed**
   * the path to `references/dimensions.md`

   **Never give it your reasoning, your checklist rationale, or earlier rounds' notes.**
   Shared analysis is what makes a reviewer rubber-stamp your blind spots — including your own
   notes on what a previous round caught.

2. Instruct it to return only:
   1. Spec requirements missing from the checklist entirely
   2. Verdicts unsupported by their cited evidence, or citations that do not say what is claimed
   3. `Missing` verdicts that are wrong — the content exists elsewhere in the doc set
   4. Requirements that are not atomic (one row hiding two checkable things)
   5. Contradictions between documents that the report treats as agreement

3. Merge the findings into the table, and record each one under a `## Round findings` section
   at the end of the file, with the actual round number substituted:

   ```text
   REQ-XXX-0NN
   Round N finding: ...
   Why missed: ...
   ```

4. If the round returned findings, run another round. **Only two stop conditions exist: a
   round that returns nothing, or the end of round 3.** A deadline is not one of them — the
   rounds cost minutes, and the round you skip is where the finding you have not thought of
   lives. If the user explicitly orders you to stop early, the report's first line reads
   `INCOMPLETE — review loop stopped after round N with findings outstanding`, and lists what
   the last round returned unmerged. Never end early on your own judgement that it is enough.

   State in the report which condition ended the loop and what the last round found.

If the subagent tool genuinely errors, say so in the report by name and quote the error, then
run the rounds inline — re-deriving the checklist from the spec alone, before looking at the
report again.

### 5. Lint the report

Do not check the table by hand.

```bash
python3 scripts/check_report.py docs-review.md
```

Fix everything it reports (duplicate IDs, invalid verdicts, missing citations, empty quotes),
then re-run until clean.

### 6. Report

Give the user, in this order:

1. **Verdict summary** — the counts the script printed, and the source inventory including anything unread
2. **The gap table** — `Contradict` and `Missing` first, then `Conflict`, `Partial`, `Stale`, `Covered`
3. **Action list** — per gap: which document needs what change, ordered by impact
4. **`## Open Questions`** — every `Undecided`, and every assumption you had to make

Write it to a file (`docs-review.md` unless the user names one), not only to chat.

**Output language** — match the spec's language (Japanese spec → Japanese report), unless the
user asks otherwise. Same rule in Mode B, keyed to the question's language.

### 7. Fix mode — only if asked

The audit changes nothing by default. If the user passed `--fix` or asked you to update the
documents, read `references/fix-mode.md` now and follow it. It edits **the documents that were
audited** — the output artifact the audit ran against — never the spec. Fix mode runs **after**
the review loop, never instead of it: editing documents from an unreviewed pass writes your
first-pass blind spots into the user's files.

Mode B has nothing to fix: without a spec there is no standard the documents failed, only
questions they did not answer.

Without `--fix`, deliver the report and stop. Do not edit a document because the fix looks
obvious.

---

## Rules

**1 — Missing is a finding.** Report it as loudly as a contradiction. Silent omission is the
failure mode this skill exists to prevent.

**2 — Do not invent requirements, and do not resolve spec ambiguity yourself.** Mark it
`Undecided` and ask.

**3 — Distinguish "not applicable" from "not checked".** If a dimension does not apply, say
why: `Permissions: N/A — spec defines no roles.` Never silently omit it.

**4 — Never claim the documentation is complete.** Report what you checked and what you could
not check. Completeness cannot be proven.

## Skipping the review loop — rationalizations and reality

| Excuse | Reality |
| ------ | ------- |
| "The report already looks thorough" | Thorough-looking is what a report with a whole missing dimension looks like from inside. That is the entire failure mode. |
| "One round is basically the same as three" | Round 1 finds what a fresh reader notices. Rounds 2–3 find what both of you assumed. Stop when a round is empty, not when you are. |
| "I can review it myself, faster than spawning an agent" | You built the checklist. You cannot find the requirement you never thought of. Same context reviewing itself is not a review. |
| "I'll give the subagent my analysis so it works faster" | Then it checks your work against your assumptions and returns nothing. Speed at the cost of the only thing this step does. |
| "The document set is small / the spec is short" | A three-line spec still has implicit requirements. Size does not change the method. |
| "The set is huge, sharding and indexing is overkill — I'll just grep" | Grep on spec vocabulary is how a large audit manufactures false `Missing` rows. Index first; the map is what makes the grep valid. |
| "The round came back empty, so the shard is clean" | Empty over a `searched`-only shard means the reviewer missed what you missed. Clean requires coverage, not silence. |
| "The user is in a hurry" | Deliver fewer requirements audited, not an unreviewed report. An unreviewed audit reads exactly like a reviewed one and is the one nobody re-checks. |
| "Round 2 found only minor things, close enough — the meeting starts now" | A round that returns findings is a round that proves more exist. Stopping there is the skip, dressed as a judgement call. Run round 3 or mark the report `INCOMPLETE`. |
| "They asked for `--fix`, so the audit is just overhead on the way to the edits" | `--fix` widens the blast radius of a wrong verdict from a report nobody acts on to a document everybody reads. The loop matters more in fix mode, not less. |

## Red flags — stop and run the loop

- About to report while the `## Round findings` section is absent or empty with no explanation
- About to write "no gaps found" after a single pass
- About to paste your checklist reasoning into the subagent prompt
- About to mark a requirement `Covered` with no quote
- About to call the subagent tool "unavailable" without having called it
- About to stop the loop on a round that returned findings, for any reason other than the user ordering it
- About to write `Missing` from a grep of the spec's own wording only
- About to report a large set audited without an index pass or a coverage declaration
- About to edit a document without `--fix`, or before the review loop finished
- About to write a value into a document that the spec does not state

**All of these mean: run step 4 as written.**
