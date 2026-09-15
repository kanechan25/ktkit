---
name: feat-req-execute
description: "Use after /ktkit:feat-req-specs has been reviewed and approved. Executes STEP 6→9 only: plan, implement, verify, document. Does NOT re-investigate or re-design — assumes spec is already written and approved."
---

# Feat-Req Execute Workflow (STEP 6→9 only)


> ⛔ **Not an entry point.** `/ktkit:chain` runs this as phase 05 of the NR and CR lane, and
> the chain is what carries the ledger between phases — the questions this workflow
> would otherwise re-derive were already settled upstream, and they are settled in a
> file rather than in a conversation this skill cannot see.
>
> Running it directly still works and still produces the same artifacts at the same
> paths. What it does not get is the ledger, the budget gate at each boundary, the
> deviation record, or step 07's convergence check — so a direct run answers
> questions twice and closes no loop.
>
> ```
> /ktkit:chain <file> --nr --execute
> ```
>
> This banner is the whole of the deprecation for now. The skill is removed as a
> user-facing entry point in a later release; nothing is being taken away today.

## Purpose

Continue the SDD pipeline from the approved spec. Skip investigation and design (already done by `/ktkit:feat-req-specs`).

**Prerequisite**: A spec file exists under `.claude/claude/specs/` — flat (`feat-*.spec.md`) or nested in a mirrored sub-folder (`.claude/claude/specs/<rel-dir>/<name>.spec.md`) — and has been reviewed/approved by the user. Search recursively (`.claude/claude/specs/**/*.spec.md`); do NOT assume a flat folder or a `feat-` prefix.

## ⚠️ FORMAT GATE (Soft Gate — applies to all steps below)

Before writing any code change, check:

> **Am I changing logic — or just reformatting?**

**NEVER do the following unless the spec explicitly requires it:**
- Remove or add semicolons
- Reformat `if / else if / else` blocks (e.g., break conditions onto new lines, inline braces)
- Add or remove blank lines between statements
- Reorder import statements
- Change quote style (`'` ↔ `"`)
- Adjust spacing inside function arguments or object literals
- Apply Prettier, ESLint auto-fix, or any cosmetic cleanup

**ONLY touch lines that are part of the fix or feature logic.** If a line is not changing behavior, do not touch it — even if the formatting looks inconsistent with surrounding code.

If you catch yourself about to make a format-only edit: **stop, undo the mental change, write only the logic diff.**

---

## 🌐 LANGUAGE GATE (Vietnamese for clarifications & assumptions)

Whenever this workflow — or any `speckit-*` skill it calls — produces **open questions, assumptions,
cross-artifact inconsistencies, severity findings or recommendations**:

- **Write in Vietnamese**: every question, assumption label, rationale, severity description
  (CRITICAL/HIGH/MEDIUM/LOW) and recommendation shown to the user.
- **Keep in English**: file paths, function/symbol/class names, flags, API names, original error
  messages, code snippets, test names, and technical terms with no settled translation (e.g. "race
  condition", "TDD", "idempotent", "side effect").
- Applies **in reasoning as well as in the final output** shown to the user.
- Plan and task file content follows the template it came from — never translate headers or keywords.

Why: the reviewer reads in Vietnamese, so prose in Vietnamese removes friction while the identifiers
stay exact.

---

## Pipeline

### STEP 5.85 — PREFLIGHT (runs before anything is spent)
> Goal: fail in one second rather than at STEP 6, after the plan has already been paid for

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py" \
  --groups artifacts,read,speckit,mcp \
  --repo "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" \
  --inputs "<the approved spec file>"
```

There is no flag that drops `speckit` from `--groups`. spec-kit is a prerequisite of this plugin,
not a mode: `hooks/prereq-gate.py` refuses to start this skill without it, and this group is the
in-run proof of the same fact.

⛔ **A missing half stops the run.** Never write the plan some other way on your own. Degrading
silently ships something other than what was asked for, under the same name.

**Exit 1 → STOP here.** Print what is missing and how to fix it, then wait:

```
⛔ /ktkit:feat-req-execute — stopped before STEP 5.9

  ✗ .specify/ is not in this repository

  spec-kit is a prerequisite of ktkit, not a mode:

    specify init --here --force --non-interactive --integration claude
    rm -rf .claude/skills/speckit-*

  Nothing ran. No code touched.
```

The `read` group is what stops the classic failure of this skill: a spec path that is wrong by one
character, discovered only after `/speckit-plan` has run.

The `artifacts` group creates `<repo-root>/.claude/claude/{prompts,analyze,specs,pipeline,implemented,compacts}`
when the repository does not have them. That layout is a rule of this plugin, not a discovery: never
probe for an alternative, never ask, and never write outside `<repo-root>/.claude/`.

---

### STEP 5.9 — RESOLVE THE FEATURE DIR (do this before anything else)
> Goal: every speckit skill in this workflow reads and writes one directory — resolve it once, here

Locate the approved spec, then classify its layout. **This decides whether the rest of the pipeline can run at all.**

| Spec path shape | Layout | `FEATURE_DIR` |
|---|---|---|
| `.claude/claude/specs/<rel-dir>/<base>/spec.md` | **current** | `.claude/claude/specs/<rel-dir>/<base>` |
| `.claude/claude/specs/<rel-dir>/<name>.spec.md` | **legacy (pre-folder)** | none — see below |

Detection is exact: `basename == "spec.md"` ⇒ current layout, `<base>` is the parent folder's name. Anything else matching `*.spec.md` is legacy. (Legacy files always carry a `feat-` / `bug-` prefix, so they can never be a bare `spec.md`.)

**Legacy spec → STOP.** A legacy spec has no folder to hold `plan.md` / `tasks.md`, so `/speckit-plan`, `/speckit-tasks` and `/speckit-analyze` have nowhere to write. Report and wait:

```
Spec đang ở layout cũ: <path>
Nhánh speckit (STEP 6 / 6.5 / 7) cần FEATURE_DIR nên không chạy được.
Chọn: (1) viết lại spec theo layout mới qua /ktkit:feat-req-specs · (2) tự chuyển tay rồi chạy lại · (3) abort
```

Do **not** move, rename, or convert the file yourself — legacy specs are left untouched by design. Do **not** quietly skip to STEP 7 either: this workflow promises a real `/speckit-analyze` pass, and silently dropping it delivers something else while reporting success.

**Current layout → pin the feature directory.** ⛔ This is the step, not a detail of the next one:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/speckit_pin.py" \
  --dir ".claude/claude/specs/<rel-dir>/<base>" \
  --repo "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
```

Read the reported `<old> -> <new>` out loud in the summary. `<old>` naming a different feature is
the normal case, not an anomaly: `.specify/feature.json` is one mutable pointer for the whole
repository, written by whichever run touched it last, and `/ktkit:feat-req-specs` may have been a
different session, a different feature, or a different toolkit.

⛔ **`export` is not an alternative here.** Shell state does not cross a tool-call boundary, and
every speckit script below runs in a shell the *skill* opens, later, clean. `SPECIFY_FEATURE_DIRECTORY`
is first in spec-kit's resolution order and so reads like the fix, but it is unset by the time the
script looks — and resolution falls through to the pin. An unpinned run does not fail loudly: it
resolves the stale pointer, writes into **another feature's directory**, and reports success.

For a speckit script you invoke yourself, put the variables **inline on that command line**:

```bash
SPECIFY_FEATURE_DIRECTORY=".claude/claude/specs/<rel-dir>/<base>" \
SPECIFY_FEATURE="$(date +%Y%m%d-%H%M%S)-<slug>" \
  bash .specify/scripts/bash/check-prerequisites.sh --json --paths-only
```

`SPECIFY_FEATURE` exists solely to clear the branch-name gate. It does **not** touch git and does **not** rename any branch — the branch you are on stays exactly as it is. Its value is throwaway; the feature directory is stable because it is pinned on disk. `<slug>` is mandatory — a bare `YYYYMMDD-HHMMSS` is rejected.

> **`$SPECIFY_FEATURE_DIRECTORY` below is a label for the resolved path, not a live variable.**
> The steps that follow write it that way for readability, but nothing exports it and no shell
> state reaches them. Substitute the actual path — `.claude/claude/specs/<rel-dir>/<base>` — every
> time you read, write or `cd` anywhere. A command that leaves the `$` in it resolves to an empty
> prefix, which turns `$SPECIFY_FEATURE_DIRECTORY/spec.md` into `/spec.md` at the filesystem root.

---

### STEP 5.95 — RUNBOOK FORK (does this repository have its own execution runbook?)
> Goal: never run plain speckit, silently, in a repository that already has a bespoke runbook

This skill is **generic** SDD. Some repositories have a skill of their own that produces an
**execution runbook** — a file describing the order of work, the tools and the review gates specific
to that repository. Running plain `/speckit-implement` while such a runbook exists produces code that
does not follow the repository's conventions.

**Detect with one command, and do NOT parse the contents**:

```bash
cat "$SPECIFY_FEATURE_DIRECTORY/runbook.ref" 2>/dev/null   # one runbook path per line, repo-root-relative
```

- **No such file** → `MODE=generic`. Continue to STEP 6 as normal. This is the **default** for every
  repository without a provider.
- **File present** → STOP and ask the user:

```
Feature dir này đã có execution runbook: <path>
/ktkit:feat-req-execute là SDD generic (speckit) — KHÔNG hiểu convention riêng của runbook đó.
Chọn:
  (1) Thi hành theo runbook  → thoát skill này, mở <path> và làm theo.
                               Runbook tự mang coverage matrix + gate + verify + finalize của nó.
  (2) Tiếp tục speckit thuần → plan.md + tasks.md + /speckit-implement.
                               Code có thể KHÔNG theo convention repo.
  (3) Abort
```

**Hard boundary — this skill does NOT**:
- ❌ read or parse the runbook's contents
- ❌ run any command taken from the runbook
- ❌ call the skill that produced the runbook

It only detects the conflict and hands the decision back to the user. Everything specific to a
repository stays on the runbook's side of that line and never leaks in here.

**No backfill**: a feature directory created before the `runbook.ref` convention existed has no such
file and is therefore always `MODE=generic`. That is intended — do not scan for one, do not warn, and
do not edit older directories.

---

### STEP 6 — PLAN (call skill `/speckit-plan`)
> Goal: HOW to build it — architecture, stack, data flow

**`/speckit-plan` then `/speckit-tasks` produce it**, under the guard below. STEP 0a proved speckit
is present -- it is a prerequisite of this plugin -- so there is no second path to choose between.

> ⚠️ **SPECKIT GUARD** — **is the pin from STEP 5.9 still on this feature?**
> Every skill in this branch is script-backed — `/speckit-plan` runs `setup-plan.sh`,
> `/speckit-tasks` runs `setup-tasks.sh`, `/speckit-analyze` runs `check-prerequisites.sh` — and
> they do not behave the same, so verify rather than assume:
>
> | Script | Feature directory | Branch-name gate |
> |---|---|---|
> | `setup-plan.sh`, `setup-tasks.sh` | the pin | **skipped** when the pin matches |
> | `check-prerequisites.sh` | the pin | enforced always — needs inline `SPECIFY_FEATURE` |
>
> So **`.specify/` existing is a false green**, and so is "STEP 5.9 ran": another session, or a
> `/speckit-specify` call in between, can have moved the pin since. Verify — it writes nothing:
> ```bash
> python3 "${CLAUDE_PLUGIN_ROOT}/scripts/speckit_pin.py" --verify \
>   --dir ".claude/claude/specs/<rel-dir>/<base>" \
>   --repo "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
> ```
> - Exit 1 (pin points elsewhere) → repin (drop `--verify`) before any speckit call. Calling
>   `/speckit-plan` on a wrong pin does not fail: it writes into that other feature's directory.
> - Exit 0 → proceed.
>
> ⛔ **`setup-plan.sh` copies the plan template over `plan.md` unconditionally** — no prompt, no
> backup, whatever was there. When `plan.md` already exists and is not a bare template (a plan
> written by hand, or by a previous run of this workflow), copy it aside first and say where:
> ```bash
> cp "<feature-dir>/plan.md" "<feature-dir>/plan.pre-speckit.md"
> ```
> Then decide deliberately: let speckit regenerate and merge back, or skip `/speckit-plan` for this
> run and write the plan yourself. Either is fine; losing the file is not.
>
> If a check still fails, do NOT write the plan by hand while still calling it a speckit run. Writing
> it by hand is allowed; saying nothing about it is not.

⛔ That hand-written path is an exception for one run whose `plan.md` must not be overwritten -- not
a mode, and never a way past a missing speckit. When you take it, write
`$SPECIFY_FEATURE_DIRECTORY/plan.md` and `.../tasks.md` yourself with the contents listed below --
the same sections, the same headings -- then continue to STEP 6.5, whose cross-artifact check is a
comparison you can perform directly, and say so at the final summary.

- Read `$SPECIFY_FEATURE_DIRECTORY/spec.md` to understand feature scope, architecture decision, and integration points
- Generate plan following the WHAT-WHY-HOW framework

```
/speckit-plan
```

Writes **`$SPECIFY_FEATURE_DIRECTORY/plan.md`** — beside the spec, inside the feature dir. It contains:
- Chosen architecture (from spec's architecture decision)
- Data models / API endpoints / data flow
- Surgical Change Map (exact symbols, file:line, change, side effects)
- Risk Level (LOW/MEDIUM/HIGH/CRITICAL from GitNexus blast radius)
- File-level changes (which files to create/modify)

Then run `/speckit-tasks` to produce **`$SPECIFY_FEATURE_DIRECTORY/tasks.md`** — STEP 6.5 cannot run without it.

**HARD GATE**: Present plan to user. Do NOT proceed to STEP 7 until confirmed. If Risk Level is HIGH/CRITICAL → require explicit approval.

---

### STEP 6.5 — ANALYZE (call skill `/speckit-analyze`)
> Goal: catch cross-artifact gaps before implementation starts

**Precondition** — all three files must exist in `$SPECIFY_FEATURE_DIRECTORY`: `spec.md`, `plan.md`, `tasks.md`. `/speckit-analyze` runs `check-prerequisites.sh --json --require-tasks --include-tasks` and aborts otherwise; it is a cross-artifact comparison and has nothing to compare without all three. If `tasks.md` is missing, run `/speckit-tasks` first (STEP 6) — do not skip this step.

After plan and tasks are generated, invoke `/speckit-analyze` to validate consistency across spec × plan × tasks:
- Requirements with no tasks → coverage gap
- Tasks with no mapped requirement → scope creep risk
- Acceptance criteria not measurable → testability issue
- Constitution violations → always CRITICAL

Action by severity:
- **CRITICAL** → STOP. Must resolve before STEP 7. Do not proceed without explicit user sign-off.
- **HIGH** → Present to user, require explicit approval to proceed.
- **MEDIUM / LOW** → Proceed, record issues in implementation report.

---

### STEP 7 — IMPLEMENT (call skill `/speckit-implement`)
> Goal: execute plan with TDD discipline and task tracking

**Before calling `/speckit-implement`**, run symbol-level impact check for each planned change:
```
gitnexus_impact({target: "<symbol>", direction: "upstream"})
```
- LOW/MEDIUM → proceed
- HIGH/CRITICAL → STOP, report to user (plan is file-level; impact is symbol-level — different granularity, different risk)

Call `/speckit-implement` to execute the task plan:
- Reads `tasks.md` phase-by-phase (Setup → Tests → Core → Integration → Polish)
- Gates on checklist completion before starting — incomplete checklists require user confirmation
- Enforces TDD order: test tasks execute before their implementation counterparts
- Marks tasks `[X]` as completed in real-time
- Validates each phase before proceeding to next; halts on non-parallel task failure

**FORMAT GATE still applies** — only touch lines that change logic. `/speckit-implement` does not override the FORMAT GATE defined above.

---

### STEP 8 — VERIFY (`GitNexus` + `verification-before-completion`)
> Goal: confirm feature works and didn't break existing flows

Invoke `superpowers:verification-before-completion` before making any completion claim.

**8a. Scope Check**:
```
gitnexus_detect_changes()   → confirm only in-scope files changed
```

**8b. Acceptance Criteria Checklist**:
Go through EACH acceptance criterion from the spec:
- [ ] Criterion 1 → evidence: [file:line or behavior confirmation]
- [ ] Criterion 2 → evidence: [...]
If any criterion is NOT satisfied → state clearly, do NOT report done.

**8c. Scenario Regression**:
For each What-If Scenario from spec:
- Handled → evidence
- Not handled → record as known limitation

**8d. Relationship Regression**:
For each related feature listed in the spec's Relationship Map:
- Feature X still works normally? → evidence
- Shared state mutated? → verify no side effects

**The test command belongs to the REPOSITORY — this skill does NOT guess it**:
- Ask the user for the repository's test/verify command, or READ it from `package.json` scripts /
  `Makefile` / `pyproject.toml` / the equivalent. Read it; never infer it.
- Record the command actually used in the `implt.md` report.
- **Do not run it** — tell the user to.

⛔ Never hardcode `yarn test` / `npm test` / `pytest`. Every repository differs, and a wrong guess
leaves the user believing something was verified when it was not.

---

### STEP 8.5 — RECORD WHAT DIVERGED (at the moment, not at the end)

⛔ **A specification that disagrees with the code is worse than no specification.** It reads as
authoritative and is quietly wrong: somebody opens it months later, believes it, and builds on a
shape that was never shipped.

So the moment you build something the spec does not describe — a different status code, an extra
file, a step in another order, a criterion you could not meet — record it **then**:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/deviation.py" add \
    --base <run-dir> --repo <root> --source "spec §4.2" \
    --said "<quote the spec, do not paraphrase>" --did "<what you built>" \
    --why "<why -- nobody can reconstruct this later>" \
    --evidence <path>:<line> [--contract]
```

`<run-dir>` is given to you by `/ktkit:chain`. Called directly without one, use the feature
directory.

| Rule | Why |
| ---- | --- |
| ⭐ **Record at the moment, not at the end** | A diff shows *that* the code differs; it never shows *why* you chose that. By the end of the phase the reason has left your context. |
| **`--said` quotes the spec** | A paraphrase makes the divergence disappear — "the spec said roughly that" agrees with anything. |
| **`--evidence` is a real `path:line`** | "I changed X" that cannot be opened is not a record. The lint opens it. |
| ⛔ **`--contract` when it changes a promise** | An acceptance criterion, an API shape, a dropped requirement. Somebody is integrating against those, so it is a gate rather than a note. ⛔ "It could not be done" is not "it did not need doing". |

⛔ **Do not edit the spec here.** Editing it mid-phase stops it being a stable reference during the
phase that reads it, and an aborted run would leave a spec describing code that was rolled back.
`/ktkit:chain` step 06 writes it, at a boundary; a direct run writes it at the end of this skill.

Nothing diverged? That is a statement, not a silence:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/deviation.py" none --base <run-dir> --repo <root>
```

Then, before the report is written:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/deviation.py" lint --base <run-dir> --repo <root>
```

Exit 1 ⇒ ⛔ **stop**: a divergence anchored to a line that is not there reads as verified and is not.
`NOT-ANSWERED` ⇒ ⛔ **stop**: nobody answered the question. `render` supplies the table for the
report — ⛔ never hand-write it, because a hand-written copy can disagree with the one in the spec.

Full rules: `references/syncback.md`.

---

### STEP 8.7 — CONVERGE (call skill `/speckit-converge`)
> Goal: the one check that reads the delivered code and asks whether it satisfies the spec

Every step before this compares one document with another — plan against spec, tasks against plan,
deviations against spec. A set of documents can agree perfectly with each other while the code does
something else. `/speckit-converge` is the only step that opens the code and asks the other question.

```
/speckit-converge
```

**Precondition**: `/speckit-implement` has run on the current `tasks.md` (STEP 7), and STEP 8.5 has
already written its deviation block. 8.5 records what the author still remembers; 8.7 reads the
finished code cold. Running them the other way round would converge against a spec about to change.

It is **append-only by its own contract** — its only write is a new `## Phase N: Convergence` section
in `tasks.md`, and it leaves the file byte-for-byte unchanged when nothing is missing. ⛔ Never
renumber, reorder or delete what it appended, and never rewrite `tasks.md` wholesale afterwards.

#### ⛔ Two rounds, and the third does not exist

```
converge → appended tasks → STEP 7 implement → converge     round 1
         → appended tasks → STEP 7 implement → converge     round 2
         → anything still missing                           ⛔ STOP
```

Round 3 is not a third attempt at the same problem — it is evidence of a different one. Work still
outstanding after two rounds of *find the gap, build the gap, look again* is not missing code; the
spec is wrong or ambiguous enough that each pass reads it differently. Appending a third round pays
to chase a target that moves every time it is reached.

At the cap: ⛔ **append nothing**, record in the report which gaps survived both rounds and what each
round appended, and take the spec section you believe is wrong to the user. Report the round count
either way — a run that converged clean on round 1 and one that hit the cap silently look identical
otherwise.

---

### STEP 9 — DOCUMENT (optional)
> Goal: institutional memory so next feature can build on this one

```
mcp__memory__create_entities + mcp__memory__add_observations
```

**Tool absent**: this plugin does not ship a memory server, because memory holds durable state and a
second copy would split the user's own. Skip this step and say so — the `implt.md` report is written
either way, and it is the durable record that matters here.

Store:
- Feature summary: what was built and why
- Architecture decision: which option was chosen and why (include rejected alternatives)
- Patterns introduced: new patterns other features can reuse
- Relationships: which existing features this interacts with
- Files affected
- Tags: `feature`, `<module name>`

---

## Output Format

> **Language**: the whole report and plan are written in **Vietnamese**. Code snippets, file paths,
> symbol names and technical names (kebab-case, camelCase and so on) stay exactly as they are — only
> the descriptive prose is Vietnamese.

Write the report to `.claude/claude/implemented/<rel-dir>/<base>.implt.md` — MIRROR the **feature dir**'s sub-path:

- `<base>` = `basename($SPECIFY_FEATURE_DIRECTORY)` — the feature's **FOLDER** name.
- `<rel-dir>` = `dirname($SPECIFY_FEATURE_DIRECTORY)` relative to `.claude/claude/specs` (may be empty).

⛔ Never derive it from `basename(<spec-file>)`: in the current layout that file is always named
`spec.md`, so every feature would produce `spec.implt.md` and overwrite the last one.

`mkdir -p` the dir if missing. Do NOT print the report content to the terminal.

After writing the file, tell the user:
> "Đã xong. Check `.claude/claude/implemented/<rel-dir>/<base>.implt.md` để biết những gì đã implement."

The file must contain:

```markdown
# Feature: <title>

Spec:  `$SPECIFY_FEATURE_DIRECTORY/spec.md`
Plan:  `$SPECIFY_FEATURE_DIRECTORY/plan.md`
Tasks: `$SPECIFY_FEATURE_DIRECTORY/tasks.md`
Runbook: <path, if STEP 5.95 found one, else `—`>
Mode: <generic | runbook-detected-but-user-chose-speckit> · <speckit | plan written by hand, and why>
Test command: <the command the user gave at STEP 8, else `—`>
Branch: <current branch>
Date: <today>

**Acceptance Criteria**: <all met / partial — list unmet>
**Blast Radius**: <LOW/MEDIUM/HIGH>
**Relationship Impact**: <none / list affected features>
**Memory Saved**: <yes/no>

## What Was Built
<summary of what was implemented>

## Files Changed
<list>

## Sai khác so với spec
<the output of `deviation.py render` — never hand-written. It is rendered from the same
`deviations.jsonl` that produced the block in spec.md, so the two cannot disagree. If nothing
diverged this section says `KHÔNG CÓ` and when that was declared.>
```

---

## Appendix — how a repository registers its own runbook

This skill depends on **no** provider, and there is no list of known ones to keep in sync. A
repository opts in by having whatever skill produces its runbook write a `runbook.ref` file into the
feature directory:

```
.claude/claude/specs/<rel-dir>/<base>/runbook.ref
```

One repo-root-relative path per line, pointing at the runbook itself — typically somewhere under
`.claude/claude/pipeline/`. That file is the entire contract. STEP 5.95 reads it and asks; nothing
here needs to change when a new repository joins.

A feature directory created before this convention existed has no `runbook.ref` and is therefore
always `MODE=generic`. Older specs, reports and docs stay exactly as they are — no backfill, no
scanning, no warning.
