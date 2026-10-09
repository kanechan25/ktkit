#!/usr/bin/env python3
"""The hint under the slash menu must be the skill's real argument surface.

Typing `/ktkit:<name>` shows the skill's `argument-hint` -- the one place a user
sees the flags without opening a page. A skill without one shows only its
description, which tells a model when to use the skill and tells the user
nothing about how. And a hint written once rots like any other prose: a flag is
added to `## Arguments` and the hint never hears about it. So the hint is
checked against the skill in both directions, the same pairing `test_help.py`
uses for the help pages.

  A1  every skill declares a non-empty `argument-hint`
  A2  every flag in a hint is one the skill's body actually mentions
                                            -- catches an invented flag
  A3  every flag in a skill's `## Arguments` section appears in its hint
                                            -- catches a forgotten flag

Run:  python3 skills/spec-recon/tests/test_argument_hint.py
"""
import glob
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
FLAG_RE = re.compile(r"(?<![\w-])--[a-z][a-z0-9-]+")
UNIVERSAL = {"--help"}

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def split(path):
    text = io.open(path, encoding="utf-8").read()
    if not text.startswith("---\n"):
        return {}, text
    end = text.index("\n---", 4)
    front, body = text[4:end], text[end + 4:]
    fields = {}
    for line in front.split("\n"):
        m = re.match(r"^([a-z-]+):\s*(.*)$", line)
        if m:
            v = m.group(2).strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            fields[m.group(1)] = v
    return fields, body


def arguments_section(body):
    m = re.search(r"^## Arguments\s*$(.*?)(?=^## |\Z)", body, re.M | re.S)
    return m.group(1) if m else ""


def flags(text):
    return set(FLAG_RE.findall(text)) - UNIVERSAL


def declared(section):
    """The flags a section declares, not every flag its prose mentions.

    Only the first column counts: a usage line's argument before its two-space
    gap, and a table row's first cell. The prose beside them names flags that
    belong to other commands (`git branch --show-current`) or that the skill
    refuses (`--deep`), and neither belongs in a hint.
    """
    out = set()
    fenced = False
    for line in section.split("\n"):
        if line.strip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            out |= flags(re.split(r"\S\s{2,}", line.strip() + "  ", 1)[0] + " ")
        elif line.startswith("|"):
            cells = line.strip().strip("|").split("|")
            if cells and not set(cells[0].strip()) <= set("-: "):
                out |= flags(cells[0])
    return out


def main():
    missing, invented, forgotten = [], [], []
    for path in sorted(glob.glob(os.path.join(ROOT, "skills", "*", "SKILL.md"))):
        name = os.path.basename(os.path.dirname(path))
        fields, body = split(path)
        hint = fields.get("argument-hint", "")
        if not hint:
            missing.append(name)
            continue
        for f in sorted(flags(hint) - flags(body)):
            invented.append("%s: %s" % (name, f))
        for f in sorted(declared(arguments_section(body)) - flags(hint)):
            forgotten.append("%s: %s" % (name, f))
    check("A1 every skill declares an argument-hint", not missing, missing)
    check("A2 every flag in a hint is one the skill mentions", not invented, invented)
    check("A3 every flag in ## Arguments appears in the hint", not forgotten, forgotten)


if __name__ == "__main__":
    main()
    print()
    if failures:
        print("%d failure(s)" % len(failures))
        sys.exit(1)
    print("all checks passed")
