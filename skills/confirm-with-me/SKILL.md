---
name: confirm-with-me
description: "Use IMMEDIATELY when encountering the literal phrase `confirm with me` in user messages, spec files, plan files, workflow steps, task instructions, or other skill bodies. Pauses execution BEFORE the marked step, posts a 5-field structured confirm block, and BLOCKS until user replies `confirm` / `abort` / `modify: <change>`. Never assume prior task-level approval covers a step marked with this phrase. Each marker = one atomic gate for one step."
---

# confirm-with-me — Per-Step Action Confirmation Gate

## Trigger

Activate the moment the literal phrase `confirm with me` appears anywhere in the active context:
- User message
- Spec file (`*.spec.md`, `docs/specs/**`)
- Plan file (`docs/plans/**`)
- Workflow step instruction
- Another skill's SKILL.md body
- Task description / checklist item

One marker = one gate, scoped to the **single step** it annotates. Do NOT extend approval from one gated step to other steps.

## Behavior (rigid — follow exactly)

1. **STOP** before executing the step that the marker annotates.
2. **POST** the confirm block below, filled with concrete details — no paraphrase, no placeholders, no "TBD".
3. **WAIT** for explicit user reply. Do NOT execute on:
   - Silence
   - Tangential reply that doesn't say `confirm` / `abort` / `modify: ...`
   - Implicit "ok" from elsewhere in conversation
4. **RESUME** only on explicit `confirm`. On `abort` → cancel the step + report. On `modify: <change>` → adjust + repost gate.

## Required confirm-block structure (post verbatim, fill every field)

```markdown
## 🔐 Action Confirmation

**1. Confirm cái gì?**
[Exact command / SQL / file edit (path + diff summary) / API call / script — paste literal text, no paraphrase]

**2. Mục đích?**
[Why this step is needed — link to which phase / task / spec section / plan step]

**3. Impact tới service / module liên quan?**
- [Service / module A]: [restart cost? cold-start time? downstream effect?]
- [Service / module B]: [touch same DB / shared lib / shared config?]
- [Frontend dev session / Redis cache / shared infra]: [running pnpm dev affected? cache invalidation needed?]
- [Other devs / shared resources]: [coordination needed? notify channel?]

**4. Mutate hoặc không mutate?**
- **Mutate**: [list — DB tables/cols/rows | FE source files | BE source files | config | external service state | infra / IaC | git refs]
- **Non-mutate** (read-only side effect): [list — SELECT, EXPLAIN, dry-run, file read, git status]

**5. Kết quả?**
- **Success path**: [post-state description + exact verify command]
- **Failure path**: [rollback strategy — exact command / migration revert / restore from dump / git revert / file restore]

➡️ Reply `confirm` để execute. `abort` để cancel. `modify: <change>` để adjust trước khi execute.
```

## Scope examples (when marker fires)

| Marker location | Gate scope |
|---|---|
| `"Step 5: run dotnet ef database update — confirm with me"` (spec) | Just that EF migration apply |
| `"Refactor extractToHelper() across 12 files, confirm with me before push"` (plan) | The push step, not each file edit |
| `"Delete docs/plans/CR-PM-002.md — confirm with me"` (user msg) | Just that delete |
| `"After step 7 (deploy), confirm with me"` (workflow) | Step between 7 and 8 only |

## Anti-patterns (NEVER do these)

- ❌ Skip gate because "user already approved the big task" — marker = atomic per-step approval.
- ❌ Batch multiple marker-gated steps into one confirm block — each marker = its own gate.
- ❌ Self-reply simulated user confirm — must wait for real user reply.
- ❌ Treat tangential user reply (e.g. "ok let's continue") as confirm if it doesn't address the gate — re-post gate, ask explicitly.
- ❌ Add fields beyond the 5 required — keep structure stable.
- ❌ Paraphrase command/SQL in field 1 — paste literal text.
- ❌ Use this skill for non-marked steps — gate ONLY where `confirm with me` literal appears.

## Composition with other skills

Other skills (e.g. `bug-fix-execute`, `refactor-pr-execute`, `sqa-migrate`) can embed `confirm with me` markers in their step instructions. When this skill fires from inside another skill's execution, it pauses just that step and returns control to the parent skill on `confirm`.
