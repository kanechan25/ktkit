---
name: bug-fix-execute
description: "Use after /ktkit:bug-fix-specs has been reviewed and approved. Executes STEP 5→7 only: applies the fix from the spec, verifies with GitNexus, and saves to memory. Does NOT re-investigate — assumes spec is already written and approved."
---

# Bug-Fix Execute Workflow (STEP 5→7 only)

## Purpose

Apply the fix described in the approved spec. Skip investigation (already done by `/ktkit:bug-fix-specs`).

**Prerequisite**: A spec file exists under `.claude/claude/specs/` — flat (`bug-*.spec.md`) or nested in a mirrored sub-folder (`.claude/claude/specs/<rel-dir>/<name>.spec.md`) — and has been reviewed/approved by the user. Search recursively (`.claude/claude/specs/**/*.spec.md`); do NOT assume a flat folder or a `bug-` prefix.

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

Whenever this workflow — or any `speckit.*` skill it calls — produces **open questions, assumptions,
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
  --groups artifacts,read \
  --repo "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" \
  --inputs "<the approved spec file>"
```

**Exit 1 → STOP before STEP 5.** Nothing has been edited yet; print what is missing and wait. This
skill needs no speckit and no MCP server — it reads an approved spec and applies it.

The `artifacts` group creates `<repo-root>/.claude/claude/{prompts,analyze,specs,pipeline,implemented,compacts}`
when the repository does not have them, so STEP 7's report has somewhere to land. That layout is a
rule of this plugin, not a discovery: never probe for an alternative, never ask, and never write
outside `<repo-root>/.claude/`.

---

### STEP 5 — FIX
> Goal: fix root cause as described in the spec

- Read the spec file to understand exact files and changes required
- Edit only files listed in the spec
- Address the root cause — no symptom patches
- No new files unless spec explicitly requires it
- No refactoring of unrelated code
- **FORMAT GATE**: Do NOT change formatting, semicolons, spacing, or line breaks on lines unrelated to the fix — see FORMAT GATE above

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

Write the report to `.claude/claude/implemented/<rel-dir>/bug-<name>.implt.md` — MIRROR the spec's sub-path: `<rel-dir>` = `dirname(<spec-file>)` relative to `.claude/claude/specs` (may be empty), filename = the spec basename with `.spec.md` replaced by `.implt.md`. `mkdir -p` the dir if missing. Do NOT print the report content to the terminal.

After writing the file, tell the user:
> "Đã xong. Check `.claude/claude/implemented/<rel-dir>/bug-<name>.implt.md` để biết những gì đã implement."

The file must contain:

```markdown
# Bug Fix: <title>

Spec: `.claude/claude/specs/<rel-dir>/bug-<name>.spec.md`
Branch: <current branch>
Date: <today>

**Root Cause**: <one sentence>
**AgentRx Class**: <category>
**Files Changed**: <list>
**Blast Radius**: <LOW/MEDIUM/HIGH>
**Memory Saved**: <yes/no>

## What Was Changed
<summary of changes>
```
