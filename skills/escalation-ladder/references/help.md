<!-- group: Decide | order: 70 -->
# ktkit:escalation-ladder — resolve an unknown from the repository before asking a human

The failure it prevents is not guessing. It is **escalating** — turning every unknown into a question
for you, when most unknowns are already answered somewhere in the repository. Every unknown is
classified into a tier before anything is done about it, and asking is forbidden until the tiers
below are provably exhausted.

```
/ktkit:escalation-ladder [<file with open questions>]
```

Most of the time you never type this. The other skills invoke it themselves — it is the reason a
`docs-review` or a `chain` run reaches you with three questions instead of thirty.

## The tiers

| Tier | What happens |
| ---- | ------------ |
| **T1** | Search — the documents' own vocabulary, the code, the file's history. **Dispatched to subagents, not read into this context.** |
| **T2** | One round of challenge on a disagreement, then move on. |
| **T3** | An external fact, from an authoritative source. |
| **T3.5** | Decide on the better-evidenced reading — **and write down what would prove it wrong**. |
| **T4** | Ask. Last resort, and it must carry a recommendation and a default. |

## The cases

```bash
# a document that already carries a list of open questions — triage and resolve them
/ktkit:escalation-ladder .claude/claude/analyze/share-links/expiry-rules.analyze.md

# a plan whose "TBD" rows you want settled from the repository instead of by meeting
/ktkit:escalation-ladder .claude/claude/specs/share-links/expiry-rules/plan.md
```

## What you get

Three blocks, in this order:

```
⛔ NEEDS A DECISION — silence accepts the default (max 3 rows)
✅ SETTLED WITHOUT YOU (T1/T2/T3) — read only, no answer needed
🟡 ASSUMPTIONS TAKEN (T3.5) — each with the falsifier that would overturn it
```

Read the first block. The second exists so you can audit what was decided for you.

## Do not

| Anti-pattern | Why |
| ------------ | --- |
| Answer the second block | It is already settled and cited. Answering it re-opens closed work. |
| Ignore the falsifier on a T3.5 assumption | The falsifier is what makes the assumption safe to have taken. |
| Treat a T4 question as the skill failing | T4 means the tiers below were exhausted. That is the skill working. |

## See also

`/ktkit:help confirm-with-me` — the other stop: not an unknown, but an irreversible step.
