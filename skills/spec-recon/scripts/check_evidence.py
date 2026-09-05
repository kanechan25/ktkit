#!/usr/bin/env python3
"""Lint the evidence files a probe run produced, before anyone reads them.

Evidence files are the whole point of this skill: they turn things a document
reader cannot see -- code, binary artifacts, forge state -- into documents that
`docs-review` can read like any other. That only works if every statement in
them is traceable and every number says where it came from.

Two defects this catches, both of which have shipped before:

  * A number with no label, or a sentence mixing a measured number with a
    derived one. A figure that was computed once got read as an observation,
    was acted on, and had to be retracted mid-run. The fix is boring and it
    works: each number carries exactly one of [measured], [quoted], [derived].

  * A file with no way to reproduce it. A measurement nobody can rerun is an
    assertion wearing a table's clothes.

Usage
    check_evidence.py <dir-or-file>... [--quiet] [--json]

Output, one line per problem:
    MIXED-LABEL   probe-artifact-tpl.md:14  [measured] and [derived] in one row
    NO-LABEL      probe-vcs-state.md:9      number '2026-09-30' carries no label
    NO-CITATION   probe-code-calc.md        no path:line and no reproduce line
    NO-ACCESS-NOTE probe-vcs-state.md       says not-accessed without a reason

Exit status
    0  every file is clean
    1  at least one problem
    2  the arguments are unusable
"""
import argparse
import io
import json
import os
import re
import sys

LABELS = ("[measured]", "[quoted]", "[derived]")
LABEL_RE = re.compile(r"\[(measured|quoted|derived)\]")

# A path:line citation, or a stated way to regenerate the row.
CITE_RE = re.compile(r"[\w./\-]+\.\w+:\d+")
REPRO_RE = re.compile(r"^\s*(Reproduce|Query|Endpoint|Command)\s*:", re.M | re.I)

# Numbers worth labelling: counts, sizes, dates, versions, percentages. Ordinary
# prose numbers inside a sentence are not the target -- table cells are.
NUM_RE = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?%?|\d{4}-\d{2}-\d{2})(?![\w])")

# Rows that are structural rather than claims.
SKIP_ROW = re.compile(r"^\s*\|\s*[-: ]+\|")

NOT_ACCESSED_RE = re.compile(r"\b(not.accessed|NOT-ACCESSED|not reached|NOT-REACHED)\b",
                             re.I)


def problems_for(path):
    out = []
    try:
        text = io.open(path, encoding="utf-8").read()
    except (OSError, IOError) as exc:
        return [("UNREADABLE", path, 0, str(exc))]

    name = os.path.basename(path)
    lines = text.split("\n")

    # --- file-level: is any of this traceable at all? ----------------------
    if not CITE_RE.search(text) and not REPRO_RE.search(text):
        out.append(("NO-CITATION", name, 0,
                    "no path:line citation and no Reproduce/Query/Endpoint line"))

    # --- file-level: an unexplained gap ------------------------------------
    for i, line in enumerate(lines, 1):
        if NOT_ACCESSED_RE.search(line):
            tail = line.split(":", 1)[-1] if ":" in line else ""
            if len(tail.strip()) < 8 and "—" not in line and "-" not in tail:
                out.append(("NO-ACCESS-NOTE", name, i,
                            "declares something not accessed without saying why"))

    # --- row-level: labels --------------------------------------------------
    in_fence = False
    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or SKIP_ROW.match(line):
            continue

        found = LABEL_RE.findall(line)
        if len(set(found)) > 1:
            out.append(("MIXED-LABEL", name, i,
                        "%s in one row; a row asserts one kind of number"
                        % " and ".join("[%s]" % f for f in sorted(set(found)))))
            continue

        # Only table rows are held to the labelling rule: prose may count things
        # without turning into a ledger.
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        # A row whose last cell is a label column is labelled; so is one with a
        # label anywhere in it.
        if found:
            continue
        payload = " ".join(cells[1:])
        nums = NUM_RE.findall(payload)
        if nums and not any(lbl in line for lbl in LABELS):
            out.append(("NO-LABEL", name, i,
                        "number %r carries no [measured]/[quoted]/[derived]"
                        % nums[0]))
    return out


def collect(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, names in os.walk(p):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for n in sorted(names):
                    if n.endswith(".md"):
                        files.append(os.path.join(root, n))
        elif os.path.isfile(p):
            files.append(p)
        else:
            sys.stderr.write("no such path: %s\n" % p)
            return None
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    files = collect(a.paths)
    if files is None:
        return 2
    if not files:
        sys.stderr.write("no evidence files found under: %s\n" % ", ".join(a.paths))
        return 2

    allp = []
    for f in files:
        allp.extend(problems_for(f))

    if a.json:
        sys.stdout.write(json.dumps(
            [{"kind": k, "file": f, "line": l, "detail": d}
             for k, f, l, d in allp], indent=1, ensure_ascii=False) + "\n")
    elif not a.quiet:
        for kind, f, line, detail in allp:
            where = "%s:%d" % (f, line) if line else f
            sys.stdout.write("%-14s %-34s %s\n" % (kind, where, detail))
        sys.stdout.write("%d file(s) checked, %d problem(s)\n"
                         % (len(files), len(allp)))
    return 1 if allp else 0


if __name__ == "__main__":
    sys.exit(main())
