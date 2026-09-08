# ktkit

Claude Code skills for spec-driven development: from a feature request or a bug report, to a
reviewed specification, to the change itself, to a record of what was done.

Fifteen skills, called with the plugin's namespace — `/ktkit:rca`, `/ktkit:docs-review`, and so on.
`/ktkit:help` lists them; `/ktkit:<skill> --help` explains one:

| | Skill | What it is for |
| - | ----- | -------------- |
| **Chain** | [`chain`](#chain) | a requirement → analysis → spec → plan, as one run instead of four commands |
| **Understand** | [`analyze-feat`](#the-sdd-pipeline) | a feature request → an analysis, before any spec exists |
| | [`rca`](#the-sdd-pipeline) | a bug report → root cause, by evidence rather than guesswork |
| **Specify** | [`feat-req-specs`](#the-sdd-pipeline) | an analysed feature → a reviewed spec, then stop |
| | [`bug-fix-specs`](#the-sdd-pipeline) | a diagnosed bug → a reviewed fix spec, then stop |
| **Execute** | [`feat-req-execute`](#the-sdd-pipeline) | an approved spec → plan, tasks, code, report |
| | [`bug-fix-execute`](#the-sdd-pipeline) | an approved fix spec → the fix, verified, reported |
| **Audit** | [`docs-review`](#docs-review) | documents against a standard, against the repository, or against themselves |
| | [`spec-recon`](#spec-recon) | measure what documents only claim: code, artifacts, version control |
| **Survive** | [`ccompact`](#working-skills) | checkpoint in-flight state before `/compact` eats it |
| | [`ccontinue`](#working-skills) | resume from that checkpoint, with the file outranking the summary |
| **Decide** | [`escalation-ladder`](#working-skills) | resolve an unknown from the repository before asking a human |
| | [`confirm-with-me`](#working-skills) | gate one irreversible step on an explicit yes |
| **Translate** | [`translate-file`](#working-skills) | a file into Vietnamese, without touching one identifier |
| **Help** | [`help`](#help) | the index, and one page per skill |

Two of them carry the heavier machinery. `docs-review` audits a document set with a team of agents
that run concurrently and challenge each other's findings — every run ends with a review pass carried
out in agents with their own context, not in the session that produced the work. `spec-recon` adds
the axis a document reviewer cannot reach: it measures code, binary artifacts and version-control
state, and hands each measurement back as a document the reviewers can read.

**Three rules hold across all fifteen.** They are worth reading once, because they are what make the
skills composable rather than merely co-located.

- **One artifact root.** Everything is written under `<repo-root>/.claude/claude/`, in
  `prompts/` · `analyze/` · `specs/` · `pipeline/` · `implemented/` · `compacts/`. A repository that
  does not have it gets one. No skill probes for an alternative layout, asks you where to write, or
  writes anywhere outside `<repo-root>/.claude/` — and creating a missing directory is the only
  filesystem change any of them makes on its own.
- **A preflight before the first token.** Each skill probes exactly what it is about to use and
  stops, with the fix command, if something required is absent. A capability is proved with a real
  request, never with a tool's opinion of itself.
- **speckit is required unless you say otherwise.** Four skills use it, and a missing `.specify/` or
  missing speckit skills **stops the run** at its preflight, with the command that fixes it. Passing
  `--no-speckit` selects the internalised equivalent instead — it chooses a path, it does not relax a
  check, and it holds even where speckit is installed. Nothing ever degrades on its own: the
  artifacts are the same either way, and the run always says which path it took.

## docs-review

Reviews documentation in whichever of three shapes your situation has: **critique one file** against
the repository and itself, **check documents against a standard**, or **ask a question of a document
set**. See [Using `docs-review`](#using-docs-review) for which is which.

- **Critique mode** — one file, nothing to compare it against. Its claims are verified against the repository, its open questions answered where the repo already answers them, its self-contradictions and unsupported conclusions named, and the consequences it committed to but never wrote down surfaced as `Implication`. Verdicts are `Verified` / `Refuted` / `Unverifiable` / `Contradict` / `Unsupported` / `Answerable` / `Open` / `Implication`. Nothing you wrote is edited; one delimited block is appended to the end of the file, holding a worklist of what is settled (section, line, what it says, what it should say, the repository line that settles it) and separately what only you can decide
- **Gap analysis mode** — decomposes the standard into atomic requirements *before* reading the docs, then maps each one to `Covered` / `Partial` / `Missing` / `Contradict` / `Conflict` / `Stale` / `Undecided` with a mandatory citation and quote
- **Investigation mode** — no standard? the checklist comes from the question instead, and answers are marked `Stated` / `Inferred` / `Conflicting` / `Absent`
- **A team of agents, not one reviewer** — a generic reviewer run once per round covers one or two of its checks per pass, which is why that shape needs four or five rounds. Here the work is split into roles that run concurrently and then challenge each other. Producers: `checklist` and `mapper` in gap analysis, `claims` in critique. Reviewers: `requirement` re-derives from the standard **without being shown the report**, `evidence` verifies every quote character by character, `coverage` attacks `Missing` rows in the documents' own vocabulary, `verify` settles a file's claims against the repository **without being shown the file**, `implication` finds what follows and was never said, `failure` attacks the review itself, `adjudicator` upholds or refutes each finding against the files, `fix-safety` gates edits. One or two rounds instead of four or five
- **Independence where it matters** — reviewers derive alone (no lead reasoning, no peer findings, no earlier wave's notes), then challenge with evidence. Only findings that survive the challenge are merged; refuted ones stay in the report with the evidence that killed them
- **The lead never reads the documents** — in an agentic loop the session's context is re-sent every turn, so documents read once are paid for repeatedly. The orchestrating session holds paths, IDs and finding lists; mappers read, shards are concatenated, findings are merged with targeted edits
- **Self-clarify ladder** — an unknown is classified before it is acted on: search the documents' vocabulary, the code and the file's history; challenge a disagreement once; look up an external fact from an authoritative source; assume the better-evidenced reading **with a falsifier written down**; and only then ask. A question reaching you needs six preconditions, a recommendation and a default, and must first survive a challenge by two reviewers
- **Convergence is computed, not claimed** — every wave logs its counts, and a report claiming convergence while the last row still shows new rows, changed verdicts or rejected citations fails the lint. `--rounds N` caps the waves; a cap reached with findings outstanding is reported on line 1, never as a clean exit
- **Scales by agent count, not by workflow** — index-then-shard is the pipeline at every size, so a set of eight documents and a set of eighty differ in how many mappers run, not in which steps happen. Above ~15 documents four things change: the document map (their vocabulary, not the spec's) becomes mandatory, shards follow spec chapters, the doc-vs-doc conflict sweep becomes its own pass because no single reviewer holds the whole set any more, and shard waves cap at two without counting toward the round ceiling
- **`--fix`** — edits the audited document (the output artifact, never the spec) after the review loop: `Missing` / `Partial` / `Stale` rows the spec states in full, as minimal in-place edits traced to a requirement ID. Every edit passes `fix-safety` first, and re-verification is done by `evidence` against the edited files rather than by the session that wrote them. In a deliverable still being drafted, `Contradict` is fixed too. In documentation of a running system it is only proposed — a doc contradicting the spec may be the one describing reality
- **Lint with named checks** — `references/report-schema.md` owns every heading, column and ID format, and `scripts/check_report.py` implements exactly its twenty-one checks: false convergence, unregistered IDs, missing citations, gates without a default, assumptions without a falsifier, coverage weaker than the verdicts imply, a degraded run that did not announce itself, and a material claim with no resolution written for it.
  Alongside it `scripts/verify_citations.py` opens every cited file and checks the quote is really at
  that line — a string comparison, so `evidence` is handed only the rows that failed instead of the
  whole report
- **Quiet by default** — the audit writes the report to a file and prints a short status summary. A table printed into the conversation is billed again on every later turn and arrives without its citations

```text
ktkit:docs-review 3 notes/analysis.md          # one file → critique it, 3 self-review rounds
ktkit:docs-review 3 spec.md ./docs             # standard + documents → gap analysis
ktkit:docs-review 3 spec.md ./docs --fix       # …and apply the fixable rows
Read ./docs and tell me what happens when the provider returns 409
```

## spec-recon

`docs-review` deliberately never touches the code — its reviewers are told *"you have no shell and no
web access"*, and that boundary is what makes them trustworthy. It is also their ceiling. A
document-only reviewer once reported a whole area as an unimplemented gap; the code had implemented
it months earlier, and nothing in a document-to-document review could have caught that.

`spec-recon` supplies the missing axis. It measures what documents cannot show, writes each
measurement out as an **evidence document**, and hands those to `docs-review` as first-class
sources. The invariant is not broken — the reviewers are simply given more to read.

- **Measures four kinds of thing** — source code (does this identifier exist, and where), binary
  artifacts (what sheets and named ranges a shipped `.xlsx` actually contains), version control
  (what state an issue, pull request or milestone is really in), and — only when you type its
  name — a live system. `--probe code,artifact` runs entirely offline
- **Absence claims are gated** — any verdict of the shape *not implemented / missing / not covered*
  is routed to an arbiter that opens the code and returns `REFUTED` with a `path:line`, or `UPHELD`
  carrying both the search terms that failed **and** the regions it could not reach. A verdict of
  that shape from a document-only reviewer is not a verdict, it is a routing state
- **A gap says where the change goes** — an upheld gap routes once more, to a role that returns an
  **anchor**: the `path:line` a change would land on, a one-sentence shape, and a neighbour where
  this codebase already does something similar. The lint opens every anchor and rejects the row if
  the line is not there, because "add a column to the `estimates` table" reads exactly like analysis
  and costs a week when that table does not exist. Effort estimates are rejected too — produced
  without team context, they get quoted downstream as though measured
- **Shards are sized in bytes, not lines** — a line is not a unit of cost: one line of minified
  markup carries 50 KB, one line of prose carries 60 bytes. On a real 62-document set the line rule
  handed one agent a 729 KB file, which is not merely expensive but infeasible — it reads part and
  reports as though it read all. Sizing by bytes cut that set from 79 agents to 43, capped the
  largest slice at 121 KB, and packed 42 documents under 24 KB into 2 agents instead of 42. Each
  agent gets an explicit byte range so it reads once instead of groping toward what it needs, and
  can answer `NEEDS-WIDER` when the answer lies outside its slice
- **Freshness is measured before anything is read** — revision markers live *inside* documents as
  per-section changelog tokens, and the signal is the **largest** one, not the first. An audit built
  on a superseded revision is wrong at the foundation and nothing downstream can detect it
- **Conventions are data, not code** — which revision syntaxes exist, which directories hold build
  output, which extensions are binary: all of it lives in `data/recon-patterns.json` and is extended
  with `--patterns <file.json>`. Your repository writes revisions in a way nobody here has seen? Add
  three values to a JSON file. Nothing in this toolkit is tied to the codebase it was built against,
  and a test scans every shipped file to keep it that way
- **One artifact, several copies** — the source, a copy under `bin/`, a test fixture, a hand-edited
  spare. Build output and stand-ins are disqualified; when more than one candidate survives the run
  refuses to choose and says so, and copies that differ by `md5` are themselves a finding
- **Every number carries one label** — `[measured]`, `[quoted]` or `[derived]`, and
  `check_evidence.py` fails a row that mixes them. The rule exists because a computed figure was
  once read as an observation, acted on, and had to be retracted mid-run
- **A preflight that proves capability instead of asking about it** — it does not run
  `gh auth status`, which inside a sandbox reports an invalid token for a perfectly valid one; it
  takes a token and makes one real request. A tool's error message is not evidence about its own
  cause. Anything genuinely unreachable becomes `not-accessed` with the reason, never a finding
- **Every large step ends in a file** — a crashed run resumes from the last completed step. The run
  this was modelled on lost an agent that had gathered everything in context and planned to write at
  the end; it lost all of its work
- **The fleet is planned by a script** — how many agents of which roles is deterministic and locked
  by a test, because a fleet that comes out different on every run is not dynamic, it is
  unreproducible. What each agent is *asked* stays with the session

```text
ktkit:spec-recon docs/ --scope "does the export template match the published form?"
ktkit:spec-recon spec.md ./docs --baseline design.md   # compare intent against current state
ktkit:spec-recon docs/ --probe code,artifact           # fully offline, no forge
ktkit:spec-recon docs/ --handoff off                   # stop at evidence, read it yourself

ktkit:spec-recon docs/ --scope "…"                     # 4M ceiling by default
ktkit:spec-recon docs/ --scope "…" --budget 8000000    # a large corpus
ktkit:spec-recon docs/ --scope "…" --budget 2000000    # a quick check
ktkit:spec-recon --resume <base> --budget 6000000      # continue where a ceiling stopped
```

## chain

The six pipeline skills below are meant to be driven one at a time, and that is often right — you
read each artifact before the next one is written. `chain` is for when it is not: one requirement,
one command, and you read the spec at the end.

```bash
/ktkit:chain .claude/claude/prompts/2472-share-links/expiry-rules.md
/ktkit:chain <file> --to B                 # stop at the spec
/ktkit:chain <file> --plan no --execute    # skip the plan, apply the change
```

It runs the same skills, writes the same artifacts to the same paths, and adds exactly two things
they cannot add alone.

**A ledger of what has already been settled.** Each phase runs its own escalation ladder. Left alone
they re-derive the same unknowns: the spec step pays a resolver to answer what the analysis step
already answered, and can reach a different conclusion than the artifact above it. So every settled
unknown goes into one append-only file — question, tier, conclusion, citation, and which phase
settled it — and every phase looks there before dispatching anything. A lookup is a grep; the
cheapest resolver spawn measured on this harness is 6,619 tokens before it has read a line. A
conclusion that changes writes a new row and leaves the old one in place, so what was believed, and
when it stopped being believed, stays in the file.

**One place where the run stops.** A clean run has no gate at all. At most there are two: what a
resolver could not settle and would be expensive to get wrong, and a CRITICAL finding during
execution. Both use the ladder's three tables — at most three rows to answer, each with a default
that is *already applied* so silence is a valid reply, each with a recommendation.

Two defaults worth knowing before the first run:

- **Implementation is off.** Without `--execute` the chain stops after the plan. Applying a change
  nobody reviewed the spec for is a decision, so it is a flag you type rather than a default you
  inherit.
- **There is no token ceiling**, but a cost line is printed after every step. `--budget` adds a
  ceiling, and it stops at a step boundary — never mid-step, which would leave a half-written
  artifact that reads as finished.

A crashed run resumes: `manifest.md` records every step and its status, and `--resume` restarts at
the first row that is `missing` or `partial`. A step marked `complete` is never re-run, because its
IDs are cited by every later row.

`--plan no` stops after the spec, which is what you want in a repository that generates its own
execution runbook — the chain hands over rather than running generic planning over it.

### Using it

```bash
# the ordinary case: requirement in, reviewed spec and plan out
/ktkit:chain .claude/claude/prompts/2472-share-links/expiry-rules.md

# a bug report — name the arm rather than letting it be asked
/ktkit:chain <prompt.md> --bug

# stop at the spec; you will generate the plan some other way
/ktkit:chain <prompt.md> --plan no

# pick up a run that was interrupted
/ktkit:chain <prompt.md> --resume

# apply the change as well
/ktkit:chain <prompt.md> --execute
```

The filename carries through the whole run: a requirement at
`prompts/<group>/<name>.md` produces `analyze/<group>/<name>.analyze.md`, then
`specs/<group>/<name>/spec.md`, then `plan.md` beside it. Nothing is re-slugified, so the trees
mirror each other and anything is findable at the matching path.

**Which arm it runs.** Three sources, first one that answers wins: `--bug`/`--feature` on the
command line, then `type: bug` / `type: feature` in the input file's frontmatter, then it asks. There
is no fourth — it never routes itself from the prose, because the wrong arm produces a plausible
artifact of the wrong kind and no later gate catches that. Put `type:` in your requirement template
and the question never comes up.

**Where it stops.** A bare `/ktkit:chain <file>` runs analysis, spec and plan, then stops — `--to`
already defaults to `C` and `--execute` already defaults to off, so neither needs typing. `--to B`
and `--to A` stop earlier; `--execute` is the only thing that writes code.

**Answering a gate.** The gate is answer-by-exception: every row already has its default applied, so
saying nothing accepts them and the run continues. Answer by row number — `1: allow reads, no
writes` — when you disagree. A reply that addresses no row ("ok, go on") is not an answer, and the
gate is re-posted.

**When it says `BELOW-FLOOR`.** The chain has decided it did not try hard enough and is refusing to
open a gate. That is the mechanism working, not a failure. `--rounds 3` gives it another pass;
`TOO-MANY-OPEN` alongside it almost always means the requirement is missing a section, and the fix is
to write that section rather than to answer four questions.

**Reading the result.** `spec.md` is the deliverable. Two files are there when you want to check its
reasoning rather than trust it: the analysis' unknowns table, and `chain/<group>/<name>/resolved.md`
— every question, the tier that settled it, and the `path:line` that settles it, including the ones
that were later overturned.

### What a `chain` run costs

A run is checked at every **phase** boundary against `cost.jsonl` — what agents actually reported —
and stops on a boundary rather than mid-phase. That matters more here than in a reconnaissance run,
because each phase ends on a *complete artifact*: stopping after phase B leaves a finished spec, not
half an evidence set.

⛔ **It will not choose a ceiling for you.** `--budget` is asked for, never assumed: `spec-recon`
defaults to 4,000,000 because it measured 453,571 tokens per agent, and nothing has measured this
skill. Step 00 prints what a comparable run cost and waits. `--budget-execute` gives phase D its own
ceiling, because its cost tracks the size of a change rather than the number of questions — and if
the remainder is under what phases A–C cost, phase D does not start, since a half-changed repository
is worse than an unchanged one.

Four files land beside the ledger: `cost.jsonl`/`cost.md`, `budget.jsonl`, `dispatch.jsonl`/
`dispatch.md`, and `lookup.jsonl`.

**The ledger lookup is now counted rather than claimed.** It had always been listed as one of five
places the tokens are saved, with the arithmetic — 6,619 per spawn against one grep — but nothing
counted the hits. `ledger.py --cache-metric` reports them as a **floor** on tokens not spent,
labelled as one, plus the near-misses between 0.45 and 0.60 that are the only evidence for where
`--threshold` belongs.

**A row now records when it was settled and against which commit.** A conclusion is only as current
as the tree it came from. That also makes `--ledger-scope dir` safe: it reads sibling runs' ledgers
in the same directory and reports a match as `FOREIGN` with **exit 2** — a lead for a resolver, never
a conclusion, printed with its age and its commit. Last week's answer may be stale, and a wrong `HIT`
is worse than a `MISS`, because the chain then cites an answer to a question nobody asked now and
stops looking.

## The SDD pipeline

Six skills, one road. Each stops at a gate you control, and each hands the next one a file rather
than a conversation — so the pipeline survives a compaction, a new session, or a different person
picking it up tomorrow.

```text
        a feature request                      a bug report
                │                                    │
     /ktkit:analyze-feat                        /ktkit:rca
     → analyze/<name>.analyze.md          → analyze/<name>.analyze.md
                │                                    │
     /ktkit:feat-req-specs                 /ktkit:bug-fix-specs
     → specs/<base>/spec.md                → specs/<base>/spec.md
                │                                    │
          ── HARD STOP: you review the spec and approve it ──
                │                                    │
    /ktkit:feat-req-execute               /ktkit:bug-fix-execute
    → plan.md, tasks.md, code             → the fix, verified
    → implemented/<base>.implt.md         → implemented/<name>.implt.md
```

- **`analyze-feat`** — reads a feature request and works out what it touches, what it conflicts with,
  and what is genuinely unknown, *before* anyone writes a spec. Unknowns go through the escalation
  ladder rather than into an interview: what the repository can answer is answered, and what reaches
  you comes as at most three rows, each with a default already applied and a recommendation.
- **`rca`** — a bug report to a root cause through five Whys, each link carrying evidence, plus an
  explicit blast radius. It writes a report and hands off; it never fixes anything.
- **`feat-req-specs` / `bug-fix-specs`** — turn that analysis into a specification with acceptance
  criteria, scenarios and a quality checklist that tests *the spec*, not the running system. Both
  stop dead afterwards. No plan, no tasks, no code.
- **`feat-req-execute` / `bug-fix-execute`** — take an approved spec and carry it out. Both refuse
  format-only edits; both read the repository's own test command instead of guessing it; and
  `feat-req-execute` detects a repository that has its own execution runbook and hands the decision
  back to you rather than silently running generic speckit over it.

Every one of them writes its output under the artifact root and tells you the path. Nothing is
printed into the conversation twice.

**Where speckit is installed, the pipeline pins the feature directory rather than exporting it.**
Every script-backed speckit skill — `plan`, `tasks`, `clarify`, `checklist`, `analyze` — resolves
its feature directory from `SPECIFY_FEATURE_DIRECTORY` first and `.specify/feature.json` second.
The environment variable is the obvious lever and the one that cannot work here: it lives in one
Bash invocation, and the shell that runs the script belongs to the skill, opened later, clean. So
resolution falls through to the file, which is a single mutable pointer for the whole repository,
written by whichever run touched it last. Left alone, `/speckit.plan` then resolves someone else's
feature, copies the plan template over **that** feature's `plan.md`, and exits 0 — a wrong write
reported as a success. `scripts/speckit_pin.py` writes the pointer at the feature in play, reports
`<old> -> <new>` so an inherited one is visible, and skips cleanly in a repository with no
`.specify/`. It also removes the branch-name gate from `setup-plan.sh` and `setup-tasks.sh`, which
skip it entirely when the pin matches — no branch renamed, no git state touched. The preflight
prints the current pin next to the scaffolding checks, before anything is spent.

## Working skills

The other five are small, and are used from inside the six above as much as directly.

- **`ccompact` / `ccontinue`** — a long pipeline outlives its context window. `ccompact` writes the
  state that exists *only* in the conversation — decisions and the reasons for them, rejected
  options, half-finished work, traps already hit — to a durable file, then hard-stops and prints the
  exact `/compact` line to paste. `ccontinue` picks it up on the far side, compares the recorded
  branch and HEAD against reality, and reports every place the compaction summary and the file
  disagree. **The file always wins.** It never copies the spec into the checkpoint: intent is
  already on disk, and the whole point is to save what is not.
- **`escalation-ladder`** — five tiers between "I do not know" and asking you. Search what is
  openable; challenge a disagreement once; look up an authoritative external fact; assume the
  better-evidenced reading **with a falsifier written down**; and only then ask, with a default
  already applied so that silence is a valid answer. A question that reaches you has failed four
  cheaper attempts first.
- **`confirm-with-me`** — when the literal phrase `confirm with me` appears anywhere in the active
  context, this gate blocks that one step until you reply `confirm`, `abort` or `modify: <change>`.
  One marker, one gate: approval of a large task never implies approval of a step inside it.
  A description alone is a ranking hint, not an order, so the plugin ships a `SessionStart` hook
  that states the rule in every session where `ktkit` is installed. It writes nothing to your
  `CLAUDE.md` — uninstalling the plugin removes the rule, which a line appended to your own rule file
  would not. It costs about 190 tokens per session.
- **`translate-file`** — translates a file's prose into Vietnamese and leaves everything else
  untouched: identifiers, code, paths, commands, URLs, JSON keys, brand names. Japanese proper nouns
  that stay untranslated get an English gloss. It confirms the source file before starting, writes
  `<stem>_vi.<ext>` beside the original, and never edits the original. It is the one skill here that
  writes outside the artifact root, because output beside the source is the point.

### A note on language

`analyze-feat`, `rca`, both `*-specs` and both `*-execute` skills write their **reports and specs in
Vietnamese**, keeping every identifier, path, snippet and technical term in English. That is
deliberate: the reviewer reads Vietnamese, and prose in Vietnamese removes friction without costing
any precision. The skill files themselves, and everything they write to a forge, are English.

### The ceiling on a `spec-recon` run

A run defaults to a **4,000,000-token ceiling**, and `--budget` moves it: `8000000` for a large
corpus, `2000000` for a quick check. It is checked at every step boundary against `cost.jsonl` —
what agents actually reported, never an estimate — and nothing is forecast: the arithmetic is
`spent + last_step × 1.5 > budget`, where `last_step` is the difference in spend since the previous
boundary.

Reaching it stops the run **between steps**, with everything finished on disk, `partial` in the
manifest naming what was not reached, and a `--resume` command printed. A cheap step still passes
where an expensive one does not — measured: at 3.17M of a 4M ceiling the gate refused another 927k
extraction batch and then allowed a 305k arbitration, so the verdicts land even when the extraction
cannot continue. That ordering is deliberate; a run that stops with evidence and no verdicts has
spent everything and delivered nothing, which is exactly the failure this replaced.

**A ceiling the window cannot reach is rejected outright**, and it hands back the number that fits:

```text
STOP  after 03-extract
  window ⛔ allows only about 11,103,750 tokens in total, at this run's own rate
           of 113,375 per 1%  [measured here, not stored]

  BUDGET-UNREACHABLE. Re-run with a ceiling this window can hold:
      --budget 11103750
  Or wait for the reset in 132 min and keep the ceiling you wanted.
```

⚠️ That figure is **computed each time and is never a constant**. It is what has been spent plus the
remaining subscription window at this run's own measured rate, so it moves as the window empties and
differs per corpus: the same rate allows ~14.5M at 84% headroom and ~4.8M at 20%, and a lighter
corpus at the same headroom allows ~35M. Writing any of those down as a limit would permit a run
that cannot finish and refuse one that could. The rate is measured inside the run and discarded with
it — never stored, because signing in with a different account moves the window from 94% used to 6%
and a persisted ratio would survive that silently.

`scripts/quota.py` reads the window on its own (`--gate <pct>`), and failing to read it never blocks
a run: unreachable is not exhausted, and the report says `quota not-checked` with the reason.

### Where the tokens actually go

A 24-agent run recorded tokens and tool calls per agent, which was enough to test the models this
toolkit had been reasoning with. They did not survive.

| Candidate driver | R² over 24 agents |
| ---------------- | ----------------: |
| `sqrt(calls)` | 0.476 |
| `calls` (linear) | 0.421 |
| **`calls(calls+1)/2` (quadratic)** | **0.298** — worst of the three |
| output tokens written | 0.145, slope negative |

⛔ **A proposed cap of six tool calls per agent rested on that quadratic and is withdrawn.** Agents
making ≥40 calls averaged 269,243 tokens against 149,564 for those making ≤6 — **1.8×**, not the
order of magnitude a quadratic implies.

**What the data shows instead is a large per-agent floor.** The cheapest agent in that run cost
**123,460 tokens at four tool calls**, and 24 × that floor is 55% of the whole run. So the lever with
measured support is **fewer agents, not fewer calls**: dropping one agent saved a mean of 222,713
tokens. Both shipped gates do exactly that — the relevance gate takes 48 mapper agents to 20, and
`probe_index.py` removes the agent entirely for an identifier with no occurrences.

⚠️ **And the floor itself is not yet explained.** Wave 1 was handed 852,260 bytes of document —
~213,000 tokens, **9.7%** of what it spent. `arbiter-B-bugs-accept` spent 398,092 tokens and wrote
2,286 back. One term was never measured: the prompt the lead composes and sends, which is written
nowhere and is re-sent on every internal turn a subagent takes. `scripts/dispatch_log.py` records it
and `dispatch.md` pairs it against spend in the shape that matters, `payload × calls`. Nothing is cut
on the strength of that yet — cutting before measuring is how the tool-call cap came to be proposed.

### The identifier sweep runs in a script

`probe-code` was the most expensive role in the fleet and should have been the cheapest. Its question
is small — does this identifier exist, and where — but the search ran inside the agent. On a real
repository `src/` holds 14,627 tracked files, and one `Grep` for `export` returns 15,358 matching
lines across 3,801 files; that lands in the agent's context and is re-sent on every later call.

`scripts/probe_index.py` runs the sweep as a script and writes an index — counts, sampled
`path:line` rows, and the exact commands. The same four searches cost ~185,000 tokens inside an agent
and **~1,700** as an index, and an identifier with zero occurrences dispatches no agent at all.

⛔ The script states counts and lines and **never** `EXISTS`, `NOT_FOUND` or `PARTIAL`. A count is a
measurement; what an absence *means* is a judgement, and moving that into a script would trade cost
for the kind of confident wrong answer this toolkit exists to prevent.

### Reading only what the question is in

Before any agent is dispatched, `--scope` becomes a search vocabulary and each input is scored in
hits per kilobyte. Measured on a real 64-file corpus, that takes wave 1 from **48 mapper agents to
20** — 54 of those files contained not one occurrence of anything the question was about.

Density, not presence: a 456 KB reference table with two incidental matches is not relevant, and an
agent sent to find them is how a run reaches fifteen million tokens.

⛔ **Narrowing is never silent.** `steps/01b-relevance.md` names every excluded file with its size
and hit count, the report carries a `## Not read` section, and an absence claim resting on an
excluded file is `not-accessed: cut by the relevance gate` — **never `UPHELD`**. Without that last
rule the gate turns "I did not read it" into "it does not exist".

**The gate declines rather than guess.** When the corpus is mostly in a script none of its terms are,
or the vocabulary matched nothing anywhere, it keeps everything and prints why. Measured: a scope
written in Vietnamese and English produced four ASCII terms against a corpus that is 68% Japanese,
and would have excluded the two main specification documents — 729 KB and 223 KB, zero hits each,
because the question said `export` and the document says `出力`. A document carrying revision markers
is separately **rescued** whatever its density: cutting the specification on a question about the
specification is the gate being wrong.

### What a `spec-recon` run cost

Cost is an artifact, not a line of chat. `<base>/cost.jsonl` gains one append-only row per agent and
`<base>/cost.md` renders it: a total, a per-wave table with a running figure, and a row per agent —
every number taken from the `usage` that agent reported.

Three rules make it worth trusting. An agent that reported nothing is recorded as having reported
nothing, and the total names how many it excludes, so it reads as a floor rather than as the bill —
never an average. The log is append-only, so a re-run wave adds rows and what the failed attempt cost
stays in the record. And the page says out loud that the lead's own turns are **not** in the total,
because an agent cannot measure the session that dispatched it and a total that silently omits the
largest term is worse than no total.

The logging is itself batched to one call per wave. Measured on a 43-agent wave that is ~521 tokens
against ~4,106 for a call per agent — 0.019% of a 2.75M-token run instead of 0.149%. Tracking that
consumed a noticeable share of what it tracks would not be worth keeping.

### Where a `spec-recon` run writes

A reconnaissance run produces a **directory** — a report, a `recon.json`, seven step files, one
evidence file per probe — and every later phase cites paths inside it. So the location is settled
before anything is measured: without `--out`, the run prints a suggested path together with the tree
it would create, and **stops for an answer**. The suggestion is derived from the inputs by the same
mirror algorithm `ccompact` uses, never built from `--scope` and never re-slugified. A path outside
`.claude/` is rejected with the reason.

Until 3.4.0 it was not like that. `--out` defaulted to the bare string `spec-recon.md`, which
resolves against the working directory, so a run put its report and its whole directory at the
repository root — outside `.claude/`, against the rule every skill here follows. Nothing failed and
no check fired; the files simply appeared in the wrong place.
`skills/spec-recon/tests/test_out_path.py` is that defect turned into sixteen assertions.

## help

```bash
/ktkit:help                  # the index: every skill, one line each
/ktkit:help chain            # one skill's page — cases, flags, output, anti-patterns
/ktkit:help --all            # every page, end to end
/ktkit:chain --help          # the same page, CLI-style
```

`--help`, `-h` and `help` work on **any** ktkit skill as long as it is the only argument; with other
arguments present the skill runs normally, so `/ktkit:chain req.md --help` runs chain. The protocol
is installed by the plugin's SessionStart hook rather than pasted into fifteen skill bodies — one
rule, paid once per session, instead of fifteen copies paid on every run.

Each page lives beside the skill it documents, at `skills/<name>/references/help.md`, and the index
is assembled from those files by `scripts/help.py` — so a skill added to this plugin appears in the
index without anyone editing a list.

**The pages are checked against the skills.** `skills/spec-recon/tests/test_help.py` compares every
page with that skill's own `## Arguments` section in both directions: a flag a page documents that
the skill does not accept fails the suite, and so does a flag the skill accepts that no page
mentions. Help that is merely written drifts; help that is checked cannot drift without going red.

## Runbooks

`/ktkit:help <skill>` answers "what are the flags". A runbook answers the other question — "what do I
actually type on a Tuesday" — and is written for the person driving rather than for the model: worked
cases end to end, the gate transcript, how to read a verdict, what to do when a ceiling stops a run.

Two exist for the two heavy skills, `chain` and `spec-recon`, and they live in the repository you are
working in rather than in this one:

```
<your repo>/.claude/claude/prompts/runbooks/ktkit-chain.runbook.md
<your repo>/.claude/claude/prompts/runbooks/ktkit-spec-recon.runbook.md
```

⛔ They are **not** shipped with the plugin and this README does not link to them, because
`.claude/` is gitignored in the repository they were written in — a README pointing at a file nobody
who clones gets is a dead link that reads like documentation. Ask the skill for its own guidance
instead: `/ktkit:help chain`, `/ktkit:help spec-recon`.

## Install

### Option A — Plugin marketplace (recommended)

```bash
# one-time: register this repo as a marketplace
claude plugin marketplace add kanechan25/ktkit

# then install — plugin@marketplace, both named ktkit
claude plugin install ktkit@ktkit
```

Or via the interactive UI:

```text
/plugin marketplace add kanechan25/ktkit
/plugin install ktkit@ktkit
```

Installing as a plugin is what registers the eighteen agents and the MCP server. Verify after
install:

```text
/context          # Custom agents: ktkit:docs-review-* and ktkit:spec-recon-*
                  # MCP tools:     mcp__plugin_ktkit_sequential-thinking__sequentialthinking
```

**What installing costs you, before you run anything.** Two of the thirteen skills use
sequential-thinking for their reasoning step, so the plugin ships that server itself in `.mcp.json`
rather than asking you to install it — a hand-installed copy registers under a different tool name
and the skills would not find it. The price is that its schema sits in **every** session that has
`ktkit` installed, used or not: **~1.3k tokens**, measured with `/context`. For scale, all eighteen
role prompts together are also ~1.3k. Worth knowing; not worth avoiding.

### Option B — Manual (copy a skill)

```bash
cp -R skills/docs-review ~/.claude/skills/docs-review
```

Copying works for any skill here, but it skips three things the plugin provides: `agents/`,
`.mcp.json`, and `${CLAUDE_PLUGIN_ROOT}`. Concretely — `docs-review` falls back to a single generic
reviewer (it still runs and still says so: the report's first line reads `DEGRADED` and
`## Review team` marks the rows, but the roles no longer see the documents independently);
`bug-fix-specs` and `feat-req-specs` lose their reasoning tool; and every skill's preflight loses the
shared `scripts/preflight.py` it resolves through the plugin root. Prefer Option A.

## Update

Two commands, then a reload. `add` and `install` are one-time; neither pulls new code.

```bash
claude plugin marketplace update ktkit && claude plugin update ktkit@ktkit
```

```text
/reload-plugins
```

The CLI ends with `Restart to apply changes` because your running session still holds the previous
version's agents and skills. `/reload-plugins` applies them in place; a new session works too.

What each command does, since the difference matters when one of them looks like a no-op:

| Command | Effect |
| ------- | ------ |
| `claude plugin marketplace update ktkit` | Refreshes the local copy of this repository, so the catalog and the plugin's declared version are current |
| `claude plugin update ktkit@ktkit` | Installs the new version into `~/.claude/plugins/cache/ktkit/ktkit/<version>/`, if the version changed |
| `/reload-plugins` | Swaps the running session onto it |

Check what you ended up on:

```bash
ls ~/.claude/plugins/cache/ktkit/ktkit/     # one directory per installed version
```

Old versions are kept beside the new one, and the one in use is recorded in
`~/.claude/plugins/installed_plugins.json`.

### Upgrading to 4.1.0 — the feature directory is pinned, not exported

Nothing to do, and one thing to know: if you run any SDD skill in a repository with speckit
scaffolding, it now writes `.specify/feature.json` before calling a speckit skill, and prints the
value it replaced.

That file is spec-kit's own persisted pointer — the same key `/speckit.specify` writes — and until
now these skills relied on `SPECIFY_FEATURE_DIRECTORY` instead, which is first in spec-kit's
resolution order and therefore looked sufficient. It is not reachable: an `export` lives in one
Bash invocation, and the shell that runs `setup-plan.sh` belongs to the speckit skill, opened
later, clean. Resolution fell through to the file, which no skill was writing, so a pointer from an
unrelated feature stayed in place and `/speckit.plan` copied the plan template into **that**
feature's directory and exited 0.

- The previous pointer is saved to `.specify/feature.json.bak` on the first repin.
- Sibling keys in that file are kept; only `feature_directory` is written.
- A repository with no `.specify/` is unaffected — the pin reports SKIP and the internalised path
  runs exactly as before.
- `preflight.py --groups speckit` now prints the current pin, so a stale one is visible before any
  spend. It never fails on it: at preflight time there is no feature directory to compare against.
- ⛔ One thing the pin cannot fix: `setup-plan.sh` copies the plan template over `plan.md`
  unconditionally, with no prompt and no backup. `feat-req-execute` and `chain` now say so and copy
  an existing plan aside first. If you drive `/speckit.plan` yourself over a hand-written plan, do
  the same.

### Upgrading to 3.1.0 — the chain, and the half of the ladder that was missing

Additive, with one behaviour change worth reading before you run `rca` again.

**`/ktkit:chain` is new.** Nothing else changed to accommodate it: it calls the existing skills and
writes the existing artifacts to the existing paths. Its own trace lives under
`.claude/claude/chain/`, which is new and is created on first use.

**`rca` and `bug-fix-specs` now use the escalation ladder.** They did not before, and `rca` carried a
constraint that said the opposite in as many words — *"if the expected behavior is ambiguous, STOP
and ask the user"*. So half the pipeline resolved its own unknowns and half interviewed you, and
nothing said which half you were in.

Both now route an unknown by what being wrong would cost: what the repository can settle is settled
by a resolver, a cheap-if-wrong reading becomes an assumption **with a falsifier written down**, and
only an expensive-if-wrong ambiguity reaches you — at most three rows, each with a default already
applied. If you relied on `rca` stopping to ask about business rules, it still does, but only for the
ones where being wrong is expensive. A test now enforces the adoption across all four analysis
skills, so it cannot drift back to half.

**`escalation-resolver` now ships with the plugin.** Two skills dispatched it by bare name while it
existed only as a user-level agent — on any other machine that dispatch found nothing. It is now
`ktkit:escalation-resolver`, and its declared tool set was corrected from `Read, Grep, Glob, Bash` to
`Read, Bash`: this harness silently drops `Grep` and `Glob` when `Bash` is granted, so the agent had
been searching without them while its prompt still told it to grep.

**The `confirm with me` marker is armed by a hook.** A `SessionStart` hook states the rule in every
session that has this plugin, at about 190 tokens. It writes nothing to your `CLAUDE.md` — and if you
added a line there yourself when the README suggested it, you can remove it; the hook covers it, and
removing the plugin now removes the rule.

**`--no-speckit` is documented as what it always was.** A missing `.specify/` stops the run; the flag
selects the internalised path deliberately, including on machines where speckit is present. No
behaviour changed here, only the wording — the old text read as though the fallback might happen on
its own.

### Upgrading to 3.0.0 — ktkit became a toolkit

Up to 2.1.0 this plugin was two skills that audit documents. 3.0.0 adds eleven more and turns it into
the whole spec-driven path: analyse, specify, execute, audit. Nothing about `docs-review` or
`spec-recon` changed in the process — the same commands, flags and outputs.

Four things are new, and all four affect skills you already had:

- **A fixed artifact root.** Every skill writes under `<repo-root>/.claude/claude/`, creating it when
  the repository has none. `ccompact` in particular no longer probes for a `.claude/claude` layout
  and fall back to `.claude/` — one rule, everywhere. **Checkpoints written by an older `ccompact`
  under `.claude/compacts/` are not moved.** Point `/ktkit:ccontinue` at the old path and it reads
  them fine; new ones land under the artifact root.
- **An MCP server ships with the plugin.** See the note under *Install* for what it costs you.
- **Skills call each other by namespace.** Every internal call is written `/ktkit:<name>` in full, so
  a skill never silently reaches a same-named copy in `~/.claude/skills/`. If you keep your own
  `/rca` or `/ccompact` there, both continue to work and stay independent — pick whichever you want,
  they cannot shadow each other.
- **speckit is now optional everywhere.** `bug-fix-specs`, `feat-req-specs` and `feat-req-execute`
  used to stop and ask when `.specify/` was missing. They now run an internalised path that produces
  the same files at the same paths, and report which path they took. `--no-speckit` chooses it up
  front. If you *want* the old hard stop, the preflight still gives it to you: it fails when
  scaffolding is absent, and names both ways forward.

### Upgrading to 1.9.0 — `--team off` does something again

`docs-review --team off` has been documented since the agent team landed, but the procedure it
pointed at — one context doing the audit, one blind reviewer attacking it each round — was left
behind in the refactor. The flag named a loop that existed in no file, so a lead that hit it
improvised. From 1.9.0 it follows `references/solo-loop.md`.

Three things worth knowing before you reach for it:

- **Mode A and Mode B only.** Critiquing a single document is refused with `--team off`, because
  Mode C's whole content is that the role settling a claim has never read the argument for it. One
  context cannot un-read the document.
- **It is not the cheap option.** A single context pays for its entire prefix on every tool call it
  makes, and that prefix holds the spec, the documents and everything it has read. Pick it for one
  transcript you can debug, or to leave the team's quota alone — not to save tokens.
- **It is not `DEGRADED`.** That is the team being unavailable, and it still says so on line 1. A
  solo run is a choice and reports as `Mode=solo`.

Its reviewer is a lean role rather than the `general-purpose` agent the pre-team version used:
measured on this harness, `general-purpose` costs **35,132** base tokens against **6,619** for a
three-tool role doing the same job.

Also in 1.9.0: Mode C gained the wave protocol it never had — whether `implication` findings reached
the adjudicator was previously left to inference, which left the reasoning axis unguarded for a round
while factual claims carried three guards.

### Upgrading to 1.8.0 — where the working files went

`docs-review` used to write its working files loose beside the report. From 1.8.0 they go into one
directory named after the report: a report at `spec.docs-review.md` keeps its artifacts in
`spec.docs-review/`.

**Your old artifacts stay where they are.** The skill does not tidy them up, on purpose: the
directory it was pointed at is also where your own files live, and a cleanup pass that guesses which
loose `.md` files were "probably the audit's" is one bad guess away from deleting your work. Delete
them yourself when you are ready — from a 1.7.0 run they are the loose `claims*.md`, `rows-*.md`,
`verdicts-*.tsv`, `findings-wave*.md` and `docs-history.md` sitting next to the report.

Inside the new directory two things are kept rather than cleaned: `claims.md` and `checklist.md` are
ID registries. Delete one and the next run re-mints IDs from 001, so every `CLM-014` in the old
report points at a different statement.

### Two things that will confuse you once

**Nothing happened, and no error.** The version is the update signal: if `version` in
`.claude-plugin/plugin.json` did not change, you keep the copy you have no matter how much code was
pushed. Compare the version in the refreshed marketplace against the one installed before assuming
the update failed.

**`EPERM: operation not permitted, rename … -> ….bak`.** `marketplace update` deletes and re-clones
rather than pulling, and the rename it does first fails if the process cannot write in
`~/.claude/plugins/`. Running it from a shell inside a sandboxed Claude Code session is the usual
cause — run it in your own terminal instead. The error suggests deleting the directory by hand; you
almost never need to.

### If you maintain a fork

Bump `version` in `.claude-plugin/plugin.json` on every release. That is the only place it lives —
the marketplace entry deliberately does not declare one, so there is a single field to change and no
second copy to forget.

## Using `docs-review`

There are three ways to point this at a document, and the skill picks between them from **what you
give it**, not from a flag:

| You give it | Mode | The question it answers |
| ----------- | ---- | ----------------------- |
| **One file, nothing else** | **C — critique** | "What in this file is wrong, unsupported, self-contradicting, or already answered elsewhere?" |
| A **standard** plus the **documents** meant to describe it | **A — gap analysis** | "Do these documents say what the standard requires?" |
| Documents plus a **question** | **B — investigation** | "What do these documents say about X, and what do they never say?" |

Several files with no standard and no question is the one case it will not guess at: it asks which
file is the standard, or what the question is. It will not summarize them instead — a summary reads
fine even when the document is missing half of what it should say, which is the failure this skill
exists to prevent.

---

### Mode C — critique one file

For the file you wrote yourself: a design note, an analysis, a spec draft, a hand-over document. The
kind of file that has correct claims, wrong claims, open questions and conclusions all mixed
together.

```text
ktkit:docs-review 3 docs/specs/billing/retry/abc.md
```

`3` is the number of **self-review rounds**. Round 1 reviews the file. **Round 2 reviews round 1's own
output** — which verdicts cite evidence that does not support them, which refutations are wrong, and
above all where the review argued with something you never wrote. Round 3 does the same to round 2. A
round that finds nothing material ends it early; `3` is a ceiling, not a quota.

There is no second file to compare against, and it will not ask you for one. Four standards live
inside the situation, and all four are checkable:

| It checks | How |
| --------- | --- |
| **Is the claim true?** | Opens the repository — source, config, docs, `git log` — and looks |
| **Does the file contradict itself?** | Two statements that cannot both hold, both quoted with line numbers |
| **Is that open question really open?** | Searches the repo and the history first. Most "TBD" notes are already answered somewhere in the tree |
| **Does the conclusion follow?** | Against the evidence the file itself supplies, not against outside knowledge |

Plus two passes that go beyond the text:

* **Knock-on** — a statement is true, something follows from it, and the file never says it. A
  decision written down without its consequence is the expensive kind of gap, because you will act on
  the decision.
* **Widening** — the file addresses A; A belongs to a class that also holds B and C it never mentions.
  The class is named, so the omission is arguable instead of a matter of taste.

What you read in the report:

| Verdict | Means |
| ------- | ----- |
| `Refuted` | The claim is false, with the line in the repo that says otherwise. The row that earns the run |
| `Answerable` | You marked it as an open question; the repo answers it. **The answer is in the row** |
| `Verified` | Checked and true, with `path:line` |
| `Contradict` | Another statement in the same file disagrees, and both are cited |
| `Unsupported` | An assertion the file's own evidence does not carry |
| `Implication` | Follows from something you wrote, and you did not write it |
| `Open` | Genuinely undecided, with the searches that establish that |
| `Unverifiable` | Nothing could settle it, with everything that was tried |

What the rows look like, from a real run:

```markdown
| CLM ID  | Statement | Kind | Verdict | Evidence | Quote | Note |
| CLM-001 | "granting Bash to an agent removes Grep and Glob" | fact | Verified | harness-probe.md:41 | "probe-set-b declared Read, Grep, Glob, Bash and received Read, Bash" | - |
| CLM-002 | "the plugin registers eight agents" | fact | Refuted | agents/:1 | "eleven files match agents/docs-review-*.md" | three roles were added after the note was written |
| CLM-004 | "open question: does .claude/agents hot-load?" | question | Answerable | .claude/agents:1 | "Agent type 'probe-set-a' not found" | Yes, with a delay: the first spawn after writing fails, a later one in the same session succeeds. No restart needed |
```

`CLM-002` is the shape worth having: a sentence that was true when it was written and is not any
more. `CLM-004` is the other one — you wrote down a question, and the answer was in the repository
the whole time.

**Nothing you wrote is edited.** Not one line. A file full of your own reasoning is the last place for
automated edits, and a reviewer that misread you would write the misreading into your file.

What does go back is one block at the **end** of the file, between markers, so the findings are in
front of you the next time you open it instead of in a report you have to remember to reopen:

```markdown
<!-- docs-review:begin -->
## Review status

`spec.docs-review.md` · round 2 · 118 claims · 76 Verified

### Settled — safe to apply

| CLM | Where, in this file | Says now | Should say | Source |
| --- | ------------------- | -------- | ---------- | ------ |
| [CLM-031](spec.docs-review.md#clm-031) | §8, line 210 | *open question:* does OnlyOffice support named ranges? | Yes | `docs/onlyoffice.md:88` |
| [CLM-014](spec.docs-review.md#clm-014) | §3.2, line 88 | `retryLimit` defaults to 5 | `retryLimit` defaults to 3 | `src/config/retry.ts:22` |

### Yours to decide — nobody can apply these for you

| CLM | Verdict | The problem |
| --- | ------- | ----------- |
| [CLM-047](spec.docs-review.md#clm-047) | Contradict | §5 and §9 disagree on when the cache is written; which one you meant is not recoverable from the file |
| [CLM-052](spec.docs-review.md#clm-052) | Unsupported | "cuts latency 40%" — the evidence in this document does not carry the number |
<!-- docs-review:end -->
```

The first table is a worklist: section, line, what it says, what it should say, and the file in the
repository that settles it. Enough to apply a row without opening the report. It is sorted by line
number descending, so applying from the top never shifts the lines below it.

The second table is everything nobody can decide for you — a contradiction where only you know which
side you meant, a number the file's own evidence does not support, a consequence you may or may not
want to write down. Between them the two tables hold **every** material finding.

Run it again and the block is replaced, not duplicated. Everything above the marker is copied byte
for byte; if that ever changed, it would be a bug in the skill, not a judgement call it is allowed to
make. The links point at `### CLM-014` headings in the report, and the skill fails the run if one of
them does not resolve.

---

### Mode A — do the docs match the standard?

Two sides: one is authoritative, the other has to describe it.

```text
ktkit:docs-review 3 docs/req-1234.md ./docs
```

The first path is the standard, the rest are the documents. Which way round matters, and both
directions are useful:

```text
# the ticket is the standard; the draft has to say what it requires
ktkit:docs-review 3 docs/req-1234.md docs/specs/billing/retry/abc.md

# abc.md is settled; the other docs have to keep up with it
ktkit:docs-review 3 docs/specs/billing/retry/abc.md ./docs ./api-design
```

You get one row per requirement in the standard:

| Verdict | Means |
| ------- | ----- |
| `Covered` | The documents state it, matching the standard |
| `Partial` | Stated but incomplete — a condition, case or value is absent |
| `Missing` | No document states it. The row records the terms it searched, so you can see where it looked |
| `Contradict` | A document states something the standard contradicts |
| `Conflict` | Two documents disagree with each other — both cited, no winner picked silently |
| `Stale` | Superseded: an old field name, a removed flow, a changed value |
| `Undecided` | The standard itself is ambiguous, or an external fact could not be verified |

`Conflict` is found by a separate sweep over every value the documents assert, because two documents
that disagree rarely land under the same requirement — a per-requirement lookup would never have
caught it.

What the rows look like, from a real run:

```markdown
| Req ID      | Requirement | Tier | Verdict | Evidence | Quote | Note |
| REQ-AMT-001 | Amount rejects values below 0 | - | Covered | docs/manual.md:42 | "values below zero are rejected" | - |
| REQ-AMT-002 | Amount rejects values above 1,000,000 | T1 | Missing | | | searched "1,000,000", "upper limit", "上限" across docs/*.md |
| REQ-AMT-003 | Rounding mode for partial units | T4 | Undecided | | | escalated as D1 |
```

A `Missing` row carries the terms it searched, so you can tell a real gap from a search that stopped
too early — the two are indistinguishable otherwise, and only one of them is the documents' fault.
The `Tier` column says how the row was settled: `T1` means the answer was found by searching, `T4`
means it became a question for you.

Mode A is the only mode that can edit:

```text
ktkit:docs-review 3 docs/req-1234.md ./docs --fix
```

`--fix` edits **the documents**, never the standard, and only after the review has finished. It
applies `Missing`, `Partial` and `Stale` rows the standard states in full, as minimal in-place edits
each traced to a requirement ID. Every edit is reviewed before it is written, and the edited sections
are re-checked by a different role than the one that wrote them. Two things it will not do quietly:
it never invents a value the standard does not state, and for documentation of a running system it
only *proposes* a fix where a document contradicts the standard — that document may be the one
describing what the system actually does. Those land in `## Proposed, not applied`.

---

### Mode B — ask a question of a document set

Two ways in — plain language, or the skill name with the question after the paths:

```text
Read ./docs and tell me: what happens to an in-flight retry when the provider returns 409?

ktkit:docs-review ./docs — what happens to an in-flight retry when the provider returns 409?
```

What makes it Mode B is that there is a **question** and no standard. Drop the question and you are
back in the case it will not guess at.

The question is decomposed into sub-questions **before** the documents are opened — a checklist built
from the documents can only find what the documents already thought of. Each answer is marked
`Stated` / `Inferred` / `Conflicting` / `Absent`.

The section to read is `## What the documents do not say`: the `Absent` and `Conflicting` rows
together. That is the part you cannot get by reading the documents yourself.

---

### Flags

| Flag | Effect |
| ---- | ------ |
| `<N>` (bare integer) | Same as `--rounds N` |
| `--rounds N` | Ceiling on review rounds. Convergence can end it earlier; the ceiling never forces an extra round |
| `--rounds auto` | The default: **3** with the team, **5** with `--team off` — one reviewer finds less per round than four specialists |
| `--max-questions N` | At most N rows may reach you as questions. Default 3 |
| `--out <path>` | Where the report goes. Default `docs-review.md` |
| `--fix` | Mode A: apply the fixable rows after the loop. Mode B has no standard the documents failed, so there is nothing to fix; Mode C never edits your file's content |
| `--silent` | Print the report path and nothing else |
| `--team off` | Run the loop in one context with one blind reviewer instead of the team. **Mode A and B only** — refused in Mode C. Not the same as `DEGRADED`, which is the team being unavailable: this is a choice, and the report marks it `Mode=solo` |
| `--ask-only` | Diagnostic: skip the searching and surface every unknown as a question. Shows you what the ladder was absorbing. Never leave it on |
| `--keep-scratch` | Keep the run's intermediate files instead of deleting them after a clean run |

A ceiling reached with findings still outstanding is not a clean pass: the report's first line says
`BUDGET-CAPPED` and lists what was left unmerged.

### If something looks wrong

| Line 1 of the report says | What happened |
| ------------------------- | ------------- |
| `DEGRADED — ran without the agent team` | The agents are not registered. Install as a plugin (Option A) rather than copying the skill, and run `/reload-plugins` after installing or updating |
| `BUDGET-CAPPED — stopped at round N of N` | The round ceiling was hit while findings were still moving. Re-run with a higher `<N>`, or read the outstanding list under that line |
| `INCOMPLETE — review loop stopped after round N` | Something ended the run early. The unmerged findings are listed under it |

Other things worth knowing:

* **It asked you what to compare against.** You gave it several files with no standard and no
  question. Name the standard first, or ask a question — see the table at the top.
* **A lot of `Missing` rows.** Check their Note: if the search terms are all the standard's own
  wording, the documents probably use different words and the rows are search failures rather than
  gaps. That is a bug worth reporting.
* **`## Needs user decision` is long.** It should be at most three rows, and each one has to prove
  the repository could not answer it. More than that means the searching gave up early.
* **The report claims it converged but the log disagrees.** The lint fails that case
  (`C1 false-convergence`); if you see it, the lint was not run.

---

### What actually happens when you run it

Not one long read — a short pipeline of agents, each with its own context:

1. **Parses and echoes** what it understood in one line, so a mistyped path or an unrecognised flag
   surfaces before any work starts.
2. **Records each document's recent commits** to `docs-history.md`. The reviewer agents have no shell,
   so this file is how the audit can tell that a paragraph has not been touched in two years.
3. **Inventories what is to be checked** — requirements from the standard in Mode A, the file's own
   statements in Mode C — before opening anything else. In Mode C this is also where your open
   questions and conclusions are picked out as separate kinds.
4. **Reads in parallel.** In Mode A one agent per slice of the checklist, searching the documents'
   own vocabulary rather than the standard's — "second approver" never matches "dual sign-off". In
   Mode C the verifying agent gets your claims and the repository but **not your file**, so a claim
   cannot be confirmed by the argument you made for it.
5. **Reviews the review.** Several roles look for different things at once, then one more opens the
   cited files and decides which findings survive. Only survivors are merged; refuted findings stay
   in the report with the evidence that killed them.
6. **Lints the report** with a script rather than a re-read. A report claiming the loop converged
   while its own log still shows changes fails that check.
7. **Writes the report and tells you almost nothing** — counts, which round converged, how many
   documents went unread, how many questions are waiting.

Working files go in one directory named after the report, never loose beside it:

```text
spec.docs-review.md              the report
spec.docs-review/
├── claims.md                    Mode C — your statements, classified. ID registry: kept
├── checklist.md                 Mode A — requirements derived from the standard. ID registry: kept
├── docs-history.md              recent commits per document
├── findings-wave1.md            what each round raised, before merging
└── scratch/                     deleted when the run finishes clean
    ├── claims-1.md …            one file per slice
    ├── rows-cv1.md …
    └── verdicts-cv1.tsv …
```

`claims.md` and `checklist.md` survive on purpose — they are ID registries, and deleting one makes the
next run re-mint from 001, so every ID in the old report points somewhere else. `scratch/` is deleted
only when the lint is clean and the run did not stop early; `--keep-scratch` keeps it regardless.

Three things it will not do to the directory you pointed it at, because that directory is also where
your own files live: move a file it did not create, delete anything outside its own `scratch/`, or
`rm -r` a path it found by globbing rather than derived from `--out`. A stray `checklists/` from
another task looks exactly like an audit artifact, and looking like one is not evidence.

The findings are not repeated in the conversation on purpose: a verdict restated in prose loses its
citation, and that is exactly where a `Partial` becomes "the docs are basically fine".
## Layout

```text
skills/docs-review/
  SKILL.md                        — mode selection, arguments, orchestration, rules
  references/critique-mode.md     — Mode C: one file, no standard
  references/investigation-mode.md — Mode B: auditing without a spec
  references/report-schema.md     — every heading, column, ID format and lint check id
  references/review-team.md       — dispatch contract + the role prompts
  references/self-clarify.md      — the five-tier ladder for unknowns
  references/dimensions.md        — requirement dimensions + how to make a row atomic
  references/i18n-jp.md           — Japanese term-variant + 全角/半角 checks
  references/large-sets.md        — index / shard / conflict-sweep workflow for big doc sets
  references/fix-mode.md          — what --fix may edit, and what it may only propose
  references/solo-loop.md         — the single-reviewer fallback used by --team off
  scripts/check_report.py         — the twenty-one schema checks (stdlib only)
  scripts/verify_citations.py     — opens every cited file and checks the quote is really there
  scripts/upsert_block.py         — writes the Review status block back into the reviewed document
  scripts/strip_rounds.py         — reviewer copy of the report, minus earlier findings
  tests/check_agent_table.py      — agent frontmatter vs the table that documents it
  tests/fixtures/                 — clean reports plus one per check, each tripping it
agents/                           — the roles, registered by the plugin
  docs-review-checklist.md          owns Req ID allocation
  docs-review-mapper.md             maps documents onto a checklist slice
  docs-review-requirement.md        re-derives from the spec, never shown the report
  docs-review-evidence.md           verifies every citation against the file
  docs-review-coverage.md           attacks Missing rows; sweeps for conflicts
  docs-review-failure.md            attacks the audit itself
  docs-review-adjudicator.md        upholds or refutes each finding
  docs-review-fix-safety.md         gates document edits before they are applied
  docs-review-solo-reviewer.md      the whole review in one agent, for --team off
  docs-review-claims.md             Mode C: inventories a file's own statements
  docs-review-verify.md             Mode C: settles them against the repository
  docs-review-implication.md        Mode C: what follows, and what contradicts
  spec-recon-probe-code.md          does this identifier exist, and where
  spec-recon-probe-artifact.md      measures binary artifacts with the stdlib
  spec-recon-probe-vcs.md           issues, PRs, milestones, history
  spec-recon-probe-runtime.md       read-only queries against a live system, on request only
  spec-recon-state-extract.md       one current-state document → baseline + change surface
  spec-recon-arbiter-impl.md        upholds or refutes every claim that something is missing
  spec-recon-gap-design.md          turns an upheld gap into an anchor line and a neighbour
  escalation-resolver.md            settles one unknown from the repository, returns one line
skills/spec-recon/
  SKILL.md                        — the five phases, arguments, rules
  references/preflight.md         — the hard gate, and the fix command for every failure
  references/probe-contracts.md   — what each probe is handed and must return; the role table
  references/step-protocol.md     — step files, the manifest, resuming a crashed run
  references/dispatch-planner.md  — sharding, caps, evidence type → probe routing
  references/arbitration.md       — how an absence claim is gated, and what UPHELD must carry
  references/evidence-format.md   — the labelling rule, reproduce lines, "not accessed"
  references/handoff.md           — passing evidence to docs-review --evidence
  references/cost-model.md        — measured base costs and the per-wave spend line
  references/incremental.md       — what is re-derived when a prior report exists
  data/recon-patterns.json        — revision syntaxes, build dirs, binary extensions; yours to edit
  scripts/recon.py                — freshness, revision markers, duplicate-source resolution
  scripts/plan_fleet.py           — recon.json → a fleet plan, deterministic and tested
  scripts/probe_xlsx.py           — .xlsx via zipfile + ElementTree; no openpyxl anywhere
  scripts/check_evidence.py       — rejects unlabelled numbers and untraceable evidence files
  tests/                          — preflight, planner, evidence lint, docs-review invariance
skills/chain/
  SKILL.md                        — the seven steps, the flags, and where the run may stop
  references/ledger.md            — the columns, the lookup, and what closes a row
  references/self-loop.md         — step 02 in full, and the five places tokens are saved
  scripts/ledger.py               — append-only record of every settled unknown; recomputes the ratio
  tests/test_ledger.py            — lookup, superseding, the falsifier rule, the metric floor
skills/analyze-feat/SKILL.md      — feature request → analysis, before any spec
skills/rca/SKILL.md               — bug report → root cause, five Whys with evidence
skills/feat-req-specs/SKILL.md    — analysis → reviewed spec, then hard stop
skills/bug-fix-specs/SKILL.md     — root cause → reviewed fix spec, then hard stop
skills/feat-req-execute/SKILL.md  — approved spec → plan, tasks, code, report
skills/bug-fix-execute/SKILL.md   — approved fix spec → the fix, verified, reported
skills/ccompact/SKILL.md          — checkpoint in-flight state before /compact
skills/ccontinue/SKILL.md         — resume from it; the file outranks the summary
skills/escalation-ladder/SKILL.md — five tiers before a question reaches a human
  tests/test_ladder_adoption.py    — every analysis skill routes unknowns through the ladder
skills/confirm-with-me/SKILL.md   — one marker, one gate, one explicit yes
skills/translate-file/SKILL.md    — prose → Vietnamese, identifiers untouched
scripts/preflight.py              — shared by every skill: capability gate before any spend
                                    groups: runtime write read vcs forge artifacts speckit mcp
scripts/speckit_pin.py            — points spec-kit's persisted feature pointer at this run's
                                    feature dir; the only channel that survives a tool-call gap
  skills/chain/tests/test_speckit_pin.py — stale pin replaced, sibling keys kept, SKIP without .specify/
hooks/confirm-marker.py           — SessionStart: states the `confirm with me` rule, writes nothing
.mcp.json                         — the sequential-thinking server the plugin ships
.claude-plugin/plugin.json        — Claude Code plugin manifest
.claude-plugin/marketplace.json   — plugin marketplace manifest
```

The ten single-file skills carry no `references/` or `scripts/` of their own — they share
`scripts/preflight.py` and resolve it through `${CLAUDE_PLUGIN_ROOT}`, which is why Option A of the
install matters for them too.

`SKILL.md` stays small on purpose — the references load only when the workflow needs them, so a
session that never touches Japanese text never pays for `i18n-jp.md`.

## License

MIT
