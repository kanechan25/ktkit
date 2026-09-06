<!-- group: Survive | order: 60 -->
# ktkit:ccompact — checkpoint in-flight state before /compact eats it

`/compact` is lossy. It summarises the conversation, and a summary of a pipeline mid-execution loses
exactly the parts that matter: which decision was taken and why, which option was rejected, what is
half-done, what the trap was. This writes those to a file first, then **hard stops** and prints the
`/compact` line for you to paste.

```
/ktkit:ccompact <input-file> [--tag <name>] [--out <dir>]
```

It **cannot run `/compact`** — that is a CLI built-in, not a tool. It prepares and stops.

## The cases

```bash
# the ordinary case: name the file the work is about
/ktkit:ccompact .claude/claude/specs/share-links/expiry-rules/spec.md

# two sessions working the same input in parallel — keep the checkpoints apart
/ktkit:ccompact .claude/claude/specs/share-links/expiry-rules/spec.md --tag frontend

# housekeeping: delete every checkpoint
/ktkit:ccompact --clear all

# retention: keep the last 14 days, delete ALL the rest
/ktkit:ccompact --clear --older 14d
```

## Flags

| Flag | Default | When you need it |
| ---- | ------- | ---------------- |
| `--tag <name>` | — | Writes `<base>.<tag>.compact.md` as a separate file. Only for deliberately parallel sessions. |
| `--out <dir>` | mirrored under `.claude/claude/compacts/` | Explicit override of the output directory. |
| `--clear all` | — | Delete **every** checkpoint. |
| `--clear --older <N>d` | — | Keep checkpoints touched in the last N days, delete **all** the rest. |

## What you get

```
.claude/claude/compacts/<rel>/<base>.compact.md
```

The path mirrors the input's sub-path. Existing file, same session → a new round is appended; the
checkpoint is a history, not an overwrite.

## Do not

| Anti-pattern | Why |
| ------------ | --- |
| Expect it to run `/compact` | It cannot. It prints the line; you paste it. |
| Let it summarise the spec | It records what **happened in this conversation** — the spec is already on disk. |
| `--clear all` to tidy up | It deletes every checkpoint, including ones another session is mid-way through. |

## See also

`/ktkit:help ccontinue` — the other half, run after `/compact`.
