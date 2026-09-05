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
    [--budget <token>]    stop cleanly at a step boundary. Default: no ceiling
    [--no-speckit]        take the internalised path even where speckit is installed
    [--rounds N]          self-loop rounds per phase. Default 2
```

| Flag | What it actually means |
| ---- | ---------------------- |
| `--bug` / `--feature` | **Names the arm outright**, and nothing overrides it — not the frontmatter, not the wording of the request. Use it whenever you already know, which is most of the time. Passing both is an error, not a preference. |
| `--no-speckit` | **Selects the internalised path**, it does not relax a check. Without it, a missing `.specify/` or missing speckit skills stops the run at step 00 and prints the install command — the chain never degrades on its own, because delivering something else under the same name is worse than stopping. |
| `--budget` | No ceiling by default. A cost line is printed after **every** step regardless. With a ceiling, the run writes `partial` into the manifest and stops **at a step boundary** — never mid-step, which would leave a half-written artifact that reads as finished. |
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

`--plan yes` ⇒ `/speckit.plan` writes `plan.md` in the feature dir. If `runbook.ref` is present the
chain **stops here and hands over**: this skill does not read a runbook, does not run a command
taken from one, and does not call the skill that produced it.

Anything the plan reveals that contradicts the spec is **synced back** — see below.

### 05 — implement

Only with `--execute`. Runs the arm's execute skill. Its own STOP conditions stand unchanged: a
`/speckit.analyze` CRITICAL finding and a HIGH/CRITICAL blast radius are gates, always. They are
"expensive if wrong", which is the definition of T4.

### 06 — sync back

Every conflict found in 04 or 05, once decided, is written back into the artifact it contradicts:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/docs-review/scripts/upsert_block.py" \
  <spec.md> --block - --marker chain
```

The block sits at the end of the file; every character above it is copied through untouched. The
marker is `chain`, so a `docs-review` block in the same file is neither read nor overwritten.

```markdown
## Sai khác phát hiện lúc thi hành — <date>
| # | Spec nói | Thực tế | Quyết định | Ai quyết | Bằng chứng |
```

## The gate

At most **two** in a whole run, and a clean run has **none**:

| When | Where |
| ---- | ----- |
| T4 survivors after step 02, or the spec skill's own T4 pool | step 03 |
| `/speckit.analyze` CRITICAL, or blast radius HIGH/CRITICAL | step 05 |

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

## Cost

Print one line after every step. Do not ask, do not stop:

```text
Step 02: 5 agents · ~180k tokens · 4m · running ~640k
```

Take the numbers from each agent's reported `usage`. ⛔ Never estimate a figure that was actually
reported.

## Stop if you are about to

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
| `references/ledger.md` | The ledger's columns, the lookup threshold, and what closes a row |
| `references/self-loop.md` | Step 02 in full, and the five places the tokens are saved |
