---
name: help
description: "Print the ktkit help index, or the help page for one skill. Trigger on `/ktkit:help`, `/ktkit:help <skill>`, or when the user asks what ktkit can do, which skill to use for something, what flags a ktkit skill takes, or how to use one of them. Prints and stops — it runs no other skill and changes nothing."
argument-hint: "[<skill>] — omit for the index; e.g. `chain`, `docs-review`, `spec-recon`"
user-invocable: true
allowed-tools: Bash
---

# ktkit:help — the index, and one page per skill

Print help. Run nothing else. Change nothing.

## What to do

Run exactly one command, then print its output **verbatim** and stop:

| Invocation | Command |
| ---------- | ------- |
| `/ktkit:help` | `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/help.py"` |
| `/ktkit:help <skill>` | `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/help.py" <skill>` |
| `/ktkit:help --all` | `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/help.py" --all` |

`<skill>` is taken as given, minus any leading `/` or `ktkit:`. An unknown name is not an error to
recover from: the script prints the known names and the nearest matches, and that output is the
answer.

## Rules

1. **Print the output verbatim.** Do not summarise it, reformat it, translate it, or add commentary
   before or after. The pages are written; re-writing them at call time is how help starts drifting
   from the skill it describes.
2. **Run nothing else.** Not the skill being asked about, not a preflight, not a search. If the user
   wanted the skill run, they would have named it.
3. **Read no files.** The script assembles the pages. Opening `SKILL.md` to "check" costs the whole
   file and answers nothing the page does not.
4. If the script fails, say so and print its error. Do not reconstruct the help from memory — a
   remembered flag list is exactly the thing this design exists to prevent.

## Where the content lives

Each page is `skills/<name>/references/help.md`, next to the skill it documents.
`skills/spec-recon/tests/test_help.py` checks every page against that skill's own `## Arguments`
section, in both directions: a flag named in a page that the skill does not accept fails, and so does
a flag the skill accepts that no page mentions.
