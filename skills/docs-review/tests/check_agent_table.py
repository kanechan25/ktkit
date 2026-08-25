#!/usr/bin/env python3
"""Check that `review-team.md` section 8 matches the agent files it describes.

This test exists because the table and the files drifted apart once, silently:
`review-team.md` declared `verify` as `sonnet` from the day it was written, the
agent file never carried a `model:` key, so the most expensive role in Mode C
inherited Opus for three releases. Nothing failed — the table said one thing and
the harness did another, and only a token bill showed it.

Run from the repository root:
    python3 skills/docs-review/tests/check_agent_table.py
"""
import glob
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
TABLE = os.path.join(ROOT, "skills", "docs-review", "references", "review-team.md")
AGENTS = os.path.join(ROOT, "agents", "docs-review-*.md")

# Tool sets that were actually probed on this harness. Declaring Bash alongside
# Grep/Glob silently drops Grep and Glob, so an unprobed combination is a defect
# even when it looks like a subset of one that works.
PROBED = {
    "Read, Grep, Glob",
    "Read, Write, Grep, Glob",
}


def frontmatter(text):
    parts = text.split("---")
    return parts[1] if len(parts) > 2 else ""


def field(fm, name, default=None):
    m = re.search(r"^%s:\s*(.+)$" % name, fm, re.M)
    return m.group(1).strip() if m else default


def main():
    table = io.open(TABLE, encoding="utf-8").read()
    problems = []
    files = sorted(glob.glob(AGENTS))
    if not files:
        print("FAIL no agent files found at %s" % AGENTS)
        return 1

    for path in files:
        fm = frontmatter(io.open(path, encoding="utf-8").read())
        role = os.path.basename(path)[len("docs-review-"):-len(".md")]
        tools = field(fm, "tools", "")
        model = field(fm, "model", "inherit")

        if tools not in PROBED:
            problems.append("%s declares an unprobed tool set: %r" % (role, tools))

        row = re.search(
            r"^\|\s*%s[^|]*\|[^|]*`ktkit:docs-review-%s`[^|]*\|\s*`([^`]+)`\s*\|\s*(\S+)\s*\|"
            % (re.escape(role), re.escape(role)), table, re.M)
        if not row:
            problems.append("%s has no row in review-team.md section 8" % role)
            continue
        if row.group(1) != tools:
            problems.append("%s tools: file=%r table=%r" % (role, tools, row.group(1)))
        if row.group(2) != model:
            problems.append("%s model: file=%r table=%r" % (role, model, row.group(2)))

    for line in problems:
        print("FAIL %s" % line)
    print("%d agents checked, %d problems" % (len(files), len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
