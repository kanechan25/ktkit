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
| `--resume <dir>` | — | ⭐ **Continue a run that stopped at a boundary.** Reads `<dir>/steps/manifest.md` and restarts at the first row marked `missing` or `partial`. Rows marked `complete` are never re-run — their ID allocations are cited by later rows, and re-minting them silently repoints every citation. This is what `budget.py` prints when a ceiling is reached; stopping is a normal outcome, so resuming has to be one too. |
| `--out <path>` | **asked, never assumed** | **The report file, and with it the whole output directory.** A run writes a directory — report, `recon.json`, seven step files, one evidence file per probe — and every later phase cites paths inside it. So without this flag the run does not pick a location: step 0 prints a suggestion and **stops for your answer**. Working files live in `<dir>/<base>/`, never loose beside the report. |
| `--handoff on\|off` | `on` | Hand phases 3–4 to `ktkit:docs-review --evidence <dir>`. `off` stops after evidence, which is also how this skill is tested. |
| `--max-questions N` | `3` | Ceiling on rows that reach you. Counts across the **whole run**, not per round. |
| `--lang <code>` | inherit | Output language. Stated, never guessed from the inputs. |
| `--patterns <file>` | — | JSON merged over `data/recon-patterns.json`. How a house convention this toolkit has never seen — a revision syntax, a build directory, an extension — is recognised **without editing any code**. |
| `--budget <tokens>` | **`4000000`** | ⭐ **Hard ceiling for the whole run — raise it freely.** `--budget 8000000` for a large corpus, `--budget 2000000` to keep a run small. Checked at every step boundary against `cost.jsonl` — what agents actually reported, never an estimate. Reaching it stops the run **at a boundary**, with everything finished on disk and a resume command printed. A run that has to stop is not a failure; a run that dies mid-wave and loses its verdicts is. |
| `--relevance <n>` | `0.01` | Minimum hits per KB an input needs before an agent reads it. `0` reads everything. The gate **declines on its own** when the vocabulary plainly does not fit the corpus, and it never removes a document carrying revision markers. |
| `--relevance-add <term>` | — | A term the scope wording does not contain — most often the corpus's own language. Repeatable. |
| `--quota-gate <pct>` | `85` | Also stop when the subscription window is at or above this percentage, whatever the token budget says. |
| `--keep-scratch` | off | Keep the working directory after a clean run. |

## The five phases

```
0  RECON     preflight gate, freshness, surface measurement   -> steps/00, 01, recon.json
1  SCAN      mappers and probes in parallel, one slice each   -> steps/03…, evidence/
2  COLLECT   concatenate, build the inventory, verify quotes  -> steps/05-collect.md
3  ANALYZE   review waves to convergence, arbitration         -> findings-wave<n>.md
4  EMIT      hand off to docs-review, or stop at evidence     -> the report
```

## 1. Phase 0 — where it writes, then the gate, then the measurement

### Step 0 — settle the output path. This is a gate.

A run does not produce a file. It produces a **directory** whose paths every later phase cites, and
whose report is read weeks later by something that has only the path. Choosing that location silently
is therefore not a convenience, it is a defect — and it was one: `--out` used to default to the bare
string `spec-recon.md`, which resolves against the working directory and put the entire run at the
repository root, outside `.claude/`.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/spec-recon/scripts/resolve_out.py" \
    --inputs <paths> --repo <repo> --out <path if the user gave one>
```

| Exit | Meaning | What you do |
| ---- | ------- | ----------- |
| `0` | `--out` was given and lands inside `.claude/` | Echo the two lines it printed, continue. |
| `3` | no `--out` | ⛔ **Print its output verbatim and STOP.** Wait for the user to confirm the suggested path or name another. Measure nothing, spawn nothing, create no directory. |
| `2` | `--out` was given and is not usable | Print the reason and the suggestion. Stop. Do not silently substitute. |

The suggestion is derived, not invented: the mirror algorithm is the one in
`skills/ccompact/SKILL.md` §A1, so a reconnaissance run lands beside the artifacts of the thing it
was run on. `<base>` is an exact string — never re-slugified, never replaced by a folder name, never
built out of `--scope`.

⛔ **Never write the confirmed path into a rule file, an env var or a settings file.** It is an
argument for this run.

### Step 0b — is there room to start at all?

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/quota.py" --gate 80
```

| Exit | What you do |
| ---- | ----------- |
| `0` | Continue. |
| `1` | ⛔ **Stop.** Print the percentage, the reset time, and say plainly that under 20% of a window is too little to begin something with this many steps. Do **not** offer flag combinations with token estimates attached — those are guesses. Offer waiting, and `--budget` if the user knows this run is small. |
| `0` with `SKIP` | Continue, and write `quota not-checked: <reason>` into the report. ⭐ Failing to check is **not** the same as being out of quota, and a gate that stops the work on its own blindness is worse than no gate. |

### Step 1 — the capability gate

Run the shared preflight. One `FAIL` line means stop: print the table, print the fix commands, spawn
nothing.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py" \
    --groups runtime,write,read,vcs,forge,artifacts \
    --out <base> --inputs <paths> --repo <repo> --report <base>/steps/00-preflight.md
```

The `artifacts` group is what makes `.claude/claude/` exist and proves it is writable. It was missing
before, which is why nothing caught the report landing outside it.

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

### Step 0c — resuming

With `--resume <dir>`, read `<dir>/steps/manifest.md` and nothing else: it is the index, and reading
the step files themselves re-pays for work already done. Restart at the first row marked `missing` or
`partial`, re-dispatch only that step's agents with the inputs the manifest records, and append the
re-run rather than editing the failed row — what failed, and when, is part of the record.

⛔ **Never re-run a row marked `complete` because it would be "safer".** `references/step-protocol.md`
gives the reason: a completed step's requirement and claim IDs are referenced by every later row, and
re-minting them repoints every citation in the previous report at a different thing, silently.

The cost ledger is append-only, so a resumed run's `--budget` applies to the **whole** run, not to
the remainder. Pass a new ceiling if you mean the remainder to have its own.

## 2. Phase 1 — narrow to what the question is in, then plan

### Step 1b — the relevance gate ⭐ the largest measured saving

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/spec-recon/scripts/relevance.py" <base>/recon.json \
    --scope "<verbatim>" --threshold <n> --add <term>... \
    --report <base>/steps/01b-relevance.md --out <base>/recon-relevant.json
```

Measured on a real 64-file corpus: **48 mapper agents become 20**. The reason it is worth this much
is that fifty-three of those files contained nothing the question was about, and the planner was
spawning an agent per shard to read all of them anyway.

Then plan from `recon-relevant.json`, not `recon.json`.

⛔ **Three rules, and the first is the one that makes the gate safe to have:**

1. **Narrowing is never silent.** `steps/01b-relevance.md` lists every excluded file with its size
   and hit count, and the report carries a `## Not read` section. `SKILL.md` already forbids the
   alternative: *"Silently narrowing the scope and then reporting as though the whole job was done is
   the one outcome worse than stopping."*
2. ⭐ **An absence claim from an excluded file is `not-accessed: cut by the relevance gate`, never
   `UPHELD`.** This is the `R-ARTIFACT` trap wearing a new hat: the gate turns *"I did not read it"*
   into *"it does not exist"* unless this rule holds.
3. **`GATE-DECLINED` is a result, not an error.** The gate refuses to act when the corpus is mostly
   in a script none of its terms are, or when it would cut most of the corpus by size. Print its
   reasons, pass every input to the planner, and continue — the run costs what it would have cost
   without the gate. Measured: a scope written in Vietnamese and English produced four ASCII terms
   and would have cut two Japanese specification documents of 729 KB and 223 KB, because the question
   said `export` and the document says `出力`.

### Step 1c — index the code before probing it ⭐ the second largest saving

If `code` is in `--probe`, the sweep runs in a script, **not in an agent**:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/spec-recon/scripts/probe_index.py" \
    --repo <repo> --paths <dirs> --variants --max-hits 20 \
    --ids <identifier>... --out <base>/steps/01c-code-index.md
```

`probe-code` was the most expensive role in the fleet and should have been the
cheapest. Its question is small — does this identifier exist, and where — but the search happened
**inside the agent**. Measured on a real repository: `src/` holds 14,627 tracked files, and one
`Grep` for `export` returns **15,358 matching lines across 3,801 files**. That lands in the agent's
context, and an agentic loop re-sends everything accumulated on every later call.

| | Tokens |
| - | -----: |
| four identifiers swept **inside** an agent | ~185,000 for the first call alone, re-sent after |
| the same four, as an index the agent **reads** | **~1,700** |

⭐ **A 109× reduction on the read, and identifiers with zero occurrences need no agent at all** — the
script settles them with the commands it ran. A run reached 7.5M with `probe-code` skipped after
being warned it would pass 8M, so the questions it would have answered went unanswered. That is the
expensive outcome, and this is what removes it.

Then size the code fleet from the index, **not from the document count**: one agent per topic cluster
of identifiers that had occurrences. `plan_fleet.py` deliberately reports `probe-code x0` until this
step has run.

⛔ **The script states counts, lines and commands. It never states `EXISTS` or `NOT_FOUND`** — those
are the agent's, and an absence still needs an agent to say what it means. Pass `--variants` so an
identifier is searched the way another house would have spelled it; an absence searched one way is
not an absence.

### Step 2 — the fleet plan

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

Each wave dispatches the reviewers in one message, plus the arbiter.

### ⭐ Before every dispatch: record what the agent is being sent

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/spec-recon/scripts/dispatch_log.py" \
    --base <base> --agent <name> --wave N --payload-file <base>/scratch/<name>.prompt
```

Write the prompt to a file, measure it, then dispatch it. This exists because the
payload is the one term in a run's cost that nobody has ever measured, and it is the term most
likely to dominate: a subagent's prompt is re-sent on every internal turn it takes.

The evidence that something is missing is arithmetic. A 24-agent run spent 5,345,133 tokens while
wave 1 handed its agents 852,260 bytes of document — about 213,000 tokens of content, **9.7%** of
what the wave spent. Three candidate explanations were fitted against those 24 agents and all three
failed:

| Candidate driver | R² |
| ---------------- | -: |
| output tokens written | **0.145** (slope came out negative) |
| tool calls made | 0.421 |
| output × calls | 0.025 |

Every model left **166,000–262,000 per agent** unexplained. `arbiter-B-bugs-accept` spent 398,092
tokens and wrote 2,286 back — 174 to 1. It was not reading and it was not writing.

⛔ **So record it and do not yet cut it.** `dispatch.md` pairs each payload against what that agent
spent, in the shape that matters — `payload × calls`. When that column tracks the spend, the payload
is the missing term and there is a defensible place to cut. Cutting first is how the tool-call cap
came to be proposed on the strength of a quadratic that the data later refused.

### ⭐ After every step: record the cost, then ask whether another step fits

Two calls, in this order, at **every** step boundary — after each dispatch batch, after each
arbitration, after each wave. This is the mechanism that keeps a run inside `--budget`, and it is
the one thing that would have prevented a run spending 15.2M tokens and returning no verdict.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/spec-recon/scripts/budget.py" \
    --base <base> --budget <tokens> --quota-gate <pct> --step <name>
```

| Exit | Meaning | What you do |
| ---- | ------- | ----------- |
| `0` | `GO` | Print its one line and continue. |
| `1` | `STOP` | ⛔ **Stop at this boundary.** It has already printed the reason, the reset time and the resume command. Write `partial` into `manifest.md` naming exactly what was not reached. Dispatch nothing further. |

**It forecasts nothing.** The arithmetic is `spent + last_step × 1.5 > budget`, and both terms are
measurements: `spent` from `cost.jsonl`, `last_step` from the difference since the previous boundary.
A step may cost more than the one before it, so the margin asks for that much again plus half. If a
boundary is checked twice, the difference is zero — the estimate then falls back to the last step
that did cost something, and says which, rather than letting a zero switch the guard off.

⭐ **Raising the ceiling is normal, and the run says whether the window can hold it.** Once a step has
reported both tokens and a window percentage, `budget.py` prints this run's own rate — tokens per
percent of window, for this account, this tier, this corpus — and what the remaining window therefore
allows in total:

```text
window allows about 14,505,000 tokens in total, at this run's own rate of
151,166 per 1%  [measured here, not stored]
```

Past that figure it says so outright: *the 20,000,000 ceiling will not be reachable in this window;
raise it only if you also wait for the reset.* ⛔ The rate is **never stored and never carried between
runs** — it is two observations from the run in front of you, and it stops being true the moment the
account, the tier or the corpus changes.

⭐ **A cheap step still passes when an expensive one does not**, and that ordering is deliberate.
Measured on the gate: at 3.17M of a 4M budget it refused another 927k extraction batch and then
allowed a 305k arbitration — so the verdicts still land when the extraction cannot continue.
Arbitration is what turns evidence into an answer; it is the last thing that should be starved.

### Recording the cost



The spend used to exist only as a line of chat, which meant it existed until somebody scrolled. It is
now an artifact of the run — written in **one call for the whole wave**, never one per agent:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/spec-recon/scripts/cost_log.py" wave \
    --base <base> --wave N \
    --row 'probe-code,A,148200,3100,14,96' \
    --row 'probe-vcs,B,,,,,no usage returned'
```

Each `--row` is `agent,toolset,tokens_in,tokens_out,tool_calls,seconds[,note]`, and an **empty field
means the agent did not report that number**.

One call per wave, never one per agent: measured on a 43-agent wave, batching is **~520 tokens
instead of ~4,100** — 0.019% of a 2.75M-token run rather than 0.149% — and one round trip instead of
43. Tracking that eats a noticeable slice of what it tracks is not worth keeping. See
`references/cost-model.md` for the measurement.

Then print the line the script gives back — it is the running total, computed from the file:

```text
Wave 2: 5 agents · 339,925 tokens · 11m · running 1,205,844
```

Three rules, and they are the reason the file is worth having:

1. **Numbers come from the `usage` each agent returned.** Never estimate a figure that was actually
   reported — a `[derived]` total that could have been `[measured]` breaks the same rule the evidence
   files are held to.
2. **An agent that reported nothing is recorded as reporting nothing.** Omit the number flags and say
   so in `--note`. The rendered total then states how many agents it excludes, so it reads as a floor
   rather than as the bill. ⛔ Never fill a gap with an average.
3. **`cost.jsonl` is append-only.** A wave that is re-run appends; it never overwrites. What the
   first attempt cost is part of the record. A mistake is `cost_log.py correct --reason <why>`.

`cost.md` beside it is a rendered view, regenerated on every append. It also states plainly that the
lead's own turns are **not** in the total — an agent cannot measure the session that dispatched it,
and a total that implies otherwise is worse than no total.

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

- Dispatch a further step after `budget.py` returned `STOP` — the ceiling is the user's, not a suggestion
- Report an `UPHELD` absence for a file the relevance gate excluded; that verdict is `not-accessed`
- Narrow the input set without writing `steps/01b-relevance.md` and the report's `## Not read` section
- Treat `GATE-DECLINED` or a quota `SKIP` as a failure — both mean *continue, and say so*
- Measure, spawn, or create a directory before the output path is confirmed — see Phase 0 step 0
- Substitute a path of your own when `resolve_out.py` rejected the one you were given
- Report a token figure an agent actually returned as though you had estimated it, or fill a
  missing one with an average — `cost_log.py` records a gap as a gap
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
| `references/cost-model.md` | estimating before a run, or recording what a wave cost |
| `references/budget.md` | the ceiling, the boundary gate, and the relevance gate |
| `references/incremental.md` | a prior report exists |
| `data/recon-patterns.json` | this repository writes revisions, build paths or fixtures differently |
| `docs-review/references/self-clarify.md` | any unknown, at any point |
| `docs-review/references/large-sets.md` | more than ~15 documents |
| `docs-review/references/i18n-jp.md` | Japanese documents |

Scripts live under `${CLAUDE_PLUGIN_ROOT}`. If that variable is empty — the skill was copied into
`~/.claude/skills/` rather than installed as a plugin — resolve paths relative to this file, and
expect the agent team to be unavailable: say so on line 1 of the report rather than running degraded
in silence.
