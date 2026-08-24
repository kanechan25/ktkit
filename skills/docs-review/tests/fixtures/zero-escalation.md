# docs-review

## Source inventory

| Doc ID | Path | What it is | Version | Read |
| ------ | ---- | ---------- | ------- | ---- |
| DOC-01 | docs/manual.md | operator manual | 2026-06-01 | full |

## Requirements

| Req ID | Requirement | Tier | Verdict | Evidence | Quote | Note |
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

The mapping pass produced the table above.

## Self-resolved

| Question | Tier | How resolved | Evidence |
| -------- | ---- | ------------ | -------- |
| Does the manual use a synonym for "upper limit"? | T1 | expanded terms to 上限 / cap / ceiling | docs/manual.md:40-58, no hit |
| Which rounding does the code apply? | T1 | read the implementation | src/amount.ts:88 |
| Does the framework cap at 1e6? | T3 | official docs, v4.2 | https://example.test/docs/limits |
| Two manuals disagree on the cutoff | T2 | evidence refuted DOC-02's reading | docs/manual.md:12 |

self_resolve_ratio=1.00 · self_resolved=4 · needs_user=0 · assumptions=0 · max_questions=3
