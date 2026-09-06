<!-- group: Specify | order: 30 -->
# ktkit:feat-req-specs — an analysed feature becomes a reviewed spec, then it stops

Runs understand → blast radius → interview → design → spec, writes the spec, and **hard stops**. No
plan, no tasks, no code until you approve. The stop is the point of the skill.

```
/ktkit:feat-req-specs <requirement.md | "described request"> [--no-speckit]
```

## The cases

```bash
# the ordinary case
/ktkit:feat-req-specs .claude/claude/prompts/share-links/expiry-rules.md

# ⭐ after a spec-recon run: the gaps already carry a verified path:line, so the
#    interview step has far less to ask
/ktkit:spec-recon docs/ --baseline docs/design/current-flow.md --scope "what is missing, and where"
/ktkit:feat-req-specs .claude/claude/prompts/share-links/expiry-rules.md

# a repository with no speckit scaffolding, and you do not want to install it
/ktkit:feat-req-specs requirement.md --no-speckit
```

## Flags

| Flag | Default | When you need it |
| ---- | ------- | ---------------- |
| `--no-speckit` | — | Take this skill's internalised path even where speckit is installed. It **selects a path, it does not relax a check** — without it, a missing `.specify/` stops the run at preflight and prints the install command. |

## What you get

```
.claude/claude/specs/<rel>/<base>/…      the spec, plus its scenarios
```

Then it stops and waits. Approve, then run `/ktkit:feat-req-execute`.

## Do not

| Anti-pattern | Why |
| ------------ | --- |
| Expect code | It stops at the spec by design. |
| Skip reading the spec before executing | The execute skill assumes the spec is approved and does not re-design. |
| Reach for `--no-speckit` because preflight failed | Preflight prints the command that fixes it. The flag is a choice of path, not a way past a check. |

## See also

`/ktkit:help feat-req-execute` — the next step. `/ktkit:help chain` — both, plus the analysis, in one
line with a ledger between them.
