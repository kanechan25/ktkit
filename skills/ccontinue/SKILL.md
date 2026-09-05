---
name: ccontinue
description: "Use AFTER running the built-in /compact to resume work from a checkpoint written by /ktkit:ccompact. Reads <base>.compact.md (schema + newest round), reconstructs the binding decisions, conventions, in-progress work and traps, compares the recorded git branch/HEAD against the current one, reports any conflict between the compaction summary and the file — the FILE always wins — then prints a self-audit and waits for the user to confirm before touching anything. Trigger on `/ktkit:ccontinue <compact-file>`, or when the user wants to resume a pipeline after compaction. Pair skill of /ktkit:ccompact."
---

# ccontinue — resume from a checkpoint

The other half of `/ktkit:ccompact`. It runs on the far side of a memory wipe: the conversation was compacted, so the summary in context is lossy and possibly wrong. The checkpoint file is the authority.

## Prime directive

> **The checkpoint file outranks the compaction summary. Always.**

If they disagree, the file is right, and you must say out loud where they diverged. A summary that quietly overrides a recorded decision is the exact failure this pair of skills exists to prevent.

## Contract with `/ktkit:ccompact`

The file is the only channel between the two skills. Five invariants:

| # | Invariant |
|---|---|
| I1 | `schema:` in the frontmatter is read **first**. Unknown value → warn, do not guess the layout. |
| I2 | Body sections are numbered **0–8** and looked up **by number**, never by heading text. |
| I3 | Each `## Round N` is **self-contained** — read only the newest round. |
| I4 | Every path in the file is repo-root-relative. |
| I5 | On conflict, the file wins, and the divergence is reported. |

## What the checkpoint contains

| § | Content |
|---|---|
| 0 | Goal + which spec/pipeline is mid-execution + which steps are DONE/pending |
| 1 | Files created/modified (⚠️ marks a path that was not on disk at write time) |
| 2 | **Decisions + reasons + rejected options** — the binding constraints |
| 3 | Conventions / schema / naming / identifiers in use |
| 4 | In progress + edge cases + known unfixed bugs |
| 5 | **Next step** — what, input, and what DONE means |
| 6 | The step after that |
| 7 | Verify commands actually run + last result |
| 8 | **Traps already hit** |

Struck-through rows in §2 marked `SUPERSEDED` are history: the decision no longer applies, but the reason it was dropped still does. Do not resurrect them.

## Flow

```
0. Read <compact-file>. Read `schema:` first (I1). Not 1 → warn, keep going carefully.
1. Take the HIGHEST `## Round N`. It is self-contained (I3) — do not stitch older
   rounds together. Older rounds are history only.
2. Read the `source:` / `pipeline:` files from the frontmatter if the next step
   needs them. Context is clean now, so this is allowed and often useful —
   the opposite of the rule that applied while writing the checkpoint.
3. Compare against reality:
     git branch --show-current   vs frontmatter `branch`
     git rev-parse --short HEAD  vs frontmatter `head`
     git status --short          vs section 1
4. Print the self-audit block (below).
5. Report every conflict between the compaction summary and the file. File wins (I5).
6. STOP. Wait for the user to confirm before editing, running, or committing anything.
```

### Step 3 — how to read the git comparison

| Observation | Meaning |
|---|---|
| `head` moved forward, same branch | Normal — work was committed after the checkpoint. Say so. |
| `head` identical | Nothing committed since the checkpoint. Expect uncommitted work in the tree. |
| **Different branch** | Serious. Stop and ask — the checkpoint may belong to other work entirely. |
| Not a git repo / `n/a` | Fine, skip the comparison. |
| Section 1 lists a path that no longer exists | Flag it. Something was moved, reverted, or the path was wrong when written. |

### Step 4 — self-audit block to print

```
📄 Checkpoint: <path>  (round N, ghi lúc <updated>)
🎯 Đang chạy: <section 0 — file being executed + step status>

Git: branch <cur> (checkpoint: <recorded>) · HEAD <cur> (checkpoint: <recorded>)
     <"khớp" | "đã tiến N commit" | "⚠️ KHÁC BRANCH — hỏi trước khi làm gì">

Ràng buộc phải tuân (§2):
  1. <decision> — <reason>
  2. <decision> — <reason>
  3. <decision> — <reason>

Step kế tiếp (§5):
  Việc:   <what>
  Input:  <where>
  DONE khi: <criteria>
  Sẽ đụng: <files>

Cạm bẫy liên quan (§8):
  - <trap>

⚠️ Lệch giữa summary và checkpoint:
  - <divergence>   (checkpoint thắng)

→ Xác nhận để tao chạy tiếp, hoặc chỉnh lại hướng.
```

Omit the divergence block entirely when there is none. Never pad it with invented items.

## Closing the loop

After work resumes and context grows again, the user runs `/ktkit:ccompact` on the **same input file**, producing Round N+1 in the **same** checkpoint file. Round N+1 carries forward the still-binding decisions, so the cycle can repeat indefinitely without drift:

```
/ktkit:ccompact → /compact → /ktkit:ccontinue → work → /ktkit:ccompact → /compact → /ktkit:ccontinue → …
```

If you finish a meaningful chunk of work and notice the context filling up, it is fair to remind the user that `/ktkit:ccompact <input-file>` is due — but never invoke a compaction flow on your own.

## Never do

- Never start editing, running, or committing before the user confirms the self-audit.
- Never trust the compaction summary over the checkpoint file.
- Never silently reconcile a conflict — name it.
- Never merge older rounds into the newest; each round is self-contained by construction.
- Never resurrect a `SUPERSEDED` decision.
- Never invent a decision, path, or identifier that is not in the file or verifiable on disk.
- Never edit the checkpoint file here — writing rounds is `/ktkit:ccompact`'s job.
