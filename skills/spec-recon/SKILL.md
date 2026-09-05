---
name: spec-recon
description: Use when a question about a specification cannot be settled by reading documents alone — whether the code implements what a spec describes, whether a shipped template matches the published form, what state issues and milestones are actually in, or how a plan compares to what is measurably true. Reconnaissance across documents, source, binary artifacts and version control, turning each measurement into evidence a documentation review can read. Also use to check whether an existing analysis is still based on the current revision of its inputs.
---

# spec-recon

`docs-review` compares documents with documents, extremely well, and deliberately never touches the
code: its reviewers declare *"you have no shell and no web access"*. That boundary is what makes it
trustworthy, and it is also its ceiling. A reviewer who can only read documents once declared a
feature missing that had been built months earlier, and nothing in the review could have caught it.

This skill supplies the missing axis. It measures the things a document cannot show — source,
binary artifacts, version control, and on explicit request a live system — and writes each
measurement out as an **evidence document**. Those documents then go into `docs-review` as
first-class sources. The invariant is not broken; the reviewers are handed more to read.

**Load `references/preflight.md` before anything else. Nothing is spawned until it passes.**

## Arguments

| Argument | Default | Meaning |
| -------- | ------- | ------- |
| `<path>...` | — | Documents, directories, or a repository root. Several allowed. |
| `--scope <text>` | — | The business question, in your words. Passed verbatim to every agent. |
| `--baseline <path>...` | — | Documents describing **current state** rather than intent. Turns on `state-extract`. ⭐ Near-required when `--scope` asks what to **add**: without a change surface, `gap-design` has to reconstruct the present itself. Say so in one line before dispatching rather than refusing. |
| `--probe code,artifact,vcs,runtime` | `code,artifact,vcs` | Which probe layers run. `runtime` is **never** in the default and is never inferred — it touches a live system, so it runs only when you type its name. Fully offline: `--probe code,artifact`. |
| `--rounds N \| auto` | `auto` = 3 | Ceiling on review waves. Convergence may end sooner; the ceiling never forces an extra one. |
| `--incremental` | on when a prior report is found | Analyse only what changed since that report. |
| `--out <path>` | `spec-recon.md` | **The report file.** Working files live in `<dir>/<base>/` — `steps/`, `evidence/`, `scratch/` — never loose beside it. |
| `--handoff on\|off` | `on` | Hand phases 3–4 to `ktkit:docs-review --evidence <dir>`. `off` stops after evidence, which is also how this skill is tested. |
| `--max-questions N` | `3` | Ceiling on rows that reach you. Counts across the **whole run**, not per round. |
| `--lang <code>` | inherit | Output language. Stated, never guessed from the inputs. |
| `--patterns <file>` | — | JSON merged over `data/recon-patterns.json`. How a house convention this toolkit has never seen — a revision syntax, a build directory, an extension — is recognised **without editing any code**. |
| `--keep-scratch` | off | Keep the working directory after a clean run. |

## The five phases

```
0  RECON     preflight gate, freshness, surface measurement   -> steps/00, 01, recon.json
1  SCAN      mappers and probes in parallel, one slice each   -> steps/03…, evidence/
2  COLLECT   concatenate, build the inventory, verify quotes  -> steps/05-collect.md
3  ANALYZE   review waves to convergence, arbitration         -> findings-wave<n>.md
4  EMIT      hand off to docs-review, or stop at evidence     -> the report
```

## 1. Phase 0 — the gate, then the measurement

Run the shared preflight. One `FAIL` line means stop: print the table, print the fix commands, spawn
nothing.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py" \
    --groups runtime,write,read,vcs,forge \
    --out <base> --inputs <paths> --repo <repo> --report <base>/steps/00-preflight.md
```

A `SKIP` is not a `FAIL`. It means a capability is unavailable for a reason the run can work
around — most often an SSH remote inside a sandbox that denies the SSH agent. Every question a
`SKIP` blocks becomes `not-accessed` **with the reason**, never a finding, never a guess.

If a capability is needed by only part of the run, its failure blocks only that part — and you must
**ask** whether to continue with the rest. Silently narrowing the scope and then reporting as though
the whole job was done is the one outcome worse than stopping.

Then measure the inputs:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/spec-recon/scripts/recon.py" <paths> \
    --repo <repo> --prior <existing report, if any> --out <base>/recon.json
```

This settles three things before a single token is spent on reading:

- **Freshness.** Revision markers live *inside* documents as changelog tokens, and the signal is the
  **largest** one, not the first. Which syntaxes count is **data**, in
  `data/recon-patterns.json`, extended by `--patterns` — every house writes revisions differently, so
  none of it belongs in code. A document matching no pattern is not an error: mtime and `git log`
  still answer the question. An input newer than the prior report is stated on line 1 of the
  report — an audit built on a superseded revision is wrong at the foundation and nothing downstream
  can detect it.
- **Ambiguous sources.** One artifact usually exists several times: the source, a copy under `bin/`,
  a test fixture, a hand-edited spare. `recon.py` disqualifies what it can prove is not the source
  and refuses to choose between the rest. If surviving copies differ by `md5`, that is already a
  finding.
- **Surface.** Bytes, lines, language, binary or not — the input the planner needs.

## 2. Phase 1 — plan the fleet, then dispatch it

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/spec-recon/scripts/plan_fleet.py" \
    <base>/recon.json --probe <layers> --baseline <paths> --rounds N
```

The planner is a script, not a paragraph, and the boundary is fixed: **the planner decides
structure** — how many agents, of which roles, in which wave — **you decide content** — what each
one is actually asked, in the words of `--scope`. A fleet that comes out different on every run is
not dynamic, it is unreproducible, and `test_plan_fleet.py` locks it down.

Print the plan as one line. Do not ask, do not stop:

```text
Recon: 6 docs (2 stale-risk) · 3 baselines · 3 binary · git+forge · prior report: none
Plan:  wave1 = 6 doc-extract + 3 state-extract + 1 artifact + 2 code + 1 vcs = 13 agents (2 batches)
```

Dispatch every agent of a wave **in one message**. Use the block shape for its kind, from
`references/probe-contracts.md`: producers get `Write to:`, reviewers return rows in the reply.
Handing a reviewer a `Write to:` line wastes the entire agent — that has happened, and it cost two
agents and roughly half a million tokens.

**Never put your own reasoning in a phase-1 dispatch.** A prober told what answer is expected finds
it.

**A soft budget, and it is a thermometer rather than a knife.** At its sixth tool call an agent
prints one line naming what it still lacks, and may continue if it genuinely needs to, saying why.
An agent finishing past twelve calls means its slice was cut too coarsely, and the report says so.
⛔ **Never make this a hard cap.** An agent out of quota concludes early instead of declaring itself
unfinished, and a shallow answer is indistinguishable from a complete one — which is worse than the
tokens it saved.

## 3. The lead does not read documents

1. **Never read a document.** Dispatch mappers. This holds for six documents as much as for sixty.
2. **You may run deterministic shell measurements** whose output is short — a grep count, a sheet
   count, `git log`, the preflight probes. This is the one place this skill departs from
   `docs-review`, and the reason is narrow: a handful of measurements decide the conclusions, they
   are cheap, and the lead should own them rather than pay an agent to relay them.
3. The boundary is exact: **reading a file is forbidden, reading a measurement is not.** If the
   output would not fit in about thirty lines, it is a file, and it belongs to an agent.
4. **Concatenate shard files; never read-then-rewrite.** `cat` them into the collect step.
4b. **Hand every reading agent a byte range**, not just a path. `plan_fleet.py` computes
   `offset`/`limit` per shard from `recon.json`; pass them through. This does not change what an
   agent sees — only how many times it pays to see it. It is only safe because every reading role
   can answer `NEEDS-WIDER` when the answer lies outside its slice; a range without that escape
   hatch turns "not in my slice" into "not present".
4c. **After wave 1, later waves read `steps/03-extract-*.md`, not the raw documents.** Those files
   already exist and are a full structured pass, not a summary, so nothing is lost by preferring
   them. A reviewer that needs the original may ask for it by `path:line` and the lead supplies that
   line — but **`verify_citations.py` and the `evidence` role always open the real file**, because
   checking a quote character by character cannot be done against anything but the source.
5. Precompute what agents cannot reach: `git log` per document into `docs-history.md`, `git diff`
   into a file for fix review. Agents `Read` those. No agent needs a shell to get history.
6. **Every large step ends in a file.** The next step's input is that file plus a list of paths —
   never the conversation. This is what makes a crashed run resumable: a run that gathered
   everything in context and wrote at the end lost an agent mid-response and lost all of its work.
7. **The report is the deliverable; the chat is two lines.** The per-wave cost line and a failing
   preflight table do not count against that — they are progress, not report.

## 4. Phase 2 — collect, then verify quotes before reviewing

Concatenate the shard files, build the inventory (requirement or claim → source → evidence type),
and run the citation checker **before** any review wave:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/docs-review/scripts/verify_citations.py" <inventory>
python3 "${CLAUDE_PLUGIN_ROOT}/skills/spec-recon/scripts/check_evidence.py" <base>/evidence/
```

A script never reads a near-match and lets it through, which is the one thing an agent doing this by
eye reliably does. The `evidence` reviewer is handed only the rows that failed, never the file.

`check_evidence.py` enforces the labelling rule: every number is `[measured]`, `[quoted]` or
`[derived]`, exactly one of them. It exists because a derived figure was once read as an
observation, acted on, and had to be retracted mid-run.

## 5. Phase 3 — waves, and the arbitration that gates absence

Each wave dispatches the reviewers in one message, plus the arbiter. After **every** wave print one
line:

```text
Wave 2: 5 agents · ~340k tokens · 11m · running ~1.2M · 1 wave left in the cap
```

**Absence claims do not reach the report unverified.** Any verdict of the shape *not implemented*,
*missing*, *not present*, *not covered* is routed to `spec-recon-arbiter-impl`, which opens the code
and returns `REFUTED` with a `path:line`, `UPHELD` with the search terms that failed **and** the
regions it could not reach, or `UNSAFE` when the answer lives somewhere it cannot go. A verdict of
that shape from a document-only reviewer is `needs-probe`, and `needs-probe` is not a verdict.

**An upheld gap then routes once more.** `UPHELD` answers *what is missing* and stops; nobody in the
fleet is allowed to answer *where would it go*, because every probe is forbidden from concluding. So
upheld verdicts go to `spec-recon-gap-design`, which returns `GAP` plus an **`ANCHOR`** — a
`path:line` it opened and read — plus a one-sentence `SHAPE` and a `NEIGHBOUR` where this codebase
already does something similar. No anchor means `UNKNOWN`, not `GAP`: `check_report.py` opens every
anchor and rejects the row if the line is not there. A `GAP` row is **input to
`ktkit:feat-req-specs`**, not a design decision — say that in the report.

Unknowns go through the five-tier ladder in `docs-review/references/self-clarify.md` — unchanged,
except that tier 1 gains a fifth source: **this run's own probe results**. Do not build a second
ladder and do not call an external escalation skill; two parallel ladders is worse than either.

Before asking the user anything, the ladder must be provably exhausted, and the answer must not be
gettable by one `grep`. When you receive an answer, the count of open questions must **go down**. A
new question may be minted only when tier 1 is exhausted *and* you cannot write a falsifier *and*
being wrong costs more than one row of a report. Otherwise decide it yourself and record the
falsifier.

## 6. Phase 4 — hand off

With `--handoff on`, evidence files become documents:

```bash
ktkit:docs-review <spec> <docs>... --evidence <base>/evidence/ --rounds N
```

They appear in `## Source inventory` marked as artifacts this run produced, not as pre-existing
documents. `docs-review` owns the report schema, the lint and the convergence recount from there —
this skill does not write a second report schema, and must not grow one.

With `--handoff off` the run stops after `check_evidence.py` passes and reports the evidence
directory. That is the supported way to use this skill on its own.

## Rules

1. **Freshness first.** No agent is spawned before every input has an mtime, a revision marker and a
   `git log` line.
2. **Missing is a finding — after a probe, never before.**
3. **A measured number and a derived number never share an unlabelled sentence.**
4. **The lead owns the deciding measurements.** Run them; do not delegate them.
5. **Independence when deriving; challenge only afterwards.**
6. **Never claim completeness.** Say what was checked, what was not, and why.
7. **Never name an identifier that was not read off a line in a real file.**

## Stop if you are about to

- Spawn anything before preflight passed, or before freshness was measured
- Tell a read-only reviewer to write a file
- Conclude "not implemented" from an agent that only read documents
- Regex a binary file, or trust `.xlsx` cell text without resolving `sharedStrings`
- Call `gh api`, `gh pr` or `gh issue` — they die on TLS in this sandbox; use a token plus `urllib`
- Treat `gh auth status` as a gate, or a sandbox-blocked command as evidence of absence
- Read a SHA from the local ref cache instead of the server
- Grant an agent `Bash` next to `Grep`/`Glob` — the harness silently removes the latter two
- Spawn more than twelve agents in one message
- Ask the user something tiers 1–3.5 of the ladder can answer
- Mint a new question number for something you can settle on the spot
- Print a finding table into the chat, or use `general-purpose` to merge rows

## References

| File | Read it when |
| ---- | ------------ |
| `references/preflight.md` | always, first — the gate and every fix command |
| `references/probe-contracts.md` | dispatching any `spec-recon-*` agent |
| `references/step-protocol.md` | writing step files, or resuming a crashed run |
| `references/dispatch-planner.md` | sharding, routing evidence types to probes, caps |
| `references/arbitration.md` | a verdict claims something is absent, or an upheld gap needs an anchor |
| `references/evidence-format.md` | writing or reviewing an evidence file |
| `references/handoff.md` | handing off to `docs-review` |
| `references/cost-model.md` | estimating, or writing the per-wave cost line |
| `references/incremental.md` | a prior report exists |
| `data/recon-patterns.json` | this repository writes revisions, build paths or fixtures differently |
| `docs-review/references/self-clarify.md` | any unknown, at any point |
| `docs-review/references/large-sets.md` | more than ~15 documents |
| `docs-review/references/i18n-jp.md` | Japanese documents |

Scripts live under `${CLAUDE_PLUGIN_ROOT}`. If that variable is empty — the skill was copied into
`~/.claude/skills/` rather than installed as a plugin — resolve paths relative to this file, and
expect the agent team to be unavailable: say so on line 1 of the report rather than running degraded
in silence.
