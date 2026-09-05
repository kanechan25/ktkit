---
name: feat-req-execute
description: "Use after /ktkit:feat-req-specs has been reviewed and approved. Executes STEP 6→9 only: plan, implement, verify, document. Does NOT re-investigate or re-design — assumes spec is already written and approved."
---

# Feat-Req Execute Workflow (STEP 6→9 only)

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

Whenever this workflow — or any `speckit.*` skill it calls — produces **open questions, assumptions,
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

Drop `speckit` from `--groups` when the user passed `--no-speckit` — that flag *is* the decision to
take the internalised path, so probing for scaffolding the run will not use would block for nothing.
The flag holds **even when speckit is installed and scaffolded**: it selects the path, it does not
merely relax the check.

⛔ **Without that flag, a missing half stops the run.** Never fall back to the internalised path on
your own. Degrading silently ships something other than what was asked for, under the same name.

**Exit 1 → STOP here.** Print what is missing and both ways forward, then wait:

```
⛔ /ktkit:feat-req-execute — stopped before STEP 5.9

  ✗ .specify/ is not in this repository

  Pick one:
    1. Run `specify init` at the repository root   → full speckit (plan → tasks → analyze → implement)
    2. Re-run with --no-speckit                    → internalised path, same artifacts, written here

  Nothing ran. No code touched.
```

The `read` group is what stops the classic failure of this skill: a spec path that is wrong by one
character, discovered only after `/speckit.plan` has run.

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

**Legacy spec → STOP.** A legacy spec has no folder to hold `plan.md` / `tasks.md`, so `/speckit.plan`, `/speckit.tasks` and `/speckit.analyze` have nowhere to write. Report and wait:

```
Spec đang ở layout cũ: <path>
Nhánh speckit (STEP 6 / 6.5 / 7) cần FEATURE_DIR nên không chạy được.
Chọn: (1) viết lại spec theo layout mới qua /ktkit:feat-req-specs · (2) tự chuyển tay rồi chạy lại · (3) abort
```

Do **not** move, rename, or convert the file yourself — legacy specs are left untouched by design. Do **not** quietly skip to STEP 7 either: this workflow promises a real `/speckit.analyze` pass, and silently dropping it delivers something else while reporting success.

**Current layout → export the two variables** and use them for every speckit call below:

```bash
export SPECIFY_FEATURE_DIRECTORY=".claude/claude/specs/<rel-dir>/<base>"
export SPECIFY_FEATURE="$(date +%Y%m%d-%H%M%S)-<slug>"   # slug MANDATORY — bare timestamp is rejected
```

`SPECIFY_FEATURE` exists solely to clear the branch-name gate in `.specify/scripts/bash/*.sh`. It does **not** touch git and does **not** rename any branch — the branch you are on stays exactly as it is. Its value is throwaway; the feature directory is stable because the first variable is always explicit.

---

### STEP 5.95 — RUNBOOK FORK (does this repository have its own execution runbook?)
> Goal: never run plain speckit, silently, in a repository that already has a bespoke runbook

This skill is **generic** SDD. Some repositories have a skill of their own that produces an
**execution runbook** — a file describing the order of work, the tools and the review gates specific
to that repository. Running plain `/speckit.implement` while such a runbook exists produces code that
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
  (2) Tiếp tục speckit thuần → plan.md + tasks.md + /speckit.implement.
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

### STEP 6 — PLAN (call skill `/speckit.plan`)
> Goal: HOW to build it — architecture, stack, data flow

**Two ways to produce the plan. Both write the same files into the same feature directory.** STEP
5.85 already decided which one this run is in — do not re-decide here, and do not fall back silently.

| Mode | When | What runs |
|---|---|---|
| **speckit** | preflight found `.specify/` **and** the speckit skills, and `--no-speckit` was not passed | `/speckit.plan` then `/speckit.tasks`, per the guard below |
| **internalised** | anything else | write `plan.md` and `tasks.md` directly, same contents, same paths |

> ⚠️ **SPECKIT GUARD** *(mode `speckit` only)* — **do the two variables from STEP 5.9 exist?**
> Every skill in this branch is script-backed — `/speckit.plan` runs `setup-plan.sh`,
> `/speckit.tasks` runs `setup-tasks.sh`, `/speckit.analyze` runs `check-prerequisites.sh`. All three
> enforce the same branch-name pattern that ordinary conventions (`feat/…`, `bugfix/…`,
> `<system>/feature/…`) do not match, so **`.specify/` existing is a false green** on its own.
> - Variables not set → go back to STEP 5.9.
> - Set → verify once, then proceed:
>   ```bash
>   bash .specify/scripts/bash/check-prerequisites.sh --json --paths-only
>   ```
>   Non-zero exit → STOP and report. Do NOT fall back to a manual plan while still calling it a
>   speckit run. Switching to mode `internalised` is allowed; saying nothing about it is not.

In mode `internalised`, write `$SPECIFY_FEATURE_DIRECTORY/plan.md` and `.../tasks.md` yourself with
the contents listed below — the same sections, the same headings — then continue to STEP 6.5, whose
cross-artifact check is a comparison you can perform directly. Report the mode at the final summary.

- Read `$SPECIFY_FEATURE_DIRECTORY/spec.md` to understand feature scope, architecture decision, and integration points
- Generate plan following the WHAT-WHY-HOW framework

```
/speckit.plan
```

Writes **`$SPECIFY_FEATURE_DIRECTORY/plan.md`** — beside the spec, inside the feature dir. It contains:
- Chosen architecture (from spec's architecture decision)
- Data models / API endpoints / data flow
- Surgical Change Map (exact symbols, file:line, change, side effects)
- Risk Level (LOW/MEDIUM/HIGH/CRITICAL from GitNexus blast radius)
- File-level changes (which files to create/modify)

Then run `/speckit.tasks` to produce **`$SPECIFY_FEATURE_DIRECTORY/tasks.md`** — STEP 6.5 cannot run without it.

**HARD GATE**: Present plan to user. Do NOT proceed to STEP 7 until confirmed. If Risk Level is HIGH/CRITICAL → require explicit approval.

---

### STEP 6.5 — ANALYZE (call skill `/speckit.analyze`)
> Goal: catch cross-artifact gaps before implementation starts

**Precondition** — all three files must exist in `$SPECIFY_FEATURE_DIRECTORY`: `spec.md`, `plan.md`, `tasks.md`. `/speckit.analyze` runs `check-prerequisites.sh --json --require-tasks --include-tasks` and aborts otherwise; it is a cross-artifact comparison and has nothing to compare without all three. If `tasks.md` is missing, run `/speckit.tasks` first (STEP 6) — do not skip this step.

After plan and tasks are generated, invoke `/speckit.analyze` to validate consistency across spec × plan × tasks:
- Requirements with no tasks → coverage gap
- Tasks with no mapped requirement → scope creep risk
- Acceptance criteria not measurable → testability issue
- Constitution violations → always CRITICAL

Action by severity:
- **CRITICAL** → STOP. Must resolve before STEP 7. Do not proceed without explicit user sign-off.
- **HIGH** → Present to user, require explicit approval to proceed.
- **MEDIUM / LOW** → Proceed, record issues in implementation report.

---

### STEP 7 — IMPLEMENT (call skill `/speckit.implement`)
> Goal: execute plan with TDD discipline and task tracking

**Before calling `/speckit.implement`**, run symbol-level impact check for each planned change:
```
gitnexus_impact({target: "<symbol>", direction: "upstream"})
```
- LOW/MEDIUM → proceed
- HIGH/CRITICAL → STOP, report to user (plan is file-level; impact is symbol-level — different granularity, different risk)

Call `/speckit.implement` to execute the task plan:
- Reads `tasks.md` phase-by-phase (Setup → Tests → Core → Integration → Polish)
- Gates on checklist completion before starting — incomplete checklists require user confirmation
- Enforces TDD order: test tasks execute before their implementation counterparts
- Marks tasks `[X]` as completed in real-time
- Validates each phase before proceeding to next; halts on non-parallel task failure

**FORMAT GATE still applies** — only touch lines that change logic. `/speckit.implement` does not override the FORMAT GATE defined above.

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
Mode: <generic | runbook-detected-but-user-chose-speckit> · <speckit | internalised>
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
