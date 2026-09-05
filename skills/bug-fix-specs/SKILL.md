---
name: bug-fix-specs
description: "Use when the user submits a bug report and wants to review specs BEFORE fixing. Runs STEP 0→4 (memory check, explore, reproduce, blast radius, root cause), then writes the spec under .claude/claude/specs/<rel-dir>/<base>/ — through /speckit.specify when the repository has speckit scaffolding, through this skill's own internalised equivalent when it does not or when called with --no-speckit. STOPS and waits for user approval before any code changes. Hand off to /ktkit:bug-fix-execute."
---

# Bug-Fix Specs Workflow

## Purpose

Same forensic pipeline as `bug-fix`, but **stops at STEP 4** and writes a spec for user review. No code is changed until the user explicitly approves and runs `/bug-fix`.

## ⚠️ FORMAT GATE (Soft Gate — carried into `/ktkit:bug-fix-execute`)

This skill writes specs only — no code changes here. But the spec you write will drive `/ktkit:bug-fix-execute`, so **when writing proposed fix snippets in the spec**:

- Show **only the logic diff** — not reformatted surrounding code
- Do NOT include semicolon removals, spacing changes, or brace-style changes in code snippets
- If a code snippet shows surrounding context lines, keep them byte-for-byte identical to the source

The executor (`/ktkit:bug-fix-execute`) has its own FORMAT GATE and will refuse format-only edits.

---

## 🌐 LANGUAGE GATE (Vietnamese for clarifications & assumptions)

Whenever this workflow — or any `speckit.*` skill it calls — produces **open questions,
assumptions, ambiguity findings or recommendations**:

- **Write in Vietnamese**: every question, assumption label, rationale, severity description and
  recommendation shown to the user.
- **Keep in English**: file paths, function/symbol/class names, flags, API names, original error
  messages, stack traces, code snippets, and technical terms with no settled translation
  (e.g. "race condition", "blast radius", "off-by-one", "null deref").
- Applies **in reasoning as well as in the final output** shown to the user.
- Spec file content (`spec.md`) follows the template it came from — never translate headers or
  keywords.

Why: the reviewer reads in Vietnamese, so prose in Vietnamese removes friction while the identifiers
stay exact.

---

## Pipeline (Sequential — Do Not Skip Steps)

### STEP 0a — PREFLIGHT (runs before anything is spent)
> Goal: fail in one second rather than at STEP 4.5, after four steps have been paid for

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py" \
  --groups artifacts,speckit,mcp --repo "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
```

Drop `speckit` from `--groups` when the user passed `--no-speckit` — that flag *is* the decision to
take the internalised path, so probing for scaffolding the run will not use would block for nothing.

**Exit 1 → STOP before STEP 0b.** Print what is missing and both ways forward, then wait:

```
⛔ /ktkit:bug-fix-specs — stopped before STEP 0b

  ✗ .specify/ is not in this repository
  ✗ ~/.claude/skills/speckit.specify is not installed

  Pick one:
    1. Run `specify init` at the repository root   → full speckit
    2. Re-run with --no-speckit                    → internalised path, the spec still comes out whole

  Nothing ran. No tokens spent on any step.
```

**Exit 0 → continue**, and say which mode the run is in. Optional capabilities that are absent are
named here too, with the exact consequence:

```
▶ /ktkit:bug-fix-specs — degraded run
  ✗ mcp__memory absent → STEP 0b skipped, no recall from earlier sessions
  ✓ artifact root · ✓ speckit scaffolding · ✓ sequential-thinking (shipped by ktkit)
```

The `artifacts` group creates `<repo-root>/.claude/claude/{prompts,analyze,specs,pipeline,implemented,compacts}`
when the repository does not have them. That layout is a rule of this plugin, not a discovery: never
probe for an alternative, never ask, and never write outside `<repo-root>/.claude/`.

---

### STEP 0b — MEMORY CHECK (optional)
> Goal: avoid reinvestigating bugs already solved

```
mcp__memory__search_nodes({query: "<symptom keywords>"})
```

- **Found**: report the stored pattern + fix, ask user if it applies
- **Not found**: proceed to STEP 1
- **Tool absent**: this plugin does not ship a memory server, because memory holds durable state and
  a second copy would split the user's own. Skip this step, say so once, and never present the empty
  result as "nothing was found before".

---

### STEP 1 — UNDERSTAND (`GitNexus` + `Context7`)
> Goal: locate the bug in the codebase with evidence

Run in parallel:
```
gitnexus_query({query: "<symptom description>"})
gitnexus_context({name: "<suspected function>"})
git log -10 --oneline -- <suspected file>
```

---

### STEP 2 — REPRODUCE
> Goal: identify the exact condition that triggers the bug

- Identify the exact log line / state / network call that confirms wrong behavior
- Write a failing test case if possible

**Hard stop**: do not proceed without a reproduction case.

---

### STEP 3 — BLAST RADIUS (`GitNexus`)
> Goal: know what will break before touching anything

```
gitnexus_impact({target: "<symbol to modify>", direction: "upstream"})
```

| Risk | Action |
|---|---|
| LOW / MEDIUM | Proceed |
| **HIGH / CRITICAL** | **STOP — report to user, do not proceed without explicit approval** |

---

### STEP 4 — ROOT CAUSE (`sequential-thinking`)
> Goal: structured diagnosis, not guessing

Use `mcp__plugin_ktkit_sequential-thinking__sequentialthinking` to reason through 5 Whys:

1. **Symptom** — What is the observed wrong behavior?
2. **Trigger** — What condition causes it to happen?
3. **Gap** — What does the current logic fail to handle?
4. **AgentRx class** — Logic error / Misinterpretation / System failure / Plan misalignment?
5. **Root cause** — One clear sentence stating the actual cause

---

### STEP 4.5 — WRITE SPEC
> Goal: document the fix plan for user review before touching code

**Two ways to write it. Both produce the same file at the same path.** STEP 0a already decided which
one this run is in — do not re-decide here, and do not fall back silently.

| Mode | When | What runs |
|---|---|---|
| **speckit** | preflight found `.specify/` **and** the speckit skills, and `--no-speckit` was not passed | `/speckit.specify`, per the guard below |
| **internalised** | anything else | the equivalent defined in this file, below |

The internalised mode is a supported way to run, not a degraded one: `.specify/` is scaffolding that
lives inside the repository being worked on, so no plugin can ship it on the user's behalf, and a
skill that only worked in repositories someone had already initialised would be useless in most of
them. Whichever mode ran, **name it at the HARD STOP.**

#### Mode `speckit` — the guard

> **Does the skill you are about to call run a shell script?**
> `.specify/scripts/bash/check-prerequisites.sh` enforces a branch-name pattern (`NNN-…` or
> `YYYYMMDD-HHMMSS-…`) that ordinary branch conventions (`feat/…`, `bugfix/…`,
> `<system>/feature/…`) do **not** match — so a script-backed skill aborts on line 1 even though
> `.specify/` exists. Directory-exists alone is a **false green**.
>
> | Skill | Runs a script? |
> |---|---|
> | `speckit.specify` | **No** — safe to call directly |
> | `speckit.clarify` / `checklist` / `analyze` | Yes — `check-prerequisites.sh` |
> | `speckit.plan` / `tasks` | Yes — `setup-plan.sh` / `setup-tasks.sh` |
>
> For a script-backed skill, set `SPECIFY_FEATURE` + `SPECIFY_FEATURE_DIRECTORY` first (see below) —
> that clears the branch gate **without touching git**. If it still fails, do not call it: switch
> that one call to the internalised equivalent and say so.

#### Mode `internalised` — write the spec directly

No speckit call, no shell script, no branch gate. Same destination, same filenames, so
`/ktkit:bug-fix-execute` and every later step read it without knowing which mode produced it:

```
.claude/claude/specs/<rel-dir>/<base>/spec.md
.claude/claude/specs/<rel-dir>/<base>/checklists/requirements.md
```

1. Resolve `<rel-dir>` and `<base>` by the priority order below, and run the collision check.
2. `mkdir -p` the feature directory and its `checklists/`.
3. Write `spec.md` covering the sections listed at the end of this step.
4. Write `checklists/requirements.md` yourself — the quality loop is the point of step 7, and it is
   the only always-on gate in this workflow. Items test **the spec**, not the running system; the
   rules for writing them are in STEP 4.7, which applies here verbatim.
5. Grade the spec against that checklist and fix every failure you can fix. What you cannot fix
   becomes an Open Question in the spec.
6. Report at the HARD STOP as `internalised` with the same counts speckit would have reported.

Do **not** call `/speckit.clarify` in this mode. STEP 4.6 has its own internalised branch.

> **Language**: the whole spec file is written in **Vietnamese**. Code snippets, file paths, symbol
> names and technical names (kebab-case, camelCase and so on) stay exactly as they are — only the
> descriptive prose is Vietnamese.

**ALWAYS write spec to a NEW file** under `.claude/claude/specs/`. NEVER modify the original bug report or analyze file provided by the user.

#### The `<base>` is a FOLDER, not a filename

One bug = one folder. Everything it produces lives inside it, under fixed filenames — which is exactly the shape spec-kit calls a `FEATURE_DIR`, so speckit skills work natively with no shim and no copying:

```
.claude/claude/specs/<rel-dir>/<base>/spec.md          ← this step writes this
.claude/claude/specs/<rel-dir>/<base>/checklists/…     ← quality checklists
```

**No `bug-` prefix.** `<base>` is carried over verbatim so one name identifies the work across `analyze/`, `specs/` and `pipeline/`.

Resolve `<rel-dir>` and `<base>` in this priority order:

**1. User specified an explicit output path** → use it verbatim. Stop here.

**2. Input came from a base file under `.claude/claude/analyze/`** (the normal case — the `/ktkit:rca` handoff):

| Var | Definition |
|---|---|
| `<rel-dir>` | `dirname(<base-file>)` relative to `.claude/claude/analyze` — may be empty |
| `<base>` | `basename(<base-file>)` minus the trailing `.analyze.md` — **verbatim**, including any layer suffix such as `.fe` / `.be` |

```
analyze  .claude/claude/analyze/2474-share-files/bug-share-link-expired.analyze.md
→ spec   .claude/claude/specs/2474-share-files/bug-share-link-expired/spec.md

analyze  .claude/claude/analyze/2410-keep-user-preference/no-render-department-data.analyze.md
→ spec   .claude/claude/specs/2410-keep-user-preference/no-render-department-data/spec.md
```

*(A `bug-` already present inside `<base>` stays — it is part of the name, not a prefix this step adds.)*

If the base file is a raw bug report under `.claude/claude/prompts/` (RCA step skipped), same rule with the root swapped.

**Keep `<base>` verbatim** — do NOT re-slugify, shorten, reorder words, or strip a layer suffix.

**3. No base file** (bug reported directly in chat) → `<rel-dir>` empty, `<base>` = kebab-case symptom description → `.claude/claude/specs/<base>/spec.md`.

#### Collision check — MANDATORY before writing

The `feat-` / `bug-` prefix used to keep a feature and a bug of the same name apart (`feat-X.spec.md` vs `bug-X.spec.md`). Without it, both resolve to the **same folder** `<rel-dir>/<base>/`, so this step can silently overwrite a feature spec. This is a real shape in practice — sub-folders such as `<feature>/bugs/` already exist.

Before `mkdir`/write, check whether `.claude/claude/specs/<rel-dir>/<base>/spec.md` already exists:

- **Does not exist** → proceed.
- **Exists** → STOP and ask, do not guess:
  ```
  Spec đã tồn tại: .claude/claude/specs/<rel-dir>/<base>/spec.md
  (u) update — ghi đè spec cũ, giữ nguyên checklists/
  (n) new — đặt <base> khác, nhập tên
  (a) abort
  ```
  Wait for the answer. On `u`, overwrite `spec.md` **only** — never delete or rewrite anything under `checklists/`.

#### Before calling `/speckit.specify` — export the two variables *(mode `speckit` only)*

```bash
export SPECIFY_FEATURE_DIRECTORY=".claude/claude/specs/<rel-dir>/<base>"
export SPECIFY_FEATURE="$(date +%Y%m%d-%H%M%S)-<slug>"   # slug MANDATORY — bare timestamp is rejected
```

- `SPECIFY_FEATURE_DIRECTORY` makes speckit write `spec.md` and `checklists/` into our tree. It is first in spec-kit's resolution order, so it wins.
- `SPECIFY_FEATURE` only clears the branch-name gate. It does **not** touch git and does **not** rename any branch. Its value is throwaway and may differ every run — the feature directory stays stable because the variable above is always explicit.
- Derive `<slug>` from `<base>`. A bare `YYYYMMDD-HHMMSS` with no trailing slug is **rejected** by the gate.

#### Do NOT truncate `/speckit.specify` at step 6 *(mode `speckit` only)*

Older versions of this workflow overrode the output path and stopped once `spec.md` was written, which silently dropped the skill's own quality loop. With `SPECIFY_FEATURE_DIRECTORY` set correctly there is no reason to stop early — let it run **through step 7**: **7a** writes `checklists/requirements.md`, **7b** grades the spec against it, **7c** fixes the failures.

That loop is the only always-on quality gate in this workflow — STEP 4.7 below is risk-gated and often does not run. Report the checklist result at the HARD STOP.

**Migration note**: older specs exist as flat `.claude/claude/specs/<rel-dir>/bug-<name>.spec.md`. Leave them exactly as they are — never move, rename, or "tidy" them. The folder layout applies to new specs only; both shapes coexist.

The spec file must cover:
- Root cause (from STEP 4)
- Detailed flow showing where the bug occurs
- Expected vs actual behavior
- Proposed fix approach (with code snippets)
- Files to be changed
- Acceptance criteria
- Open questions (if any)
- Blast radius assessment

---

### STEP 4.6 — CLARIFY
> Goal: tighten spec before user reviews

In mode `speckit`, invoke `/speckit.clarify` focused on bug-fix scope. In mode `internalised`, do the
same scan yourself and write the answers back into `spec.md` — the questions below are the whole of
it, and nothing about them needs a shell script. Either way the taxonomy scan prioritises:
- Is reproduction case unambiguous and step-by-step verifiable?
- Is expected vs actual behavior measurable (not just "it doesn't work")?
- Is fix scope clearly bounded — what NOT to change?
- Are rollback / revert requirements defined if fix causes regression?
- Are affected roles / permissions documented?

Generates ≤5 high-impact questions → encodes answers back into spec file.

**Hard gate**: Complete clarification loop before HARD STOP.

---

### STEP 4.7 — FIX QUALITY CHECKLIST (risk-gated — often SKIPPED)
> Goal: unit-test the fix spec itself before anyone writes code against it

> Source: item-writing rules + file semantics adapted from `speckit.checklist` (snapshot 2026-08-24). Internalised on purpose — that skill's `check-prerequisites.sh --json` demands a `plan.md`, and this workflow HARD-STOPs *before* planning.

**Gate — compute the risk first, then decide:**

```
risk = max( STEP 3 blast radius , risk recorded in the input .analyze.md )
```

Comparing across two vocabularies — the analyze file uses 5 bands, this workflow uses 4 — on one merged ladder:

```
LOW  <  LOW–MEDIUM  <  MEDIUM  <  MEDIUM–HIGH  <  HIGH  <  CRITICAL
└────── skip this step ───────┘  └───────────── run it ─────────────┘
```

- `risk ≥ MEDIUM` → run this step.
- Otherwise → **skip and say so** at the HARD STOP (`"risk = LOW, checklist skipped"`). Most bugs are narrow; a 40-item checklist on a one-line fix is noise.
- No `.analyze.md` → single source, use the local value. A stale HIGH still forces the step: deliberate, fail-safe.

**Write to** `.claude/claude/specs/<rel-dir>/<base>/checklists/bugfix.md` — a **separate file** from the `requirements.md` that `/speckit.specify` step 7a created, so there is no format collision. New file → number from `CHK001`; file already exists → append, continuing from the last CHK ID. Never delete or rewrite existing content.

**Write items that test the SPEC, not the running system.** The distinction matters more here than anywhere, because a bug spec is *about* behaviour:

| ❌ Testing the system | ✅ Testing the spec |
|---|---|
| "Verify the bug no longer reproduces" | "Are the reproduction steps deterministic — same input, same observed failure? [Clarity]" |
| "Test that the null check works" | "Is the expected value specified for the null case, not just 'no crash'? [Completeness, Gap]" |
| "Confirm nothing else broke" | "Does the spec state which call sites are in scope and which are explicitly NOT? [Consistency]" |

**Banned openers**: `Verify` / `Test` / `Confirm` / `Check` followed by system behaviour; anything about clicking, rendering, executing; test plans or QA procedures.

**Required shape**: a question about what the spec does or does not say, tagged with a quality dimension, and traceable. **≥80% of items must carry** a `[Spec §X]` reference or one of `[Gap]` / `[Ambiguity]` / `[Conflict]` / `[Assumption]`.

**Cover these 5 dimensions** (the bug-shaped subset — skip one only when the spec has no surface for it, and say which):

| Dimension | The question it asks of the spec |
|---|---|
| Reproduction Clarity | Are the steps deterministic and complete — environment, data shape, timing, user action? |
| Expected-vs-Actual Measurability | Is *expected* an observable value, not "it should work"? Can a reviewer tell pass from fail? |
| Fix Scope Boundedness | Does the spec say what must NOT change? Are the touched symbols enumerated? |
| Rollback / Regression | If the fix regresses, is the revert path stated? Are the flows that must keep working named? |
| Roles & Permissions | Are the affected roles documented, including any whose behaviour must stay unchanged? |

**Cap**: soft limit 25 items — a bug spec smaller than a feature spec should get a smaller checklist.

**Then act on it**: any item that fails is a **spec defect**. Fix the spec now and tick the item. Leave it unticked only when fixing needs an answer you do not have — then it becomes an Open Question in the spec, and say so at the HARD STOP. A checklist handed over with unexplained unticked boxes has done nothing.

---

## HARD STOP

**After STEP 4.6: do NOT proceed to fix.** Output the following and wait:

```
## Spec Ready for Review

**Root Cause**: <one sentence>
**Blast Radius**: <LOW/MEDIUM/HIGH/CRITICAL>
**Spec written by**: <`speckit` | `internalised` — and why, in four words>
**Feature dir**: `.claude/claude/specs/<rel-dir>/<base>/`
**Spec written to**: `<…>/spec.md`
**Spec quality checklist**: `<…>/checklists/requirements.md` — <N/16 passed, M fixed by step 7c>
**Clarifications**: <N questions answered / "no critical ambiguities detected">
**Fix quality checklist (STEP 4.7)**: <"risk = <band>, N items, M spec defects fixed, K left open" | "risk = <band> < MEDIUM — skipped">

➡️ Review the spec above. When ready, run `/ktkit:bug-fix-execute` to apply the fix (STEP 5→7 only, no re-investigation).
```
