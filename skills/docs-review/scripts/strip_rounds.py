#!/usr/bin/env python3
"""Write a copy of a docs-review report with the '## Round findings' section removed.

Reviewers must not see earlier waves' notes — a reviewer that reads what a previous round
caught looks for the same things. Stripping the section by hand costs the lead a full read
of the report plus a full write of the copy; this does it without either.

Usage:
    strip_rounds.py REPORT [-o OUT]        # default OUT is REPORT with '.stripped.md'
Prints the path it wrote, which is what gets passed to the reviewers.
"""
import argparse
import sys

DROP = "## Round findings"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()

    out = args.out or args.report.rsplit(".md", 1)[0] + ".stripped.md"
    if out == args.report:
        print("refusing to overwrite the report in place", file=sys.stderr)
        return 2

    kept, dropping, found = [], False, False
    for line in open(args.report, encoding="utf-8"):
        if line.startswith("## "):
            dropping = line.strip() == DROP
            found = found or dropping
        if not dropping:
            kept.append(line)

    with open(out, "w", encoding="utf-8") as fh:
        fh.writelines(kept)

    print(out)
    if not found:
        print(f"note: {DROP} was not present", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
