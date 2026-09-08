#!/usr/bin/env python3
"""Insert or replace one delimited status block at the end of a document.

The block is delimited by HTML comments so it can be replaced on every later run
without touching a single character the author wrote:

    <!-- docs-review:begin -->
    ...
    <!-- docs-review:end -->

Everything above BEGIN is copied through byte for byte. That is the whole point:
the reviewed document is the author's own reasoning, and the only thing this
script may add is one delimited block after it.

The marker name is a parameter so a second workflow can own a second block in
the same file without either one being able to overwrite the other. It defaults
to `docs-review`, so every existing call keeps its exact previous behaviour.

Usage
    upsert_block.py <document> --block <file>   write/replace from a file
    upsert_block.py <document> --block -        write/replace from stdin
    upsert_block.py <document> --marker <name>  which block to own (default: docs-review)
    upsert_block.py <document> --verify         check every #clm-nnn link resolves
                                --report <path> (required by --verify)
Exit status
    0  written, unchanged, or verified clean
    1  a link does not resolve, or the document is malformed
    2  the marker name is not a usable one
"""
import argparse
import os
import re
import sys

DEFAULT_MARKER = "docs-review"

# A marker becomes part of an HTML comment, so anything that could close the
# comment early or collide with a path separator is rejected rather than
# escaped: a malformed delimiter would split someone's document in half.
MARKER_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,39}\Z")


def markers(name):
    """Return (BEGIN, END) for a marker name."""
    return "<!-- %s:begin -->" % name, "<!-- %s:end -->" % name


BEGIN, END = markers(DEFAULT_MARKER)


def split(text, marker=DEFAULT_MARKER):
    """Return (prefix, block, suffix). block is None when no marker pair exists."""
    begin, end = markers(marker)
    i = text.find(begin)
    if i == -1:
        if end in text:
            raise ValueError("found %s with no %s" % (end, begin))
        return text, None, ""
    j = text.find(end, i)
    if j == -1:
        raise ValueError("found %s with no %s" % (begin, end))
    return text[:i], text[i:j + len(end)], text[j + len(end):]


def upsert(text, body, marker=DEFAULT_MARKER):
    """Replace the block, or append one. Nothing above BEGIN is ever touched."""
    begin, end = markers(marker)
    prefix, block, suffix = split(text, marker)
    new = begin + "\n" + body.strip("\n") + "\n" + end
    if block is None:
        sep = "" if prefix.endswith("\n\n") else ("\n" if prefix.endswith("\n") else "\n\n")
        return prefix + sep + new + "\n"
    return prefix + new + suffix


def verify_links(doc_text, report_path, marker=DEFAULT_MARKER):
    """Every #clm-nnn the block links to must exist as '### CLM-nnn' in the report."""
    _, block, _ = split(doc_text, marker)
    if block is None:
        return []
    wanted = {m.upper() for m in re.findall(r"#(clm-\d{3})\b", block, re.I)}
    if not wanted:
        return []
    with open(report_path, encoding="utf-8") as fh:
        have = set(re.findall(r"^###\s+(CLM-\d{3})\s*$", fh.read(), re.M))
    return sorted(wanted - have)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("document")
    ap.add_argument("--block", help="file holding the block body, or - for stdin")
    ap.add_argument("--marker", default=DEFAULT_MARKER,
                    help="name of the block this call owns (default: %s)" % DEFAULT_MARKER)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--report", help="report path, required with --verify")
    args = ap.parse_args()

    if not MARKER_RE.match(args.marker):
        print("FAIL bad-marker: %r is not [A-Za-z0-9][A-Za-z0-9._-]{0,39}" % args.marker)
        return 2

    with open(args.document, encoding="utf-8") as fh:
        text = fh.read()

    if args.verify:
        if not args.report:
            ap.error("--verify needs --report")
        try:
            missing = verify_links(text, args.report, args.marker)
        except ValueError as exc:
            print("FAIL malformed-block: %s" % exc)
            return 1
        for anchor in missing:
            print("FAIL anchor-broken: %s has no '### %s' in %s"
                  % (anchor.lower(), anchor, os.path.basename(args.report)))
        if missing:
            return 1
        print("anchors ok")
        return 0

    if not args.block:
        ap.error("give --block or --verify")
    body = sys.stdin.read() if args.block == "-" else open(args.block, encoding="utf-8").read()
    try:
        out = upsert(text, body, args.marker)
    except ValueError as exc:
        print("FAIL malformed-block: %s" % exc)
        return 1
    if out == text:
        print("unchanged")
        return 0
    with open(args.document, "w", encoding="utf-8") as fh:
        fh.write(out)
    print("wrote %s block to %s" % (args.marker, args.document))
    return 0


if __name__ == "__main__":
    sys.exit(main())
