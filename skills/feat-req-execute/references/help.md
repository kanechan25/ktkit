<!-- group: Execute | order: 40 -->
# ktkit:feat-req-execute — an approved spec becomes a plan, tasks, code and a record

> ⛔ **Not an entry point.** `/ktkit:chain --nr --execute` runs this as part of the NR and CR lane, with the ledger, the budget gate and step 07's convergence check that a direct run does not get. Running it directly still works and writes the same files.

Picks up where `/ktkit:feat-req-specs` stopped. It does **not** re-investigate and does **not**
re-design: the spec is assumed approved. Plan → analyze → implement → verify → document.

```
/ktkit:feat-req-execute [<spec-path>]
```

**Prerequisite:** a spec under `.claude/claude/specs/` that you have read and approved. The skill
searches recursively — a flat file or a mirrored sub-folder both work.

## The cases

```bash
# the ordinary case: the spec was just written and approved
/ktkit:feat-req-execute

# name the spec outright when several are in flight
/ktkit:feat-req-execute .claude/claude/specs/share-links/expiry-rules/spec.md

```

## Flags

| Flag | Default | When you need it |
| ---- | ------- | ---------------- |

## What you get

The change itself, plus:

```
.claude/claude/implemented/<rel>/<base>.implt.md      what was built, and what was verified
```

## Do not

| Anti-pattern | Why |
| ------------ | --- |
| Run it on a spec nobody read | It assumes approval. Nothing here re-opens the design. |
| Expect it to reconsider the spec | It carries the spec out. Disagreement belongs in the spec phase. |

## See also

`/ktkit:help feat-req-specs` — the step before. `/ktkit:help chain` with `--execute` — both, in one
line.
