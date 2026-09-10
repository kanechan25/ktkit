---
name: raise-issue
description: "Turn a messy problem description into a well-formed, AI-ready issue statement BEFORE any analysis. Triggers '/ktkit:raise-issue <description>', 'raise issue này lên', 'viết issue cho vấn đề này', 'frame lại cái bug này trước khi phân tích'. Handles bug reports, new requirements (NR) and change requirements (CR). Extracts the facts, verifies the code hints, locates the entry point from an anchor, asks only what it cannot resolve itself, confirms with the user that it understood the right problem, then writes one Vietnamese issue file. RAISES ONLY — never diagnoses root cause, never proposes a fix, never writes spec or code."
argument-hint: "[free-text description | --file <path>] [--issue <#N|url>] [--type bug|nr|cr] [--slug <n-desc>] [--out <dir>] [--no-ask]"
user-invocable: true
disable-model-invocation: true
---

# Raise an issue — `/ktkit:raise-issue $ARGUMENTS`

```text
$ARGUMENTS
```

## 🎯 Identity — read before anything else

**This skill FRAMES a problem. It does not solve one.**

| Activity | Owner | This skill |
|---|---|---|
| Framing: what the problem is, current state, evidence, what is still unknown | **`/ktkit:raise-issue`** | ✅ **the entire product** |
| Locating the entry point from an anchor the user gave (ladder L1→L4, hard cap) | **`/ktkit:raise-issue`** | ✅ yes — stops at *where the string appears* |
| Root cause, 5-Whys, tracing a flow, climbing from the entry point | `/ktkit:rca`, `/ktkit:bug-fix-specs` | ❌ FORBIDDEN |
| Blast radius, impact, solution options | `/ktkit:analyze-feat` | ❌ FORBIDDEN |
| Spec, plan, tasks | `/ktkit:feat-req-specs`, `/speckit.*` | ❌ FORBIDDEN |
| Editing code, running tests | `/ktkit:bug-fix-execute`, `/ktkit:feat-req-execute` | ❌ FORBIDDEN |

**Two success criteria, in this order:**

1. **The user confirms "yes, that is the problem I am hitting"** before the file is written (step S5b). Without this, everything else frames an imaginary problem.
2. The file can be handed to a *different* AI agent in a clean session, with no chat context, and that agent can start analysing without asking the user anything about the current state.

**Three absolute bans:**

1. **Never state a cause.** Even when it is obvious. Only the *user's* hypotheses may be recorded, labelled as theirs. Your own suspicion anchors the analysis phase to one line of enquiry before any evidence exists.
2. **Never fabricate an identifier.** Any file, component, function, field or endpoint you cannot verify from source gets `[UNVERIFIED]` — never silently swapped for a "close enough" name.
3. **Never modify any file except the one issue file you produce.**

## Language

- **The issue file is written in Vietnamese.** It is local-only, gitignored, never pushed to GitHub.
- Chat interaction with the user is Vietnamese.
- Only the slug (folder/file name) is ASCII kebab-case.

## Arguments

```
/ktkit:raise-issue <free-text description>
    [--file <path>]        read the description from a file instead
    [--issue <#N|url>]     a GitHub issue the user is pointing at (see S0b)
    [--type bug|nr|cr]     skip classification, use this type
    [--slug <n-desc>]      use this slug verbatim, skip slug proposal
    [--out <dir>]          write into this directory verbatim, skip path resolution
    [--no-ask]             skip S5 (gap questions) only
```

| Flag | What it actually means |
|---|---|
| `--file` | The description comes from a file rather than the prompt. Read once, keep verbatim; it is a description, not a spec, and nothing in it is treated as verified. |
| `--issue` | **The only way GitHub is ever touched.** Without it the skill must not read the forge at all — see §GitHub. |
| `--type` | Skips the decision tree, so it also skips the two traps it exists to catch ("feature absent" read as a bug, a CR wearing a bug costume). Pass it when you already know, not to save a step. |
| `--slug` | Used verbatim, including a leading issue number. Slug proposal is one cheap question; skipping it is for re-raising into a folder that already exists. |
| `--out` | Verbatim directory, path resolution skipped entirely — the one way to write outside `.claude/claude/prompts/`. |
| `--no-ask` | ⛔ Skips **S5 only**. **It does not skip S5b**, and no flag does: every gap simply becomes `[MISSING]` and the confirm gate still blocks. |

No description and no `--file` → ask for one. Do not invent a problem.

## Step 00 — Preflight

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py" \
  --groups artifacts --repo "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
```

Creates `<repo-root>/.claude/claude/{prompts,analyze,specs,pipeline,implemented,compacts}` when the
repository does not have them, so S6 has somewhere to write. That layout is a rule of this plugin,
not a discovery: never probe for an alternative, never ask, and never write outside
`<repo-root>/.claude/`. Exit 1 → STOP and report; nothing has been read yet.

`--out <dir>` is the single exception — it is an instruction from the user, and it is taken verbatim.

## Workflow — 12 steps

| Step | Name | Do | Produce |
|---|---|---|---|
| **S00** | PREFLIGHT | Run the artifact-root check (see §Step 00). Exit 1 → STOP | a writable `prompts/` |
| **S0** | INTAKE | Capture the description verbatim, including any screenshot the user pasted. Do not interpret, do not fix their wording | raw text kept intact |
| **S0b** | FETCH-GH *(conditional)* | Only if the user gave `#N`/URL — one read (see §GitHub) | issue body, tagged `[GH #N]` |
| **S1** | CLASSIFY | Run the decision tree (see §Classification) | `BUG` / `NR` / `CR` |
| **S2** | SPLIT-CHECK | Detect several independent problems in one description; pick the main one, park the rest | list of secondary problems |
| **S3** | EXTRACT | Load `references/form-<type>.md`, map each fact into its slot. No data → `[MISSING]`, never inferred | partly filled slot map |
| **S3b** | LOCATE *(conditional)* | Only when the user gave no direct path/symbol — run the ladder (see §Locate) | `[LOCATED …]` or `[MISSING]` |
| **S4** | VERIFY | Verify every identifier/path the user named (see §Verify) | code table with labels |
| **S5** | INTERVIEW | Batch the gaps worth asking about (see §Interview). Max 2 rounds. **`--no-ask` skips this step** | user's answers |
| **S5b** | **CONFIRM** 🔴 | Replay the problem, ≤ 10 lines, and ask outright whether that is the problem they are hitting. **BLOCKS.** No flag skips this | `đúng` / `sai: …` |
| **S6** | RENDER | Resolve the path, run the self-audit, write the file | the `.md` file |
| **S7** | HANDOFF | Print path + 3-line summary + suggested next skill. **STOP** | chat output |

**Two gates, do not confuse them:**

- **Soft gate (missing data)** — a required field is still `[MISSING]` and the user said they do not know → **write the file anyway**, marked `[MISSING] — user confirmed no information`. Never block the user over missing data.
- **Hard gate (S5b)** — **no `đúng` from the user, no file.** This is the only gate allowed to stop the write.

## Classification — BUG / NR / CR

Stop at the first branch that matches:

1. The system does something **wrong against what it was itself meant to do** (error, crash, wrong number, blank screen, error log) → **BUG**.
2. The system behaves **as designed**, but the user wants **different behaviour for something that already exists** → **CR**.
3. The user wants something that **does not exist yet** → **NR**.

Two traps:

- **"Feature absent" ≠ BUG.** Ask: *has this ever worked correctly?* If never, it is `NR`.
- **CR wearing a BUG costume.** "It computes the wrong deadline" while the code matches the spec = the business changed its mind → `CR`. Ask: *does any spec say it should differ?*

Cannot decide after reading everything → **ask**. Do not guess: wrong type = wrong slot map = wrong file.

## Verify — what "verify-only" means

**Allowed**: `Read`, `Grep`, `Glob`, `git log -1 <file>`, `ls`.
**Forbidden**: running tests, building, starting services, reading databases, broad `git blame` used to reason about causes.

| Outcome | Write |
|---|---|
| Found | `[VERIFIED] path/to/File.tsx:142` |
| Not found | `[UNVERIFIED] "FooBar" — grepped 3 variants (FooBar, foo_bar, foo-bar), no hit` — **always say how you searched** |
| Found under a different name | `[VERIFIED-ALIAS] user said "FilterModal", actual FilterDialog at path:line — needs user confirmation` → raise it in S5 |

Budget: **≤ 8 read operations**. Over budget means you are drifting into recon — stop, mark `[UNVERIFIED]`, let the analysis phase handle it.

## Locate — finding the entry point yourself

Runs only when the user did not hand you a path or symbol. The user normally gives a **relative area** ("on the version-creation screen, the table on the right"), so the job is **narrowing an area down to a file**, not searching blind.

**Selectivity is a function of (anchor × area), not of the anchor alone.** A generic business token is useless repo-wide and perfectly usable inside one area. Therefore: **narrow the area FIRST, grep the literal SECOND.** Inverting that order is the fastest way to get 200 hits and guess.

| Rung | Input from the user | Action |
|---|---|---|
| **L0** | a path or symbol | verify it (§Verify), no locating needed |
| **L1** | **relative area** — screen name, feature, route/URL, "the X part of Y" | `Glob` / list directories to pin **one area** |
| **L2** | **literal string** — visible label, error text, button caption, column header | `Grep` the literal **inside the L1 area** |
| **L3** | code-shaped token — field name, function name, screen/API code | `Grep` inside the L1 area |
| **L4** | no area could be pinned, or > 15 files remain after L2/L3 | **STOP and ask one question** |

**Selectivity gate (mandatory)**: count matching files **before reading anything**. **> 15 files ⇒ the anchor is too generic — treat that rung as failed** and drop to L4. Never "take the first three hits".

**Hard cap**: ≤ **6** tool calls for the whole of LOCATE, ≤ **1** `Read`. Prefer `Grep` with `-n -C 3` over reading whole files — reading files is what burns tokens, grepping is not. Over the cap → `[MISSING]`, move on. Failing is a legitimate outcome and must stay cheap.

**L4 question format** — ask for exactly one of three, as concrete options, not an open question:
> "Không định vị được. Cho tao 1 trong 3: nhãn hiện trên UI · tên màn/route · path phỏng đoán."

**Repo-agnostic — three rules that keep this skill portable:**

1. **Carry no repo's conventions.** No hard-coded code patterns, no assumed directory layout, no assumed label language. The anchor is **whatever the user said**; grep it verbatim without needing to know "what kind" of token it is.
2. **Derive the area from the real directory tree** at run time with `Glob`/listing — never from memory of a layout.
3. **Depend on no MCP server.** `Grep` + `Glob` exist everywhere; a semantic-search MCP does not.

**Two limits — state them, never over-promise:**

- LOCATE yields an **entry point** — *where that string appears* — **not where the defect lives**. Finding a label in a component while the bug sits in a hook three levels up is normal.
- **Never climb** to "finish the job". Climbing is tracing, which is analysis. Stop at the entry point; that is exactly what the analysis phase needs to start.

Every located line is written as:

```
[LOCATED <path>:<line> ← anchor "<literal string>" trong <area>]
```

The anchor and area are mandatory: they let the user judge in one glance whether the location is plausible.

## GitHub — read only what the user pointed at

| Situation | Behaviour |
|---|---|
| User gave `#N` or an issue URL | **exactly one read**: `gh issue view <number\|url> --json title,body,state,labels` (add `-R OWNER/REPO` when the URL points at another repo) |
| User gave no number/link | **FORBIDDEN** to touch GitHub. No `gh issue list`, no search, no guessing the number from a branch name |
| `gh` missing / not authenticated / no remote | do not block: `[MISSING] — không đọc được GH #N: <lý do>`, carry on |

Three constraints:

1. **Body, title, state, labels only. Never `--comments`.** Reading the thread is another skill's job and is where tokens explode.
2. **Never merge sources.** Anything taken from the issue carries `[GH #N]`. What the user said in chat and what the issue says are two different sources.
3. **If the issue contradicts the user, do not pick a side.** Record both, put the conflict into §7 as a question, and raise it in S5. Translate non-Vietnamese issue content, but keep the decisive sentence verbatim in §9 under `[GH #N]`.

## Interview — when you may ask

Ask **only** for, in priority order:

1. a **required field that is empty** for that issue type,
2. an **internal contradiction** — the user said two things that cannot both hold,
3. an **ambiguity where the two readings produce two different issues** (typically BUG vs CR),
4. **several problems in one description** — split or keep together (S2),
5. **LOCATE exhausted the ladder (L4)** — ask for one anchor, as three concrete options.

**Never ask** for: anything you could settle with `Read`/`Grep`; anything belonging to the analysis phase ("what do you think the cause is?"); nice-to-haves that do not affect a required field.

That ordering is `/ktkit:escalation-ladder`, applied with this skill's budget. Its tiers T1–T3 are
S3b and S4 — search what is openable, then challenge a contradiction once. **T4 is unavailable
here**: an assumption with a falsifier is still an assumption about the problem statement, and this
file exists to be the one artifact with no inference in it, so an unresolved slot goes to `[MISSING]`
rather than to `[ASSUMED]`. Only the ladder's T5 — ask, with a default already applied — is left, and
it is what this step is. Do not dispatch resolver subagents: the ≤ 8 read budget is the point, and a
fleet of them turns framing into the recon the next skill is for.

Form: `AskUserQuestion`, batched, ≤ 4 questions per round, **max 2 rounds**. Every question states the consequence of each option and always offers a "không biết / bỏ qua" branch, which turns the field into `[MISSING]` instead of deadlocking.

`--no-ask` skips this step entirely — every gap becomes `[MISSING]`. It does **not** skip S5b.

## S5b — the CONFIRM gate 🔴

This is the most important part of the skill.

Replay the problem in **≤ 10 lines**: the problem · current state · expectation · code area (**including every `[LOCATED]` line — the user has never seen those**) · what you are **not** sure about.

Then ask via `AskUserQuestion`:

- `đúng, ghi đi`
- `gần đúng, sửa: <chỗ lệch>`
- `sai hẳn, tao mô tả lại`

Branches 2 and 3 return to S3. **Max 2 replay rounds**; still wrong after that → stop and tell the user the problem is not yet clear enough to frame. **Do not write a half-formed file.**

**Why after verifying, not before**: asking before verification means the user confirms a description that may contain a wrong component name. Confirming afterwards shows them the `[UNVERIFIED]` and `[LOCATED]` lines so they can correct on the spot — that catches the most expensive class of error, a misremembered screen or function name.

**The mistake to avoid**: presenting the replay *together with* a guess at the cause, "to make it easier to confirm". That is the back door for your own hypothesis, which is banned. The replay contains the phenomenon, never an explanation of it.

**No off switch.** No flag skips S5b — `--no-ask` only skips S5. Consequently **every** file this skill produces carries `confirmed_by_ops: true`; there is no code path that writes `false`. The field stays in the front matter as a visible invariant: a file missing it, or holding `false`, was not produced by this skill's proper flow.

## Output path

```
<prompts-root>/<slug>/<slug>-<YYYYMMDDHHMM>.md
```

- `<slug>` = `<gh-issue-number>-<kebab-description>`; the number is **optional** — drop it and its dash when absent.
- Kebab description: ASCII, lowercase, 2–5 words, English. Only the name is ASCII; the content is Vietnamese.
- Timestamp: local time, `date +%Y%m%d%H%M`.
- **Never overwrite.** Re-raising the same problem → **same folder, new file, new timestamp**.
- Folder already exists → reuse it; never create a near-duplicate name.
- You propose the slug, the user approves it in the interview round (one cheap question). `--slug` skips this.

`<prompts-root>` is `<repo-root>/.claude/claude/prompts/`. **Fixed by the plugin, not discovered.**
Step 0 has already created it, so there is nothing to probe for and nothing to ask about. The one
override is `--out <dir>`, used verbatim.

Writing under `prompts/` is what makes the file an input to the rest of the toolkit rather than a
note: `/ktkit:chain`, `/ktkit:analyze-feat` and `/ktkit:rca` all mirror a prompt's sub-path into
their own output, so the analysis, the spec and the record land beside the issue that started them.

## Output file structure

**The skeleton lives in `references/form-<type>.md` — front matter, the ten sections, the required-slot count for `completeness`, and why each slot exists. Load exactly one form, the one matching the classified type, and copy its skeleton verbatim.** Never rebuild the structure from memory, never rename or reorder a section, never drop an empty one (print a label instead).

The three forms share §1–§10 and differ only in what §2/§3 mean and which slots are required:

| Type | §2 | §3 | Extra required |
|---|---|---|---|
| BUG | symptom | expected behaviour | environment, "has it ever worked" |
| NR | today's gap | user story + business value | **integration point** |
| CR | **old behaviour** | new behaviour | reason, requester, backward-compat raised as a §7 question |

### Labels — mandatory on every field

**Source labels** — who said this:

| Label | Meaning |
|---|---|
| `[CONFIRMED]` | the user said it plainly |
| `[GH #N]` | from the GitHub issue body, not from chat |
| `[SCREENSHOT]` | read off an image the user pasted |
| `[LOCATED path:line ← anchor "<s>" trong <area>]` | **you found it**; the user has not seen it |

**Confidence labels** — how far it can be trusted:

| Label | Meaning |
|---|---|
| `[VERIFIED path:line]` | the user named it, you confirmed it in source |
| `[UNVERIFIED]` | the user named it, you could not find it — say how you searched |
| `[ASSUMED: …]` | you inferred it — **must carry a falsifier**: "wrong if …" |
| `[MISSING]` | no data — say "asked in round N" or "not asked, not required" |
| `[N/A]` | not applicable to this issue type |

A field may carry one label of each kind. `[VERIFIED]` and `[LOCATED]` are not the same thing: the first is *user-stated, you confirmed*; the second is *you found, user has not looked*.

**Screenshots**: describe into §4 what is *readable* in the image (error text, button labels, displayed numbers, which column is empty), tagged `[SCREENSHOT]` with its source — never what you cannot see.

## Determinism — same shape ten times out of ten

1. **Fixed slots, fixed order.** Copy the skeleton from `references/form-<type>.md`; never reconstruct it from memory.
2. **Fill slots, do not write prose.** Facts plus labels. Free-form prose is where inference sneaks in.
3. **Never go silent.** No data → print `[MISSING]`; never delete a section.
4. **§9 keeps the user's words verbatim** — no spelling fixes, no terminology normalisation. Everything else can be checked against it.
5. **Every `[ASSUMED]` carries a falsifier.** An assumption with no falsifying condition is banned.
6. **Your own hypotheses are banned** (see Identity). Only the user's, recorded as `§7 — ops nghi ngờ X (chưa kiểm chứng)`.

### Self-audit before writing (all must pass)

- [ ] Exactly one `type`, decision tree actually run?
- [ ] All ten sections present, correct order, none renamed or dropped?
- [ ] Every field carries a label?
- [ ] Every identifier/path in the file is `[VERIFIED]`, `[UNVERIFIED]` or `[LOCATED]` — **none bare**?
- [ ] No sentence asserting a cause or proposing a fix?
- [ ] Every `[ASSUMED]` has a "wrong if …"?
- [ ] §9 verbatim, not edited?
- [ ] Path matches `<slug>/<slug>-<YYYYMMDDHHMM>.md`, no existing file overwritten?
- [ ] **S5b passed — the user answered `đúng`?** (`confirmed_by_ops: true`)
- [ ] Everything from the GitHub issue tagged `[GH #N]`, not mixed into the user's words?
- [ ] Folder already had a previous raise → §10 delta points at it?
- [ ] Every `[LOCATED]` carries its anchor and area?
- [ ] LOCATE stayed within cap (≤ 6 calls, ≤ 1 `Read`) and did not climb past the entry point?

## S7 — handoff

Print the file path, a three-line summary, and the suggested next skill. Then **stop**.

| `type` | Suggested next |
|---|---|
| BUG | `/ktkit:rca` or `/ktkit:bug-fix-specs` with the file path |
| NR | `/ktkit:analyze-feat` → `/ktkit:feat-req-specs` |
| CR | `/ktkit:analyze-feat` → `/ktkit:feat-req-specs` |
| any | `/ktkit:chain <file> --bug\|--feature` — runs the whole column above in one loop |

The file is written where every one of those reads from, so the handoff is the path and nothing else.

Chaining is manual in both directions: this skill never runs the next one, and nothing can auto-invoke this skill (`disable-model-invocation: true`).

## Red flags — you are doing it wrong

| Symptom | Meaning |
|---|---|
| The file contains "the cause is…" | drifted into analysis |
| A component name with no label · `[LOCATED]` without its anchor/area | possible fabrication; the user cannot judge the location |
| More than 8 questions asked | interviewing instead of framing |
| §7 (unknowns) empty | either the problem is trivial or you are pretending to know everything |
| More than 8 files read · `Read`ing whole files during LOCATE | over budget, doing recon; use `Grep -n -C 3` |
| A second file overwrote the first | wrong path rule — must be a new timestamp |
| §9 "tidied up" | loses arbitration value; editing it is banned |
| File written without `confirmed_by_ops: true` | S5b bypassed |
| GitHub content present without the user giving a number/link · issue sentences unlabelled in §2 | went hunting, or merged sources |
| The S5b replay contains "chắc là do…" | your hypothesis entering by the back door |
| Grepping a generic token with no area, then picking the first hits | guessing; the > 15 files gate exists for this |
| LOCATE climbed from component into hooks/services | that is tracing, i.e. analysis |
| Repo-specific patterns hard-coded anywhere | this ships to every repository, not just yours |
