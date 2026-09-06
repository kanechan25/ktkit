#!/usr/bin/env python3
"""The help surface for this plugin: an index, and one page per skill.

Help that is typed out by a model drifts. It invents a flag that was renamed,
keeps one that was dropped, and reads exactly as authoritative either way. So
none of it is typed at call time: every page is a file in the skill it
describes, this script assembles them, and
`skills/spec-recon/tests/test_help.py` checks each page against the skill's own
`## Arguments` section -- a flag named here that the skill does not accept, or
a flag the skill accepts that is named nowhere here, fails the suite.

  help.py                 the index -- every skill, one line each
  help.py <skill>         that skill's page
  help.py --all           every page
  help.py --list          bare skill names, one per line (for tests and shells)

A page is `skills/<name>/references/help.md`. Its first two significant lines
carry the index metadata:

    <!-- group: Audit | order: 20 -->
    # ktkit:spec-recon -- measure what documents only claim

`group` buckets the index, `order` sorts within and across buckets, and the
text after the dash is the one-line summary. A skill with no page still appears
in the index, summarised from its frontmatter `description`, because a skill
missing from the index is worse than one summarised badly.

Stdlib only, Python 3.9. No dependency is worth adding to print a list.
"""
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")

META_RE = re.compile(r"<!--\s*group:\s*([^|]+?)\s*\|\s*order:\s*(\d+)\s*-->")
H1_RE = re.compile(r"^#\s+(?:ktkit:)?([\w-]+)\s+[-—]{1,2}\s+(.+?)\s*$", re.M)
DEFAULT_GROUP = "Other"
DEFAULT_ORDER = 900


def read(path):
    return io.open(path, encoding="utf-8").read()


def skill_names():
    if not os.path.isdir(SKILLS):
        return []
    return sorted(n for n in os.listdir(SKILLS)
                  if os.path.isfile(os.path.join(SKILLS, n, "SKILL.md")))


def page_path(name):
    return os.path.join(SKILLS, name, "references", "help.md")


def frontmatter_summary(name):
    """Last resort: the first sentence of the skill's own description."""
    try:
        text = read(os.path.join(SKILLS, name, "SKILL.md"))
    except IOError:
        return "(no description)"
    m = re.search(r"^description:\s*(.*?)(?=^\w+:|^---)", text, re.M | re.S)
    if not m:
        return "(no description)"
    body = " ".join(m.group(1).split()).strip().strip('">')
    body = re.sub(r"^[>|]\s*", "", body)
    first = re.split(r"(?<=[a-z0-9)`])\.\s", body)[0]
    return (first[:110] + "...") if len(first) > 110 else first


def entry(name):
    """(group, order, name, summary) for one skill."""
    path = page_path(name)
    if not os.path.isfile(path):
        return (DEFAULT_GROUP, DEFAULT_ORDER, name, frontmatter_summary(name))
    text = read(path)
    m = META_RE.search(text)
    group = m.group(1) if m else DEFAULT_GROUP
    order = int(m.group(2)) if m else DEFAULT_ORDER
    h = H1_RE.search(text)
    summary = h.group(2) if h else frontmatter_summary(name)
    return (group, order, name, summary)


def version():
    try:
        man = json.loads(read(os.path.join(ROOT, ".claude-plugin", "plugin.json")))
        return man.get("version", "?")
    except Exception:                                          # noqa: BLE001
        return "?"


def index():
    entries = [entry(n) for n in skill_names()]
    entries.sort(key=lambda e: (e[1], e[2]))
    width = max([len(e[2]) for e in entries] + [12])
    out = ["ktkit %s — spec-driven development toolkit for Claude Code" % version(),
           "%d skills. Type the name to run it." % len(entries),
           ""]
    seen = None
    for group, _order, name, summary in entries:
        if group != seen:
            out.append("%s" % group.upper())
            seen = group
        out.append("  ktkit:%-*s  %s" % (width, name, summary))
    out += ["",
            "Detail for one skill:",
            "  /ktkit:<skill> --help        e.g.  /ktkit:spec-recon --help",
            "  /ktkit:help <skill>          e.g.  /ktkit:help chain",
            "",
            "Start here if you are new:  /ktkit:help chain"]
    return "\n".join(out)


def detail(name):
    if name not in skill_names():
        near = [n for n in skill_names() if name in n or n in name]
        msg = ["No skill named %r." % name,
               "Known: %s" % ", ".join(skill_names())]
        if near:
            msg.insert(1, "Did you mean: %s ?" % ", ".join(near))
        return "\n".join(msg), 1
    path = page_path(name)
    if not os.path.isfile(path):
        return ("ktkit:%s has no help page yet.\n\n%s\n\n"
                "Its full instructions are skills/%s/SKILL.md."
                % (name, frontmatter_summary(name), name)), 1
    return META_RE.sub("", read(path)).lstrip("\n").rstrip() + "\n", 0


def main(argv):
    args = [a for a in argv[1:] if a.strip()]
    if not args:
        print(index())
        return 0
    if args[0] in ("--list", "-l"):
        print("\n".join(skill_names()))
        return 0
    if args[0] in ("--all", "-a"):
        parts = []
        for n in skill_names():
            body, _rc = detail(n)
            parts.append(body)
        print(("\n\n" + "-" * 78 + "\n\n").join(p.rstrip() for p in parts))
        return 0
    if args[0] in ("--help", "-h", "help"):
        print(__doc__.strip())
        return 0
    body, rc = detail(args[0].lstrip("/").replace("ktkit:", ""))
    print(body)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
