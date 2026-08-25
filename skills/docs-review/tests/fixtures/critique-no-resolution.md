# docs-review — critique of abc.md

<!-- fixture: two material claims have no ### subsection; R3 must fire twice -->

## Source inventory

| Doc ID | Path | What it is | Version | Read |
| ------ | ---- | ---------- | ------- | ---- |
| DOC-01 | abc.md | design note under critique | 2026-08-24 | full |

## Claims

| CLM ID | Statement | Kind | Verdict | Evidence | Quote | Note |
| ------ | --------- | ---- | ------- | -------- | ----- | ---- |
| CLM-001 | "granting Bash to an agent removes Grep and Glob" | fact | Verified | DOC-01 harness-probe.md:41 | "probe-set-b declared Read, Grep, Glob, Bash and received Read, Bash" | - |
| CLM-002 | "the plugin registers eight agents" | fact | Refuted | agents/:1 | "eleven files match agents/docs-review-*.md" | three Mode C roles were added after the note was written |
| CLM-003 | "we should cap role prompts at 800 words" | assertion | Unsupported | abc.md:24 | "800 words keeps the spawn cheap" | the note gives no measurement; the 800 figure appears nowhere else in it |
| CLM-004 | "open question: does .claude/agents hot-load?" | question | Answerable | .claude/agents:1 | "Agent type 'probe-set-a' not found" | Yes with a delay: the first spawn after writing fails, a later one in the same session succeeds. No restart needed |
| CLM-005 | "so a single reviewer is enough" | conclusion | Refuted | tests/fixtures/false-converged.md:30 | "| 2 | TOTAL | 4 | 3 | 1 | 2 | 1 | 1 | 1 |" | a single reviewer produced this row and called it converged |

## Knock-on and widening

| CLM ID | Kind | What follows, or what the class is missing | Evidence | Severity |
| ------ | ---- | ----------------------------------------- | -------- | -------- |
| CLM-001 | knock-on | If Bash removes Grep, every role that greps must route shell work elsewhere — the note decides the tool set but never says who runs git | abc.md:12 | material |
| CLM-003 | widening | Prompt length is one of three things charged per spawn; the note omits the tool-schema and skill-list costs it measured elsewhere | abc.md:24 | material |

## Resolutions

### CLM-001
**Verdict** Verified · **Kind** knock-on · **Severity** material

> abc.md:12: "we grant Bash only where a role needs git"

`harness-probe.md:41` — "probe-set-b declared Read, Grep, Glob, Bash and received Read, Bash"

The claim holds, and the note stops there. Nothing in it says who runs git once no role can.

### CLM-004
**Verdict** Answerable · **Kind** question · **Severity** material

> "open question: does .claude/agents hot-load?"

`.claude/agents:1` — "Agent type 'probe-set-a' not found"

Yes, with a delay. The first spawn after writing the file fails; a later spawn in the same session
succeeds. No restart is needed — the open question can be closed.

### CLM-005
**Verdict** Refuted · **Kind** conclusion · **Severity** material

> "so a single reviewer is enough"

`tests/fixtures/false-converged.md:30` — `| 2 | TOTAL | 4 | 3 | 1 | 2 | 1 | 1 | 1 |`

A single reviewer produced that row and called it converged. The conclusion does not survive its own
example.

## Review team

| Wave | Role | Agent | Model | Mode |
| ---- | ---- | ----- | ----- | ---- |
| 1 | claims | ktkit:docs-review-claims | sonnet | agents |
| 1 | verify | ktkit:docs-review-verify | sonnet | agents |
| 1 | implication | ktkit:docs-review-implication | inherit | agents |

## Round log

| Round | Reviewer | Raised | Upheld | Refuted | New rows | Verdict changes | Citations rejected | Nits |
| ----- | -------- | ------ | ------ | ------- | -------- | --------------- | ------------------ | ---- |
| 1 | verify | 5 | 4 | 1 | 3 | 2 | 1 | 0 |
| 1 | implication | 2 | 2 | 0 | 2 | 0 | 0 | 1 |
| 1 | TOTAL | 7 | 6 | 1 | 5 | 2 | 1 | 1 |
| 2 | TOTAL | 1 | 0 | 1 | 0 | 0 | 0 | 2 |

## Round findings

CLM-005
Round 2 finding: round 1 recorded this as Unsupported; re-reading the note, the author states it as a conclusion drawn from CLM-003, so Refuted is the correct verdict and the evidence had to change with it.
Why missed: round 1 verified the wording and not what the sentence was doing in the argument.
Challenge: UPHELD — the false-converged fixture settles it against the claim.

CLM-002
Round 1 finding: the note says eight agents; the directory holds eleven.
Why missed: the count was written before the Mode C roles were added.
Challenge: UPHELD — counted the files.

## Self-resolved

| Question | Tier | How resolved | Evidence |
| -------- | ---- | ------------ | -------- |
| Does .claude/agents hot-load? | T1 | spawned immediately after writing, then again later in the same session | .claude/agents:1 |
| How many agents does the plugin ship? | T1 | counted the files | agents/:1 |
| Is 800 words measured anywhere? | T1 | searched the note for the figure and for any token measurement | abc.md:24 |

The loop converged at round 2.

self_resolve_ratio=1.00 · self_resolved=3 · needs_user=0 · assumptions=0 · max_questions=3
