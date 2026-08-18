# testcase

Two Claude Code skills for QA work — `testcase` generates manual test cases, `docs-review` audits documentation against a spec. Both end with a mandatory review pass run in an independent subagent.

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
- **Review loop** — an independent subagent re-derives the checklist from the spec alone and attacks the report; repeats until a round finds nothing, max 3 rounds. Earlier rounds' notes are stripped before the next round, so each reviewer stays independent
- **Large sets** — over ~15 documents it switches workflow: index the documents first (their vocabulary, not the spec's), shard the audit by spec chapter, sweep for doc-vs-doc conflicts separately, and require a per-document coverage declaration before a review round counts as clean
- **`--fix`** — edits the audited document (the output artifact, never the spec) after the review loop: `Missing` / `Partial` / `Stale` rows the spec states in full, as minimal in-place edits traced to a requirement ID, then re-verifies each edited section. In a deliverable still being drafted, `Contradict` is fixed too. In documentation of a running system it is only proposed — a doc contradicting the spec may be the one describing reality
- **Lint** — a script checks every row for a valid verdict, a citation, unique IDs, a source inventory, and that the loop actually ran

```text
Review the docs in ./docs against spec.md
Review the docs in ./docs against spec.md --fix
```

## Install

### Option A — Plugin marketplace (recommended)

```bash
# one-time: register this repo as a marketplace
claude plugin marketplace add xtieume/testcase

# then install
claude plugin install testcase@testcase-marketplace
```

Or via the interactive UI:

```text
/plugin marketplace add xtieume/testcase
/plugin install testcase@testcase-marketplace
```

### Option B — Manual (copy the skill)

Copy the whole skill folder into your local skills folder:

```bash
cp -R skills/testcase ~/.claude/skills/testcase
cp -R skills/docs-review ~/.claude/skills/docs-review
```

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

## Layout

```text
skills/testcase/
  SKILL.md                        — workflow, output format, rules
  references/coverage-map.md      — the coverage dimensions + worked example
  references/i18n-jp.md           — Japanese charset coverage
  references/review-mode.md       — auditing an existing test case list
  scripts/summarize.py            — count, lint, export CSV (stdlib only)
skills/docs-review/
  SKILL.md                        — mode selection, gap workflow, review loop, rules
  references/dimensions.md        — requirement dimensions + how to make a row atomic
  references/i18n-jp.md           — Japanese term-variant + 全角/半角 checks
  references/large-sets.md        — index / shard / conflict-sweep workflow for big doc sets
  references/fix-mode.md          — what --fix may edit, and what it may only propose
  references/investigation-mode.md — auditing without a spec
  scripts/check_report.py         — lint verdicts, citations, duplicate IDs (stdlib only)
.claude-plugin/plugin.json        — Claude Code plugin manifest
.claude-plugin/marketplace.json   — plugin marketplace manifest
```

`SKILL.md` stays small on purpose — the references load only when the workflow needs them, so a session that never touches Japanese text never pays for `i18n-jp.md`. `docs-review/SKILL.md` works the same way.

## License

MIT
