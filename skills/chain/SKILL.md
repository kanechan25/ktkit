---
name: chain
description: "Run a requirement through analysis, spec and plan as one closed loop instead of four hand-typed commands. Takes a requirement file or a described request, routes it to one of four lanes -- BUG, CR, NR or TRIVIAL -- runs the analysis skill, then resolves the open questions that analysis deliberately did not ask -- dispatching resolver subagents and recording every answer in an append-only ledger the later phases read instead of re-deriving. Produces the same artifacts the skills always produced, at the same paths. Stops only for what a resolver cannot settle and being wrong would be expensive. Implementation is off unless --execute is passed. Trigger on /ktkit:chain <file>, or when the user wants a requirement carried to a reviewed spec without driving each step."
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
    [--bug|--cr|--nr|--trivial]  which lane to run. Overrides everything below.
    [--feature]           an alias for --nr, kept because it is what was here before
    [--to A|B|C]          stop after this phase. Default C.
    [--plan yes|no]       skip the question at step 00
    [--execute]           run phase D as well. Default OFF.
    [--resume | --fresh]  what to do when a previous run exists
    [--budget <token>]    stop cleanly at a step boundary. Asked for, never assumed
    [--budget-execute <n>] a separate ceiling for phase D. Default: what A-C cost
    [--ledger-scope run|dir]  `dir` reads sibling runs' ledgers, as leads only
    [--rounds N]          self-loop rounds per phase. Default 2
```

| Flag | What it actually means |
| ---- | ---------------------- |
| `--bug` / `--cr` / `--nr` / `--trivial` | **Names the lane outright**, and nothing overrides it — not the frontmatter, not the wording of the request. Use it whenever you already know, which is most of the time. Passing two of them is an error, not a preference. `--feature` is an alias for `--nr`. |
| `--trivial` | The only lane with no analysis and no spec, so it is the only one where a wrong call produces a change nobody reviewed. It is **never** inferred — not from the frontmatter, not from the size of the diff — and its four entry conditions are all required, not weighed: see `references/lanes.md`. It also requires `--execute`: without it the lane has nothing to run, and the chain stops rather than writing an empty trace. |
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
          07-converge.md
                        ^^^^^^^^^ 04 and 07 are CR · NR only — the BUG lane has
                                  no plan phase and no tasks.md to converge

.claude/claude/analyze/<rel>/<base>.analyze.md              A
.claude/claude/specs/<rel>/<base>/spec.md                   B   CR · NR
.claude/claude/specs/<rel>/<base>/fix.md                    B   BUG
.claude/claude/specs/<rel>/<base>/plan.md                   C   CR · NR only
.claude/claude/implemented/<rel>/<base>.implt.md            D  (only with --execute)
```

⛔ **The BUG lane writes `fix.md`, never `spec.md`, and has no phase C.** A specification says what a
system should do; a bug is a disagreement with one that already exists, and writing a second thinner
one beside it leaves the next reader unable to tell which is authoritative. There is no plan phase
either: the plan for a bug is the failing test.

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

1. **Preflight.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py" \
     --groups artifacts,speckit,superpowers,testcmd,mcp --repo <root>
   ```

   Exit 1 ⇒ ⛔ **STOP**, print what is missing and the command that fixes it. Nothing has been
   spent. There is no flag that turns this into a warning: spec-kit is a prerequisite of the plugin,
   and `hooks/prereq-gate.py` has already refused to start this skill without it.

   | Row | Why the run needs it |
   | --- | -------------------- |
   | `speckit converge` | **FAIL since 5.0.0.** Step 07 is the only step that opens the delivered code and asks whether it satisfies the spec. Without it this is a pipeline, not a loop. |
   | `superpowers` | the BUG lane runs on it outright, and `05` dispatches its reviewer |
   | `test command` | **SKIP is expected**, and it means *ask once*. See the free gate in `05`. |
2. **Feature or bug?** Decided by the first of these that answers, and never by anything below it:

   | | Source | How |
   | - | ------ | -- |
   | 1 | **`--bug` / `--cr` / `--nr` / `--trivial`** | Settled. Stop here, and do not read the input to second-guess it. |
   | 2 | **Frontmatter of the input file** | `type:` matched against the vocabulary below, case-insensitively. Anything else is not a vote — fall through. |
   | 3 | **⛔ Ask.** | State which lane you would pick and the one phrase that made you pick it, so a wrong guess is visible in one line. |

   **The `type:` vocabulary.** Matched case-insensitively, because these values are written by
   different hands: `/ktkit:raise-issue` emits an uppercase code, `/ktkit:rca` emits a slug, and a
   person writing frontmatter by hand writes neither.

   | `type:` | Lane | Written by |
   | ------- | ---- | ---------- |
   | `BUG` | BUG | `/ktkit:raise-issue` |
   | `bug-analysis` | BUG | `/ktkit:rca` |
   | `bug` | BUG | a person, by hand |
   | `NR` | NR | `/ktkit:raise-issue` |
   | `feature` | NR | a person, by hand |
   | `CR` | CR | `/ktkit:raise-issue` |

   `CR` is its own lane and not the bug lane. `form-cr.md` defines a CR as something that **already
   exists and works as designed** but needs different behaviour — nothing is wrong, so there is no
   root cause to find, and `/ktkit:rca` would spend a whole phase looking for one.

   **TRIVIAL is not in that table, and never will be.** No `type:` value selects it, because no
   producer can know whether the four entry conditions hold — that takes reading the repository, not
   reading the request. It is reached by `--trivial` and by nothing else.

   ⛔ **A value not in that table is not a near miss to be interpreted.** It falls to row 3 and is
   asked about. `skills/chain/tests/test_route_vocab.py` keeps the table and the forms in step, in
   both directions.

   ⛔ **There is still no fourth row.** Four lanes, three sources — the vocabulary widened, the
   mechanism did not. The chain never routes itself from the prose alone. Getting this wrong is
   expensive in a way the later gates cannot catch: the wrong lane produces a plausible artifact of
   the wrong kind, and by the time that is obvious, phase 01 has been paid for.

   The reading in row 3 is a suggestion for the human, never a decision: a report of something
   behaving wrongly is BUG, a request for something that does not exist yet is NR, and a request to
   change something that exists and works as designed is CR. Plenty of real requests are honestly
   between two of them; that is what row 3 is for.
3. **Does a previous run exist?** `--resume` / `--fresh` decides; neither flag ⇒ ask here.
4. **Does the repository have its own runbook?** `cat <feature-dir>/runbook.ref`. Present ⇒ default
   `--plan no`; absent ⇒ default `--plan yes`.

Ask whatever of 2–4 is still open as **one block**, once, with the defaults filled in — not three
separate questions. A run that passed a lane flag, `--resume`/`--fresh` and `--plan` asks nothing at
all and goes straight to 01.

Record the lane **and how it was decided** in `steps/00-route.md` — `flag`, `frontmatter`, or
`asked`. When the artifacts later turn out to be the wrong kind, that one word says whether the
chain guessed or was told. Then initialise `resolved.md` and `manifest.md`.

| Lane | 01 | 03 | 05 (only with `--execute`) |
| ---- | -- | -- | -- |
| BUG | `/ktkit:rca` | `/ktkit:bug-fix-specs` | `/ktkit:bug-fix-execute` |
| CR | `/ktkit:analyze-feat` | `/ktkit:feat-req-specs` | `/ktkit:feat-req-execute` |
| NR | `/ktkit:analyze-feat` | `/ktkit:feat-req-specs` | `/ktkit:feat-req-execute` |
| TRIVIAL | — | — | a test-driven change, no spec |

**CR runs the NR column until a dedicated `cr-delta` skill exists (C3).** It is a separate lane from today, so the
manifest and the ledger record which one ran, and the day `cr-delta` exists only this table changes.
Routing CR into NR now and splitting the lane later is recoverable; routing it into BUG and
discovering the mistake after phase 01 is not.

**TRIVIAL has no 01 and no 03**, so `--execute` is not optional for it — see `references/lanes.md`
for the four conditions that must all hold before the lane may be named at all.

### 01 — analyse

Run the lane's analysis skill on the input. It writes `A` and, by design, **asks nothing**: its
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

Run the lane's spec skill, pointed at `A`, and **pass it the ledger path**. That skill runs its own
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

Only with `--execute`. Runs the lane's execute skill. Its own STOP conditions stand unchanged: a
`/speckit-analyze` CRITICAL finding and a HIGH/CRITICAL blast radius are gates, always. They are
"expensive if wrong", which is the definition of T4.

**TRIVIAL has no execute skill.** It runs `superpowers:test-driven-development` directly against the
one file, under the ceiling in `references/lanes.md`: a failing test first, then the change, then
`superpowers:verification-before-completion`. There is no spec to diverge from, so the deviation
record below does not apply to it — what applies instead is the ceiling, and crossing it escalates
to CR rather than finishing.

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

#### ⛔ The free gate runs first, and the reviewer never sees code that failed it

```
worker finishes ──► build · test · lint · typecheck        0 tokens, 0 usage
                              │
                        FAIL ─┴─ PASS
                          │        │
                   back to worker  superpowers:requesting-code-review
                                                            costs usage
```

⛔ **A reviewer must never be dispatched over code that does not compile.** Every finding it returns
is then about a file the compiler would have rejected in a second, and the run pays model usage to
be told something free. This is a cost lever and a quality lever at once, which is rare enough to be
worth stating twice.

**The command comes from the repository, never from a guess.** `preflight.py --groups testcmd` says
which file states it — `package.json` `scripts.test`, a `Makefile` `test:` target, `pyproject.toml`,
`pytest.ini`, `tox.ini`. Read that file and use what it says.

⛔ **`SKIP` means ask, once.** No file states a command ⇒ ask for it in the same block as the other
step-00 questions, write the answer to `<chain-dir>/testcmd`, and never ask again in that run.
⛔ Never infer `npm test` from a `package.json` that has no test script: a green from the wrong
command is worse than no gate, because it is believed.

A failing gate sends the work back to the worker. It is not a finding, not a deviation, and not
something to note and carry forward — it is unfinished work.

#### Then, and only then, the reviewer

```bash
# gate PASS, and not before
```

Invoke `superpowers:requesting-code-review` on the change. This is the step that costs usage, and it
is worth it precisely because everything a compiler can answer has already been answered for free.

⛔ **Gate FAIL ⇒ this step does not run at all.** Not "runs with a note", not "runs and mentions the
failure" — a reviewer given broken code spends its attention on the breakage and returns findings
about a file that was never going to ship in that state.

Findings come back as ordinary work for the worker, and the free gate runs again afterwards: a change
made in response to a review is a change, and it can break the build like any other.

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

### 07 — converge

Only with `--execute`, and only on the CR and NR lanes. **This is the step that closes the loop.**

Every step before it compares one document with another: analysis against request, spec against
analysis, plan against spec, deviations against spec. Not one of them opens the delivered code and
asks *does this satisfy what we said it would do*. `/speckit-converge` does exactly that, and it is
the only step in the whole path that does.

```
/speckit-converge
```

It is **append-only by its own contract** — its operating constraints say its only write is a new
`## Phase N: Convergence` section in `tasks.md`, and that it must leave the file byte-for-byte
unchanged when nothing is missing. So there is nothing to enforce here. There is something to avoid
breaking: ⛔ never edit, renumber or reorder what it appended, and never let a later step rewrite
`tasks.md` wholesale.

**The BUG lane does not run it.** It has no `tasks.md` and no plan phase; what a bug converges
against is its failing test, and `/ktkit:bug-fix-execute` already turned that green.

#### ⛔ Two rounds, and the third does not exist

```
converge ─► appended tasks ─► 05 implement ─► converge      round 1
         ─► appended tasks ─► 05 implement ─► converge      round 2
         ─► anything still missing                          ⛔ STOP
```

Round 3 is not a third attempt — it is a different problem. Work still missing after two rounds of
*find the gap, build the gap, look again* is not missing code; it is a spec that is wrong or
ambiguous, and appending more tasks is paying to chase a target that moves every time you reach it.

At the cap:

1. ⛔ **Append nothing.** The convergence section from round 2 stands as the record.
2. Write the reason into `manifest.md`: which gaps survived both rounds, what was appended each
   time, and which reading of the spec each gap implies.
3. Escalate to the user through **`/ktkit:confirm-with-me`**, naming the spec section you believe is
   wrong or ambiguous. This is the same third-gate exemption the contract-level deviation has: it is
   a report of something that happened, not a question about what to do next.

Record the round count in the manifest as it goes. A run that shows `converge round 1 clean` cost one
call; one that reaches the cap silently, with nothing saying it did, is how a loop becomes a spiral.

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
- Continue past a speckit FAIL at step 00 by writing the artifacts some other way.
- Run phase D without `--execute`.
- Create a branch.

## References

| File | What it settles |
| ---- | --------------- |
| `references/budget.md` | the boundary gate, and every measurement behind it |
| `references/syncback.md` | recording a deviation, and the gate a contract-level one hits |
| `references/ledger.md` | The ledger's columns, the lookup threshold, and what closes a row |
| `references/self-loop.md` | Step 02 in full, and the five places the tokens are saved |
| `references/converge-loop.md` | Step 07 in full: what converge is, the two-round cap, and which lanes run it |
| `references/lanes.md` | the four lanes, TRIVIAL's entry conditions, and the BUG lane's boundary with SDD |
