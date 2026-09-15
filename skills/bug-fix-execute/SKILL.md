---
name: bug-fix-execute
description: "Use after /ktkit:bug-fix-specs has been reviewed and approved. Runs the failing test red first (superpowers:test-driven-development), applies the fix from fix.md, and verifies with GitNexus and superpowers:verification-before-completion. Stops outright after a third failed attempt rather than trying a fourth. Does NOT re-investigate — the analysis and the plan are already written."
---

# Bug-Fix Execute Workflow (STEP 5→7 only)

## Purpose

Apply the fix described in the approved fix plan. Skip investigation — `/ktkit:rca` did it once, and `/ktkit:bug-fix-specs` turned it into a plan.

**Prerequisite**: an approved fix plan under `.claude/claude/specs/`. Resolve it in this order, and stop at the first hit:

| # | Path shape | Layout |
|---|---|---|
| 1 | `.claude/claude/specs/<rel-dir>/<base>/fix.md` | **current** |
| 2 | `.claude/claude/specs/<rel-dir>/<base>/spec.md` | written before the BUG lane renamed the artifact |
| 3 | `.claude/claude/specs/<rel-dir>/<name>.spec.md` | **legacy (pre-folder)** |

⛔ **Detection is by `basename`, never by glob.** `basename == "fix.md"` ⇒ row 1; `basename == "spec.md"` ⇒ row 2, and `<base>` is the parent folder either way. Anything else matching `*.spec.md` is legacy. The old instruction here searched `.claude/claude/specs/**/*.spec.md`, which does not match `<base>/spec.md` at all — the layout every run has produced since the folder change. It found nothing and said so as though nothing existed.

Rows 2 and 3 are read, **never renamed and never rewritten**: an old file stays exactly as it is.

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

**ONLY touch lines that are part of the fix logic.** If a line is not changing behavior, do not touch it — even if the formatting looks inconsistent with surrounding code.

If you catch yourself about to make a format-only edit: **stop, undo the mental change, write only the logic diff.**

---

## 🌐 LANGUAGE GATE (Vietnamese for clarifications & assumptions)

Whenever this workflow produces **open questions, assumptions,
verification findings or recommendations**:

- **Write in Vietnamese**: every question, assumption label, rationale, severity description and
  recommendation shown to the user.
- **Keep in English**: file paths, function/symbol/class names, flags, API names, original error
  messages, stack traces, code snippets, test names, and technical terms with no settled translation
  (e.g. "regression", "race condition", "null deref").
- Applies **in reasoning as well as in the final output** shown to the user.

Why: the reviewer reads in Vietnamese, so prose in Vietnamese removes friction while the identifiers
stay exact.

---

## Pipeline

### STEP 4.9 — PREFLIGHT (runs before the first edit)
> Goal: a spec path that is wrong by one character should cost a second, not a half-applied fix

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py" \
  --groups artifacts,read,superpowers \
  --repo "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" \
  --inputs "<the approved fix plan>"
```

**Exit 1 → STOP before STEP 4.95.** Nothing has been edited yet; print what is missing and wait.
This skill needs **no speckit** — a bug is a disagreement with a specification that already exists.
It does need superpowers: STEP 4.95 is `test-driven-development` and STEP 6 is
`verification-before-completion`, and without them this skill is a fix with nothing holding it to
account.

The `artifacts` group creates `<repo-root>/.claude/claude/{prompts,analyze,specs,pipeline,implemented,compacts}`
when the repository does not have them, so STEP 7's report has somewhere to land. That layout is a
rule of this plugin, not a discovery: never probe for an alternative, never ask, and never write
outside `<repo-root>/.claude/`.

---

### STEP 4.95 — RED (the test comes first)
> Goal: a failing test that fails for the stated reason, before a single line of code moves

Invoke `superpowers:test-driven-development`.

1. **Take the test from the analysis.** `/ktkit:rca` Step 3.9 wrote one, with its path and its red
   output. Run it and confirm it is still red.
2. **No test there ⇒ write one** from the reproduction case in the fix plan. It goes where the
   repository already keeps its tests.
3. ⛔ **Red for the right reason.** Read the failure and check it names the assertion the hypothesis
   predicted. Red because of a missing import, a wrong path or a syntax error proves nothing, and a
   fix made green against it is a fix for the wrong problem.
4. Record the path and the red output — STEP 7's report cites both.

⛔ **Nothing in STEP 5 may run until this test is red for the right reason.** A fix written first and
tested afterwards can only ever confirm itself.

---

### STEP 5 — FIX
> Goal: fix root cause as described in the fix plan, and turn exactly one test green

- Read the fix plan to understand exact files and changes required
- Edit only files listed in the spec
- Address the root cause — no symptom patches
- No new files unless spec explicitly requires it
- No refactoring of unrelated code
- **FORMAT GATE**: Do NOT change formatting, semicolons, spacing, or line breaks on lines unrelated to the fix — see FORMAT GATE above
- **Green means that test, and no new red.** The test from STEP 4.95 passes, and nothing that passed before now fails.

#### ⛔ Count the failed attempts. There is no fourth.

A fix that does not make the test green is a **failed attempt**, and attempts are counted out loud.

| Failed attempts | What happens |
| --------------- | ------------ |
| 1 or 2 | The hypothesis was wrong, not the code. Return to a new hypothesis — ⛔ never stack a second fix on the first. |
| **3** | ⛔ **STOP. Do not attempt a fourth.** |

At three, this is not a failed hypothesis — it is the wrong architecture, and one more patch buys
another symptom somewhere else. Record it and escalate:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/deviation.py" add --contract \
    --base <run-dir> --repo <root> --source "fix plan §root cause" \
    --said "<what the plan said the cause was>" \
    --did "<three fixes, and what each one revealed>" \
    --why "<the architectural signal: coupling surfacing elsewhere, or every fix needing a large refactor>" \
    --evidence "<path:line>"
```

Then stop and put the architectural question to the user. This is Phase 4 step 5 of
`superpowers:systematic-debugging`, placed where the code is actually being changed rather than
where it was diagnosed.

---

### STEP 6 — VERIFY (`GitNexus` + `verification-before-completion`)
> Goal: confirm fix works and didn't break anything else

Invoke `superpowers:verification-before-completion` before making any completion claim.

```
gitnexus_detect_changes()   → confirm only in-scope files changed
```

- Re-run the reproduction case from the spec → must pass
- If the fix changes observable behavior → update spec file to mark as implemented
- **Do NOT run the test suite automatically** — and do not guess its command. Read it from the
  repository (`package.json` scripts / `Makefile` / `pyproject.toml` / the equivalent) or ask, then
  remind the user to run it after review.

---

### STEP 6.2 — DEFENCE IN DEPTH (risk-gated — often SKIPPED)
> Goal: when bad data crossed several layers, stop it at each one — not only where it surfaced

**Runs when `risk >= MEDIUM`**, on the same combined scale STEP 4.7 of `/ktkit:bug-fix-specs` uses.
Below that ⇒ ⛔ **skip it and say so** at the report: `"risk = LOW, defence in depth skipped"`. A
one-line bug does not earn four layers of guard, and guards nobody asked for are code somebody has
to maintain.

When it runs, the layers come from the analysis: `/ktkit:rca` writes a *Defence in depth* section
when the root cause is bad data crossing more than one layer, and that section lists them. No such
section ⇒ this step has nothing to act on ⇒ skip and say so.

For each layer the bad value passed through, add the check that layer should have had. ⛔ Each one is
a separate, named change in the report — not folded into the fix, where a reviewer reading the diff
cannot tell the root-cause fix from the guards around it.

---

### STEP 6.5 — RECORD WHAT DIVERGED (at the moment, not at the end)

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

### STEP 7 — DOCUMENT (optional)
> Goal: build institutional memory so this bug is never reinvestigated

```
mcp__memory__create_entities + mcp__memory__add_observations
```

**Tool absent**: this plugin does not ship a memory server, because memory holds durable state and a
second copy would split the user's own. Skip this step and say so — the `implt.md` report below is
written either way, and it is the durable record that matters here.

Store:
- Bug pattern: symptom + root cause (one sentence each)
- Fix summary: what was changed and why
- Files affected
- Tags: `bugfix`, `<module name>`

---

## Output Format

> **Language**: the whole report is written in **Vietnamese**. Code snippets, file paths, symbol
> names and technical names (kebab-case, camelCase and so on) stay exactly as they are — only the
> descriptive prose is Vietnamese.

Write the report to `.claude/claude/implemented/<rel-dir>/bug-<name>.implt.md` — MIRROR the fix plan's sub-path: `<rel-dir>` = `dirname(<fix-plan>)` relative to `.claude/claude/specs` (may be empty), and the filename is `bug-<base>.implt.md`, where `<base>` is that directory's name (legacy layout: the basename with `.spec.md` replaced by `.implt.md`). `mkdir -p` the dir if missing. Do NOT print the report content to the terminal.

After writing the file, tell the user:
> "Đã xong. Check `.claude/claude/implemented/<rel-dir>/bug-<name>.implt.md` để biết những gì đã implement."

The file must contain:

```markdown
# Bug Fix: <title>

Fix plan: `.claude/claude/specs/<rel-dir>/<base>/fix.md`
Failing test: `<path:line>` — red before the fix, green after
Failed attempts: <0-3; at 3 this report exists because the run escalated, not because it finished>
Defence in depth: <the layers guarded, or "risk = LOW, skipped">
Branch: <current branch>
Date: <today>

**Root Cause**: <one sentence>
**AgentRx Class**: <category>
**Files Changed**: <list>
**Blast Radius**: <LOW/MEDIUM/HIGH>
**Memory Saved**: <yes/no>

## Sai khác so với fix plan
<the output of `deviation.py render` — never hand-written, so it cannot disagree with the block in
`fix.md`. `KHÔNG CÓ` when nothing diverged, with when that was declared.>

⚠️ This lane has no plan phase, so a divergence only ever concerns the fix plan. That is expected and
is stated rather than left to be noticed.

## What Was Changed
<summary of changes>
```
