# Fix Mode — Applying the Audit to the Documents

Read this only when the user passes `--fix` or asks you to fix / update the documents. Never enter
fix mode on your own initiative: an audit changes nothing, and the user decides when it starts
changing their documentation.

**Fix mode runs after the full audit, including the review loop.** Fixing findings from an
unreviewed pass means editing documents based on the gaps you happened to notice first — and
`--fix` widens the blast radius of a wrong verdict from a report nobody acts on to a document
everybody reads. The loop matters more here, not less.

Section names and the columns of `## Fixes applied` and `## Proposed, not applied` come from
`report-schema.md`. This file decides *what may be edited*; that one owns *how it is recorded*.

## What fix mode edits

It edits **the documents that were audited** — the output artifact the audit ran against. Never the
spec: the spec is the standard being checked against, and a fix that edits the standard to match the
output makes every verdict trivially `Covered`. A genuine problem in the spec is an `Undecided` row
and a question for its owner.

Which document that is decides what may be applied:

| The audited document is… | Then |
| ------------------------ | ---- |
| **A deliverable being produced** — a design doc, a spec write-up, a report, a handover document the team is still drafting from the requirement | The requirement is authoritative. Apply `Missing`, `Partial`, `Stale` **and** `Contradict`: the document is supposed to say what the requirement says, and nothing about it describes a shipped system yet. |
| **Documentation of a running system** — a user manual, a runbook, an API reference for something already deployed | Apply only `Missing`, `Partial`, `Stale`. `Contradict` about behavior gets proposed, not applied — see the trap below. |

If you cannot tell which case you are in, ask. The answer decides whether a `Contradict` row gets
rewritten or escalated, and getting it wrong in the second case puts a false statement into the
documentation of a live system.

## What may be fixed automatically

The audit says what is wrong. It does not always say what is true. Only the first group is safe:

| Verdict | Action |
| ------- | ------ |
| `Missing` | Add the missing statement to the document the audit names, **only if the spec states the content in full**. If the spec is vague about it, this is not a fix — it is authorship. |
| `Partial` | Complete the existing statement with the condition, value, or case the spec names. Edit the sentence in place; do not rewrite the section. |
| `Stale` | Update the superseded value or name to the spec's current one, and update the document's revision line. |
| `Contradict` | In a deliverable being drafted: apply. In documentation of a running system: **propose, do not apply**, unless the contradiction is a value the spec unambiguously owns (a limit, format, ID pattern, cutoff time). |
| `Conflict` | **Propose, do not apply.** Two documents disagreeing means someone has to decide which is right; the spec may be the stale one. |
| `Undecided` | Never fix. Either the spec is ambiguous, or an external fact could not be verified. Both are questions, not edits. |

**Rows settled at tier 3.5** — an evidenced assumption rather than a stated fact — may be fixed, but
the edit **must name its `ASM ID`** in `## Fixes applied`. A fix resting on an assumption and hiding
that fact is worse than no fix: the next reader cannot tell which sentences in their documentation
are the spec's and which are ours.

**The trap in `Contradict`, for documentation of a running system:** a document describing behavior
the spec puts out of scope may be describing what the system actually does. Deleting that paragraph
makes the documentation match the spec and stop matching reality. When a `Contradict` row is about
behavior rather than a stated value, write the proposed edit into the report and stop.

## Rules for the edits themselves

1. **One requirement, one edit.** Every change traces to a `Req ID`. A change that traces to nothing
   does not belong in this run, however obviously right it looks.
2. **Minimal diff.** Edit the sentence, not the section. Do not reformat, re-order, re-word, or
   "improve" surrounding text — the reviewer must be able to see what the audit changed.
3. **Match the document's voice.** Same tense, terminology, and heading style as the file you are
   editing. A document with one paragraph in your register reads as an error.
4. **Use the document's own vocabulary,** not the spec's, when the document already has a term for
   the concept. Introducing the spec's wording alongside the document's creates the next audit's
   `Conflict` row.
5. **Never invent a value.** If the fix needs a number, name, or behavior the spec does not state, it
   is unfixable — list it, do not guess.
6. **Never delete content to close a gap.** Deleting the contradicting paragraph is not a
   documentation fix unless the user decided that paragraph is wrong.

## Before editing

1. Check the working tree is clean (`git status`). If it is not, say so and ask before touching
   files — your edits must be separable from work already in progress.
2. If the documents are not in version control, say so explicitly and list the files you are about to
   change before changing them.

Do not commit. The user commits, unless they asked otherwise.

## The safety gate — before anything is written

Write the intended changes to `pending.diff` and put them, plus the spec, through the `fix-safety`
role in `references/review-team.md`. It returns `APPROVE` or `BLOCK` per edit with the rule number.

**Apply only what it approved.** Blocked edits go into `## Proposed, not applied` with the reason it
gave, and they are as much the deliverable as the applied ones.

This gate exists because the failure mode here is invisible from the inside: the audit that decided
a value is `Missing` is the same audit that then writes the value in, and a wrong verdict becomes a
wrong sentence in someone's manual without anything in between noticing.

## After editing

1. **Re-verification is done by the `evidence` role, not by you.** Dispatch it against the edited
   files with the rows you changed. A fix believed rather than checked is the failure this whole skill
   exists to prevent, and you cannot check your own edit — you already believe the quote supports the
   verdict, which is why you wrote it.
2. Update each row's verdict to `Covered` with the new citation and quote **that `evidence` confirmed**,
   not the one you intended to create.
3. Fill in `## Fixes applied` and `## Proposed, not applied`.
4. Re-run `check_report.py`. `A2 fix-untraced` fails a fix row that traces to neither a `Req ID` nor
   an `ASM ID`.

## Reporting

The closing summary carries counts only: rows fixed, rows proposed, rows left, files touched. The
detail lives in the report, next to the citations — see the output rule in `SKILL.md`. Never report
"documentation updated" without the count of what was left undecided; the unfixed rows are the ones
that need a human.
