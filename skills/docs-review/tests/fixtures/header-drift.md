# docs-review

## Source inventory

| Doc ID | Path | What it is | Version | Read |
| ------ | ---- | ---------- | ------- | ---- |
| DOC-01 | docs/manual.md | operator manual | 2026-06-01 | full |

## Requirements

| Req ID | Requirement | Tier | Verdict | Citation | Quote | Note |
| ------ | ----------- | ---- | ------- | -------- | ----- | ---- |
| REQ-AMT-001 | Amount rejects values below 0 | - | Covered | DOC-01 docs/manual.md:42 | "values below zero are rejected" | - |
| REQ-AMT-002 | Amount rejects values above 1,000,000 | T1 | Missing | | | searched "1,000,000", "upper limit", "上限" across docs/*.md |
| REQ-AMT-003 | Rounding mode for partial units | T4 | Undecided | | | escalated as D1 |

## Review team

| Wave | Role | Agent | Model | Mode |
| ---- | ---- | ----- | ----- | ---- |
| 1 | evidence | ktkit:docs-review-evidence | sonnet | agents |

## Round log

| Round | Reviewer | Raised | Upheld | Refuted | New rows | Verdict changes | Citations rejected | Nits |
| ----- | -------- | ------ | ------ | ------- | -------- | --------------- | ------------------ | ---- |
| 1 | evidence | 3 | 2 | 1 | 1 | 1 | 1 | 2 |
| 1 | TOTAL | 3 | 2 | 1 | 1 | 1 | 1 | 2 |
| 2 | TOTAL | 0 | 0 | 0 | 0 | 0 | 0 | 1 |

## Round findings

REQ-AMT-002
Round 1 finding: verdict was Covered on a quote that does not exist in DOC-01.
Why missed: quote paraphrased from the spec, not copied from the document.
Challenge: UPHELD — grep for the sentence over docs/ returns nothing.

## Self-resolved

| Question | Tier | How resolved | Evidence |
| -------- | ---- | ------------ | -------- |
| Does the manual use a synonym for "upper limit"? | T1 | expanded terms to 上限 / cap / ceiling | docs/manual.md:40-58, no hit |
| Which rounding does the code apply? | T1 | read the implementation | src/amount.ts:88 |
| Does the framework cap at 1e6? | T3 | official docs, v4.2 | https://example.test/docs/limits |
| Two manuals disagree on the cutoff | T2 | evidence refuted DOC-02's reading | docs/manual.md:12 |

## Assumptions taken

| ASM ID | Assumption | Reading chosen | Evidence | Falsifier | Blast radius |
| ------ | ---------- | -------------- | -------- | --------- | ------------ |
| ASM-001 | "amount" means gross, not net | gross | DOC-01:12 uses gross in every worked example | any document using net in a worked example | one row of the report |

## Needs user decision

### D1 · REQ-AMT-003 — Which rounding mode applies to partial units?

- [x] T1 exhausted
- [x] T2 exhausted
- [x] T3 exhausted
- [x] T3.5 rejected — neither reading has more evidence, and the value is written into a live runbook
- [x] The user has not already answered it
- [x] Options, consequences, a recommendation and a default are written below

**Searched:** "rounding", "端数", "half-up", "truncate" across docs/*.md, src/**, git log -- docs/manual.md
**Why no artifact can answer it:** no document or commit states a rounding mode; the choice was never recorded
**Why not an evidenced assumption:** the value goes into a runbook operators follow, so being wrong is not cheap to correct
**Options:** (a) half-up → matches the finance sheet; (b) truncate → matches the current code
**Recommendation:** (a), because the finance sheet is the contractual artifact
**Default if you do not answer:** (a), recorded in `## Assumptions taken`.

The loop converged at wave 2.

self_resolve_ratio=0.80 · self_resolved=4 · needs_user=1 · assumptions=1 · max_questions=3
