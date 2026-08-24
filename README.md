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

Investigates documentation on one principle: **what the spec requires vs what the documents actually contain**.

- **Gap analysis mode** — decomposes the spec into atomic requirements *before* reading the docs, then maps each one to `Covered` / `Partial` / `Missing` / `Contradict` / `Conflict` / `Stale` / `Undecided` with a mandatory citation and quote
- **Investigation mode** — no spec? the checklist comes from the question instead, and answers are marked `Stated` / `Inferred` / `Conflicting` / `Absent`
- **A team of eight agents, not one reviewer** — a generic reviewer run once per round covers one or two of its checks per pass, which is why that shape needs four or five rounds. Here the work is split into roles that run concurrently and then challenge each other: `checklist` and `mapper` produce, `requirement` re-derives from the spec **without being shown the report**, `evidence` verifies every quote character by character, `coverage` attacks `Missing` rows in the documents' own vocabulary and sweeps for doc-vs-doc conflicts, `failure` attacks the audit itself, `adjudicator` upholds or refutes each finding against the files, and `fix-safety` gates edits. One or two waves instead of four or five rounds
- **Independence where it matters** — reviewers derive alone (no lead reasoning, no peer findings, no earlier wave's notes), then challenge with evidence. Only findings that survive the challenge are merged; refuted ones stay in the report with the evidence that killed them
- **The lead never reads the documents** — in an agentic loop the session's context is re-sent every turn, so documents read once are paid for repeatedly. The orchestrating session holds paths, IDs and finding lists; mappers read, shards are concatenated, findings are merged with targeted edits
- **Self-clarify ladder** — an unknown is classified before it is acted on: search the documents' vocabulary, the code and the file's history; challenge a disagreement once; look up an external fact from an authoritative source; assume the better-evidenced reading **with a falsifier written down**; and only then ask. A question reaching you needs six preconditions, a recommendation and a default, and must first survive a challenge by two reviewers
- **Convergence is computed, not claimed** — every wave logs its counts, and a report claiming convergence while the last row still shows new rows, changed verdicts or rejected citations fails the lint. `--rounds N` caps the waves; a cap reached with findings outstanding is reported on line 1, never as a clean exit
- **Large sets** — index the documents first (their vocabulary, not the spec's), shard the audit, sweep for doc-vs-doc conflicts separately, and require a per-document coverage declaration before a wave counts as clean
- **`--fix`** — edits the audited document (the output artifact, never the spec) after the review loop: `Missing` / `Partial` / `Stale` rows the spec states in full, as minimal in-place edits traced to a requirement ID. Every edit passes `fix-safety` first, and re-verification is done by `evidence` against the edited files rather than by the session that wrote them. In a deliverable still being drafted, `Contradict` is fixed too. In documentation of a running system it is only proposed — a doc contradicting the spec may be the one describing reality
- **Lint with named checks** — `references/report-schema.md` owns every heading, column and ID format, and `scripts/check_report.py` implements exactly its twenty checks: false convergence, unregistered IDs, missing citations, gates without a default, assumptions without a falsifier, coverage weaker than the verdicts imply, and a degraded run that did not announce itself
- **Quiet by default** — the audit writes the report to a file and prints a short status summary. A table printed into the conversation is billed again on every later turn and arrives without its citations

```text
Review the docs in ./docs against spec.md
Review the docs in ./docs against spec.md --fix
docs-review 3 spec.md ./docs          # cap the review at 3 waves
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

# then install
claude plugin install ktkit@ktkit-marketplace
```

Or via the interactive UI:

```text
/plugin marketplace add kanechan25/ktkit
/plugin install ktkit@ktkit-marketplace
```

Installing as a plugin is what registers the eight `docs-review` agents. Verify them after install:

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

## Usage

Ask for test cases in natural language:

```text
Write test cases for: user can change 工種コード via a dropdown, value reflected immediately in L1.
```

The skill triggers automatically on any request to write / create / generate / review test cases, or invoke it directly with `/testcase`.

Test cases are written to a file, so they can be linted and exported:

```bash
python3 skills/testcase/scripts/summarize.py testcases.md
python3 skills/testcase/scripts/summarize.py testcases.md --csv out.csv
```

The CSV is UTF-8 with BOM, so Excel opens Japanese text correctly.

For `playwright-notion`, install the script deps once, then it drives the browser for you:

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
  SKILL.md                        — arguments, orchestration, the review wave, rules
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
