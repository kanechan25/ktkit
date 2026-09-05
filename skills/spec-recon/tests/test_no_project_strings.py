#!/usr/bin/env python3
"""No shipped file may name a specific project, repository or codebase.

These skills are installed into repositories that have nothing to do with the
one they were developed against. An example lifted from that repository -- a
real identifier, a real filename, a domain term from its business -- looks like
generic guidance and is not: it teaches a probe to search for a thing that does
not exist here, and it leaks the internals of one project into everyone else's
tooling.

This check exists because writing the rule down was not enough. The rule was
stated as a portability constraint, agreed, and then broken in four files during
the very build that introduced it -- with real identifiers, a real spreadsheet
filename and real domain terms used as illustrations. Prose does not enforce
prose. A test does.

Examples must be invented. If an example needs to look like a real system, make
one up.

Run:  python3 skills/spec-recon/tests/test_no_project_strings.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

# Everything a user installs. Tests and fixtures are excluded: a fixture's whole
# job is to be a realistic sample, and it is never read by an agent.
SHIPPED = [
    ("skills", (".md",)),
    ("agents", (".md",)),
    ("scripts", (".py",)),
    (".claude-plugin", (".json",)),
    ("README.md", None),
]
EXCLUDE_DIRS = {"tests", "fixtures", "__pycache__"}

# Names of the projects this toolkit was developed against, their organisations,
# and identifiers taken from their source. Add to this list when working inside
# a new codebase; never relax it.
BANNED = [
    (r"\bfeec\b", "a project name"),
    (r"\bFARM\b", "a project name"),
    (r"\bgantt-chart\b", "a project name"),
    (r"\bArentInc\b", "an organisation name"),
    (r"\bkanechan25\b", "a personal account"),
    (r"\bkhoatran25\b", "a personal account"),
    (r"\bES\d{4}\b", "an identifier from one project's issue scheme"),
    (r"calcEngineVersion", "an identifier from one project's source"),
    (r"GenkaPrintRow", "an identifier from one project's source"),
    (r"BusinessEntitySeeder", "an identifier from one project's source"),
    (r"quotation[-_.]", "a filename from one project"),
    (r"工事区分", "a domain term from one project"),
    (r"印字行", "a domain term from one project"),
    (r"内法定福利費", "a domain term from one project"),
    (r"様式", "a domain term from one project"),
    (r"積算", "a domain term from one project"),
    (r"見積", "a domain term from one project"),
    (r"\.claude/claude/", "a directory layout private to one machine"),
    (r"/Users/[a-z]+/", "an absolute path from one machine"),
]

# The homepage and repository fields of the manifest legitimately name the
# account that publishes the plugin.
ALLOW = {
    ".claude-plugin/plugin.json": ("kanechan25",),
    ".claude-plugin/marketplace.json": ("kanechan25",),
    "README.md": ("kanechan25",),
}

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def shipped_files():
    for entry, exts in SHIPPED:
        path = os.path.join(ROOT, entry)
        if os.path.isfile(path):
            yield entry, path
            continue
        for root, dirs, names in os.walk(path):
            dirs[:] = [d for d in dirs
                       if d not in EXCLUDE_DIRS and not d.startswith(".")]
            for n in sorted(names):
                if exts and not n.endswith(exts):
                    continue
                full = os.path.join(root, n)
                yield os.path.relpath(full, ROOT), full


def test_no_shipped_file_names_a_specific_project():
    hits = []
    for rel, full in shipped_files():
        allowed = ALLOW.get(rel, ())
        text = io.open(full, encoding="utf-8").read()
        for i, line in enumerate(text.split("\n"), 1):
            for pattern, why in BANNED:
                if any(a in pattern for a in allowed):
                    continue
                m = re.search(pattern, line)
                if m:
                    hits.append("%s:%d  %r is %s" % (rel, i, m.group(0), why))
    check("no shipped file names a specific project, org, path or identifier",
          not hits, "\n       " + "\n       ".join(hits[:12]))


def test_the_scan_actually_covers_the_shipped_files():
    """A scan over nothing passes trivially. Prove it reads what ships."""
    rels = [r for r, _ in shipped_files()]
    check("the scan reaches the skill bodies",
          any(r.endswith("skills/spec-recon/SKILL.md") for r in rels), rels[:5])
    check("the scan reaches the agent prompts",
          sum(1 for r in rels if r.startswith("agents/")) >= 12, len(rels))
    check("the scan reaches the shared scripts",
          any(r == "scripts/preflight.py" for r in rels), rels[:5])
    check("the scan skips tests and fixtures",
          not any("/tests/" in r or "fixtures" in r for r in rels), rels[:5])


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
