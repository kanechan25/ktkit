---
name: chain
description: "Run a requirement through analysis, spec and plan as one closed loop instead of four hand-typed commands. Takes a requirement file or a described request, routes it to the feature or the bug arm, runs the analysis skill, then resolves the open questions that analysis deliberately did not ask -- dispatching resolver subagents and recording every answer in an append-only ledger the later phases read instead of re-deriving. Produces the same artifacts the skills always produced, at the same paths. Stops only for what a resolver cannot settle and being wrong would be expensive. Implementation is off unless --execute is passed. Trigger on /ktkit:chain <file>, or when the user wants a requirement carried to a reviewed spec without driving each step."
---

# chain — one requirement in, a reviewed spec out

This skill runs no analysis of its own. It **orchestrates** six skills that already exist, and adds
the two things none of them can add alone: a record of what has already been settled, so a later
phase never re-asks it, and a single place where the run stops.

## Hard constraints

1. **The lead does not read source files.** Not the repository, not the artifacts the phases write.
   In an agentic loop the lead's context is re-sent every turn, so a file opened at step 01 is paid
   for at every step after it. The lead reads step files and gate blocks, nothing else.
2. **Every phase hands off through a file, never through this conversation.** A phase receives
   paths. It does not receive the lead's reasoning about what the previous phase found.
3. **Implementation is off** unless the user passes `--execute`. Without it the chain stops after
   the plan, with the artifacts written and nothing applied to the repository.
4. **Never create or switch a branch.** Whatever is checked out stays checked out.
5. **This skill invents no policy.** Tiers, budgets and gate format come from
   `/ktkit:escalation-ladder`. Where this file and that one disagree, that one wins.

## Arguments

```
/ktkit:chain <requirement.md | "described request">
    [--bug | --feature]   which arm to run. Overrides everything below.
    [--to A|B|C]          stop after this phase. Default C.
    [--plan yes|no]       skip the question at step 00
    [--execute]           run phase D as well. Default OFF.
    [--resume | --fresh]  what to do when a previous run exists
    [--budget <token>]    stop cleanly at a step boundary. Asked for, never assumed
    [--budget-execute <n>] a separate ceiling for phase D. Default: what A-C cost
    [--ledger-scope run|dir]  `dir` reads sibling runs' ledgers, as leads only
    [--no-speckit]        take the internalised path even where speckit is installed
    [--rounds N]          self-loop rounds per phase. Default 2
```

| Flag | What it actually means |
| ---- | ---------------------- |
| `--bug` / `--feature` | **Names the arm outright**, and nothing overrides it — not the frontmatter, not the wording of the request. Use it whenever you already know, which is most of the time. Passing both is an error, not a preference. |
| `--no-speckit` | **Selects the internalised path**, it does not relax a check. Without it, a missing `.specify/` or missing speckit skills stops the run at step 00 and prints the install command — the chain never degrades on its own, because delivering something else under the same name is worse than stopping. |
| `--budget` | ⭐ **Asked for, never assumed.** Without it, step 00 prints what a comparable run cost — from `cost.jsonl`, if one exists nearby — and **stops for your answer**. It does not pick a number: `ktkit:spec-recon` defaults to 4M because 453,571 tokens per agent was measured there, and this skill has a different shape and **no measurement yet**. Checked at every step boundary against `cost.jsonl`; reaching it writes `partial` into the manifest and stops **at a boundary** — never mid-step, which would leave a half-written artifact that reads as finished. |
| `--budget-execute` | Phase D is the one phase whose cost tracks the size of a change rather than the number of questions, so it gets its own ceiling. Default: **what phases A–C actually cost**, measured. ⛔ Running out mid-implementation leaves a repository half-changed, which is worse than one not changed at all — so if the remainder is under that figure, phase D does not start. |
| `--ledger-scope` | `run` (default) reads only this run's ledger. `dir` also reads sibling runs' `resolved.md` in the same `prompts/<rel>/`, and reports a match as **`FOREIGN` with exit 2** — a lead for a resolver, never a conclusion. A row settled last week may be stale, and a wrong `HIT` is worse than a `MISS` because the chain cites an answer to a question nobody asked now and stops looking. |
| `--resume` | Read `manifest.md`, restart at the first row marked `missing` or `partial`. Rows marked `complete` are never re-run: their ID allocations are cited by every later row, and re-minting them repoints those citations at something else, silently. |
| `--fresh` | Start at step 00. ⛔ Deletes nothing — the previous run directory is renamed `<base>.<timestamp>/`, and the artifacts under `analyze/`, `specs/` and `pipeline/` are left alone. |
| `--rounds` | Per `/ktkit:escalation-ladder`: at most 5 resolvers per round, at most 2 rounds for one question. `--rounds` moves the second number only. |

## Layout

Artifacts stay exactly where the skills already put them. The chain adds only a trace directory:

```
.claude/claude/prompts/<rel>/<base>.md            the input

.claude/claude/chain/<rel>/<base>/
    manifest.md                                    the index, and the resume instruction
    resolved.md                                    the ledger — see below
    steps/00-route.md   01-analyze.md   02-clarify.md
          03-spec.md    04-plan.md      05-implement.md   06-syncback.md

.claude/claude/analyze/<rel>/<base>.analyze.md              A
.claude/claude/specs/<rel>/<base>/spec.md                   B
.claude/claude/specs/<rel>/<base>/plan.md                   C
.claude/claude/implemented/<rel>/<base>.implt.md            D  (only with --execute)
```

`<rel>` and `<base>` mirror the input's sub-path under `prompts/`, exactly as `/ktkit:analyze-feat`
resolves them. Do not re-slugify. The artifact root `.claude/claude/` is a rule of this plugin:
`mkdir -p` what is missing, never probe for an alternative, never write outside `.claude/`.

## The ledger — why the chain is more than four commands in a row

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/chain/scripts/ledger.py" <ledger> --lookup "<question>"
```

Each phase runs its own ladder. Left alone they re-derive the same unknowns: phase B pays a resolver
to answer what phase A already answered, and can reach a different conclusion than the artifact
above it. The ledger is the fix, and it is a file so that any agent can read it.

| Rule | Why |
| ---- | --- |
| **Look up before dispatching.** A hit means skip the spawn and cite the existing row. | A resolver costs ~6.6k tokens before it reads anything. A lookup costs nothing. |
| **Append-only.** A changed conclusion is a new row for the same ID; the old row stays. | What was believed, and when it stopped being believed, is the tracking log. |
| **A T4 row the user answered is closed.** No phase may re-open it. | Re-deciding a settled question overwrites a decision somebody made on purpose. |

`--metric` recomputes `self_resolve_ratio` from the rows. ⛔ Never report a ratio an agent asserted.

Full reference: `references/ledger.md`.

## The steps

### 00 — route

Cheap, and before anything is spent. In order:

1. **Preflight.** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py" --groups artifacts,speckit,mcp --repo <root>`.
   Drop `speckit` from `--groups` only when `--no-speckit` was passed. Exit 1 ⇒ ⛔ **STOP**, print
   what is missing and the command that fixes it. Nothing has been spent.
2. **Feature or bug?** Decided by the first of these that answers, and never by anything below it:

   | | Source | How |
   | - | ------ | -- |
   | 1 | **`--bug` / `--feature`** | Settled. Stop here, and do not read the input to second-guess it. |
   | 2 | **Frontmatter of the input file** | `type: bug` / `type: bug-analysis` / `type: feature`. Anything else in `type:` is not a vote — fall through. |
   | 3 | **⛔ Ask.** | State which arm you would pick and the one phrase that made you pick it, so a wrong guess is visible in one line. |

   ⛔ **There is no fourth row.** The chain never routes itself from the prose alone. Getting this
   wrong is expensive in a way the later gates cannot catch: the wrong arm produces a plausible
   artifact of the wrong kind, and by the time that is obvious, phase 01 has been paid for.

   The reading in row 3 is a suggestion for the human, never a decision: a report of something
   behaving wrongly is the bug arm, a request for something that does not exist yet is the feature
   arm, and plenty of real requests ("change how X is calculated") are honestly both.
3. **Does a previous run exist?** `--resume` / `--fresh` decides; neither flag ⇒ ask here.
4. **Does the repository have its own runbook?** `cat <feature-dir>/runbook.ref`. Present ⇒ default
   `--plan no`; absent ⇒ default `--plan yes`.

Ask whatever of 2–4 is still open as **one block**, once, with the defaults filled in — not three
separate questions. A run that passed `--bug`/`--feature`, `--resume`/`--fresh` and `--plan` asks
nothing at all and goes straight to 01.

Record the arm **and how it was decided** in `steps/00-route.md` — `flag`, `frontmatter`, or `asked`.
When the artifacts later turn out to be the wrong kind, that one word says whether the chain guessed
or was told. Then initialise `resolved.md` and `manifest.md`.

| Arm | 01 | 03 | 05 (only with `--execute`) |
| --- | -- | -- | -- |
| feature | `/ktkit:analyze-feat` | `/ktkit:feat-req-specs` | `/ktkit:feat-req-execute` |
| bug | `/ktkit:rca` | `/ktkit:bug-fix-specs` | `/ktkit:bug-fix-execute` |

### 01 — analyse

Run the arm's analysis skill on the input. It writes `A` and, by design, **asks nothing**: its
unknowns land in a table rather than in a question. Record the path in `steps/01-analyze.md`.

### 02 — self-clarify

The step that makes the chain worth building. Detailed in `references/self-loop.md`; the shape is:

```
read ONLY the gate block of A            ← not the whole report
for each unsettled row:
    ledger --lookup  → HIT ⇒ skip, cite the existing row
                     → MISS ⇒ queue it
round = 1
while queue and round <= --rounds:
    take at most 5, dispatch ktkit:escalation-resolver — one question per agent,
    all in ONE message so they run concurrently
    each returns ONE line; append it to the ledger; drop what reached T1..T3.5
    round += 1
survivors are T4. Cap at 3, merge the rest into one representative row.
ledger --metric  → below 0.70 and rounds left ⇒ loop again
                 → below 0.70 and out of rounds ⇒ say so in the step file,
                   ⛔ do not open the gate and do not call the artifact clean
upsert A's gate block:  upsert_block.py <A> --block - --marker chain
```

⛔ The lead never opens the files the resolvers read. It holds the question, the tier, and a
one-line conclusion with its citation.

### 03 — spec

Run the arm's spec skill, pointed at `A`, and **pass it the ledger path**. That skill runs its own
ladder — the chain does not run one for it — but the ledger stops it re-asking what step 02 settled.

Its HARD STOP is **conditional here**: `--metric` clean and no OPEN row ⇒ print the ✅ and 🟡 tables
into `steps/03-spec.md` and continue. Otherwise this is the gate. See below.

### 04 — plan

`--plan no` ⇒ skip, and say in `steps/04-plan.md` that `B` is where the chain stopped and why.

`--plan yes` ⇒ `/speckit-plan` writes `plan.md` in the feature dir. If `runbook.ref` is present the
chain **stops here and hands over**: this skill does not read a runbook, does not run a command
taken from one, and does not call the skill that produced it.

⛔ **Before that call, confirm the pin — 03 writing the spec is not proof it still holds:**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/speckit_pin.py" --verify --dir <feature-dir> --repo <root>
```

`/speckit-plan` runs `setup-plan.sh`, which resolves its feature directory from
`.specify/feature.json` — one mutable pointer for the whole repository — and then copies the plan
template over `plan.md` there. A pin aimed at an unrelated feature does not make it fail: it
writes into **that** feature's directory and reports success, destroying whatever `plan.md` held.
Exit 1 ⇒ repin (drop `--verify`) first. And when this feature's `plan.md` already exists as real
content, copy it to `plan.pre-speckit.md` before the call — the template copy is unconditional and
takes no backup. Record either action in `steps/04-plan.md`.

Anything the plan reveals that contradicts the spec is **synced back** — see below.

### 05 — implement

Only with `--execute`. Runs the arm's execute skill. Its own STOP conditions stand unchanged: a
`/speckit-analyze` CRITICAL finding and a HIGH/CRITICAL blast radius are gates, always. They are
"expensive if wrong", which is the definition of T4.

⭐ **Pass the run directory and require a deviation record.** The execute skill records every
divergence **at the moment it happens**, into `<chain-dir>/deviations.jsonl`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/deviation.py" add \
    --base <chain-dir> --repo <root> --source "spec §4.2" \
    --said "POST /exports returns 202" --did "returns 201" \
    --why "202 needs a job queue the spec does not describe" \
    --evidence src/api/ExportController.cs:88 [--contract]
```

⛔ **The spec is not touched here.** Editing it mid-phase would stop it being a stable reference
during the very phase that reads it, would let a contract-level change land before anyone approved
it, and would leave an aborted run with a specification describing code that was rolled back — worse
than the original problem. Step 06 does the writing, at a boundary.

⭐ **Why the moment matters:** the reason is the one part nobody can reconstruct afterwards. A diff
shows that the code differs; it never shows why somebody chose that. `--why` is mandatory and the
lint refuses a row without it.

Nothing diverged? That is a **statement**, not a silence:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/deviation.py" none --base <chain-dir> --repo <root>
```

### 06 — sync back

⛔ **A specification that disagrees with the code is worse than no specification**: it reads as
authoritative and is quietly wrong. Somebody opens it three months later, believes it, and builds on
a shape that was never shipped. Closing that is not optional.

**1. Lint the record. A failure is a stop, not a warning.**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/deviation.py" lint --base <chain-dir> --repo <root>
```

| Result | What you do |
| ------ | ----------- |
| `LINT … 0 unsafe` | continue |
| exit 1 | ⛔ **STOP.** A deviation anchored to a line that is not there reads as verified and is not. Fix or withdraw the row. |
| `NOT-ANSWERED` | ⛔ **STOP.** Nothing was recorded and no `--none` was declared, so nobody answered the question. Silence is not "nothing diverged". |
| `DECLARED-NONE` | continue; the block will say so, with when it was declared |
| `⚠️ contract-level` | see 3 below — **a gate, not a sync** |

Anchors are re-checked against the tree, because a `path:line` captured mid-phase drifts as the code
keeps changing. A line that moved is **re-resolved** and marked; a line that is gone is a stop.
⛔ Without that, every anchor only means "true at some point".

**2. Render once, into both files.**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/deviation.py" render --base <chain-dir> --repo <root> \
  | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/upsert_block.py" <spec.md> --block - --marker chain
```

The same rendered table goes into `.implt.md`. ⭐ **Neither is authored separately, so they cannot
drift, and reading `spec.md` alone is enough** — which is the point: a hand-written table in one file
and a hand-written table in the other are two authorings that can disagree.

The block sits at the end of the file; every character above it is copied through untouched, so
citations into the spec keep their line numbers. The marker is `chain`, so a `docs-review` block in
the same file is neither read nor overwritten.

```markdown
## Sai khác phát hiện lúc thi hành — <date>
| # | Nguồn | Spec nói | Thực tế | Vì sao | Bằng chứng | |
```

**3. A contract-level row is a gate.**

Implementation detail syncs on its own. A change to what the spec **promises** does not: an
acceptance criterion, an API shape, a dropped requirement. Somebody is integrating against those.

⇒ Any row marked `--contract` stops the run and goes through **`/ktkit:confirm-with-me`** before it
is written. ⛔ "It could not be done" is not "it did not need doing".

⚠️ This is a **third** gate, and it does not count against the two below: it is not a question, it
is confirmation of a change that has already happened.

Conflicts found in step 04 go into the same block, by the same route.

## The gate

At most **two questions** in a whole run, and a clean run has none:

| When | Where |
| ---- | ----- |
| T4 survivors after step 02, or the spec skill's own T4 pool | step 03 |
| `/speckit-analyze` CRITICAL, or blast radius HIGH/CRITICAL | step 05 |

⭐ **A contract-level deviation is a third stop and is not counted here**, because it is not a
question: the change has already happened, and what is being asked is whether the specification may
be rewritten to say so. Only `--execute` runs can reach it.

Format is `/ktkit:escalation-ladder`'s three tables: ⛔ CẦN CHỐT (≤3 rows, each with a default that
is **already applied** and a recommendation), ✅ ĐÃ TỰ CHỐT, 🟡 GIẢ ĐỊNH CÓ BẰNG CHỨNG.

Post it by invoking **`/ktkit:confirm-with-me`** explicitly. ⛔ Do not rely on the literal marker
firing: the rule that arms it comes from this plugin's SessionStart hook, and a run must not depend
on a hook having been read.

Silence accepts the defaults — that is what makes a default worth writing. A reply that does not
address the gate is not an answer; re-post it.

## The manifest

One row per step, appended as it completes. It **is** the resume instruction.

```markdown
| Step | File | Status | Consumed by |
| ---- | ---- | ------ | ----------- |
| 00 | steps/00-route.md | complete | 01 |
| 01 | steps/01-analyze.md | complete | 02 |
| 02 | steps/02-clarify.md | partial: 3 of 5 unknowns resolved, budget reached | 03 |
```

Partial work beats work that looks complete: a step file covering half its job while reading as
finished cannot be told from a finished one, by a human or by the next phase.

## Cost — measured at every boundary, written to a file

### Step 00 — before anything is spent

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/quota.py" --gate 80
```

Under 20% of a subscription window left is too little to begin something with this many phases.
`SKIP` is **not** a stop: failing to read the quota is not the same as being out of it, so the run
continues and writes `quota not-checked: <reason>` into the manifest.

⛔ **Then settle `--budget`.** Without it, print what a comparable run cost and **stop for an
answer**. Do not choose a number — `spec-recon` defaults to 4M because it measured 453,571 tokens
per agent, and nothing has measured this skill.

### After every phase

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cost_log.py" wave \
    --base <chain-dir> --wave 02-clarify \
    --row 'resolver-1,A,148200,3100,14,96' --row 'resolver-2,A,…'

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/budget.py" \
    --base <chain-dir> --budget <n> --quota-gate 85 --step 02-clarify
```

One call per phase, not one per agent: measured on a 43-agent wave, batching is ~521 tokens against
~4,106, and tracking that consumes a noticeable share of what it tracks is not worth keeping.

⭐ **Record the six pipeline skills too, not only the resolvers.** `chain` dispatches
`analyze-feat` (688 lines), `feat-req-specs` (611), `rca` (372) and three more as subagents, each
loading its whole body. `cost-model.md` measures that a long body is a tax on **every** spawn — a
four-tool agent with a long body came to 23,375 tokens against 6,619 for a short one — and nobody has
ever measured what these six cost. They are the largest unmeasured term in this skill.

`budget.py` returns `GO` (continue) or `STOP`. On `STOP`: write `partial` into `manifest.md` naming
what was not reached, and print the `--resume` line it gives you. ⛔ Dispatch nothing further.

⭐ **A boundary here is worth more than in `spec-recon`**, because each phase ends on a *complete
artifact*. Stopping after phase B leaves a finished spec, not half an evidence set.

### Before phase D

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/budget.py" \
    --base <chain-dir> --budget <budget-execute> --step 05-implement-precheck
```

Phase D costs by the size of the change, not the number of questions. If what remains is less than
phases A–C actually cost, ⛔ **do not start it**: say so, and say that a half-changed repository is
worse than an unchanged one.

### What lands on disk

```
<chain-dir>/cost.jsonl · cost.md         what each phase and each agent cost
<chain-dir>/budget.jsonl                 the gate's verdict at every boundary
<chain-dir>/dispatch.jsonl · dispatch.md what each agent was sent, against what it spent
<chain-dir>/lookup.jsonl                 every ledger lookup, and what it saved
```

Three rules: **missing is missing** (an agent that reported no usage is recorded as such, and the
total names how many it excludes and calls itself a floor — never an average) · **append-only** ·
**the lead's own turns are not in the total**, and the file says so.

### Before every dispatch

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dispatch_log.py" \
    --base <chain-dir> --agent <name> --wave <phase> --payload-file <path>
```

The prompt a subagent receives is composed in the dispatch call and written nowhere, and it is
re-sent on every internal turn the agent takes. On a 24-agent `spec-recon` run, three candidate
explanations for the cost were fitted and all three failed — output tokens R² 0.145, tool calls
0.421, output × calls 0.025 — leaving 166,000–262,000 per agent unexplained. This is the term that
was never measured. ⛔ It is recorded and **not** cut: cutting an unsized term is how a tool-call cap
came to be proposed on a model the data later refused.

### What the ledger lookup saved

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/chain/scripts/ledger.py" <ledger> --cache-metric
```

Pass `--record` to every `--lookup` so this has something to count. `references/self-loop.md` lists
the lookup as one of five places the tokens are saved and gives the arithmetic — 6,619 per spawn
against one grep — but nothing counted the hits, so it was an assertion. The metric reports hits as a
**floor** on tokens not spent, labelled `[derived]`, plus the near-misses between 0.45 and 0.60 —
the only evidence for whether `--threshold` sits where it should.

## Stop if you are about to

- Dispatch a further phase after `budget.py` returned `STOP`, or start phase D with less than
  phases A–C cost
- Choose a `--budget` yourself instead of asking; no measurement of this skill exists yet
- Treat a `FOREIGN` row as an answer, or let one close a row in this run's ledger
- Read a source file in the lead because it would be quicker than dispatching.
- Carry a phase's findings forward in conversation instead of in its step file.
- Re-run a step the manifest marks `complete`.
- Open a gate for something a resolver was never asked.
- Report a `self_resolve_ratio` that was asserted rather than recomputed.
- Fall back to the internalised path because speckit is missing and nobody passed `--no-speckit`.
- Run phase D without `--execute`.
- Create a branch.

## References

| File | What it settles |
| ---- | --------------- |
| `references/budget.md` | the boundary gate, and every measurement behind it |
| `references/syncback.md` | recording a deviation, and the gate a contract-level one hits |
| `references/ledger.md` | The ledger's columns, the lookup threshold, and what closes a row |
| `references/self-loop.md` | Step 02 in full, and the five places the tokens are saved |
