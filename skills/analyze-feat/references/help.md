<!-- group: Understand | order: 20 -->
# ktkit:analyze-feat — a feature request becomes an analysis, before any spec exists

The phase people skip. It reads the request, orients itself in the codebase, and writes down what the
change actually touches — **no spec, no plan, no tasks, no code**. Deliberately so: a spec written
before the blast radius is known is a spec that gets rewritten.

```
/ktkit:analyze-feat <requirement.md | "described request">
```

## The cases

```bash
# a requirement file that someone handed you
/ktkit:analyze-feat .claude/claude/prompts/share-links/expiry-rules.md

# no file — describe it
/ktkit:analyze-feat "expiring share links: 24h default, owner can override to 7d"

# a requirement nested under a sub-path; the analysis mirrors that sub-path
/ktkit:analyze-feat .claude/claude/prompts/2410-preferences/stage-2/toggle-save.md
```

## What you get

```
.claude/claude/analyze/<rel>/<base>.analyze.md
```

`<rel>` mirrors the input's sub-path under `prompts/`, so the analysis, the spec and the record all
land beside each other later.

## Do not

| Anti-pattern | Why |
| ------------ | --- |
| Expect a spec out of it | It stops before one on purpose. `/ktkit:feat-req-specs` writes that. |
| Run it on a bug report | Bugs need evidence, not requirement analysis. Use `/ktkit:rca`. |
| Run it, then re-answer the same questions in the spec phase | That is what `/ktkit:chain` exists to stop. |

## See also

`/ktkit:help chain` — runs this, then the spec, then the plan, carrying every answer forward in a
ledger so nothing is asked twice. `/ktkit:help feat-req-specs` — the next step if you drive by hand.
