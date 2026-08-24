# ktkit

Three Claude Code skills — `testcase` generates manual test cases, `docs-review` audits documentation against a spec, `playwright-notion` pulls Notion pages down to markdown when the API and the Export button are both unavailable. The two QA skills end with a mandatory review pass that runs in agents with their own context, not in the session that produced the work.

## testcase

Generates comprehensive manual test cases and performs a mandatory missing-test-case review.

It systematically analyzes: positive, negative, boundary, validation, state, permission, error, data, UI, integration, and regression scenarios — then runs a second adversarial pass **in an independent subagent** to catch missed cases before returning the result.

Extras:

- **Japanese i18n coverage** — 全角/半角, surrogate pairs, Unicode normalization, byte-vs-character length limits, export/search round-trips
- **Review mode** — audit an existing test case list against the requirement, not against itself
- **Lint + CSV export** — a script counts the cases and flags duplicate IDs, missing expected results, invalid priorities, and vague steps

## docs-review

Reviews documentation in whichever of three shapes your situation has: **critique one file** against
the repository and itself, **check documents against a standard**, or **ask a question of a document
set**. See [Using `docs-review`](#using-docs-review) for which is which.

- **Critique mode** — one file, nothing to compare it against. Its claims are verified against the repository, its open questions answered where the repo already answers them, its self-contradictions and unsupported conclusions named, and the consequences it committed to but never wrote down surfaced as `Implication`. Verdicts are `Verified` / `Refuted` / `Unverifiable` / `Contradict` / `Unsupported` / `Answerable` / `Open` / `Implication`
- **Gap analysis mode** — decomposes the standard into atomic requirements *before* reading the docs, then maps each one to `Covered` / `Partial` / `Missing` / `Contradict` / `Conflict` / `Stale` / `Undecided` with a mandatory citation and quote
- **Investigation mode** — no standard? the checklist comes from the question instead, and answers are marked `Stated` / `Inferred` / `Conflicting` / `Absent`
- **A team of agents, not one reviewer** — a generic reviewer run once per round covers one or two of its checks per pass, which is why that shape needs four or five rounds. Here the work is split into roles that run concurrently and then challenge each other. Producers: `checklist` and `mapper` in gap analysis, `claims` in critique. Reviewers: `requirement` re-derives from the standard **without being shown the report**, `evidence` verifies every quote character by character, `coverage` attacks `Missing` rows in the documents' own vocabulary, `verify` settles a file's claims against the repository **without being shown the file**, `implication` finds what follows and was never said, `failure` attacks the review itself, `adjudicator` upholds or refutes each finding against the files, `fix-safety` gates edits. One or two rounds instead of four or five
- **Independence where it matters** — reviewers derive alone (no lead reasoning, no peer findings, no earlier wave's notes), then challenge with evidence. Only findings that survive the challenge are merged; refuted ones stay in the report with the evidence that killed them
- **The lead never reads the documents** — in an agentic loop the session's context is re-sent every turn, so documents read once are paid for repeatedly. The orchestrating session holds paths, IDs and finding lists; mappers read, shards are concatenated, findings are merged with targeted edits
- **Self-clarify ladder** — an unknown is classified before it is acted on: search the documents' vocabulary, the code and the file's history; challenge a disagreement once; look up an external fact from an authoritative source; assume the better-evidenced reading **with a falsifier written down**; and only then ask. A question reaching you needs six preconditions, a recommendation and a default, and must first survive a challenge by two reviewers
- **Convergence is computed, not claimed** — every wave logs its counts, and a report claiming convergence while the last row still shows new rows, changed verdicts or rejected citations fails the lint. `--rounds N` caps the waves; a cap reached with findings outstanding is reported on line 1, never as a clean exit
- **Scales by agent count, not by workflow** — index-then-shard is the pipeline at every size, so a set of eight documents and a set of eighty differ in how many mappers run, not in which steps happen. Above ~15 documents four things change: the document map (their vocabulary, not the spec's) becomes mandatory, shards follow spec chapters, the doc-vs-doc conflict sweep becomes its own pass because no single reviewer holds the whole set any more, and shard waves cap at two without counting toward the round ceiling
- **`--fix`** — edits the audited document (the output artifact, never the spec) after the review loop: `Missing` / `Partial` / `Stale` rows the spec states in full, as minimal in-place edits traced to a requirement ID. Every edit passes `fix-safety` first, and re-verification is done by `evidence` against the edited files rather than by the session that wrote them. In a deliverable still being drafted, `Contradict` is fixed too. In documentation of a running system it is only proposed — a doc contradicting the spec may be the one describing reality
- **Lint with named checks** — `references/report-schema.md` owns every heading, column and ID format, and `scripts/check_report.py` implements exactly its twenty checks: false convergence, unregistered IDs, missing citations, gates without a default, assumptions without a falsifier, coverage weaker than the verdicts imply, and a degraded run that did not announce itself
- **Quiet by default** — the audit writes the report to a file and prints a short status summary. A table printed into the conversation is billed again on every later turn and arrives without its citations

```text
ktkit:docs-review 3 notes/analysis.md          # one file → critique it, 3 self-review rounds
ktkit:docs-review 3 spec.md ./docs             # standard + documents → gap analysis
ktkit:docs-review 3 spec.md ./docs --fix       # …and apply the fixable rows
Read ./docs and tell me what happens when the provider returns 409
```

## playwright-notion

For the common corporate lockout: the workspace won't issue an integration token, the Export button is greyed out by permission, and the only access you have is a browser tab you're already logged into.

The skill attaches to your **running** Brave/Chrome/Edge over the Chrome DevTools Protocol and calls Notion's own endpoints from inside that tab. Read-only — nothing in Notion is created, edited, or deleted.

- **Export first** — a greyed-out Export button is often only a client-side role check, so it enqueues Notion's native markdown export (`enqueueTask`). Where that passes, output is Notion's own markdown: person mentions resolved to real names, page mentions to titles plus URLs, embedded images downloaded alongside
- **Converter fallback** — when a workspace really did disable export server-side, it converts `loadPageChunk` / `queryCollection` block JSON itself: properties, nested lists, to-do checkboxes, callouts, code blocks with language tags, and tables with correct columns including embedded database views
- **Two dead ends it refuses to walk into** — copying the browser profile cannot carry the session (Chromium 127+ App-Bound Encryption binds the cookie key to the original profile, so a copy lands on the login screen), and DOM scraping emits every table ~3x with cells doubled while losing all page properties
- **Batch-safe** — recycles the browser tab every few pages because Notion leaks memory and crashes the renderer, retries crashed pages, and logs per-page results to grep for verification

```text
Tôi không có Notion API token, Export bị disable. Tải các trang này về markdown: <links>
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

Installing as a plugin is what registers the eleven `docs-review` agents. Verify them after install:

```text
/context          # Custom agents should list ktkit:docs-review-*
```

### Option B — Manual (copy the skill)

```bash
cp -R skills/testcase ~/.claude/skills/testcase
cp -R skills/docs-review ~/.claude/skills/docs-review
cp -R skills/playwright-notion ~/.claude/skills/playwright-notion
```

Copying skips `agents/`, so `docs-review` falls back to a single generic reviewer. It still runs and still says so — the report's first line reads `DEGRADED` and `## Review team` marks the rows — but the roles no longer see the documents independently, and the generic agent has no structured search tools. Prefer Option A for `docs-review`.

## Using `testcase`

Ask in natural language, or invoke it as `/ktkit:testcase`. It triggers on any request to write,
create, generate, review, improve or check test cases.

### Generating cases

```text
Write test cases for: the user changes 工種コード from a dropdown, and the value is
reflected in L1 immediately without a save.
```

You get a table written to `testcases.md` (or the file you name), one row per case, with an ID,
preconditions, steps, expected result and priority. The generation pass walks eleven scenario
families — positive, negative, boundary, validation, state, permission, error, data, UI, integration,
regression — and then a **second pass in an independent agent** goes looking for what the first pass
missed. That second pass is not optional and not a formality: it is the step that catches the
boundary case you did not think to ask for.

The more the request pins down, the less the skill has to assume. Compare:

```text
# thin — the skill will have to guess the limits, and will say so
Write test cases for the amount field.

# useful — every constant here becomes a boundary case
Write test cases for the amount field: integer yen, 0 to 1,000,000 inclusive,
rejected values show 金額が不正です, and the field is disabled once the claim is approved.
```

### Reviewing cases somebody else wrote

Hand it an existing list and it switches to review mode — auditing the cases against the
**requirement**, not against themselves, which is the only way a missing case can surface:

```text
Review these test cases against the spec in docs/spec.md and tell me what is not covered:
<paste the table, or give the file path>
```

### Linting and exporting

The output is a file on purpose, so a script can check it:

```bash
python3 skills/testcase/scripts/summarize.py testcases.md            # counts + lint findings
python3 skills/testcase/scripts/summarize.py testcases.md --csv out.csv   # export for TestRail/Excel
python3 skills/testcase/scripts/summarize.py --selfcheck             # verify the script itself
```

The lint flags duplicate IDs, missing expected results, invalid priorities and vague steps
("check it works" is not a step). The CSV is UTF-8 with BOM, so Excel opens Japanese text without
mojibake.

Japanese features get their own coverage — 全角/半角 pairs, surrogate pairs, Unicode normalization,
byte-versus-character length limits, and export/search round-trips — because a field that accepts
20 characters and a field that accepts 20 bytes fail differently and only one of them is tested by
ASCII input.

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
ktkit:docs-review 3 .claude/claude/specs/billing/retry/abc.md
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

**Your file is never edited.** The review lands beside it; what to change is your call, and a file
full of your own reasoning is the last place for automated edits.

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
ktkit:docs-review 3 docs/req-1234.md .claude/claude/specs/billing/retry/abc.md

# abc.md is settled; the other docs have to keep up with it
ktkit:docs-review 3 .claude/claude/specs/billing/retry/abc.md ./docs ./api-design
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
| `--max-questions N` | At most N rows may reach you as questions. Default 3 |
| `--out <path>` | Where the report goes. Default `docs-review.md` |
| `--fix` | Mode A only: apply the fixable rows |
| `--silent` | Print the report path and nothing else |
| `--team off` | Run without the agent team. Emergency fallback; the report says it ran degraded |
| `--ask-only` | Diagnostic: skip the searching and surface every unknown as a question. Shows you what the ladder was absorbing. Never leave it on |

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

Working files land beside the report so you can delete the lot in one gesture:

```text
docs-review.md          the report
checklist.md            Mode A — the requirements it derived, and the ID registry
claims.md               Mode C — your statements, classified, and the ID registry
docs-history.md         recent commits per document
shard-1.md, shard-2.md  what each reading agent found, before merging
```

The findings are not repeated in the conversation on purpose: a verdict restated in prose loses its
citation, and that is exactly where a `Partial` becomes "the docs are basically fine".
## Using `playwright-notion`

Install the script deps once, then it drives the browser for you:

```bash
cd skills/playwright-notion/scripts && npm install
```

Run manually if you prefer:

```bash
# start (or verify) the browser with CDP — closes a running instance first
skills/playwright-notion/scripts/start-browser.sh brave 9222

# one URL per line, then export (preferred) or download (fallback)
node skills/playwright-notion/scripts/export.mjs   urls.txt ./notion-docs 9222
node skills/playwright-notion/scripts/download.mjs urls.txt ./notion-docs 9222

grep -c OK /tmp/notion_export.log
```

Brave commonly accepts CDP on its default profile dir where Chrome refuses.

## Layout

```text
skills/testcase/
  SKILL.md                        — workflow, output format, rules
  references/coverage-map.md      — the coverage dimensions + worked example
  references/i18n-jp.md           — Japanese charset coverage
  references/review-mode.md       — auditing an existing test case list
  scripts/summarize.py            — count, lint, export CSV (stdlib only)
skills/docs-review/
  SKILL.md                        — mode selection, arguments, orchestration, rules
  references/critique-mode.md     — Mode C: one file, no standard
  references/report-schema.md     — every heading, column, ID format and lint check id
  references/review-team.md       — dispatch contract + the eight role prompts
  references/self-clarify.md      — the five-tier ladder for unknowns
  references/dimensions.md        — requirement dimensions + how to make a row atomic
  references/i18n-jp.md           — Japanese term-variant + 全角/半角 checks
  references/large-sets.md        — index / shard / conflict-sweep workflow for big doc sets
  references/fix-mode.md          — what --fix may edit, and what it may only propose
  references/investigation-mode.md — auditing without a spec
  scripts/check_report.py         — the twenty schema checks (stdlib only)
  scripts/strip_rounds.py         — reviewer copy of the report, minus earlier findings
  tests/fixtures/                 — one clean report plus six, each tripping one check
agents/                           — the eight docs-review roles, registered by the plugin
  docs-review-checklist.md          owns Req ID allocation
  docs-review-mapper.md             maps documents onto a checklist slice
  docs-review-requirement.md        re-derives from the spec, never shown the report
  docs-review-evidence.md           verifies every citation against the file
  docs-review-coverage.md           attacks Missing rows; sweeps for conflicts
  docs-review-failure.md            attacks the audit itself
  docs-review-adjudicator.md        upholds or refutes each finding
  docs-review-fix-safety.md         gates document edits before they are applied
  docs-review-claims.md             Mode C: inventories a file's own statements
  docs-review-verify.md             Mode C: settles them against the repository
  docs-review-implication.md        Mode C: what follows, and what contradicts
skills/playwright-notion/
  SKILL.md                        — workflow, the two dead ends, verification
  scripts/start-browser.sh        — launch Brave/Chrome/Edge with CDP on the real profile
  scripts/export.mjs              — Notion's native markdown export via enqueueTask (preferred)
  scripts/download.mjs            — block JSON → markdown converter (fallback)
  scripts/package.json            — playwright dependency
.claude-plugin/plugin.json        — Claude Code plugin manifest
.claude-plugin/marketplace.json   — plugin marketplace manifest
```

`SKILL.md` stays small on purpose — the references load only when the workflow needs them, so a session that never touches Japanese text never pays for `i18n-jp.md`. `docs-review/SKILL.md` works the same way.

## License

MIT
