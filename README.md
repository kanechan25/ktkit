# ktkit

Claude Code skills for reviewing documentation and for checking documentation against the thing it describes. `docs-review` audits a document set with a team of agents that run concurrently and challenge each other's findings — every run ends with a review pass carried out in agents with their own context, not in the session that produced the work. `spec-recon` adds the axis a document reviewer cannot reach: it measures code, binary artifacts and version-control state, and hands each measurement back as a document the reviewers can read.

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
```

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

Installing as a plugin is what registers the twelve `docs-review` agents. Verify them after install:

```text
/context          # Custom agents should list ktkit:docs-review-*
```

### Option B — Manual (copy the skill)

```bash
cp -R skills/docs-review ~/.claude/skills/docs-review
```

Copying skips `agents/`, so `docs-review` falls back to a single generic reviewer. It still runs and still says so — the report's first line reads `DEGRADED` and `## Review team` marks the rows — but the roles no longer see the documents independently, and the generic agent has no structured search tools. Prefer Option A for `docs-review`.

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
scripts/preflight.py              — shared by both skills: capability gate before any spend
.claude-plugin/plugin.json        — Claude Code plugin manifest
.claude-plugin/marketplace.json   — plugin marketplace manifest
```

`SKILL.md` stays small on purpose — the references load only when the workflow needs them, so a
session that never touches Japanese text never pays for `i18n-jp.md`.

## License

MIT
