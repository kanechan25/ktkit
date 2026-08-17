# testcase

A Claude Code skill that generates comprehensive manual test cases and performs a mandatory missing-test-case review.

It systematically analyzes: positive, negative, boundary, validation, state, permission, error, data, UI, integration, and regression scenarios — then does a second adversarial pass to catch missed cases before returning the result.

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

Copy the skill into your local skills folder:

```bash
mkdir -p ~/.claude/skills/testcase
cp skills/testcase/SKILL.md ~/.claude/skills/testcase/SKILL.md
```

## Usage

Ask for test cases in natural language:

```text
Write test cases for: user can change 工種コード via a dropdown, value reflected immediately in L1.
```

The skill triggers automatically on any request to write / create / generate / review test cases, or invoke it directly with `/testcase`.

## Layout

```text
skills/testcase/SKILL.md   — the skill
plugin.json                — Claude Code plugin manifest
marketplace.json           — plugin marketplace manifest
```

## License

MIT
