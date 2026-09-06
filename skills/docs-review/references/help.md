<!-- group: Audit | order: 50 -->
# ktkit:docs-review — audit documents against a standard, the repository, or themselves

A team of agents that run concurrently and then **challenge each other's findings**. Reviewers derive
alone — no lead reasoning, no peer findings — then attack with evidence. Only what survives the
challenge is merged; refuted findings stay in the report with the evidence that killed them.

```
/ktkit:docs-review <path>... [flags]
```

## Pick the mode first — it is decided by what you pass, not by a flag

| You have | Mode | What happens |
| -------- | ---- | ------------ |
| A standard **and** documents | **A — gap analysis** | The standard is decomposed into atomic requirements *before* the documents are read, then each is mapped to `Covered` / `Partial` / `Missing` / `Contradict` / `Conflict` / `Stale` / `Undecided`, with a mandatory citation and quote. |
| Documents **and a question** | **B — investigation** | The checklist comes from your question. Answers are `Stated` / `Inferred` / `Conflicting` / `Absent`. |
| **One file**, nothing to compare it against | **C — critique** | Its claims are verified against the repository, its open questions answered where the repo answers them, its self-contradictions named. Nothing you wrote is edited — one delimited block is appended. |

## The cases

```bash
# ── Mode A: do the docs actually cover the spec?
/ktkit:docs-review docs/spec/payments.md docs/

# ── Mode B: ask a question of a document set
/ktkit:docs-review docs/ "what happens to an in-flight refund when the account is closed"

# ── Mode C: critique one file against the repository and itself
/ktkit:docs-review .claude/claude/analyze/share-links.analysis.md

# ── cap the loop: a small set converges early, and a bare integer is the same as --rounds
/ktkit:docs-review 2 docs/spec.md docs/
/ktkit:docs-review docs/spec.md docs/ --rounds 2

# ── one context, one reviewer, one debuggable transcript
/ktkit:docs-review docs/spec.md docs/ --team off

# ── write the fixes as well, not just find them
/ktkit:docs-review docs/spec.md docs/ --fix

# ── surface every unknown instead of resolving them (diagnostic)
/ktkit:docs-review docs/spec.md docs/ --ask-only

# ── report somewhere other than the default
/ktkit:docs-review docs/spec.md docs/ --out .claude/claude/analyze/payments-audit.md

# ── ⭐ read measurements a spec-recon run produced, and reason about code without a shell
/ktkit:spec-recon docs/ --scope "..." --handoff off
/ktkit:docs-review docs/spec.md docs/ --evidence .claude/claude/analyze/spec-recon/evidence/
```

## Flags

| Flag | Default | When you need it |
| ---- | ------- | ---------------- |
| `<N>` (bare leading integer 1–9) | — | Same as `--rounds N`. |
| `--rounds N \| auto` | `auto` = **3** with the team, **5** with `--team off` | A **ceiling**. Convergence may end the loop earlier; the ceiling never forces an extra wave. |
| `--team off` | team on | One context, one blind reviewer per round. **Mode A and B only.** Choose it for a single debuggable transcript, not because it is cheaper — it usually is not. |
| `--max-questions N` | `3` | Ceiling on rows that may reach you. |
| `--ask-only` | off | Diagnostic: skip the lower tiers of the ladder and surface every unknown. The report says it ran this way. |
| `--fix` | off | Enter fix mode after the loop. Edits are gated by a `fix-safety` reviewer before anything is written. |
| `--evidence <dir>` | — | Load every `.md` under `<dir>` as **evidence produced by a probing run**. Written by `ktkit:spec-recon`. Optional and inert: without it nothing behaves differently. |
| `--out <path>` | `docs-review.md` | Report path. |
| `--silent` | off | Print the report path and nothing else. |
| `--keep-scratch` | off | Keep `<base>/scratch/`. For debugging this skill. |

## What it prints

One line before it starts, one summary at the end. That is the entire chat output — the audit lives
in the report.

```text
Mode A · spec=spec.md · docs=./docs (12 files) · waves cap=3 · team=on · max-questions=3 · fix=off
```

A ceiling reached with findings still outstanding is **not** a clean exit: line 1 of the report reads
`BUDGET-CAPPED`, and the outstanding findings are listed unmerged.

## Do not

| Anti-pattern | Why |
| ------------ | --- |
| Use it to ask whether the **code** does something | It has no shell by construction. That is `/ktkit:spec-recon`. |
| Pass `--team off` to save money | One reviewer needs more rounds to find the same things. It is usually not cheaper. |
| Pass `--fix` before reading the report | Fix mode acts on the findings. Read them first. |
| Read a `Missing` verdict as settled fact about the code | It is settled about the **documents**. Only `spec-recon` can settle it about the code. |

## See also

`/ktkit:help spec-recon` — the axis this skill cannot reach: source, binary artifacts, forge state.
