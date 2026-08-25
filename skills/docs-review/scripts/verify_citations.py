#!/usr/bin/env python3
"""Check every citation in an audit report against the file it cites.

A citation is a path, a line, and a verbatim quote. Whether the quote is really
at that line is a string comparison, so it is settled here rather than by an
agent: a script never reads a near-match and lets it through, and it costs no
tokens to run over two hundred rows.

Rows this cannot settle are printed as MISMATCH / OFF_BY / NOT_FOUND for the
`evidence` reviewer to look at. It is handed those rows only, never the report.

Usage
    verify_citations.py <report> [--root <dir>] [--window N] [--quiet]

Output, one line per row that is not clean:
    MISMATCH  CLM-014  spec.md:88   quote is not at that line
    OFF_BY    CLM-045  spec.md:88   quote found at line 91
    NOT_FOUND CLM-031  docs/x.md    cannot open the file
    NO_LINE   CLM-052  spec.md      citation names no line
Exit status
    0  every citation with a checkable quote holds
    1  at least one did not

What it deliberately does not do
    A quote is allowed to span up to four lines from the line cited, because
    reports wrap them. So a citation off by one or two lines whose quote is long
    reads as exact. This tool exists to catch a quote that is not in the file at
    all, or not where the report says; it is not a line-accuracy checker, and a
    row it passes is not proof the verdict is right — only that the text is real.
"""
import argparse
import os
import re
import sys

ID_RE = re.compile(r"(REQ-[A-Z0-9]{2,8}-\d{3}|CLM-\d{3}|Q-\d{3}|ASM-\d{3})")
# `path:line`, `path:line-line` or `path:§section` inside a table cell.
CITE_RE = re.compile(r"([\w./\-]+\.\w+):(\d+)(?:-(\d+))?")
# Quotes are stored with surrounding double quotes or backticks; both are stripped.
STRIP = ' \t`"“”'


def norm(text):
    """Collapse whitespace so a re-wrapped quote still matches."""
    return re.sub(r"\s+", " ", text).strip().strip(STRIP).lower()


def cells_of(line):
    s = line.strip()
    if not s.startswith("|") or set(s) <= set("|- :"):
        return None
    return [c.strip() for c in s.strip("|").split("|")]


def read_lines(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read().splitlines()


def _at(lines, start, want, span=4):
    """True when `want` appears in up to `span` lines joined from `start` (1-based).

    A quote is allowed to span lines because reports wrap them; it is not allowed
    to start earlier than the line cited, which is what makes OFF_BY meaningful.
    """
    for end in range(start, min(start + span - 1, len(lines)) + 1):
        if want in norm(" ".join(lines[start - 1:end])):
            return True
    return False


def find_quote(lines, lineno, quote, window):
    """Return 'exact', the line where the quote really starts, or None.

    The cited line is tested first. Testing the window first reports OFF_BY for a
    correct citation whenever the quote also falls inside a join that began one
    line earlier — every multi-line quote hits that.
    """
    want = norm(quote)
    if not want:
        return "exact"
    if _at(lines, lineno, want):
        return "exact"
    lo = max(1, lineno - window)
    hi = min(len(lines), lineno + window)
    # Single lines first, so OFF_BY names the line the quote actually starts on
    # rather than the earliest line of a join that happens to contain it.
    for span in (1, 4):
        for start in range(lo, hi + 1):
            if start != lineno and _at(lines, start, want, span=span):
                return start
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--root", default=None,
                    help="resolve cited paths against this directory (default: the report's)")
    ap.add_argument("--window", type=int, default=3,
                    help="lines either side of the cited line to accept as OFF_BY")
    ap.add_argument("--quiet", action="store_true", help="print only the summary")
    args = ap.parse_args()

    root = args.root or os.path.dirname(os.path.abspath(args.report))
    with open(args.report, encoding="utf-8") as fh:
        report = fh.read()

    cache, problems, checked = {}, [], 0
    for line in report.splitlines():
        cells = cells_of(line)
        if not cells:
            continue
        ids = ID_RE.findall(cells[0])
        if not ids:
            continue
        rid = ids[0]
        joined = " | ".join(cells[1:])
        cite = CITE_RE.search(joined)
        if not cite:
            continue
        rel, lineno = cite.group(1), int(cite.group(2))
        # The quote is whatever cell holds the longest quoted or backticked run.
        quotes = re.findall(r'"([^"]{4,})"|`([^`]{4,})`', joined)
        quote = max(("".join(q) for q in quotes), key=len, default="")
        if not quote:
            continue
        checked += 1
        path = os.path.join(root, rel)
        if path not in cache:
            cache[path] = read_lines(path) if os.path.isfile(path) else None
        lines = cache[path]
        if lines is None:
            problems.append(("NOT_FOUND", rid, rel, "cannot open the file"))
            continue
        if lineno > len(lines):
            problems.append(("MISMATCH", rid, "%s:%d" % (rel, lineno),
                             "file has %d lines" % len(lines)))
            continue
        where = find_quote(lines, lineno, quote, args.window)
        if where is None:
            problems.append(("MISMATCH", rid, "%s:%d" % (rel, lineno),
                             "quote is not at that line"))
        elif where != "exact":
            problems.append(("OFF_BY", rid, "%s:%d" % (rel, lineno),
                             "quote found at line %d" % where))

    if not args.quiet:
        for kind, rid, where, why in problems:
            print("%-9s %-14s %-28s %s" % (kind, rid, where, why))
    print("%d citations checked, %d need a look" % (checked, len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
