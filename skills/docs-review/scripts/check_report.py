#!/usr/bin/env python3
"""Lint a docs-review report: verdict validity, duplicate IDs, missing citations."""
import re
import sys
from collections import Counter

VERDICTS_A = {"Covered", "Partial", "Missing", "Contradict", "Conflict", "Stale", "Undecided"}
VERDICTS_B = {"Stated", "Inferred", "Conflicting", "Absent"}
NO_EVIDENCE_NEEDED = {"Missing", "Undecided", "Absent"}
ID_RE = re.compile(r"^(REQ|Q)-[A-Z0-9]+-\d{3}$|^Q-?\d+$", re.I)


def rows(path):
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        line = line.strip()
        if not line.startswith("|") or set(line) <= set("|- :"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        yield n, cells


def main():
    path = sys.argv[1]
    verdicts = VERDICTS_B if "--mode" in sys.argv and "b" in sys.argv[-1].lower() else VERDICTS_A
    problems, seen, counts = [], Counter(), Counter()

    for n, cells in rows(path):
        if len(cells) < 3 or not ID_RE.match(cells[0]):
            continue
        rid, verdict = cells[0], next((c for c in cells if c in verdicts), None)
        seen[rid] += 1
        if verdict is None:
            problems.append(f"{path}:{n}: {rid} has no valid verdict (one of {sorted(verdicts)})")
            continue
        counts[verdict] += 1
        rest = " ".join(cells[cells.index(verdict) + 1:])
        if verdict not in NO_EVIDENCE_NEEDED and not rest.strip():
            problems.append(f"{path}:{n}: {rid} is '{verdict}' with no evidence or quote")
        if verdict in NO_EVIDENCE_NEEDED and verdict != "Undecided" and not rest.strip():
            problems.append(f"{path}:{n}: {rid} is '{verdict}' without the search terms you checked")

    problems += [f"{path}: duplicate ID {rid} ({c} rows)" for rid, c in seen.items() if c > 1]

    if not counts:
        problems.append(f"{path}: no verdict rows found — is this the right file?")
    text = open(path, encoding="utf-8").read()
    if "## Round findings" not in text:
        problems.append(f"{path}: no '## Round findings' section — was the review loop run?")
    if "## Round log" not in text:
        problems.append(f"{path}: no '## Round log' table — convergence is asserted, not shown")
    if not re.search(r"^#+ .*(Source inventory|Inventory)", text, re.M | re.I):
        problems.append(f"{path}: no source inventory — which documents were read, and which were not?")
    if re.search(r"\bshard|not-accessed\b", text, re.I) and "coverage" not in text.lower():
        problems.append(f"{path}: sharded audit with no coverage declaration")

    print(f"{sum(counts.values())} rows: " + ", ".join(f"{v}={c}" for v, c in counts.most_common()))
    for p in problems:
        print("  " + p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
