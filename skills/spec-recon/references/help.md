<!-- group: Audit | order: 51 -->
# ktkit:spec-recon — measure what documents only claim: code, artifacts, version control

`docs-review` compares documents with documents and never touches the code — that boundary is what
makes it trustworthy, and it is also its ceiling. A reviewer who can only read once declared a
feature missing that had been built months earlier. `spec-recon` is the axis it cannot reach: it
greps source, opens spreadsheets, reads issues and milestones, and **gates every claim that
something is missing behind an agent whose only job is to refute it**.

```
/ktkit:spec-recon <path>... --scope "<your business question>"
```

You type one line. Preflight, freshness, fleet planning, dispatch, citation verification, evidence
linting and handoff all run on their own. There is no step you run by hand.

## `--scope` is the most important thing you type

It is passed **verbatim** to every agent, and it decides what they go looking for.

| Weak | Strong |
| ---- | ------ |
| `--scope "review docs"` | `--scope "spec asks for three export flows EXP-021/030/033 — what exists in code, what is missing"` |
| `--scope "check code"` | `--scope "does the invoice template in code match Form A Rev.03 the customer sent"` |

`<path>...` takes a file, many files, a directory, many directories, or a repository root.

## The cases

```bash
# ── the flagship: "the spec asks for X — what is missing, and where does it go?"
/ktkit:spec-recon docs/spec/ \
  --baseline docs/design/current-export-flow.md \
  --scope "spec asks for three export flows — what is missing in code, and where would it go"

# ── the cheap one: "is my old analysis still based on the current documents?"
/ktkit:spec-recon docs/spec/ --scope "is the previous analysis still current"

# ── "does the shipped template match the published form?"
/ktkit:spec-recon src/api/Templates/ docs/forms/ \
  --scope "does the invoice template in code match Form A Rev.03"

# ── "does the plan match what is measurably true?"
/ktkit:spec-recon docs/plan/ --scope "is the export work actually attached to the Q3 milestone"

# ── keeping a run small, in order of effect
/ktkit:spec-recon docs/ --scope "..." --relevance 0.05      # read less
/ktkit:spec-recon docs/ --scope "..." --incremental         # only what changed
/ktkit:spec-recon docs/ --scope "..." --rounds 2            # one fewer review wave
/ktkit:spec-recon docs/ --scope "..." --probe code,artifact # offline, no forge
/ktkit:spec-recon docs/ --scope "..." --handoff off         # stop at evidence
/ktkit:spec-recon docs/ --scope "..." --budget 2000000      # a tighter ceiling

# ── continue a run the ceiling stopped
/ktkit:spec-recon --resume .claude/claude/analyze/<batch>/export-flows

# ── a repository with its own revision convention
/ktkit:spec-recon docs/ --patterns my-conventions.json --scope "..."
```

## ⭐ `--baseline` — the flag most people miss

If your question is **"what needs to be added"** and not merely **"what is missing"**, pass a
document describing the **current state**. Without it nobody builds a change surface, `gap-design`
has to reconstruct the present by itself, and the report tells you something is absent without
telling you which layer it is absent from. The run prints a one-line warning and continues; it does
not refuse.

## Reading the output

```
REFUTED   V-007  src/api/ExportService.cs:88   public enum ExportFlow {
UPHELD    V-014  searched: retryBudgetMs, retry_budget_ms, RetryBudgetMs
                 unsearched: generated bundles under dist/, injected at build time
UNSAFE    V-021  the answer is inside a spreadsheet; routed to the artifact probe

GAP       G-001  spec asks for a version gate on export | the client references no version
ANCHOR    G-001  src/web/exportClient.ts:142
SHAPE     G-001  a new branch in the existing switch, beside the template selection
NEIGHBOUR G-001  src/web/importClient.ts:88   ← this codebase already gates a version here
UNKNOWN   G-001  which version is the default when the field is absent — code cannot decide
```

| Line | What it means |
| ---- | ------------- |
| `REFUTED` | The verdict is dead and carries a `path:line`. **Do not rebuild something that exists.** This is the single most valuable line the skill produces. |
| `UPHELD` | Genuinely absent. ⭐ **Read `unsearched`** — empty, next to a broad claim, is a defect, not strong evidence. |
| `ANCHOR` | A real line, opened and read. The report lint re-opens it. A gap that cannot be anchored comes out as `UNKNOWN`, never as `GAP`. |
| `NEIGHBOUR` | ⭐ Where this codebase already does something similar. Checkable, and it teaches the house style. |
| `UNKNOWN` | Code cannot decide it. A real question, not a place to guess. |
| `NEEDS-WIDER` | An agent looked past the edge of its slice and said so. **The system working**, not a failure. |
| `not-accessed` | A source could not be reached — unreachable, or excluded by the relevance gate — and the reason is given. **Never** silently converted into "it does not exist". |

`GAP` is **input to `/ktkit:feat-req-specs`**, not a design decision. `SHAPE` is one sentence — never
a diff, never an effort estimate; the lint rejects a row carrying one.

## The full chain

```bash
/ktkit:spec-recon <docs> --baseline <current state> --scope "what is missing, and where does it go"
   ↓  a report whose every gap carries a verified path:line
/ktkit:feat-req-specs        ← reads it directly, no re-investigation
   ↓
/ktkit:feat-req-execute
```

## Flags

| Flag | Default | When you need it |
| ---- | ------- | ---------------- |
| `--scope "<text>"` | — | ⭐ **Always.** Your business question, in your words. |
| `--baseline <path>...` | — | ⭐ When you are asking what to **add**. A document describing current state. |
| `--probe code,artifact,vcs` | `code,artifact,vcs` | Drop `vcs` to run offline. |
| `--probe ...,runtime` | **never default** | Touches a live system. Runs only when you type its name. |
| `--rounds N \| auto` | `auto` = 3 | A small document set converges at `2`. |
| `--incremental` | on when a prior report exists | Re-run after the documents changed. Wave 1 is about two thirds of the cost, so this is the biggest lever. |
| `--out <path>` | **asked, never assumed** | Where the run writes — the report, and with it the whole directory. Omit it and step 0 prints a suggested path with the tree it would create, then **stops for your answer**; nothing is measured and no directory is created until you confirm. A path outside `.claude/` is rejected with the reason. |
| `--handoff on\|off` | `on` | `off` stops after evidence — use it to look before the review waves spend anything. |
| `--max-questions N` | `3` | Ceiling on questions that reach you, across the **whole run**. |
| `--lang <code>` | inherit | Output language. Stated, never guessed. |
| `--patterns <file>` | — | A JSON file merged over the shipped conventions. How a house revision syntax is recognised **without editing code**. |
| `--budget <tokens>` | **`4000000`** | ⭐ **Hard ceiling — raise it freely.** `8000000` for a large corpus, `2000000` to keep a run small. Checked at every boundary against what agents actually reported, never an estimate. Reaching it stops the run **at a boundary**, work on disk, resume command printed. |
| `--relevance <n>` | `0.01` | Minimum hits per KB before an agent reads an input. `0` reads everything. Measured on a real 64-file corpus: **48 mapper agents become 20**. |
| `--relevance-add <term>` | — | A term the scope wording lacks — usually the corpus's own language. Repeatable. |
| `--quota-gate <pct>` | `85` | Also stop when the subscription window is at or above this, whatever the token budget says. |
| `--keep-scratch` | off | Keep the working directory. For debugging this skill. |

## ⭐ What it will cost, and where it stops

Default ceiling **4,000,000 tokens**. Nothing is forecast: at every step boundary the run adds up
what the agents reported and asks whether another step the size of the last one still fits.

```
GO    after 03-extract b2   1,828,500 / 4,000,000  ·  last step 916,500  ·  window 11%

STOP  after 03-extract b3   2,756,000 / 4,000,000  ·  last step 927,500
  ⛔ 1,244,000 tokens left, and a step like the last one needs 1,391,250 (927,500 x 1.5)
  Everything finished so far is on disk. The window resets in 173 minutes.
  Resume:  ktkit:spec-recon --resume <base> --budget <new>
```

⭐ **A cheap step passes where an expensive one does not** — measured: at 3.17M of 4M the gate refused
another 927k extraction and then allowed a 305k arbitration, so the verdicts land even when the
extraction cannot continue.

### Raising it

The default is a default, not a limit. A large corpus is `--budget 8000000`; a quick check is
`--budget 2000000`. Same spend, four ceilings, and the arithmetic is the only thing deciding:

```
spent 2,908,000 · last step 2,908,000 · a step like that needs 4,362,000

  --budget 2000000   STOP    --budget 6000000   STOP
  --budget 4000000   STOP    --budget 8000000   GO    (5,092,000 left)
```

⭐ **And the run tells you whether the window can hold the ceiling you asked for** — from its own
measured rate, never a stored one:

```
window allows about 14,505,000 tokens in total, at this run's own rate of
151,166 per 1%  [measured here, not stored]
  ⇒ the 20,000,000 ceiling will not be reachable in this window;
    raise it only if you also wait for the reset
```

⚠️ At ~450k tokens per agent, 4M is about **8–9 agents**. A ceiling does **not** make a large wave
fit; it guarantees the run stops cleanly with work banked instead of dying mid-wave and losing every
verdict. To make a run *fit* rather than merely survive, narrow it: `--relevance`, `--rounds 2`,
`--probe code,artifact`, fewer inputs, a tighter `--scope`.

## Reading only what the question is in

`--scope` becomes a search vocabulary; each input is scored in hits per kilobyte. Density, not
presence — a 456 KB table with two incidental matches is not relevant, and an agent sent to find them
is how a run reaches fifteen million tokens. Measured on a 64-file corpus: **48 mapper agents → 20**.

⛔ **Narrowing is never silent.** `steps/01b-relevance.md` names every excluded file with its size and
hit count, the report carries `## Not read`, and an absence claim resting on an excluded file is
`not-accessed: cut by the relevance gate` — **never `UPHELD`**.

⭐ **The gate declines rather than guess** — when the corpus is mostly in a script none of its terms
are, or the vocabulary matched nothing anywhere, it keeps everything and prints why. A revision-marked
document is **rescued** whatever its density: cutting the specification on a question about the
specification is the gate being wrong.

The full mechanism, and every measurement behind it, is in `references/budget.md`.

## Where it writes — it asks first

A run produces a **directory**, not a file, and every later phase cites paths inside it. So the
location is settled before anything is measured. Without `--out`:

```
OUT-UNSET  the run writes a directory, so the location is settled before anything is measured.

Suggested:
  report   .claude/claude/analyze/<batch>.recon.md
  folder   .claude/claude/analyze/<batch>/

Derived: mirrored from .claude/claude/docs/<batch> under .claude/claude/analyze/
Confirm this path, or give another under .claude/claude/.
```

Then it stops. Confirm, or name another path. The suggestion is **derived** from the inputs by the
mirror algorithm `ktkit:ccompact` already uses — never built out of `--scope`, never re-slugified —
so a run lands beside the artifacts of whatever it was run on. A path outside `.claude/` is rejected
with the reason rather than quietly accepted.

## What you get — a directory, not a file

The report is the way in; the measurements are the substance, and each one is readable on its own.

```
<dir>/<base>.recon.md            ← the report
<dir>/<base>/
    steps/manifest.md            ⭐ the index — read this first if a run stopped
         00-preflight.md · 01-recon.md · 01b-relevance.md · 02-fleet-plan.md
         03-extract-<slice>.md · 04-state-<doc>.md · 05-collect.md · 06-handoff.md
    evidence/probe-*.md          ⭐ the measurements, each with a reproduce command
    recon.json                   freshness, surface, which copy of an artifact is the source
    cost.jsonl · cost.md         ⭐ what it cost, one append-only row per agent
    budget.jsonl                 what each step cost, and the gate's verdict at each boundary
    scratch/                     removed after a clean run unless --keep-scratch
```

**Cost is a file, not a line of chat.** `cost.md` carries a total, a per-wave table and a row per
agent, every figure from the `usage` that agent reported. An agent that reported nothing is recorded
as such and the total names how many it excludes — so it reads as a floor, not the bill. The lead's
own turns are not in it, and the file says so.

**Two modes, one path.** With `--handoff on` (default) the report is written by `ktkit:docs-review`,
which owns the report schema and the lint; with `off` the run stops after the evidence lint and
writes the report itself. `<base>/` is the same either way, and the path you confirm is used in both
— so the deliverable never falls back to another skill's default.

## Do not

| Anti-pattern | Why |
| ------------ | --- |
| Ask "what should be added" with no `--baseline` | Nobody can build a change surface, so the answer stays at "absent". |
| Treat `SHAPE` as a settled design | It is one sentence, and it is input to `feat-req-specs`. |
| Ignore `unsearched` on an `UPHELD` row | Empty plus a broad claim is a defect, not evidence. |
| Read `NEEDS-WIDER` as an error | It is the guard that stops "not in my slice" becoming "not in the codebase". |
| Raise `--budget` to get past a `STOP` without looking at why | The stop names what was reached and what was not. Read that first; a bigger ceiling buys more of the same cost. |
| Read `GATE-DECLINED` as an error | It means *continue, reading everything* — the gate refusing to be the reason a finding was missed. |
| Trust an `UPHELD` on a file the gate excluded | It cannot exist: that verdict is `not-accessed`. If you see one, it is a defect. |
| Answer the path question with something outside `.claude/` | It is rejected with the reason. Every artifact this plugin writes stays inside `.claude/`, so one run landing elsewhere is one run nothing else can find. |
| Delete `<base>/checklist.md` to "run clean" | IDs re-mint from 001 and every citation in the old report silently repoints. |
| `--scope "review docs"` | The agents have nothing to look for. |

## See also

`/ktkit:help docs-review` — if reading the documents would answer it, you do not need this skill.
`/ktkit:help chain` — once the gaps are known and you want a spec.

**One-line rule:** answerable by **reading** → `docs-review`. Needs a binary opened, source grepped
or an API called → `spec-recon`.
