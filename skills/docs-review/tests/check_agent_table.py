#!/usr/bin/env python3
"""Check that each role table matches the agent files it describes.

This test exists because the table and the files drifted apart once, silently:
`review-team.md` declared `verify` as `sonnet` from the day it was written, the
agent file never carried a `model:` key, so the most expensive role in Mode C
inherited Opus for three releases. Nothing failed — the table said one thing and
the harness did another, and only a token bill showed it.

It now also enforces the harder rule, which was learned the same way. Tool
grants on this harness are **not monotonic**: declaring `Bash` alongside `Grep`
and `Glob` removes both, with no warning, and a tool name the harness does not
recognise is dropped in silence. So a tool set is allowed here only if it was
probed directly. A set that merely looks like a safe subset of a probed one is a
defect — that exact mistake once shipped three roles search-blind.

Run from the repository root:
    python3 skills/docs-review/tests/check_agent_table.py             # every suite
    python3 skills/docs-review/tests/check_agent_table.py docs-review
"""
import glob
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

# Tool sets probed directly on this harness, with the base tokens each costs per
# spawn. `Read, Bash` is what the harness actually handed back when the
# declaration said `Read, Grep, Glob, Bash` — it is probed, but only as that
# outcome, which is why anything asking for Bash next to Grep is rejected below.
#
#   Read, Grep, Glob          probe-set-a    6,619
#   Read, Bash                probe-set-b   11,353
#   Read, Write, Grep, Glob   probe-set-c    6,875
PROBED = {
    "Read, Grep, Glob": 6619,
    "Read, Bash": 11353,
    "Read, Write, Grep, Glob": 6875,
}

# Each suite: the table documenting the roles, and the agent files it covers.
SUITES = {
    "docs-review": {
        "table": os.path.join(ROOT, "skills", "docs-review", "references",
                              "review-team.md"),
        "agents": os.path.join(ROOT, "agents", "docs-review-*.md"),
        "prefix": "docs-review-",
    },
    "spec-recon": {
        "table": os.path.join(ROOT, "skills", "spec-recon", "references",
                              "probe-contracts.md"),
        "agents": os.path.join(ROOT, "agents", "spec-recon-*.md"),
        "prefix": "spec-recon-",
    },
}


def frontmatter(text):
    parts = text.split("---")
    return parts[1] if len(parts) > 2 else ""


def field(fm, name, default=None):
    m = re.search(r"^%s:\s*(.+)$" % name, fm, re.M)
    return m.group(1).strip() if m else default


def check_suite(name, spec, problems):
    if not os.path.isfile(spec["table"]):
        problems.append("%s: no role table at %s" % (name, spec["table"]))
        return 0
    table = io.open(spec["table"], encoding="utf-8").read()
    files = sorted(glob.glob(spec["agents"]))
    if not files:
        problems.append("%s: no agent files at %s" % (name, spec["agents"]))
        return 0

    prefix = spec["prefix"]
    for path in files:
        fm = frontmatter(io.open(path, encoding="utf-8").read())
        role = os.path.basename(path)[len(prefix):-len(".md")]
        tools = field(fm, "tools", "")
        model = field(fm, "model", "inherit")

        if tools not in PROBED:
            problems.append(
                "%s/%s declares an unprobed tool set: %r (probed: %s)"
                % (name, role, tools, "; ".join(sorted(PROBED))))
        if "Bash" in tools and ("Grep" in tools or "Glob" in tools):
            problems.append(
                "%s/%s asks for Bash next to Grep/Glob; this harness would hand "
                "it 'Read, Bash' and drop the rest, silently" % (name, role))

        row = re.search(
            r"^\|\s*%s[^|]*\|[^|]*`ktkit:%s%s`[^|]*\|\s*`([^`]+)`\s*\|\s*(\S+)\s*\|"
            % (re.escape(role), re.escape(prefix), re.escape(role)), table, re.M)
        if not row:
            problems.append("%s/%s has no row in %s"
                            % (name, role, os.path.basename(spec["table"])))
            continue
        if row.group(1) != tools:
            problems.append("%s/%s tools: file=%r table=%r"
                            % (name, role, tools, row.group(1)))
        if row.group(2) != model:
            problems.append("%s/%s model: file=%r table=%r"
                            % (name, role, model, row.group(2)))
    return len(files)


def main(argv):
    wanted = argv[1:] or sorted(SUITES)
    unknown = [w for w in wanted if w not in SUITES]
    if unknown:
        print("unknown suite(s): %s; known: %s"
              % (", ".join(unknown), ", ".join(sorted(SUITES))))
        return 2

    problems = []
    total = 0
    for name in wanted:
        total += check_suite(name, SUITES[name], problems)

    for line in problems:
        print("FAIL %s" % line)
    print("%d agents checked across %d suite(s), %d problems"
          % (total, len(wanted), len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
