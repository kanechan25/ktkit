---
name: rca
description: Root Cause Analysis — The Investigator. Evidence-first forensic debugging using 5 Whys + AgentRx. Use when a bug report is submitted and before invoking /ktkit:bug-fix-specs for fix implementation.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

---

## Goal

Perform a disciplined, evidence-based root cause analysis. **NO guessing. NO assumptions.** Every conclusion must be backed by actual evidence retrieved from the codebase (grep output, file:line read, GitNexus query result, or log analysis). If evidence cannot be found, state `EVIDENCE NOT FOUND` explicitly — never fill gaps with assumptions.

---

## Operating Constraints

- **Evidence-first**: You MUST run at least one tool call (Grep, Read, GitNexus query) to verify **every** causal claim before stating it.
- **Sequential only**: Do NOT run investigation steps in parallel. Each step's output feeds the next.
  This governs *steps*. Inside one step, several `ktkit:escalation-resolver` subagents answering
  independent questions **are** dispatched in one message — that is one step, not several.
- **No fix yet**: This command investigates only. Code changes happen in `/ktkit:bug-fix-specs` → `/ktkit:bug-fix-execute`.
- **Stop condition**: If blast radius returns HIGH or CRITICAL → stop, present report, wait for user confirmation before proceeding.
- **Data Provenance**: If a bug is traced to input data (params/props), you MUST identify its source. Distinguish between **Missing Logic** (data was never updated/calculated) and **Faulty Logic** (update logic exists but is incorrect). 
- **No Assumption on Requirements** — never *assume*, but resolving is not assuming. An ambiguous
  expected behaviour is an **unknown**: run it through `/ktkit:escalation-ladder` and route it by
  what being wrong would cost. Only the last row stops the run.

  | The ambiguity is about | Tier | Example |
  |---|---|---|
  | Something the repository can settle — which branch runs, what a field holds, which config wins | **T1** — dispatch a resolver | "which handler owns retry?" |
  | Observable behaviour — what the log says, which test fails | **T1** | |
  | A business rule where one reading is better evidenced **and** being wrong is cheap and reversible | **T3.5** — decide, record a **falsifier** | "round half up or half down?" |
  | A business rule where being wrong is expensive — money, data loss, access — or hard to reverse | **T4** — the single gate | "may an expired user still read old records?" |

  ⛔ A guess with no falsifier is still an assumption; that is what this constraint forbids. Asking
  the user before the tiers below are exhausted is the other failure, and costs a round-trip per
  question.
- **Historical Context**: For any suspected code, ask: "Why was this NOT a bug before?". Use Git history at current branch to examine the last 2-3 changes to those specific lines to understand the original intent and context.
- **Surgical Precision**: Focus ONLY on the bug. Do NOT refactor, reformat (Prettier), or change style in unrelated lines. If formatting is severely broken, flag it to the user instead of auto-fixing.

---

## Execution Steps

### Step 0: PREFLIGHT

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py" \
  --groups artifacts --repo "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
```

Creates `<repo-root>/.claude/claude/{prompts,analyze,specs,pipeline,implemented,compacts}` when the
repository does not have them, so Step 6 has somewhere to write. That layout is a rule of this
plugin, not a discovery: never probe for an alternative, never ask, and never write outside
`<repo-root>/.claude/`. Exit 1 → STOP and report; nothing else in this skill has run yet.

### Step 1: RECALL — Check Memory First (optional)

Search the memory server for similar bugs previously solved in this codebase:
- Query: symptom keywords from the bug report
- If a matching past resolution exists → present it to the user and ask: "Is this the same issue?"
- If yes → skip to Step 6 and output previous root cause
- If no → continue to Step 2
- **Tool absent**: this plugin does not ship a memory server, because memory holds durable state and
  a second copy would split the user's own. Skip this step, say so once, and never present the empty
  result as "this bug has not been seen before".

### Step 2: UNDERSTAND — Map the Symptom to Code

Invoke `superpowers:systematic-debugging`. Run **Phase 1** (Root Cause Investigation) and **Phase 2** (Pattern Analysis) ONLY.

**SCOPE NOTE**: Do NOT follow Phase 4 (Implementation) — fixes are handled by `/ktkit:bug-fix-specs` + `/ktkit:bug-fix-execute`. Stop after Phase 2 and continue to Step 3.

Phase 1 covers: reproduce consistently, check recent git changes, trace data flow.
Phase 2 covers: find working examples of similar code, compare working vs broken, list every difference.

Use Phase 2 findings as the evidence base for Step 3 (5 Whys chain).

Additionally run in parallel:
1. **GitNexus `query`** with the symptom description to find relevant execution flows.
2. **GitNexus `context`** on the most likely entry point symbol to see callers, callees, and process participation.
3. **Read the actual file** at the suspected location — do not rely on GitNexus context alone.
4. If a library is involved, use **Context7** to check for known bugs or API changes in that library version.

Document what you found:
```
SYMPTOM MAPPED TO:
- Execution flow: [process name from GitNexus]
- Entry point: [function name @ file:line]
- Code path: [brief A → B → C trace]
- Working example found: [file:line of similar working code]
- Key differences: [list from Phase 2]
```


### Step 3: THE 5 WHYS (Evidence Chain)

Apply the 5 Whys iteratively. For **each Why**, you MUST:
1. State the question.
2. Run a tool call to find evidence.
3. **Trace Data (if applicable)**: If the "Why" involves bad data, use `grep` or GitNexus to find where that data was last mutated.
4. **Historical Regression Check**: Check the `git log` of the suspicious lines (last 2-3 commits) at current branch. Explain what changed recently that might have triggered the symptom now.
5. State the conclusion based on evidence — not intuition.

**Format (repeat 5 times or until root cause reached):**

```
WHY [N]: [Question about the previous conclusion]

EVIDENCE QUERY: [describe what you searched for]
EVIDENCE RESULT:
  File: [path/to/file.ts]
  Line: [line number]
  Code: `[actual code snippet]`

CONCLUSION: [What this evidence tells us — one sentence]
```

**Stop condition for 5 Whys**: Stop when you reach a conclusion that is:
- A missing check / wrong condition / incorrect logic in a specific function, OR
- An incorrect assumption about data shape or API contract, OR
- A state management issue with clear evidence of when state diverges

If you reach WHY 5 and the root cause is still unclear, state: `ROOT CAUSE INCONCLUSIVE — additional evidence needed` and list what evidence is missing.

### Step 3.5: REQUIREMENT CLARIFY (conditional — usually SKIPPED)

> Source: taxonomy adapted from `speckit.clarify` (snapshot 2026-08-24). Internalised on purpose — `speckit.clarify` reads and writes a `spec.md` under a spec-kit `FEATURE_DIR`, which does not exist at RCA time.

**Trigger — run ONLY if one of these is true.** Otherwise skip silently and go to Step 4:

- Step 3 ended in `ROOT CAUSE INCONCLUSIVE`, OR
- the T4 pool is non-empty after the ladder ran — i.e. an ambiguity about *expected* behaviour
  survived T1, T2, T3 and T3.5.

Neither case is reached by an ambiguity the ladder could settle, so this step no longer costs an
interruption for anything a resolver could have answered. Never run it just to be thorough — RCA is
a one-shot flow.

**Scan** the bug report + evidence chain against these 5 categories (the subset of the clarify taxonomy that can change a root-cause verdict). Mark each `Clear` / `Partial` / `Missing`:

| Category | What to look for |
|---|---|
| Functional Scope & Behavior | What is the *correct* behavior, and who decides it? Is any part explicitly out of scope? |
| Domain & Data Model | Entity/attribute meaning, identity & uniqueness rules, lifecycle/state transitions the code assumes |
| Edge Cases & Failure Handling | Negative paths, concurrency/conflict resolution, what "should" happen in the failing branch |
| Completion Signals | How is "fixed" verified? Is the expected result measurable, not "it works"? |
| Terminology & Consistency | Same concept named differently across report / code / docs — a frequent source of false root causes |

**Resolve first.** Every `Partial` or `Missing` category is an unknown, not a question: dispatch
`Agent(subagent_type: "ktkit:escalation-resolver")`, one question per call, several in one message
when independent. ⛔ The lead does not open files. Only what survives as genuine T4 reaches the user.

**Then ask, once** — **at most 3 rows**, in a single block, answer-by-exception. Every row carries a
default that is **already applied**, so silence is a valid answer, and a recommendation. Only ask
what would change the root-cause verdict, the AgentRx class, or the fix boundary. More than 3
survivors ⇒ ⛔ do not list them all: report one row `N ambiguities of the same kind` with three
representatives, and say the bug report is missing a section.

**Write back** into the `## Root Cause Analysis` section of the report file (Step 6), under
`### Unknowns and how each was settled` — one row per unknown, in the table its tier belongs to. An
answer, or a resolver verdict, that invalidates a WHY step means that step must be re-run with
evidence, not patched in prose.

**If the user says nothing**: the default stated in the row is what was applied — that is the point
of writing it. Record it as a T3.5 row with its falsifier and carry the falsifier into *Recommended
Fix Approach* as a precondition. ⛔ A row whose default you cannot state is not ready to be asked:
send it back to T1.

### Step 4: AGENTX CLASSIFICATION

Classify the root cause into one of these AgentRx categories:

| Category | Meaning |
|---|---|
| **Logic Error** | Wrong condition, off-by-one, incorrect algorithm |
| **State Management Bug** | State diverges from expected at a specific point |
| **Misinterpretation** | Code misreads API response, data shape, or event payload |
| **Intent–Plan Misalignment** | Implementation doesn't match original spec/requirement |
| **Plan Adherence Failure** | A required step was skipped in the execution flow |
| **Invention of New Info** | Code assumes data that was never sent/stored (hallucinated contract) |
| **System Failure** | Infrastructure issue — timeout, connection drop, env config |
| **Race Condition** | Timing-dependent bug — async ops in wrong order |
| **Config Error** | Wrong env variable, feature flag, or deployment setting |

### Step 5: BLAST RADIUS

Run **GitNexus `impact`** on the root cause symbol:
```
gitnexus_impact({ target: "[symbol at root cause]", direction: "upstream" })
```

Map results:
- `d=1` — WILL BREAK: direct callers that must be updated
- `d=2` — LIKELY AFFECTED: indirect dependents to test
- `d=3` — MAY NEED TESTING: transitive dependencies

Determine **Risk Level**:
- **LOW**: d=1 count ≤ 2, no critical path, no shared state
- **MEDIUM**: d=1 count 3–6, or affects a shared utility/store
- **HIGH**: d=1 count > 6, or affects auth/data persistence/WebSocket layer
- **CRITICAL**: d=1 includes cross-team modules, public API contracts, or production data layer

> If Risk Level is HIGH or CRITICAL → **STOP**. Present report. Do NOT proceed without explicit user confirmation.

### Step 6: RCA REPORT — Write to File

Resolve the output path in this priority order:

**1. User specified an explicit output path** → use it verbatim. Stop here.

**2. Investigation started from a base file under `.claude/claude/prompts/`** (the normal case — the
user points at `.claude/claude/prompts/<rel-dir>/<name>.md` and asks for it to be read closely) →
MIRROR its sub-path into `.claude/claude/analyze/`:

| Var | Definition |
|---|---|
| `<rel-dir>` | `dirname(<base-file>)` relative to `.claude/claude/prompts` — may be empty |
| `<base-name>` | `basename(<base-file>)` minus the trailing `.md`; if what remains still ends in `.prompt`, drop that too |

Output: `.claude/claude/analyze/<rel-dir>/<base-name>.analyze.md` — `mkdir -p` the dir if missing.

```
base    .claude/claude/prompts/2474-share-files/bug-share-link-expired.md
→       .claude/claude/analyze/2474-share-files/bug-share-link-expired.analyze.md
```

**Keep the base filename verbatim** — do NOT re-slugify, shorten, or prepend `bug-`. The tree under `analyze/` mirrors `prompts/` exactly so the downstream chain (`analyze/` → `specs/` → `pipeline/`) stays aligned.

If the base file lives outside `.claude/claude/prompts/`, mirror is not possible → fall through to rule 3 and state the chosen path to the user.

**3. No base file** (bug reported directly in chat) → `.claude/claude/analyze/bug-<describe-bug-name-here>.analyze.md` (flat). Filename kebab-case, describing the bug concisely (e.g., `bug-bol-pdf-missing-cargo-rows.analyze.md`).

Write the file with the following structure — be **specific, detailed, and Claude-friendly** (clear section headers, concrete evidence references, no ambiguity). This file will be fed directly as input to `/ktkit:bug-fix-specs`, so every section must be self-contained and actionable:

```markdown
---
type: bug-analysis
status: rca-complete
created: [YYYY-MM-DD]
base_file: [.claude/claude/prompts/<rel-dir>/<base-name>.md — omit if none]
---

# Bug Analysis: [Bug Title]

## Bug Report Summary

[2–3 sentences summarizing what the user reported: what broke, where, and under what conditions.]

## How to Reproduce

1. [Step-by-step reproduction steps derived from the bug report and code trace]
2. [Include environment context if relevant — locale, data shape, user action]
3. [Expected result vs. actual result]

**Expected**: [What should happen]
**Actual**: [What happens instead]

---

## Root Cause Analysis

**Root Cause**: [One sentence — specific and actionable. Must name the exact file, line, and function.]
**Location**: `path/to/file.ts:LINE` — `functionName()`
**AgentRx Category**: [category from Step 4]
**Risk Level**: LOW / MEDIUM / HIGH / CRITICAL

### Unknowns and how each was settled

Three tables, per `/ktkit:escalation-ladder`. Omit a table only when it is genuinely empty — an
absent table reads as "nothing was decided", which is never true.

#### ⛔ CẦN CHỐT — im lặng = nhận default (≤3 dòng)
| # | Câu | Default áp luôn | Khuyến nghị | Sai thì mất gì | Đổi ở đâu |
|---|---|---|---|---|---|

#### ✅ ĐÃ TỰ CHỐT (T1/T2/T3) — chỉ đọc, không cần trả lời
| Câu | Tier | Kết luận | Bằng chứng (file:line) |
|---|---|---|---|

#### 🟡 GIẢ ĐỊNH CÓ BẰNG CHỨNG (T3.5)
| ASM | Cách đọc đã chọn | Bằng chứng | Falsifier | Blast radius |
|---|---|---|---|---|

**Escalation metric**: `self_resolve_ratio=0.xx · self_resolved=N · needs_user=M · assumptions=K · gates=1`

`self_resolve_ratio = self_resolved / (self_resolved + needs_user)`. **Below 0.70 ⇒ tiers 1–3 were
not exhausted**: dispatch more resolvers before writing this file. Every 🟡 row must carry a
non-empty Falsifier, and every ⛔ row a Default that is already applied.

[Carry each Falsifier into Recommended Fix Approach as a precondition.]

### Evidence Chain (5 Whys)

**WHY 1**: [question]
→ Evidence: `file:line` — `code snippet`
→ Conclusion: [finding]

**WHY 2**: [question]
→ Evidence: `file:line` — `code snippet`
→ Conclusion: [finding]

[...repeat until root cause reached...]

**Root Cause**: [Final conclusion with file:line citation]

---

### Blast Radius

| Depth | Module / Symbol | Impact |
|---|---|---|
| d=1 | `symbolName` @ `file.ts:line` | WILL BREAK |
| d=2 | `symbolName` @ `file.ts:line` | LIKELY AFFECTED |

---

## Recommended Fix Approach

[2–3 sentences describing what needs to change and why — no code yet. Be precise about which function/file/logic to target. This section guides `/ktkit:bug-fix-specs` in generating the correct fix plan.]
```

After writing the file, inform the user of the file path created.

---

## Unknown handling (bindingly, before any question reaches the user)

Whenever anything is unknown — a symbol that cannot be found, two sources disagreeing, a bug report
with two readings, a fact about a library — **invoke skill `/ktkit:escalation-ladder`** and follow
it. An ambiguous *expected behaviour* is covered by the table in Operating Constraints above.

Delegate the searching: **`Agent(subagent_type: "ktkit:escalation-resolver")`, one question per
call**, several in one message when independent. ⛔ The lead does not open files — it holds the
question, the `Tier`, and a one-line conclusion with its citation. The resolver has `Read, Bash` and
no `Grep`/`Glob`; it searches through the shell.

⛔ Nothing reaches the user before the ladder has run, and this workflow opens **exactly one**
gate — Step 3.5 — capped at 3 rows, every row with a default and a recommendation.

Budget, per `/ktkit:escalation-ladder`: at most **5 resolvers per round, 2 rounds per question**. Out
of budget is not a reason to escalate — it moves the unknown to T3.5 if one reading is better
evidenced, or leaves it `Undecided`.

**Fallback** — `/ktkit:escalation-ladder` ships with this plugin, so it is present wherever this
skill is. If it somehow cannot be loaded, apply the tiers inline: T1 resolve from repo with a
citation · T2 one round of challenge · T3 external fact, else `Undecided` · T3.5 decide with a
mandatory falsifier · T4 the single gate. ⛔ A missing skill is never a reason to reinstate the
interview.

---

### Step 7: HANDOFF TO /ktkit:bug-fix-specs

After the file is written, prompt the user:

> "RCA complete. Analyze file saved to `.claude/claude/analyze/<rel-dir>/<base-name>.analyze.md`. Run `/ktkit:bug-fix-specs` to generate the fix spec?"

If user confirms → invoke `/ktkit:bug-fix-specs` with the analyze file as input context. Pass the full file path so the skill reads it as its primary input.

---

## Context

$ARGUMENTS
