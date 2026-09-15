---
name: bug-fix-specs
description: "Use when a bug has been through /ktkit:rca and the fix plan needs reviewing BEFORE any code changes. Reads the .analyze.md that skill wrote — it does not investigate again — and writes fix.md under .claude/claude/specs/<rel-dir>/<base>/, with a quality checklist it grades itself against. No speckit: the BUG lane runs on superpowers:systematic-debugging, and a bug is a disagreement with a specification that already exists rather than a reason to write another. STOPS and waits for user approval. Hand off to /ktkit:bug-fix-execute."
---

# Bug-Fix Specs Workflow


> ⛔ **Not an entry point.** `/ktkit:chain` runs this as phase 03 of the BUG lane, and
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
> /ktkit:chain <file> --bug
> ```
>
> This banner is the whole of the deprecation for now. The skill is removed as a
> user-facing entry point in a later release; nothing is being taken away today.

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

Whenever this workflow produces **open questions,
assumptions, ambiguity findings or recommendations**:

- **Write in Vietnamese**: every question, assumption label, rationale, severity description and
  recommendation shown to the user.
- **Keep in English**: file paths, function/symbol/class names, flags, API names, original error
  messages, stack traces, code snippets, and technical terms with no settled translation
  (e.g. "race condition", "blast radius", "off-by-one", "null deref").
- Applies **in reasoning as well as in the final output** shown to the user.
- Fix plan content (`fix.md`) follows the template it came from — never translate headers or
  keywords.

Why: the reviewer reads in Vietnamese, so prose in Vietnamese removes friction while the identifiers
stay exact.

---

## Pipeline (Sequential — Do Not Skip Steps)

### STEP 0a — PREFLIGHT (runs before anything is spent)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py" \
  --groups artifacts,mcp --repo "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
```

⛔ **No `speckit` group, and that is the point.** The BUG lane does not touch spec-driven
development: a bug is a disagreement with a specification that already exists, and writing a second
one to describe the disagreement produces a document that has to be kept true, while the failing
test from `/ktkit:rca` Step 3.9 says the same thing and cannot drift. The lane contract
`/ktkit:chain` publishes says so; this skill is where it becomes true.

The investigation itself runs on `superpowers:systematic-debugging`, and it has already happened —
in `/ktkit:rca`, once. This skill does not repeat it, so it does not need that group either.

**Exit 1 → STOP.** Print what is missing and the command that fixes it. Nothing has been spent.

**Exit 0 → continue.** Optional capabilities that are absent are named with their exact
consequence, never silently worked around.

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

### STEP 1 — READ THE ANALYSIS. DO NOT INVESTIGATE AGAIN.
> Goal: start from what `/ktkit:rca` already established, and add nothing to it

⛔ **One bug, one investigator.** This skill used to re-run `gitnexus_query`, a reproduction, an
impact query and a 5 Whys — every one of them a step `/ktkit:rca` had just finished. On the BUG
lane the chain runs both, so the whole investigation was paid for twice and the second pass could
disagree with the first with nothing to say which was right.

**Input**: the `.analyze.md` written by `/ktkit:rca`, carrying `type: bug-analysis` and
`status: rca-complete` in its frontmatter.

Read from it, and take these as settled:

| From the analysis | Used for |
| ----------------- | -------- |
| Root Cause + Location | what the fix has to change |
| Evidence Chain (the 5 Whys) | why that is the cause, quoted rather than re-derived |
| Blast Radius | the risk level that gates STEP 4.7 |
| Hypothesis & Minimal Experiment | the failing test `/ktkit:bug-fix-execute` must see red first |
| Defence in depth, when present | the layers STEP 6.2 of the execute skill will guard |

⛔ **No analysis file ⇒ STOP.** Say exactly this and wait:

```
⛔ /ktkit:bug-fix-specs — stopped before STEP 1

  No .analyze.md with `status: rca-complete` for this bug.

  Run `/ktkit:rca <bug-report>` first. That skill owns the investigation:
  it runs superpowers:systematic-debugging Phases 1-3 and leaves a failing
  test this skill's fix is written against.

  Nothing ran. No tokens spent on any step.
```

Investigating here instead would be the same work under a different name, done with less of the
method — which is worse than stopping.

⛔ **Do not "verify" the root cause by re-deriving it.** If you believe the analysis is wrong, say
which line of its Evidence Chain you disbelieve and stop; do not quietly produce a second answer.

---

### STEP 2 — WRITE THE FIX PLAN
> Goal: one reviewable document saying what will change and why, before any code moves

**One way to write it, and the artifact is `fix.md`.**

```
.claude/claude/specs/<rel-dir>/<base>/fix.md
.claude/claude/specs/<rel-dir>/<base>/checklists/bugfix.md
```

⛔ **`fix.md`, not `spec.md`.** A specification says what a system should do; this document says what
is wrong with one and what will change. Calling it a spec put a second, thinner specification beside
the real one, and the next reader had no way to tell which was authoritative.

*Migration*: `fix.md` absent but `spec.md` present in that same directory ⇒ read the `spec.md`, and
⛔ **do not edit it and do not rename it.** Same rule the legacy-spec case already follows: an old
file is left exactly as it is, and the new rule applies to new work.

1. Resolve `<rel-dir>` and `<base>` by the priority order below, and run the collision check.
2. `mkdir -p` the feature directory and its `checklists/`.
3. Write `fix.md` covering the sections listed at the end of this step. Root Cause, Evidence Chain
   and Blast Radius are **quoted from the analysis**, not re-derived; cite the analysis path.
4. Write `checklists/bugfix.md` yourself — the quality loop is the only always-on gate in this
   workflow. Items test **this document**, not the running system; the rules for writing them are in
   STEP 4.7, which applies here verbatim.
5. Grade `fix.md` against that checklist and fix every failure you can fix. What you cannot fix
   becomes an Open Question in the document.

⛔ **No feature pin here.** `scripts/speckit_pin.py` exists so a script-backed speckit skill resolves
the right directory. Nothing on this lane runs one — `/ktkit:bug-fix-execute` states outright that it
needs no speckit — so pinning was a rite with nothing on the other end of it.

> **Language**: the whole document is written in **Vietnamese**. Code snippets, file paths, symbol
> names and technical names (kebab-case, camelCase and so on) stay exactly as they are — only the
> descriptive prose is Vietnamese.

**ALWAYS write to a NEW file** under `.claude/claude/specs/`. NEVER modify the original bug report or
analyze file provided by the user.

#### The `<base>` is a FOLDER, not a filename

One bug = one folder. Everything it produces lives inside it, under fixed filenames, so every
later step finds them by construction rather than by searching:

```
.claude/claude/specs/<rel-dir>/<base>/fix.md           ← this step writes this
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
→ fix    .claude/claude/specs/2474-share-files/bug-share-link-expired/fix.md

analyze  .claude/claude/analyze/2410-keep-user-preference/no-render-department-data.analyze.md
→ fix    .claude/claude/specs/2410-keep-user-preference/no-render-department-data/fix.md
```

*(A `bug-` already present inside `<base>` stays — it is part of the name, not a prefix this step adds.)*

If the base file is a raw bug report under `.claude/claude/prompts/` (RCA step skipped), same rule with the root swapped.

**Keep `<base>` verbatim** — do NOT re-slugify, shorten, reorder words, or strip a layer suffix.

**3. No base file** (bug reported directly in chat) → `<rel-dir>` empty, `<base>` = kebab-case symptom description → `.claude/claude/specs/<base>/fix.md`.

#### Collision check — MANDATORY before writing

The `feat-` / `bug-` prefix used to keep a feature and a bug of the same name apart (`feat-X.spec.md` vs `bug-X.spec.md`). Without it, both resolve to the **same folder** `<rel-dir>/<base>/`. The artifacts no longer collide -- a feature writes `spec.md`, a bug writes `fix.md` -- but `checklists/` is shared, so the check below still runs. This is a real shape in practice — sub-folders such as `<feature>/bugs/` already exist.

Before `mkdir`/write, check whether `.claude/claude/specs/<rel-dir>/<base>/fix.md` already exists:

- **Does not exist** → proceed.
- **Exists** → STOP and ask, do not guess:
  ```
  Fix plan đã tồn tại: .claude/claude/specs/<rel-dir>/<base>/fix.md
  (u) update — ghi đè spec cũ, giữ nguyên checklists/
  (n) new — đặt <base> khác, nhập tên
  (a) abort
  ```
  Wait for the answer. On `u`, overwrite `fix.md` **only** — never delete or rewrite anything under `checklists/`.

### STEP 4.6 — RESOLVE, THEN (MAYBE) ASK
> Goal: tighten the spec by **resolving** what is unclear, not by interviewing the user

**Invoke skill `/ktkit:escalation-ladder` and follow it for this whole step.** Each item below is an
*unknown*: it goes T1 → T2 → T3 → T3.5 first, and only what survives as genuine T4 becomes a
candidate row for the single gate at the HARD STOP.

Delegate the searching: **`Agent(subagent_type: "ktkit:escalation-resolver")`, one question per
call**, several in one message when independent. ⛔ The lead does not open files.

⛔ **This step blocks on nothing.** The scan prioritises:

| # | Unclear thing | Usually settled by |
|---|---|---|
| 1 | Is the reproduction case unambiguous and step-by-step verifiable? | T1 — the report, the failing test, the log |
| 2 | Is expected vs actual measurable, not "it doesn't work"? | T1, else T3.5 with a falsifier |
| 3 | Is fix scope bounded — what must NOT change? | T1 — blast radius from STEP 3 |
| 4 | Are rollback / revert requirements defined? | T1 — how the repo reverts, from its history |
| 5 | Are affected roles / permissions documented? | T1 — the auth layer; **T4 when being wrong widens access** |

Route each one:

| Ladder outcome | Where it goes |
|---|---|
| T1 / T2 — resolved from repo, docs, history, prior run | spec §Settled, with `file:line` |
| T3 — external fact; three portable steps fail | spec §Settled as `Undecided` — ⛔ never a question |
| T3.5 — one reading better evidenced, cheap if wrong | spec §Assumptions, with falsifier |
| T4 — undecidable **and** expensive if wrong | **pool for the HARD STOP gate** (max 3 total) |

Run the scan yourself and write the conclusions back into `fix.md`. ⛔ Do not call speckit
for the taxonomy — that skill reads and writes a `spec.md` under a spec-kit `FEATURE_DIR`, and this
lane produces neither.

**No gate here.** Merge the surviving T4 rows into the HARD STOP pool and continue.

---

### STEP 4.7 — FIX QUALITY CHECKLIST (risk-gated — often SKIPPED)
> Goal: unit-test the fix spec itself before anyone writes code against it

> Source: item-writing rules + file semantics adapted from `speckit-checklist` (snapshot 2026-08-24). Internalised on purpose — that skill's `check-prerequisites.sh --json` demands a `plan.md`, and this workflow HARD-STOPs *before* planning.

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

**Write to** `.claude/claude/specs/<rel-dir>/<base>/checklists/bugfix.md`. New file → number from `CHK001`; file already exists → append, continuing from the last CHK ID. Never delete or rewrite existing content.

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

## HARD STOP — the single gate

**After STEP 4.6: do NOT proceed to fix.**

This is the **only** gate in the workflow. It is answer-by-exception, not an interview:

- **Max 3 rows.** More T4 candidates than that ⇒ ⛔ do not list them all; report one row
  `N ambiguities of the same kind` with three representatives, and say the bug report is missing a
  section.
- **Every row carries a Default that is already applied**, phrased so **silence is a valid answer**.
- **Every row carries a Recommendation.** A question without one hands the whole task back.
- Rows come from the merged T4 pool: the `.analyze.md` unknowns table + STEP 4.6. Drop any row the
  ladder settled in the meantime.

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
## Fix Plan Ready for Review

**Root Cause**: <one sentence>
**Blast Radius**: <LOW/MEDIUM/HIGH/CRITICAL>
**Analysis read**: `<path to the .analyze.md this was written from>`
**Fix dir**: `.claude/claude/specs/<rel-dir>/<base>/`
**Fix plan written to**: `<…>/fix.md`
**Quality checklist**: `<…>/checklists/bugfix.md` — <N passed, M fixed>
**Clarifications**: <N questions answered / "no critical ambiguities detected">
**Fix quality checklist (STEP 4.7)**: <"risk = <band>, N items, M spec defects fixed, K left open" | "risk = <band> < MEDIUM — skipped">

**Escalation metric**: `self_resolve_ratio=0.xx · self_resolved=N · needs_user=M · assumptions=K · gates=1`

➡️ Review the spec above. When ready, run `/ktkit:bug-fix-execute` to apply the fix (STEP 5→7 only, no re-investigation).
```

`self_resolve_ratio = self_resolved / (self_resolved + needs_user)`. **Below 0.70 ⇒ tiers 1–3 were
not exhausted**: go back to STEP 4.6, dispatch more resolvers, and ⛔ do not open the gate yet.
`needs_user` must be ≤ 3, and every T3.5 row must have a non-empty Falsifier.

---

## Unknown handling (bindingly, before any question reaches the user)

Whenever anything is unknown — a symbol that cannot be found, two sources disagreeing, a report with
two readings, a fact about a library — **invoke skill `/ktkit:escalation-ladder`** and follow it.

Delegate the searching: **`Agent(subagent_type: "ktkit:escalation-resolver")`, one question per
call**, several in one message when independent. ⛔ The lead does not open files — it holds the
question, the `Tier`, and a one-line conclusion with its citation.

⛔ Nothing reaches the user before the ladder has run, and the workflow opens **exactly one** gate
(the HARD STOP), capped at 3 rows, every row with a default and a recommendation.

Budget, per `/ktkit:escalation-ladder`: at most **5 resolvers per round, 2 rounds per question**. Out
of budget is not a reason to escalate — it moves the unknown to T3.5 if one reading is better
evidenced, or leaves it `Undecided`.

**Fallback** — `/ktkit:escalation-ladder` ships with this plugin, so it is present wherever this
skill is. If it somehow cannot be loaded, apply the tiers inline: T1 resolve from repo with a
citation · T2 one round of challenge · T3 external fact, else `Undecided` · T3.5 decide with a
mandatory falsifier · T4 the single gate. ⛔ A missing skill is never a reason to reinstate the
interview.
