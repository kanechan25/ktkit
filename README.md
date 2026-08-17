# testcase

A Claude Code skill that generates comprehensive manual test cases and performs a mandatory missing-test-case review.

It systematically analyzes: positive, negative, boundary, validation, state, permission, error, data, UI, integration, and regression scenarios — then runs a second adversarial pass **in an independent subagent** to catch missed cases before returning the result.

Extras:

- **Japanese i18n coverage** — 全角/半角, surrogate pairs, Unicode normalization, byte-vs-character length limits, export/search round-trips
- **Review mode** — audit an existing test case list against the requirement, not against itself
- **Lint + CSV export** — a script counts the cases and flags duplicate IDs, missing expected results, invalid priorities, and vague steps

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
.claude-plugin/plugin.json        — Claude Code plugin manifest
.claude-plugin/marketplace.json   — plugin marketplace manifest
```

`SKILL.md` stays small on purpose — the references load only when the workflow needs them, so a session that never touches Japanese text never pays for `i18n-jp.md`.

## License

MIT
