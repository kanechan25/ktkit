---
name: analyze-feat
description: >
  Analyze a new feature requirement before writing any spec or code. TRIGGER this skill whenever the
  user provides a feature request, requirement document, product brief, or says things like "tao muốn
  thêm tính năng X", "analyze this feature", "understand this requirement", "/ktkit:analyze-feat", "cho tao
  biết feature này ảnh hưởng gì", "cần làm gì để implement X", "feature này tác động gì", "help me
  understand this PR requirement". Also trigger when the user pastes a requirement or links a prompt
  file without explicitly asking for analysis — if it looks like an unanalyzed feature description,
  use this skill. This is the ANALYSIS phase only — no spec, no code, no tasks produced.
---

# Feature Analysis Skill (`/ktkit:analyze-feat`)

## Purpose

Produce a crisp, actionable analysis of a feature requirement so you and the user deeply understand:

1. **What** the feature actually is (clarified, not assumed)
2. **What** existing code will change and how
3. **What** net-new code needs to be created
4. **Which** execution flows / processes are affected and at what risk level
5. **What** open questions or blockers remain before speccing or building

This is **pure analysis**. Output = structured report. Not a spec, not tasks, not code.

---

## Phase 0: Preflight + Memory + Input

### 0 — Preflight

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py" \
  --groups artifacts --repo "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
```

Creates `<repo-root>/.claude/claude/{prompts,analyze,specs,pipeline,implemented,compacts}` when the
repository does not have them, so Phase 6 has somewhere to write. That layout is a rule of this
plugin, not a discovery: never probe for an alternative, never ask, and never write outside
`<repo-root>/.claude/`. Exit 1 → STOP and report; no source file has been opened yet.

Then two things happen in parallel, still before touching any source files.

### 0a — Parse Input

| Input form | Action |
|---|---|
| Inline text | Read directly |
| File path / `.md` file | `Read` tool, extract requirement sections |
| GitHub issue URL | `mcp__plugin_github_github__issue_read` |
| GitHub PR URL | `mcp__plugin_github_github__pull_request_read` |
| Vague / partial | Go to Phase 1 first |

### 0b — Memory Check (optional, run in parallel with 0a)

Search cross-session memory for prior decisions before asking the user anything:

```
mcp__memory__search_nodes({query: "<feature keywords>"})
mcp__plugin_claude-mem_mcp-search__smart_search({query: "<feature concept>"})
```

**If prior analysis/decisions found** → surface them up front:
> "Found prior context: [summary]. Still applies or has this changed?"

**If nothing found** → proceed silently.

**Tools absent** → skip and proceed silently as well. This plugin ships neither memory server: they
hold durable state, and a second copy would split the user's own. An empty search here means "not
looked up", never "nothing exists".

This prevents asking the user to re-explain decisions already made.

### 0c — Decision log (run before anything else in Phase 1)

If the repo keeps a decision log for this work — by convention
`.claude/context/decisions/<slug>.md` — **read it now**.

Every question already carrying an ID there is **settled**. ⛔ Do not ask it again, and ⛔ do not
decide it again: quote the existing entry into report §10 as already-decided and move on.
Re-deciding a logged question silently overwrites a decision somebody made on purpose.

No log, or no matching entry → proceed.

---

## Phase 1: Resolve Requirements (⛔ do not ask yet)

**Invoke skill `/ktkit:escalation-ladder` and follow it.** Every dimension that is not settled by the stack
profile below is an *unknown*, and an unknown goes through the ladder — T1 search, T2 challenge,
T3 lookup, T3.5 evidenced assumption — **before** anybody considers asking the user.

⛔ **This phase asks the user nothing.** What survives the ladder as genuine T4 becomes a candidate
row in report §10, batched into a single gate downstream — it does not stop this phase.

Do the searching by **dispatching `Agent(subagent_type: "ktkit:escalation-resolver")`, one question per
call**, several in one message when they are independent. ⛔ Do not open the files yourself: lead
context is re-sent every turn, and touching a source file also pulls in the repo's auto-loaded
conventions.

**Before asking, derive the stack from the ACTIVE repo — never from memory.** This skill is repo-agnostic: it runs against whichever repository is open, so it must not carry any repo's stack names in its own text.

**Step 1a — build the stack profile** (do this once, before any question):

1. Read the repo's context file — `CLAUDE.md` at the repo root, plus a directory-scoped one if the feature lives under a path that has its own.
2. Extract only what could change a design decision: runtime/framework per layer, state management, data store, auth mechanism, transport (HTTP / WebSocket / queue / batch), and **any place the repo offers more than one option** (two backends, two stores, two auth systems, two channels…).
3. Each "more than one option" found is a **fork** — a place where the requirement must pick a side. Forks are the highest-value questions; a dimension with exactly one option answers itself.

**Fallback when the repo has no context file**: do not assume a stack. Detect what you can from manifests (`package.json`, `*.csproj`, `*.sln`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `docker-compose.yml`) plus the top-level directory layout, state what you inferred as an explicit assumption in report §4, and fall back to asking the 5 dimensions below.

**5 dimensions to probe when the stack profile does not settle them:**

1. **Entry point** — What triggers this? User action, API call, WebSocket event, cron?
2. **Scope boundary** — What is explicitly OUT of scope?
3. **Data contract** — What flows in, out, persisted? New DB schema needed?
4. **Success condition** — How does the user know it works? Observable behavior?
5. **Constraints** — Auth? Rate limits? i18n? Backward compat? Offline mode?

**Skip Phase 1** only when ALL 5 can be inferred without ambiguity:

| Dimension | Skip if... |
|---|---|
| Entry point | Requirement explicitly states the trigger (e.g., "user clicks X button"), or the stack profile shows exactly one transport |
| Scope boundary | Requirement lists what's out of scope, or scope is obviously implied |
| Data contract | Input/output/persistence fully described with field names |
| Success condition | Observable, measurable outcome stated (not vague like "works correctly") |
| Constraints | Auth/rate/compat requirements stated OR provably irrelevant from context |

If a dimension is still ambiguous after the table → **it does not become a question yet.** Run it
through the ladder:

| Ladder outcome | Where it lands |
|---|---|
| Resolver found it in the repo (T1/T2) | report §10 table **A** — settled, with `file:line` |
| Only resolvable outside the repo (T3) | report §10 table **A**, or `Undecided` if the three portable steps fail — ⛔ never a question |
| Ambiguous, one reading better evidenced, cheap if wrong (T3.5) | report §10 table **B** — assumption + **falsifier** + blast radius |
| Genuinely undecidable and expensive if wrong (T4) | report §10 table **C** — max 3 rows, each with a default |

State every inferred dimension as an explicit assumption in report §4 as before.

---

## Phase 2: Codebase Orientation (GitNexus First)

GitNexus graph gives execution flow context in ~200 tokens vs thousands for source reading. Always exhaust graph tools before opening files.

### Step 2a — Discover repo + check index freshness
```
READ gitnexus://repos                       → get repo name for this project
READ gitnexus://repo/{name}/context         → check index freshness, get codebase overview
```
Stale index → tell user to run `npx gitnexus analyze`, fall back to Grep.

### Step 2b — Find relevant execution flows
```
gitnexus_query({query: "<feature concept in 2-4 words>"})
```
Run 2–3 queries if feature spans multiple domains. Collect **process names** and **symbols**.

### Step 2c — Deep dive key symbols
```
gitnexus_context({name: "symbolName"})
```
Callers, callees, process participation — all from graph. No file read needed.

### Step 2d — Trace the most relevant flow
```
READ gitnexus://repo/{name}/process/{processName}
```
Trace only 1–2 flows most directly related. Skip peripheral flows.

### Step 2e — Explore functional clusters (when feature spans subsystem)
```
READ gitnexus://repo/{name}/clusters         → all functional areas
READ gitnexus://repo/{name}/cluster/{name}   → members + file paths
```
Use instead of `gitnexus_group_query` (that tool does NOT exist).

### Step 2f — API surface (for backend/route changes)
```
gitnexus_route_map({...})    → existing API route inventory
```
Use when feature adds or modifies REST/WebSocket endpoints.

### Step 2g — Git recency check (always run, cheap)

Surface files being actively modified before analysis — avoids reasoning from stale context:

```bash
git log --oneline -20 -- <relevant-path>
```

Run for each directory the feature will likely touch — derive those directories from the Phase 1 stack profile and the Phase 2 graph hits, not from a fixed list. If a file shows commits in the last 3–5 days → flag it in the report as "actively changing — coordinate before modifying."

### Step 2h — External library docs (Context7, conditional)

Trigger **only** when the feature involves behavior of an external library that can't be inferred from existing usage in the codebase:

```
mcp__plugin_context7_context7__resolve-library-id({libraryName: "<lib>"})
→ mcp__plugin_context7_context7__query-docs({context7CompatibleLibraryID: "<id>", topic: "<specific behavior>"})
```

**Trigger conditions** (any one = use Context7):
- Feature introduces a lib not yet in the codebase (e.g., new Socket.io feature, new Bull job type)
- Existing lib behavior differs from what the codebase assumes (version upgrade path)
- Feature relies on edge-case API behavior not visible from current usage patterns

**Do NOT use** just because a lib is mentioned — if the codebase already uses it and patterns are visible via Grep/Peek, that's enough.

**Token budget Phase 2: ≤ 2,000 tokens total** (Context7 cost is additive — use sparingly).

---

## Phase 3: Iterative Source Exploration

Three-step pattern. Never skip to Full Read — always start from Scan.

### Step 3a — Scan (find candidates, ~0 tokens per file)

Locate relevant symbols before opening anything:

```
Grep(pattern: "export class BolService|export function generatePdf", type: "ts")
```

Identifies which files are worth peeking, without reading them.

### Step 3b — Peek (confirm relevance, ~350 tokens / ~50 lines per file)

For each candidate, grep top-level declarations:

```
Grep(
  pattern: "^export (class|function|interface|type|const)",
  path: "src/foo/foo.service.ts",
  output_mode: "content",
  head_limit: 50
)
```

This surfaces the module's public contract without reading the body. A senior dev judges file relevance from this alone.

**When Peek is enough**: GitNexus gave you callers/callees, and Peek confirms the interface. Body logic not needed for impact analysis.

### Step 3c — Full Read (only confirmed edit targets, ~500–2,000 tokens per file)

Read a file in full ONLY when ALL three are true:
- GitNexus already confirmed this file will be modified
- Business logic or data flow details required (not just structure)
- Peek showed relevant section is deeper than visible declarations

Use `offset` + `limit` when target line is known from GitNexus context.

**Hard cap: 3 files in Full Read.** Need more → use Phase 4 group exploration instead.

### When to go Full Read immediately (skip Scan/Peek)

| Situation | Reason |
|---|---|
| Confirmed direct edit target | Need adjacent code context to avoid breaks |
| Complex pipeline (PDF gen, WebSocket action processing, queue jobs) | Intent buried in body, not signatures |
| Global state / module-level side effects | Missing init code causes runtime errors |
| Refactoring task | Must see all usages within file |

---

## Phase 4: Blast Radius

### Option A — Cluster exploration (default, cheap)

For features affecting 1–2 subsystems:

```
READ gitnexus://repo/{name}/clusters          → see all functional areas
READ gitnexus://repo/{name}/cluster/{name}    → all symbols + relationships in area
```

Sequential cluster reads share context from prior steps. No agent overhead.

### Option B — Symbol-level impact (when you know the target symbol)

```
gitnexus_impact({
  target: "symbolName",
  direction: "upstream",
  minConfidence: 0.7,
  maxDepth: 3
})
```

### Option C — Git-diff based (feature already partially started)

```
gitnexus_detect_changes({scope: "all"})
```

### Option D — Custom graph query (complex dependency trace)

```
gitnexus_cypher({query: "MATCH (a)-[:CALLS*1..3]->(b {name: 'targetFn'}) RETURN a, b"})
```

### Risk Classification

Criteria are **structural**, not stack-specific — they hold in any repo. Where a row names a concern (auth, routing…), resolve it to whatever that concern is called in the active repo's stack profile.

| Criteria | Risk Level |
|---|---|
| Adds new files only, no existing code touched | LOW |
| 1–4 symbols modified, ≤2 flows affected | LOW–MEDIUM |
| 5–15 symbols, 3–5 flows, or touches shared utilities | MEDIUM–HIGH |
| Touches a cross-cutting concern: auth/permission, routing, global state, or any layer every feature depends on | HIGH |
| >15 symbols, **or** touches a critical-path process — one where a wrong result is silent, unrecoverable, or corrupts persisted data (identify these from the repo's own flows, do not assume) | CRITICAL |

**Scale note (do not flatten)**: this skill uses a 5-band scale. Downstream `bug-fix-specs` / `feat-req-specs` use a 4-band scale without the hyphenated bands. The merged order is:

```
LOW  <  LOW–MEDIUM  <  MEDIUM  <  MEDIUM–HIGH  <  HIGH  <  CRITICAL
```

Downstream steps gated at "risk ≥ MEDIUM" therefore trigger on `MEDIUM–HIGH`, `HIGH`, `CRITICAL` from this skill — and not on `LOW` or `LOW–MEDIUM`. Report the band verbatim in §8 so the downstream skill can compare without re-deriving.

---

## Phase 5: Parallel Agents (Opt-In Only)

Parallel agents cost 2,000–5,000 tokens in warmup alone. Use only when BOTH are true:

1. Feature touches **3+ truly independent subsystems** (no shared context between explorations)
2. User explicitly wants deep dive OR feature is HIGH/CRITICAL risk

For everything else, sequential cluster reads (Phase 4, Option A) give equivalent coverage at fraction of cost.

**Decision rule:**

```
if subsystems <= 2 OR subsystems share context:
    → sequential cluster reads (Phase 4A)
else if user wants speed AND risk >= HIGH:
    → parallel Explore agents, one per independent subsystem
```

**Worth it for**: Race conditions, cross-layer security analysis, features restructuring multiple independent modules simultaneously.

---

## Phase 6: Write + Save the Analysis Report

> **Language**: the whole of `.claude/claude/analyze/<filename>.analyze.md`, and the summary printed
> to chat in 6c, are written in **Vietnamese**. Technical terms, code snippets, file paths, symbol
> names and technical names (kebab-case, camelCase and so on) stay exactly as they are — only the
> descriptive prose is Vietnamese.

### 6a — Determine output path

Resolve in this priority order:

**1. User specified an explicit output path** → use it verbatim. Stop here.

**2. Input came from a base file under `.claude/claude/prompts/`** (the normal case — the user points
at `.claude/claude/prompts/<rel-dir>/<name>.md` and asks for it to be read closely) → MIRROR its
sub-path into `.claude/claude/analyze/`:

| Var | Definition |
|---|---|
| `<rel-dir>` | `dirname(<base-file>)` relative to `.claude/claude/prompts` — may be empty |
| `<base-name>` | `basename(<base-file>)` minus the trailing `.md`; if what remains still ends in `.prompt`, drop that too |

Output: `.claude/claude/analyze/<rel-dir>/<base-name>.analyze.md` — `mkdir -p` the dir if missing.

```
base    .claude/claude/prompts/2472-2473-preview-edit-office-files/stage-developer/phase3-license-infra.md
→       .claude/claude/analyze/2472-2473-preview-edit-office-files/stage-developer/phase3-license-infra.analyze.md
```

**Keep the base filename verbatim** — do NOT re-slugify, shorten, or prepend `feat-`/`bug-`. The folder tree under `analyze/` must mirror `prompts/` exactly so the downstream chain (`analyze/` → `specs/` → `pipeline/`) stays aligned.

If the base file lives outside `.claude/claude/prompts/`, mirror is not possible → fall through to rule 3 and state the chosen path to the user.

**3. No base file** (feature described directly in chat) → `.claude/claude/analyze/<short-feature-name>.analyze.md` (flat):
- kebab-case, max 5 words, derived from feature name (shape: `<verb-or-domain>-<object>-<qualifier>`)
- Create `.claude/claude/analyze/` if missing

**This file is the handoff artifact.** `/ktkit:feat-req-specs` and `/ktkit:bug-fix-specs` will read it as primary input. Write it as if future-Claude has zero context from this conversation — every decision, assumption, and risk must be explicit.

### 6b — Report template

Write EXACTLY this structure. Omit a section only when it genuinely has no content. Do NOT compress or summarize to save space — this file is meant to be thorough.

```markdown
# Feature Analysis: [Feature Name]
> **File**: `.claude/claude/analyze/<rel-dir>/<base-name>.analyze.md`
> **Base file**: `.claude/claude/prompts/<rel-dir>/<base-name>.md` (omit if none)
> **Date**: YYYY-MM-DD
> **Risk Level**: LOW / MEDIUM / HIGH / CRITICAL
> **Suggested next skill**: `/ktkit:feat-req-specs` | `/ktkit:bug-fix-specs` | `/feature-dev`

---

## 1. What This Feature Does
[3–5 sentences. Plain language. What user problem does it solve? What does the user experience before vs after? Why does this feature exist now?]

## 2. Assumptions Made
[Every assumption where requirement was ambiguous. Future-Claude must know these to write a correct spec. Omit section only if zero assumptions.]
- **[Assumption label]**: [what was assumed and why]
- ...

## 3. Prior Context Found
[Decisions, patterns, or prior analysis from memory check. Omit if nothing found.]
- [Source: memory/claude-mem] [Decision / pattern]

## 4. Tech Stack Context (stack profile — Phase 1 Step 1a)
[The rows below are DERIVED from the active repo's context file, not from a fixed list. Emit one row per layer this feature actually touches; drop layers it does not. Name the real components of THIS repo.]

- **Repo**: [repo name] — profile source: [`CLAUDE.md` path(s) read, or "inferred from manifests — see Assumptions"]
- **[Layer]**: [component chosen] — [why, if there was a fork]
- ... one row per touched layer (UI / API / domain / persistence / transport / auth / jobs / infra — whatever this repo actually has)
- **Forks resolved**: [each place the repo offered >1 option and which side this feature picks]
- **External libs involved**: [list any, with Context7 findings if applicable]

## 5. What Needs to Be Built (Net New)
[Every file, component, API, schema, table that does NOT exist yet. Be specific — future-Claude will use this to scope implementation.]
- `path/to/new/file.ts` — [what it does, why net-new and not extending existing]
- New DB table/column: `[name]` — [schema, purpose]
- New API endpoint: `METHOD /path` — [request/response contract]
- New WebSocket event: `[event-name]` — [payload shape, direction]

## 6. What Needs to Change (Existing Code)
[Every existing file/symbol that must be modified. Include file:line from actual reads.]

| File | Symbol / Line | Change Required | Blast Depth |
|------|--------------|-----------------|-------------|
| `src/foo/bar.ts:42` | `functionName` | Add param X, update return type | d=1 |
| `src/routes/index.ts` | route registry | Register new route `/api/v1/x` | d=2 |

## 7. Affected Execution Flows
[Every GitNexus process / execution flow that changes. Describe WHICH step in the flow changes and HOW.]
- **[FlowName]** (`gitnexus://...process/FlowName`): Step 3 "validate action" must now also check [X] before proceeding
- **[FlowName]**: New branch added after step 2 — triggers [Y] when condition Z

## 8. Blast Radius
**Risk Level: [LOW / MEDIUM / HIGH / CRITICAL]**

**Reason for this level**: [1–2 sentences explaining why, citing specific flows/symbols]

Direct (d=1 — WILL BREAK if not updated):
- `symbolName` → `file:line` — [why it breaks]

Indirect (d=2 — likely affected, must test):
- `symbolName` → `file:line` — [what behavior changes]

Actively changing files (git recency — coordinate before touching):
- `path/to/file` — last commit: [date/hash] — [who/what changed it]

## 9. Architecture Notes
[Patterns to follow, constraints to respect, gotchas to avoid. Future-Claude must read this before designing anything.]
- **Follow pattern**: [pattern X] as seen in [`reference/file.ts:line`] — [why this pattern applies]
- **Must respect**: [constraint] — [reason, consequence if violated]
- **Reuse opportunity**: [existing util/hook/service] at [`path:line`] already handles [X] — extend don't recreate
- **Watch out for**: [specific gotcha] — [what goes wrong if ignored]

## 10. Unknowns — triaged by the ladder
[Every unknown this analysis met, in exactly one of the three tables. An unknown with no `Tier` is a
search that stopped early. If a table is empty, keep the heading and write `none`.]

### A. ✅ Settled without the user (T1 / T2 / T3)
| Question | Tier | Conclusion | Evidence (`file:line`) |
|---|---|---|---|

### B. 🟡 Assumptions taken (T3.5)
| ASM | Reading chosen | Evidence | Falsifier | Blast radius |
|---|---|---|---|---|
[⛔ An empty Falsifier is not an assumption, it is a preference — send it back to T1 or up to T4.]

### C. ⛔ Needs a decision (T4) — **max 3 rows**, silence accepts the default
| # | Question | Default applied | Recommendation | Cost if wrong | Where it changes |
|---|---|---|---|---|---|
[Every row must tick all 6 T4 preconditions from `/ktkit:escalation-ladder`. More than 3 candidates ⇒ do
NOT list them all: report one row `N ambiguities of the same kind` with three representatives.]

### Decision-log entries reused (from Phase 0c)
| D-ID | Question | Decision already on record |
|---|---|---|

## 11. Files Read During Analysis
[Exact files read in Phase 3, with line ranges. Lets future-Claude verify freshness.]
- `path/to/file.ts` (lines 1–120, Full Read) — [what was learned]
- `path/to/other.ts` (Peek only) — [relevance confirmed/rejected]

## 12. Suggested Next Step
→ **`/ktkit:feat-req-specs`** — if open questions resolved and risk is LOW/MEDIUM: feed this file as input
→ **`/ktkit:feat-req-specs`** — if HIGH risk: include blast radius section prominently in the interview
→ **`/ktkit:bug-fix-specs`** — if this analysis reveals a bug rather than a feature
→ **`/feature-dev`** — if architecture section has unresolved design options
→ **Team discussion first** — if CRITICAL risk: do not spec until blast radius is reviewed

## 13. Self-Audit
[Written by Phase 6.5. Findings about THIS report, not about the codebase. If a pass found nothing, say so — do not omit the pass.]

| ID | Pass | Severity | Location | Finding | Fix applied |
|----|------|----------|----------|---------|-------------|
| U1 | Underspecification | HIGH | §6 row 2 | "update the handler" names no symbol | Resolved to `file.ts:88 handleX` |

**Metrics**: assumptions §2: N · net-new items §5: N · changed items §6: N · files actually read §11: N · unresolved findings: N

**Escalation metric** (last line of the report file, exactly this shape):

```
self_resolve_ratio=0.88 · self_resolved=7 · needs_user=1 · assumptions=1 · gates=0
```

`self_resolve_ratio = self_resolved / (self_resolved + needs_user)` where `self_resolved` = rows in
§10 table A and `needs_user` = rows in §10 table C, two decimals. `gates=0` because this skill opens
no gate — the single gate lives downstream.
```

### 6.5 — SELF-AUDIT (mandatory, before 6c)

> Source: 6 detection passes adapted from `speckit.analyze` (snapshot 2026-08-24). Internalised on purpose — `speckit.analyze` compares `spec.md` × `plan.md` × `tasks.md` and refuses to run before `tasks.md` exists; this skill runs before any of them. Same passes, different target: **the report you just wrote**.

Re-read the file you just saved and run these 6 passes over it. This catches the failure mode where each section is individually plausible but the document as a whole contradicts itself — the exact defect that survives into the spec.

| Pass | Question asked of the report |
|---|---|
| **Duplication** | Does the same item appear in both §5 (net-new) and §6 (changed)? Two §6 rows describing one edit? |
| **Ambiguity** | Vague adjectives without a measure ("fast", "robust", "properly"). Unresolved `TODO` / `???` / `<placeholder>`. A §6 "Change Required" cell that names no symbol |
| **Underspecification** | §5 or §6 entry with no file path. §7 flow naming no step. §8 risk with no cited symbol. §9 "follow pattern X" with no reference location |
| **Assumption/Question coherence** | Does an §2 assumption silently answer an §10 open question? Then it is not open — resolve or downgrade it. Does an §10 question invalidate an §2 assumption? Then the assumption is unsafe |
| **Coverage gaps** | Every §6 changed symbol appears in §8 blast radius (or §8 says why not). Every §11 file read is actually cited somewhere. Every §5/§6 item traces to a requirement in §1 — an item tracing to nothing is scope creep |
| **Risk consistency** | Does the §8 band follow from the structural criteria given the actual §6/§7 counts? A band asserted without matching evidence is the most consequential defect in the whole report — it gates downstream steps |

| **Escalation discipline** | Does every §10 row carry a `Tier`? Does every table-C row tick all 6 T4 preconditions and carry a non-empty Default **and** Recommendation? Does every table-B row carry a non-empty Falsifier? Is `self_resolve_ratio ≥ 0.70`? Is table C at most 3 rows? Any "no" is a **CRITICAL** finding: ⛔ do not save the report — go back to T1, dispatch more resolvers, and re-audit |

**Severity**: `CRITICAL` = the report would send the spec down a wrong path · `HIGH` = a decision cannot be made from what is written · `MEDIUM` = ambiguity that survives to implementation · `LOW` = wording.

**Act, do not just log**: fix `CRITICAL` and `HIGH` findings **in the report file now** — that is the point of auditing before handoff. Record each in §13 with what was changed. Leave a finding unfixed only when fixing it needs information you do not have — and even then it does
not automatically become a user question: run it through `/ktkit:escalation-ladder` and record it in §10
table A, B or C according to what the ladder decides. Say so in §13.

Cap at 20 findings; if more, keep the highest severity and note the overflow count.

### 6c — After saving, output summary to chat

Print to conversation (NOT the full report — just the handoff summary):

```
## Analysis Complete

**Feature**: [name]
**File saved**: `.claude/claude/analyze/<rel-dir>/<base-name>.analyze.md`
**Risk Level**: LOW / LOW–MEDIUM / MEDIUM–HIGH / HIGH / CRITICAL
**Key findings**:
- [1 sentence on most important existing code impact]
- [1 sentence on biggest risk or open question]
**Self-audit**: [N findings, M fixed in-place / "clean"]

**Next**: Run `/ktkit:feat-req-specs` and point it at `.claude/claude/analyze/<rel-dir>/<base-name>.analyze.md`
(it will mirror the same `<rel-dir>` into `.claude/claude/specs/`)
```

---

## Rules

**Do:**
- State assumptions explicitly in the report
- Cite specific file paths and line numbers you actually read
- Distinguish net-new code vs changed code — different risk profiles
- Surface reuse opportunities ("this pattern already exists at X")
- Give honest risk levels — don't downgrade to avoid concern

**Do not:**
- Write a spec, acceptance criteria, user stories, or tasks
- Write any implementation code
- Use shell `grep`/`sed`/`find` — use `Grep`, `Read(limit/offset)`, `Glob` instead
- Use `Bash` except for system commands (`npx gitnexus analyze`, `git log`) with no native tool equivalent
- Call `gitnexus_group_query` or `gitnexus_group_list` — **these tools do not exist**
- Read a file in full before exhausting GitNexus graph + Peek
- Spawn parallel agents when sequential cluster reads suffice
- **Name any framework, store, service, channel or auth system that you have not seen in THIS repo** — this skill is shared across repos. Every stack name must come from the Phase 1 stack profile (repo `CLAUDE.md` / manifests), never from this skill's own text and never from memory of another project
- Skip Phase 6.5 — a report that has not been self-audited is not finished

---

## Token Budget

| Phase | Tool | Cost | When |
|---|---|---|---|
| 0b — Memory | `mcp__memory__search_nodes` + `claude-mem smart_search` | ~300 | Always |
| 2 — Graph | `gitnexus_query/context/process/clusters` | ~2,000 | Always |
| 3a — Scan | `Grep` for exports | ~0 | Always |
| 3b — Peek | `Grep` top-level, head_limit: 50 | ~350/file | Before Full Read |
| 3c — Full Read | `Read` with offset/limit | ~500–2,000 | Max 3 files |
| 4 — Impact | `gitnexus_impact` or cluster reads | ~1,000 | Always |
| 5 — Agents | Parallel `Explore` agents | ~5,000+ | Opt-in only |
| 6.5 — Self-audit | Re-read own report, no new tool calls | ~600 | Always |
| Context7 | Library docs lookup | Variable | External lib behavior only |
| LSP | TypeScript diagnostics/type info | ~200 | When type conflicts suspected |

**Target totals:**
- Small feature (1 layer, 1 backend): ~3,500 tokens
- Medium feature (2 layers, cross-stack): ~6,000 tokens
- Large feature (3+ layers, real-time sync): ~9,000 tokens (no agents)

---

## Example Workflow (shape only — placeholders are NOT real names)

Every `<…>` below is a placeholder to be replaced by whatever the **active repo** actually contains. This section demonstrates the *sequence and token discipline*, never a stack.

**Requirement**: "Export `<entity>` list to `<format>`"

```
Phase 0:
  Read requirement inline
  mcp__memory__search_nodes({query: "<entity> export <format>"})   → prior work? 
  claude-mem smart_search({query: "export download"})              → prior work?

Phase 1:
  Step 1a — read repo CLAUDE.md → build stack profile, list the forks
  Ask ONLY the unresolved forks + any of the 5 dimensions still ambiguous
  User answers → proceed

Phase 2:
  gitnexus_query({query: "<entity> export download"})     → is there an existing export flow?
  gitnexus_query({query: "<entity> data access"})         → which layer owns the data
  gitnexus_context({name: "<symbol from the hits>"})      → callers, callees, flows
  READ gitnexus://repo/<repo>/clusters                    → is there an "export" area already?
  READ gitnexus://repo/<repo>/cluster/<closest-area>      → members + file paths

Phase 3:
  Scan: Grep for the export/serialise symbols the graph pointed at
  Peek: Grep("^export|^public |^def ", path: "<candidate>", head_limit: 50)
  Full Read: <the one file confirmed as the edit target> — max 3

Phase 4:
  gitnexus_impact({target: "<data-access symbol>", direction: "upstream"})
  READ gitnexus://repo/<repo>/cluster/<adjacent-area>

Phase 5: Skip unless 3+ independent subsystems AND risk ≥ HIGH

Phase 6:   Write report → assign risk from the structural criteria, cite the evidence
Phase 6.5: Self-audit the report before summarising
```

---

## Unknown handling (bindingly, before any question reaches the user)

Whenever anything in this analysis is unknown — a term that cannot be found, two sources
disagreeing, a sentence with two readings, a fact about a library — **invoke skill
`escalation-ladder`** and follow it.

The searching itself is delegated: **`Agent(subagent_type: "ktkit:escalation-resolver")`, one question per
call**, several in one message when independent. ⛔ The lead does not open files; it holds the
question, the `Tier`, and a one-line conclusion with its citation.

⛔ No question reaches the user before the ladder has run. Every unknown gets a `Tier` written into
report §10. The report's last line carries the escalation metric; `self_resolve_ratio < 0.70` means
tiers 1–3 were not exhausted — go back to T1 and ⛔ do not save the report.

**Fallback** — `/ktkit:escalation-ladder` ships with this plugin, so it is present wherever this
skill is. If it somehow cannot be loaded, use `## Unknown handling — inline fallback` below. ⛔ A
missing skill is never a reason to go back to asking the user.

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
  expensive or hard to reverse ⇒ user. Max 3 rows, each with a default (silence accepts it) and a
  recommendation.

Leap a tier only by proving the one below is exhausted — never because it looks hard. Four things
stop the run outright: an irreversible or destructive operation, a security-sensitive action, a side
effect outside this workspace (merge, push to a shared branch, publish), or a plan so broken every
path forward is a guess. Everything else is a ruling: record
`Ruling: <what you decided> — <why> — <what it costs if wrong>` and keep going.
