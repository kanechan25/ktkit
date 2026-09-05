---
name: ccompact
description: "Use BEFORE running the built-in /compact, to checkpoint in-flight execution state to a durable file so it survives compaction. Writes <compact-root>/<rel-dir>/<base>.compact.md mirroring the input file's sub-path (always under the plugin's fixed `.claude/claude/compacts` root, created when missing), captures what ACTUALLY happened in this conversation (decisions + reasons, rejected options, in-progress work, traps) — never a summary of the spec — then HARD STOPS and prints the exact /compact line to paste. Also handles cleanup modes `--clear all` and `--clear --older Nd`. Trigger on `/ktkit:ccompact <file>`, or when the user wants to compact without losing pipeline state. Does NOT run /compact (a CLI built-in) and does NOT continue the work — that is /ktkit:ccontinue."
---

# ccompact — durable checkpoint before compaction

Write the state of the current in-flight work to a file that survives `/compact`, then stop.

## Hard constraints

1. **You CANNOT run `/compact`.** It is a CLI built-in, not a tool. You prepare everything and print the exact line for the user to paste. Never claim you compacted anything.
2. **You do NOT continue the work.** After writing the checkpoint you HARD STOP. Continuing is exactly what causes the context blow-up this skill exists to prevent.
3. **You do NOT touch `CLAUDE.md`, `.claude/CLAUDE.md`, or any shared rule file.** Ever.

## P0 — the one thing this file is for

> **Save the STATE and the WORK-IN-FLIGHT that exists only in this conversation.**

Everything else is secondary. Concretely:

- The `<input-file>` argument is a **naming key** used to derive the output path. It is **not** a content source.
- The spec/pipeline describes **INTENT**. It is already on disk and `/ktkit:ccontinue` can read it. Copying it here is the #1 anti-pattern: zero value, and it dilutes the parts that do have value.
- If this session **diverged** from the spec — changed approach, rejected an option, found the spec wrong — that divergence is the single most valuable thing to record. It is also the first thing compaction destroys.
- Pass criterion, apply it literally: *"Would a brand-new session with zero memory, reading only this file, produce the same result on the next step as this session would?"*

Write this mindset into every section you produce.

## Contract with `/ktkit:ccontinue`

The checkpoint file is the only channel between the two skills — treat it as an API, not a note. `/ktkit:ccontinue` relies on these five invariants; breaking one fails **silently**:

| # | Invariant | Where it is honoured here |
|---|---|---|
| I1 | `schema: 1` present in the frontmatter | A4 |
| I2 | Body sections numbered **0–8**, looked up by number — never renumbered, never omitted (write `(none)` instead) | A4 |
| I3 | Each `## Round N` is **self-contained** | A3 |
| I4 | Every path repo-root-relative — no `./`, no absolute | A4 |
| I5 | On conflict the file outranks the compaction summary | enforced by `/ktkit:ccontinue` |

## Modes

| Invocation | Mode |
|---|---|
| `/ktkit:ccompact <input-file> [--tag <name>] [--out <dir>]` | **A — checkpoint** (default) |
| `/ktkit:ccompact --clear all` | **B — delete every checkpoint** |
| `/ktkit:ccompact --clear --older <N>d` | **B — retention: keep last N days, delete ALL the rest** |

If `--clear` is present, jump straight to Mode B. Do not gather any work context first.

---

# Mode A — write the checkpoint

## A1. Resolve the output path

### Roots

The artifact root is a **fixed rule of this plugin**, not something to detect:

```
<workdir-root>  = git rev-parse --show-toplevel   (fallback: $PWD when not a git repo)
<artifact-base> = <workdir-root>/.claude/claude   ALWAYS — `mkdir -p` it when missing
```

Never probe for an alternative layout, never ask, never vary it per repository. One rule is easier
to hold than two, and a checkpoint that lands in a predictable place is the whole point.

`<compact-root>`, first match wins:

```
1. --out <dir>                                       explicit override
2. $CCOMPACT_DIR                                     env override
3. <artifact-base>/compacts                          the rule
```

Six sibling directories live under `<artifact-base>`, each with one owner:
`prompts/` (user-authored input) · `analyze/` · `specs/` · `pipeline/` · `implemented/` ·
`compacts/`.

**Creating a missing directory is the only filesystem change permitted here.** Never tidy, move or
delete anything that was already there, and never write outside `<workdir-root>/.claude/`.

### Mirror algorithm

```
1. <input-root> = the nearest ancestor directory of <input-file> whose parent is <artifact-base>
   (typically specs/ | pipeline/ | analyze/ | prompts/)
2. <rel-dir>    = dirname(<input-file>) relative to <input-root>   (may be empty)
3. <base>       = basename(<input-file>) with the first matching suffix stripped, in order:
                    .spec.md
                    .be.pipeline.md | .fe.pipeline.md | .fs.pipeline.md | .sqa.pipeline.md
                    .pipeline.md
                    .analyze.md
                    .compact.md
                    .md
4. output       = <compact-root>/<rel-dir>/<base>[.<tag>].compact.md
5. no <input-root> found (input lives outside <artifact-base>)
   → <compact-root>/_external/<base>.compact.md  and WARN the user
```

`<base>` is an **exact string**. Never re-slugify it, never substitute a folder name for it.

Examples:

```
.claude/claude/specs/issue-123/sub-issues/123.spec.md
  → .claude/claude/compacts/issue-123/sub-issues/123.compact.md

.claude/claude/pipeline/2202-preview/foo-p1.fs.pipeline.md
  → .claude/claude/compacts/2202-preview/foo-p1.compact.md

.claude/claude/analyze/feat-foo.analyze.md
  → .claude/claude/compacts/feat-foo.compact.md
```

Then `mkdir -p` the target directory.

### No argument given

Rare — the expected workflow always passes the file. Handle it softly: infer the spec/pipeline/analyze file this session has been executing **from the conversation**, print the proposed output path, and **ask the user to confirm** before writing. Never invent a slug and never write silently.

### Target file already exists

| Situation | Action |
|---|---|
| Same session continuing (round 2, 3, …) | **Append** a new `## Round N` section. One path, always. |
| Possibly another session on the same input | Cannot be told apart automatically → ask: `File đã tồn tại: <path>. Append round (a) / Ghi file mới với --tag (t) / Abort (x)?` — default abort |
| `--tag <name>` given | Write `<base>.<tag>.compact.md`, a separate file. Only for deliberately parallel sessions. |

`<compact-root>` is normally gitignored — there is **no git undo**. Always print the path before writing or overwriting.

## A2. Read discipline — INTENT vs REALITY

Budget is not the constraint here; **correctness** is. The rule is about which source you draw from.

| Source | Allowed? | Why |
|---|---|---|
| `.spec.md`, `.pipeline.md`, `.analyze.md`, prompt `.md` | ❌ **FORBIDDEN** | INTENT. Already on disk, `/ktkit:ccontinue` reads it. |
| Source files, exploratory Grep/Glob | ❌ FORBIDDEN | Re-readable any time. Not what compaction destroys. |
| Subagents | ❌ FORBIDDEN | A subagent cannot see this conversation, so it has nothing to save. |
| **This checkpoint file itself, when round ≥ 2** | ✅ **REQUIRED** | See A3 — without it, decisions silently decay. |
| `git status --short`, `git diff --stat` | ✅ RECOMMENDED | Build the file list from disk, not memory. |
| `git log --oneline <base>..HEAD` | ✅ RECOMMENDED | Recover what was committed when memory is fuzzy. |
| `git rev-parse`, `git branch --show-current` | ✅ | Frontmatter. |
| `test -f <path>` per listed file | ✅ REQUIRED | Guard against invented paths. |

One sentence: **read REALITY, never read INTENT.**

## A3. Rounds

The lifecycle is a loop:

```
/ktkit:ccompact (round 1) → /compact → /ktkit:ccontinue → more work → /ktkit:ccompact (round 2) → /compact → …
```

Round 2 is written **after** a compaction, so you no longer remember round 1's decisions. Therefore:

- If the file already exists, **Read it first** (the one allowed exception in A2).
- Round N must be **self-contained**: carry forward every still-binding decision (section 2) and trap (section 8) from earlier rounds.
- A decision that was later overturned is **kept and struck through**, never deleted — knowing why an option was rejected stops the next round walking into the same dead end:

```markdown
| ~~Use project_code as the key~~ | ~~seed data was keyed by code~~ | step 3 — **SUPERSEDED @ Round 2**: switched to UUID for cross-system |
```

Because each round is self-contained, `/ktkit:ccontinue` only ever reads the newest one.

## A4. File format

Frontmatter — every value derived at runtime, nothing hardcoded:

```yaml
---
schema: 1
source: <input path, repo-root-relative>
pipeline: <pipeline path, repo-root-relative>   # omit entirely if unknown — never guess
created: <ISO-8601, first round>
updated: <ISO-8601, this round>
round: <N>
repo: <basename of workdir-root>
branch: <branch name | detached@SHA | n/a>
head: <short SHA | n/a>
status: <one line: which step is DONE, which is pending>
---
```

Derivation, failing soft outside a git repo (`n/a`, never an error):

```bash
git rev-parse --show-toplevel 2>/dev/null || pwd
git branch --show-current 2>/dev/null
git rev-parse --short HEAD 2>/dev/null
date -Iseconds
```

Body — fixed numbering 0–8. `/ktkit:ccontinue` looks sections up **by number**, so never renumber or drop one; write `(none)` if a section is genuinely empty.

```markdown
## Round <N> — <ISO timestamp>

### 0. Goal + which spec/pipeline is mid-execution
One paragraph: what this pipeline is for, WHICH file is being executed (name it),
and which steps are DONE vs in progress.

### 1. Files created/modified
| Path | New/Modified | One-line summary | Verified |
Built from `git status --short` + `git diff --stat`, not from memory.

### 2. Technical decisions locked in
| Decision | REASON | Locked at which step |
Include options that were REJECTED and why. Carry forward from earlier rounds.
This section is the highest-value part of the file.

### 3. Conventions / schema / naming / identifiers in use
Real, verified names only. Never invent an identifier.

### 4. In progress + edge cases + known unfixed bugs
What is half-done right now, and what would surprise someone picking it up.

### 5. Next step
What to do, where the input is, and what DONE means for it.

### 6. Step after that
Same shape.

### 7. Verify commands run + last result
Only commands actually executed in this session, with their real outcome.

### 8. Traps already hit
The things a fresh session would walk straight back into.
```

Sections **2, 4, 8** cannot be reconstructed from the spec, from git, or by re-running anything. If something has to be cut, cut 1 (rebuildable from `git diff`), then 7 (re-runnable) — never 2, 4, or 8.

Size budget: **3k–10k tokens per round**. The ceiling protects the *reading* side — `/ktkit:ccontinue` has to absorb the whole thing, and a bloated file becomes the very context garbage this skill removes. Keep it dense: no pasted code (cite `path:line`), no spec copying, record conclusions rather than the journey to them.

All paths inside the body must be **repo-root-relative** — never `./`, never absolute.

## A5. Execution steps

```
1. Resolve <compact-file> (A1). Print it. If inferred, ask for confirmation.
2. mkdir -p its directory.
3. If it exists → decide append-round / --tag / abort (A1).
3b. If round ≥ 2 → Read the existing file, extract still-binding sections 2 and 8.
4. Collect metadata (A4), failing soft.
4b. Inspect reality: git status --short, git diff --stat, git log --oneline.
5. Write the checkpoint (A4) from conversation context + 3b + 4b.
   Never read the spec/pipeline/source (A2).
6. `test -f` every path listed in section 1. Mark missing ones ⚠️ in the file.
7. Self-check against the P0 pass criterion. Fill gaps yourself — do not hand
   an incomplete checkpoint to the user; there is plenty of headroom.
8. Print the handoff block (A6). HARD STOP.
```

## A6. Handoff block to print

```
✅ Checkpoint: <compact-file>  (round N, ~X token)

Soi nhanh 3 điểm:
  1. Path ở mục 1 có thật không? (⚠️ = không tìm thấy trên đĩa)
  2. Quyết định nào mày nhớ mà file thiếu?
  3. Mục 5 (step kế tiếp) đã đủ rõ để người lạ làm chưa?

Bước tiếp — copy dòng này:

/compact Giữ nguyên: đường dẫn file đã sửa, quyết định kỹ thuật + lý do, schema/naming đang dùng, yêu cầu step kế tiếp, cạm bẫy đã gặp. Bỏ: nội dung file đã đọc, log build/test, output tool, các nhánh thử sai. State đầy đủ nằm ở <compact-file> — PHẢI Read file đó trước khi làm tiếp.

Sau khi compact xong:

/ktkit:ccontinue <compact-file>
```

Then stop. No further tool calls, no "while I'm here" work.

---

# Mode B — cleanup

Two modes only.

| Command | Meaning |
|---|---|
| `--clear all` | Delete **every** `*.compact.md` under `<compact-root>` |
| `--clear --older <N>d` | **Retention**: keep checkpoints touched within the last N days, delete **ALL** the rest |

The flag is `--older`, not `--older-than`. `N` is a parameter (`1d`, `3d`, `7d`, `30d`).

Age comes from **file mtime**, not the `created` field. Appending a round refreshes mtime, so "recently active" means "kept" — using `created` would delete a long-running pipeline while it is still in use.

```
1. Resolve <compact-root> (A1). Missing entirely → nothing was ever written; STOP.
2. Build the list:
     all         → find <compact-root> -name '*.compact.md'
     --older Nd  → find <compact-root> -name '*.compact.md' -mtime +N
3. Empty → print "không có gì để xoá", STOP. Do not ask a pointless question.
4. Print: file count, total size, first 20 paths (+ "… và N file nữa").
   For --older, ALSO print the files being KEPT — retention is easy to read
   backwards, and showing both sides is the cheapest guard against that.
5. WARN: <compact-root> is gitignored — there is NO git undo.
   (verify with `git check-ignore -v <compact-root>`)
6. Confirm gate: use the literal phrase `confirm with me`, and BLOCK until the
   user replies confirm / abort.
7. Delete the matched files, prune empty directories, KEEP <compact-root> itself.
8. Print how many were deleted and how many remain.
```

---

# Never do

- Never run or claim to run `/compact`.
- Never continue the work after writing the checkpoint.
- Never read the spec/pipeline/analyze/source to fill the checkpoint.
- Never dispatch a subagent.
- Never write to `CLAUDE.md`, `.claude/CLAUDE.md`, or any shared rule file.
- Never hardcode a repo name, branch, SHA or date — derive them at runtime. The `.claude/claude`
  layout is the exception: it is the plugin's rule, so it IS hardcoded (A1).
- Never delete anything in Mode B without the confirm gate.
- Never invent a file path, identifier, or command that was not actually used.
