---
name: feat-req-specs
description: "Use when the user provides a feature request and wants to review specs BEFORE implementing. Runs STEP 0→5 (memory check, understand, blast radius, interview, design, spec) and writes the spec under .claude/claude/specs/<rel-dir>/<base>/ — through /speckit.specify when the repository has speckit scaffolding, through this skill's own internalised equivalent when it does not or when called with --no-speckit. Then STOPS and waits for user approval before any code or plan is written. Hand off to /ktkit:feat-req-execute."
---

# Feat-Req Specs Workflow

## Purpose

Same SDD pipeline as `feat-req-done`, but **stops at STEP 5** and writes a spec for user review. No plan, no tasks, no code until the user explicitly approves and runs `/ktkit:feat-req-execute`.

## ⚠️ FORMAT GATE (Soft Gate — carried into `/ktkit:feat-req-execute`)

This skill writes specs only — no code changes here. But the spec you write will drive `/ktkit:feat-req-execute`, so **explicitly document in the spec's "Files to Change" section** that format-only lines must NOT be touched:

When writing the proposed fix / change snippets in the spec:
- Show **only the logic diff** — not reformatted surrounding code
- Do NOT include semicolon removals, spacing changes, or brace-style changes in code snippets
- If a code snippet shows surrounding context lines, keep them byte-for-byte identical to the source

The executor (`/ktkit:feat-req-execute`) has its own FORMAT GATE and will refuse format-only edits.

---

## 🌐 LANGUAGE GATE (Vietnamese for clarifications & assumptions)

Whenever this workflow — or any `speckit.*` skill it calls — produces **open questions, assumptions,
ambiguity findings, cross-artifact issues or recommendations**:

- **Write in Vietnamese**: every question, assumption label, rationale, severity description and
  recommendation shown to the user.
- **Keep in English**: file paths, function/symbol/class names, flags, API names, original error
  messages, code snippets, and technical terms with no settled translation (e.g. "race condition",
  "blast radius", "TDD", "idempotent").
- Applies **in reasoning as well as in the final output** shown to the user.
- Spec file content (`spec.md`) follows the template it came from — never translate headers or
  keywords.

Why: the reviewer reads in Vietnamese, so prose in Vietnamese removes friction while the identifiers
stay exact.

---

## Pipeline (Sequential — Do Not Skip Steps)

### STEP 0a — PREFLIGHT (runs before anything is spent)
> Goal: fail in one second rather than at STEP 5, after five steps have been paid for

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py" \
  --groups artifacts,speckit,mcp --repo "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
```

Drop `speckit` from `--groups` when the user passed `--no-speckit` — that flag *is* the decision to
take the internalised path, so probing for scaffolding the run will not use would block for nothing.
The flag holds **even when speckit is installed and scaffolded**: it selects the path, it does not
merely relax the check.

⛔ **Without that flag, a missing half stops the run.** Never fall back to the internalised path on
your own. Degrading silently ships something other than what was asked for, under the same name.

**Exit 1 → STOP before STEP 0b.** Print what is missing and both ways forward, then wait:

```
⛔ /ktkit:feat-req-specs — stopped before STEP 0b

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
▶ /ktkit:feat-req-specs — degraded run
  ✗ mcp__memory absent → STEP 0b skipped, no recall from earlier sessions
  ✓ artifact root · ✓ speckit scaffolding · ✓ sequential-thinking (shipped by ktkit)
```

The `artifacts` group creates `<repo-root>/.claude/claude/{prompts,analyze,specs,pipeline,implemented,compacts}`
when the repository does not have them. That layout is a rule of this plugin, not a discovery: never
probe for an alternative, never ask, and never write outside `<repo-root>/.claude/`.

---

### STEP 0b — MEMORY CHECK (optional)
> Goal: avoid reinventing patterns already established in this codebase

```
mcp__memory__search_nodes({query: "<feature keywords>"})
```

- **Found similar feature**: report prior decisions (architecture, patterns, ADRs) and treat them as
  the starting position. ⛔ Do not ask whether they still apply — that is an unknown, so run it
  through `/ktkit:escalation-ladder`: a decision contradicted by current code is T1/T2 evidence, not
  a question.
- **Not found**: proceed to STEP 1
- **Tool absent**: this plugin does not ship a memory server, because memory holds durable state and
  a second copy would split the user's own. Skip this step, say so once, and never present the empty
  result as "no prior work exists".

**Also read the decision log**: `.claude/context/decisions/<slug>.md`, if the repo keeps one. A
question already carrying a `D-ID` there is **settled** — ⛔ do not ask it again and ⛔ do not decide
it again; quote the entry and move on.

---

### STEP 1 — UNDERSTAND + RELATIONSHIP MAPPING (`GitNexus`)
> Goal: find existing patterns and related features before designing anything

Run in parallel:
```
gitnexus_query({query: "<feature description>"})   → find execution flows similar to what we're building
gitnexus_context({name: "<entry point module>"})    → callers, callees, which flows it participates in
```

**1b. Relationship Mapping**:
```
gitnexus_query({query: "<feature name> OR <related keyword>"})
```

Identify and report:
- **Reusable features**: similar features already exist → reuse pattern or create new?
- **Potential conflicts**: existing features that may conflict with the new one → guard logic needed?
- **Shared infrastructure**: stores, APIs, WebSocket channels that can be reused

**If feature needs a new library**:
```
Context7: resolve-library-id → query-docs for "<library name>"
```

Report findings + relationship map before proceeding. Do not design yet.

---

### STEP 2 — PRELIMINARY BLAST RADIUS (`GitNexus`)
> Goal: early warning on integration points before designing

```
gitnexus_impact({target: "<integration point>", direction: "upstream"})
```

Run for each known integration point from STEP 1.

| Risk | Action |
|---|---|
| LOW / MEDIUM | Proceed |
| **HIGH / CRITICAL** | **STOP — report to user, do not proceed without explicit approval** |

---

### STEP 3 — RESOLVE, THEN (MAYBE) ASK
> Goal: eliminate hidden assumptions before designing — by resolving them, not by interviewing

**Invoke skill `/ktkit:escalation-ladder` and follow it for this whole step.** Every item below is an
*unknown*: it goes T1 → T2 → T3 → T3.5 first, and only what survives as genuine T4 becomes a
candidate row for the single gate at the HARD STOP.

Delegate the searching: **`Agent(subagent_type: "ktkit:escalation-resolver")`, one question per call**,
several in one message when independent. ⛔ The lead does not open files.

⛔ **STEP 3 blocks on nothing.** Both blocking gates that used to sit here are removed on purpose — they cost 2 of
the 5–9 round-trips this workflow used to spend per feature.

**3a. Surface assumptions first.** Explicitly list what you're assuming based on STEP 0–2 findings. ⛔ Do not ask the user to confirm them — each one becomes a T3.5 record with a falsifier, and the reader can refute it from the falsifier alone:

```
ASSUMPTIONS I'M MAKING:
1. [Reuse assumption — which existing component/flow of THIS repo it plugs into, no new one created]
2. [Scope assumption — who/what is affected, and who/what is explicitly NOT]
3. [Data assumption — no migration / migration needed, backward compat]
→ Correct me now or I'll proceed with these.
```

Each assumption must name components that exist in the **active repo** (from the `.analyze.md` §4 stack profile, or read the repo's `CLAUDE.md` if there is no analyze file). Never carry stack names over from another project.

Do not silently fill in ambiguous requirements. The spec's entire purpose is to surface misunderstandings *before* design — assumptions are the most dangerous form of misunderstanding.

⛔ **No gate here.** Each assumption is a **T3.5 record**, not a question: reading chosen + evidence
(`file:line`) + **falsifier (mandatory)** + blast radius. An assumption you cannot falsify is not an
assumption — send it back to T1, or promote it to T4 if being wrong is expensive.

Carry the T3.5 rows into the spec's assumptions table and keep going.

**3b. Probe these 5 areas — resolve first, do not ask first:**

1. **Corner cases** in business logic the requirement doesn't mention
2. **Failure behavior** — what happens on disconnection, timeout, concurrent edits?
3. **Permissions / roles** — who should NOT have access to this feature?
4. **Scale** — how should it behave when data grows 10x?
5. **Feature interaction** — conflicts with existing features found in STEP 1?

⛔ **No gate here.** Run all five through the ladder and route each one:

| Ladder outcome | Where it goes |
|---|---|
| T1 / T2 — resolved from repo, docs, history, prior run | spec §Settled, with `file:line` |
| T3 — external fact; three portable steps fail | spec §Settled as `Undecided` — ⛔ never a question |
| T3.5 — one reading better evidenced, cheap if wrong | spec §Assumptions, with falsifier |
| T4 — undecidable **and** expensive if wrong | **pool for the HARD STOP gate** (max 3 total) |

Then proceed to STEP 4 immediately. A T4 row does not block design: apply its **default** and note
that the design rests on it.

---

### STEP 4 — DESIGN (`sequential-thinking`)
> Goal: structured trade-off analysis, not "first idea wins"

Use `mcp__plugin_ktkit_sequential-thinking__sequentialthinking` to analyze:

1. **Requirement** — WHAT does this feature need to do? WHY does it exist?
2. **Options** — Enumerate ≥2 architectural approaches
3. **Trade-offs** — For each option: complexity, blast radius, consistency with existing patterns from STEP 1
4. **Decision** — Which option and why (must reference STEP 1 patterns + CLAUDE.md constraints)
5. **Integration** — How does it plug into existing code without breaking existing flows?

⛔ **No hard stop here.** Ambiguous expected behaviour after STEP 3 is an unknown like any other:
ladder it. If it lands at T4, apply the default, record it as the assumption the chosen option rests
on, and continue designing. Only the four ruling-exceptions stop a run — irreversible/destructive
operation, security-sensitive action, side effect outside this workspace, or a plan so broken every
path forward is a guess.

---

### STEP 5 — SPEC + SCENARIOS
> Goal: single source of truth — WHAT and WHY, no HOW yet

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
`/ktkit:feat-req-execute` and every later step read it without knowing which mode produced it:

```
.claude/claude/specs/<rel-dir>/<base>/spec.md
.claude/claude/specs/<rel-dir>/<base>/checklists/requirements.md
```

1. Resolve `<rel-dir>` and `<base>` by the priority order below, and run the collision check.
2. `mkdir -p` the feature directory and its `checklists/`.
3. Write `spec.md` with the sections listed at the end of this step — Testing Strategy and all three
   Scenario groups included; they are what makes this a spec rather than a summary.
4. Write `checklists/requirements.md` yourself. Items test **the spec**, not the running system; the
   item-writing rules in STEP 5.6 apply here verbatim.
5. Grade the spec against that checklist and fix every failure you can fix. What you cannot fix
   becomes an Open Question in the spec.
6. Report at the HARD STOP as `internalised` with the same counts speckit would have reported.

Do **not** call `/speckit.clarify` or `/speckit.analyze` in this mode. STEP 5.5 has its own
internalised branch.

> **Language**: the whole spec file is written in **Vietnamese**. Code snippets, file paths, symbol
> names and technical names (kebab-case, camelCase and so on) stay exactly as they are — only the
> descriptive prose is Vietnamese.

**ALWAYS write spec to a NEW file** under `.claude/claude/specs/`. NEVER modify the original feature request or analyze file provided by the user.

#### The `<base>` is a FOLDER, not a filename

One feature = one folder. Everything the feature produces lives inside it, under fixed filenames — which is exactly the shape spec-kit calls a `FEATURE_DIR`, so speckit skills work natively with no shim and no copying:

```
.claude/claude/specs/<rel-dir>/<base>/spec.md          ← this step writes this
.claude/claude/specs/<rel-dir>/<base>/checklists/…     ← quality checklists
.claude/claude/specs/<rel-dir>/<base>/plan.md          ← later, /ktkit:feat-req-execute
.claude/claude/specs/<rel-dir>/<base>/tasks.md         ← later, /ktkit:feat-req-execute
```

**No `feat-` prefix.** `<base>` is carried over verbatim so one name identifies the feature across `analyze/`, `specs/` and `pipeline/`.

Resolve `<rel-dir>` and `<base>` in this priority order:

**1. User specified an explicit output path** → use it verbatim. Stop here.

**2. Input came from a base file under `.claude/claude/analyze/`** (the normal case):

| Var | Definition |
|---|---|
| `<rel-dir>` | `dirname(<base-file>)` relative to `.claude/claude/analyze` — may be empty |
| `<base>` | `basename(<base-file>)` minus the trailing `.analyze.md` — **verbatim**, including any layer suffix such as `.fe` / `.be` |

```
analyze  .claude/claude/analyze/2472-preview-edit-office/stage-developer/phase3-license-infra.analyze.md
→ spec   .claude/claude/specs/2472-preview-edit-office/stage-developer/phase3-license-infra/spec.md

analyze  .claude/claude/analyze/2410-user-preference/CR-toggle-save.fe.analyze.md
→ spec   .claude/claude/specs/2410-user-preference/CR-toggle-save.fe/spec.md
```

If the base file is a raw prompt under `.claude/claude/prompts/` (analyze step skipped), same rule with the root swapped.

**Keep `<base>` verbatim** — do NOT re-slugify, shorten, reorder words, or strip a layer suffix.

**3. No base file** (feature described directly in chat) → `<rel-dir>` empty, `<base>` = kebab-case description (concise, shape `<verb-or-domain>-<object>-<qualifier>`) → `.claude/claude/specs/<base>/spec.md`.

#### Collision check — MANDATORY before writing

The `feat-` / `bug-` prefix used to keep a feature and a bug of the same name apart (`feat-X.spec.md` vs `bug-X.spec.md`). Without it, both resolve to the **same folder** `<rel-dir>/<base>/`, so a second run can silently overwrite the first. This is a real shape in practice — sub-folders such as `<feature>/bugs/` already exist.

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

Older versions of this workflow overrode the output path and stopped once `spec.md` was written, which silently dropped the skill's own quality loop. With `SPECIFY_FEATURE_DIRECTORY` set correctly there is no reason to stop early — let it run **through step 7**:

- **7a** writes `checklists/requirements.md` (16 items: Content Quality / Requirement Completeness / Feature Readiness).
- **7b** grades the spec against each item.
- **7c** fixes the failures it finds.

That loop is the only always-on quality gate in this workflow — STEP 5.6 below is risk-gated and often does not run. Report the checklist result at the HARD STOP.

**Migration note**: older specs exist as flat `.claude/claude/specs/<rel-dir>/feat-<name>.spec.md`. Leave them exactly as they are — never move, rename, or "tidy" them. The folder layout applies to new specs only; both shapes coexist.

**If requirement is vague, reframe it as testable success criteria first:**

```
REQUIREMENT: "Đồng bộ hóa realtime"

REFRAMED SUCCESS CRITERIA:
- Action của user A visible với user B trong vòng < 300ms
- Khi disconnect và reconnect, state được restore đầy đủ
- 2 user edit cùng 1 element → conflict resolved, không có element freeze
→ Are these the right targets?
```

Confirm reframed criteria with user before writing spec content.

The spec file must cover:
- User story + acceptance criteria (reframed from STEP 5 if applicable)
- Business value / reason this feature exists
- Architecture decision summary (from STEP 4 — chosen option + why)
- Integration points (which components, stores, APIs)
- Out-of-scope (what NOT to build)
- Open questions (from STEP 3 unanswered items)
- Relationship map (from STEP 1b — related features + interaction notes)
- Blast radius assessment (from STEP 2)
- Testing strategy (what tests need to be written for this feature)

**Testing Strategy section:**

```markdown
## Testing Strategy

- **Unit tests**: [which functions/services need unit tests, file locations]
- **Integration tests**: [which flows need integration tests — e.g., WebSocket action → store update]
- **E2E / manual**: [which scenarios require manual verification or Playwright tests]
- **Coverage expectation**: [critical paths that must have coverage]
```

**Must also include Scenarios section:**

```markdown
## Scenarios

### Happy Path
- [Step-by-step user flow when everything works]

### Error / Edge Cases
- [ ] When user loses connection mid-operation → behavior?
- [ ] When 2 users trigger the feature simultaneously → conflict resolution?
- [ ] When data is empty / data is extremely large → graceful degradation?

### What-If Scenarios
- "What happens if feature X (existing) interacts with this new feature?"
- "What happens if data grows 10x?"
- "What happens if rollback is needed?"
```

---

### STEP 5.5 — CLARIFY (call skill `/speckit.clarify`) — ⛔ **CONDITIONAL, usually SKIPPED**
> Goal: reduce spec ambiguity before user reviews

**Gate — run this step only when BOTH hold:**

```
risk >= MEDIUM            (same merged ladder as STEP 5.6)
AND the T4 pool is EMPTY  (nothing from STEP 3 survived to the gate)
```

**Why the second condition.** `/speckit.clarify` asks its questions **one at a time** — its own body
says *"Do NOT output them all at once"*, up to 5 — so it can cost **five sequential round-trips**.
It also has no view of what `/ktkit:escalation-ladder` already settled, so it re-asks resolved ground. When
the T4 pool is non-empty, its questions would be a second gate on top of the one gate this workflow
is allowed. ⛔ Skip it and say so at the HARD STOP: `"T4 pool non-empty — clarify skipped"`.

⛔ **Never edit `speckit.clarify` itself** — it is an upstream skill and an update would erase the
change. The condition lives here, in the caller.

When the gate does open, invoke `/speckit.clarify` with the spec file as context — or, in mode
`internalised`, run the same taxonomy scan yourself and write the answers back into `spec.md`. The
categories below are the whole of it; none of them needs a shell script.

The scan is structured across 8 categories:
- Functional Scope & Behavior
- Domain & Data Model
- Interaction & UX Flow
- Non-Functional Attributes (performance, security, availability, observability)
- Integration & External Dependencies
- Edge Cases & Failure Handling
- Constraints & Tradeoffs
- Terminology & Consistency

Generates ≤5 high-impact questions → encodes answers back into spec file incrementally.

**When the gate opened**: complete the loop, then go to the HARD STOP — its questions merge into the
same single gate, still capped at 3 rows total.
**When the gate did not open**: say which condition failed at the HARD STOP. Skipping is the
expected path, not a shortcut.

---

### STEP 5.6 — SPEC QUALITY CHECKLIST (risk-gated — often SKIPPED)
> Goal: unit-test the requirements themselves before anyone plans against them

> Source: item-writing rules + file semantics adapted from `speckit.checklist` (snapshot 2026-08-24). Internalised on purpose — that skill's `check-prerequisites.sh --json` demands a `plan.md`, and this workflow HARD-STOPs *before* planning.

**Gate — compute the risk first, then decide:**

```
risk = max( STEP 2 preliminary blast radius , risk recorded in the input .analyze.md §8 )
```

Comparing across two vocabularies — the analyze file uses 5 bands, this workflow uses 4 — on one merged ladder:

```
LOW  <  LOW–MEDIUM  <  MEDIUM  <  MEDIUM–HIGH  <  HIGH  <  CRITICAL
└────── skip this step ───────┘  └───────────── run it ─────────────┘
```

- `risk ≥ MEDIUM` → run this step.
- Otherwise → **skip and say so** at the HARD STOP (`"risk = LOW, checklist skipped"`). The `/speckit.specify` step-7 loop already covered the baseline.
- No `.analyze.md` → single source, use the local value. A stale HIGH in the analyze file still forces the step: that is deliberate, the failure mode is one extra checklist, not a missed one.

**Write to** `.claude/claude/specs/<rel-dir>/<base>/checklists/requirements.md` — the same file `/speckit.specify` step 7a created. Append under a **new `##` heading**, numbering CHK IDs independently from `CHK001`:

```markdown
## Requirements Quality (STEP 5.6)

- [ ] CHK001 - Are …? [Completeness, Spec §FR-1]
```

Why a separate heading: step 7a's 16 items carry **no CHK IDs**, so "continue from the last CHK ID" has nothing to continue from; and the two blocks test different things — 7a is a content-quality gate run *before* clarify, this block is requirements-quality run *after*. Never renumber or edit 7a's items.

**Write items that test the REQUIREMENTS, not the implementation.** This is the whole point:

| ❌ Testing implementation | ✅ Testing the requirement |
|---|---|
| "Verify the export button works" | "Are the exported fields enumerated? [Completeness, Spec §FR-3]" |
| "Test error handling" | "Is behaviour specified for a partial-failure export? [Gap]" |
| "Confirm it loads fast" | "Is 'fast' quantified with a threshold? [Clarity, Spec §NFR-1]" |

**Banned openers**: `Verify` / `Test` / `Confirm` / `Check` followed by system behaviour; anything about clicking, rendering, navigating, executing; test plans or QA procedures.

**Required shape**: a question about what the spec does or does not say, tagged with a quality dimension, and traceable. **≥80% of items must carry** a `[Spec §X.Y]` reference or one of `[Gap]` / `[Ambiguity]` / `[Conflict]` / `[Assumption]`.

**Cover these 9 dimensions** (skip one only when the spec genuinely has no surface for it — and say which you skipped): Requirement Completeness · Requirement Clarity · Requirement Consistency · Acceptance Criteria Quality · Scenario Coverage · Edge Case Coverage · Non-Functional Requirements · Dependencies & Assumptions · Ambiguities & Conflicts.

**Cap**: soft limit 40 items — above that, keep the highest-risk and merge near-duplicates into one item.

**Then act on it**: any item that fails is a **spec defect**. Fix the spec now and tick the item. Leave it unticked only when fixing needs an answer you do not have — then it becomes an Open Question in the spec, and say so at the HARD STOP. A checklist handed over with unexplained unticked boxes has done nothing.

---

## HARD STOP — the single gate

**After STEP 5.5: do NOT proceed to plan or implement.**

This is the **only** gate in the workflow. It is answer-by-exception, not an interview:

- **Max 3 rows.** More T4 candidates than that ⇒ ⛔ do not list them all; report one row
  `N ambiguities of the same kind` with three representatives, and say the requirement is missing a
  section.
- **Every row carries a Default that is already applied**, phrased so **silence is a valid answer**.
- **Every row carries a Recommendation.** A question without one hands the whole task back.
- Rows come from the merged T4 pool: `.analyze.md` §10 table C + STEP 3 + (if it ran) STEP 5.5.
  Drop any row the ladder settled in the meantime.

```markdown
## ⛔ CẦN CHỐT — im lặng = nhận default (≤3 dòng)
| # | Câu | Default áp luôn | Khuyến nghị | Sai thì mất gì | Đổi ở đâu |

## ✅ ĐÃ TỰ CHỐT (T1/T2/T3) — chỉ đọc, không cần trả lời
| Câu | Tier | Kết luận | Bằng chứng (file:line) |

## 🟡 GIẢ ĐỊNH CÓ BẰNG CHỨNG (T3.5)
| ASM | Cách đọc đã chọn | Bằng chứng | Falsifier | Blast radius |
```

Then output the following and wait:

```
## Spec Ready for Review

**Feature**: <name>
**Architecture**: <chosen approach from STEP 4>
**Blast Radius**: <LOW/MEDIUM/HIGH/CRITICAL>
**Related Features**: <list from STEP 1b>
**Spec written by**: <`speckit` | `internalised` — and why, in four words>
**Feature dir**: `.claude/claude/specs/<rel-dir>/<base>/`
**Spec written to**: `<…>/spec.md`
**Spec quality checklist**: `<…>/checklists/requirements.md` — <N/16 passed, M fixed by step 7c>
**Clarifications**: <N questions answered / "no critical ambiguities detected">
**Requirements checklist (STEP 5.6)**: <"risk = <band>, N items, M spec defects fixed, K left open" | "risk = <band> < MEDIUM — skipped">

**Escalation metric**: `self_resolve_ratio=0.xx · self_resolved=N · needs_user=M · assumptions=K · gates=1`

➡️ Review the spec above. When ready, run `/ktkit:feat-req-execute` to continue (STEP 6→10: plan → tasks → implement → verify → document).
```

`self_resolve_ratio = self_resolved / (self_resolved + needs_user)`. **Below 0.70 ⇒ tiers 1–3 were
not exhausted**: go back to STEP 3, dispatch more resolvers, and ⛔ do not open the gate yet.
`needs_user` must be ≤ 3, and every T3.5 row must have a non-empty Falsifier.

---

## Unknown handling (bindingly, before any question reaches the user)

Whenever anything is unknown — a term that cannot be found, two sources disagreeing, a sentence with
two readings, a fact about a library — **invoke skill `/ktkit:escalation-ladder`** and follow it.

Delegate the searching: **`Agent(subagent_type: "ktkit:escalation-resolver")`, one question per call**,
several in one message when independent. ⛔ The lead does not open files — it holds the question, the
`Tier`, and a one-line conclusion with its citation.

⛔ Nothing reaches the user before the ladder has run, and the workflow opens **exactly one gate**
(the HARD STOP), capped at 3 rows, every row with a default and a recommendation.

**Fallback** — `/ktkit:escalation-ladder` ships with this plugin, so it is present wherever this
skill is. If it somehow cannot be loaded, use `## Unknown handling — inline fallback` below. ⛔ A
missing skill is never a reason to reinstate the interview.

## Unknown handling — inline fallback (only when `/ktkit:escalation-ladder` cannot be loaded)

- **T1 RESOLVABLE** — answer exists in something openable (docs → code → `git log -5 -- <path>` →
  the artifact the work is about, read with a real parser → a prior run's analysis/spec → memory, if
  this session has it). Resolve it, cite `file:line` + a verbatim quote.
- **T2 CONFLICT** — two evidenced sources disagree ⇒ one round of challenge, `UPHELD`/`REFUTED` with
  evidence. ⛔ No second round.
- **T3 EXTERNAL FACT** — library/API/format/limit ⇒ documentation lookup tool if this session has one
  (detect at runtime, ⛔ never hardcode a tool name) → fetch official docs + version → read the
  installed dependency. All three fail ⇒ record `Undecided`, ⛔ do not ask the user.
- **T3.5 EVIDENCED ASSUMPTION** — ambiguous but one reading has more evidence **and** being wrong is
  cheap ⇒ decide, and record reading + evidence + **falsifier (mandatory)** + blast radius.
- **T4 TRUE AMBIGUITY** — readings equally supported, consequences differ materially, wrong is
  expensive or hard to reverse ⇒ the single gate. Max 3 rows, each with a default (silence accepts
  it) and a recommendation.

Leap a tier only by proving the one below is exhausted — never because it looks hard. Four things
stop the run outright: an irreversible or destructive operation, a security-sensitive action, a side
effect outside this workspace (merge, push to a shared branch, publish), or a plan so broken every
path forward is a guess. Everything else is a ruling: record
`Ruling: <what you decided> — <why> — <what it costs if wrong>` and keep going.
