#!/usr/bin/env python3
"""Lint a docs-review report against references/report-schema.md.

Implements exactly the checks listed in that file's lint contract, with the same ids.
It adds none of its own, and it never renames a section to make a check pass.

Usage:
    check_report.py REPORT [--mode a|b] [--max-questions N] [--rounds-cap N]
                           [--checklist PATH]
Exit code 1 if any check fails. Warnings do not fail the run.
"""
import argparse
import re
import sys
from collections import Counter

VERDICTS_A = {"Covered", "Partial", "Missing", "Contradict", "Conflict", "Stale", "Undecided"}
VERDICTS_B = {"Stated", "Inferred", "Conflicting", "Absent"}
VERDICTS_C = {"Verified", "Refuted", "Unverifiable", "Contradict", "Unsupported",
              "Answerable", "Open", "Implication"}
NO_EVIDENCE = {"Missing", "Undecided", "Absent", "Unverifiable", "Open"}
KINDS_C = {"fact", "assertion", "question", "conclusion"}
TIERS = {"T1", "T2", "T3", "T3.5", "T4", "-"}
READ_VALUES = {"full", "searched", "not-accessed"}

ID_RE = {
    "Doc ID": re.compile(r"^DOC-\d{2}$"),
    "Req ID": re.compile(r"^REQ-[A-Z0-9]{2,8}-\d{3}$"),
    "ASM ID": re.compile(r"^ASM-\d{3}$"),
    "Q ID": re.compile(r"^Q-\d{3}$"),
    "CLM ID": re.compile(r"^CLM-\d{3}$"),
}

HEADERS = {
    "## Source inventory": ["Doc ID", "Path", "What it is", "Version", "Read"],
    "## Requirements": ["Req ID", "Requirement", "Tier", "Verdict", "Evidence", "Quote", "Note"],
    "## Findings": ["Q ID", "Sub-question", "Answer", "Confidence", "Evidence", "Quote"],
    "## Claims": ["CLM ID", "Statement", "Kind", "Verdict", "Evidence", "Quote", "Note"],
    "## Knock-on and widening": ["CLM ID", "Kind",
                                 "What follows, or what the class is missing", "Evidence", "Severity"],
    "## Review team": ["Wave", "Role", "Agent", "Model", "Mode"],
    "## Round log": ["Round", "Reviewer", "Raised", "Upheld", "Refuted",
                     "New rows", "Verdict changes", "Citations rejected", "Nits"],
    "## Self-resolved": ["Question", "Tier", "How resolved", "Evidence"],
    "## Assumptions taken": ["ASM ID", "Assumption", "Reading chosen", "Evidence",
                            "Falsifier", "Blast radius"],
    "## Fixes applied": ["Req ID", "ASM ID", "Document", "Old verdict", "Change made",
                         "New verdict"],
    "## Proposed, not applied": ["Req ID", "Verdict", "Proposed edit", "Decision needed"],
}

REQUIRED = {
    "a": ["## Source inventory", "## Requirements", "## Review team", "## Round log",
          "## Round findings", "## Self-resolved"],
    "b": ["## Source inventory", "## Findings", "## Review team", "## Round log",
          "## Round findings", "## Self-resolved"],
    "c": ["## Source inventory", "## Claims", "## Resolutions", "## Review team",
          "## Round log", "## Round findings", "## Self-resolved"],
}

# Mode C verdicts that oblige a `### <CLM ID>` subsection in `## Resolutions`.
# `Verified` is excluded on purpose: confirmations would double the section.
MATERIAL_VERDICTS_C = ("Refuted", "Answerable", "Contradict", "Unsupported")

GATE_LABELS = [
    "**Searched:**",
    "**Why no artifact can answer it:**",
    "**Why not an evidenced assumption:**",
    "**Options:**",
    "**Recommendation:**",
    "**Default if you do not answer:**",
]
STATUS_TOKENS = ("BUDGET-CAPPED", "INCOMPLETE", "DEGRADED")
MATERIAL_COLS = ("New rows", "Verdict changes", "Citations rejected")


def split_sections(text):
    """Map '## Heading' -> its body lines. Keeps order of first occurrence."""
    out, current = {}, None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line.strip()
            out.setdefault(current, [])
        elif current is not None:
            out[current].append(line)
    return out


def rows_of(lines):
    """Yield (lineno_within_section, cells) for markdown table rows, skipping separators."""
    for i, line in enumerate(lines):
        s = line.strip()
        if not s.startswith("|") or set(s) <= set("|- :"):
            continue
        yield i, [c.strip() for c in s.strip("|").split("|")]


def table(section_lines):
    """Return (header_cells, data_rows) for the first table in a section."""
    it = list(rows_of(section_lines))
    if not it:
        return None, []
    return it[0][1], [cells for _, cells in it[1:]]


def as_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--mode", choices=["a", "b", "c"], default="a")
    ap.add_argument("--max-questions", type=int, default=3)
    ap.add_argument("--rounds-cap", type=int, default=None)
    ap.add_argument("--checklist", default=None,
                    help="registry file: checklist.md in mode a, claims.md in mode c")
    args = ap.parse_args()

    text = open(args.report, encoding="utf-8").read()
    sections = split_sections(text)
    fails, warns = [], []
    verdicts = {"a": VERDICTS_A, "b": VERDICTS_B, "c": VERDICTS_C}[args.mode]

    def fail(cid, msg):
        fails.append(f"{cid}: {msg}")

    def warn(cid, msg):
        warns.append(f"{cid}: {msg}")

    # --- S1 required sections -------------------------------------------------
    for h in REQUIRED[args.mode]:
        if h not in sections:
            fail("S1 missing-section", f"{h} is absent")
    if not re.search(r"^self_resolve_ratio=", text, re.M):
        fail("S1 missing-section", "no metrics line (self_resolve_ratio=...)")

    # --- S2 header rows -------------------------------------------------------
    for h, expected in HEADERS.items():
        if h in sections:
            got, _ = table(sections[h])
            if got is None:
                fail("S2 header-mismatch", f"{h} has no table")
            elif got != expected:
                fail("S2 header-mismatch", f"{h} header is {got}, expected {expected}")

    first_line = next((l for l in text.splitlines() if l.strip()), "")

    # --- inventory: R1, I2 ----------------------------------------------------
    doc_read = {}
    if "## Source inventory" in sections:
        hdr, data = table(sections["## Source inventory"])
        for cells in data:
            if len(cells) < 5:
                fail("R1 coverage-missing", f"inventory row is short: {cells}")
                continue
            did, read = cells[0], cells[4]
            if not ID_RE["Doc ID"].match(did):
                fail("I2 bad-id-format", f"{did} is not DOC-nn")
            if read not in READ_VALUES:
                fail("R1 coverage-missing", f"{did} Read={read!r}, expected one of {sorted(READ_VALUES)}")
            doc_read[did] = read

    # --- requirements / findings: I1, I2, I3, V1, V2, V3, R2 ------------------
    seen = Counter()
    counts = Counter()
    material_ids = []
    key = {"a": "## Requirements", "b": "## Findings", "c": "## Claims"}[args.mode]
    id_col = {"a": "Req ID", "b": "Q ID", "c": "CLM ID"}[args.mode]
    registry = None
    if args.mode in ("a", "c"):
        default_name = "checklist.md" if args.mode == "a" else "claims.md"
        pattern = r"REQ-[A-Z0-9]{2,8}-\d{3}" if args.mode == "a" else r"CLM-\d{3}"
        path = args.checklist
        if path is None:
            import os
            cand = os.path.join(os.path.dirname(os.path.abspath(args.report)), default_name)
            path = cand if os.path.exists(cand) else None
        if path:
            registry = set(re.findall(pattern, open(path, encoding="utf-8").read()))

    if key in sections:
        hdr, data = table(sections[key])
        cols = HEADERS[key]
        for cells in data:
            if len(cells) < len(cols):
                fail("S2 header-mismatch", f"{key} row has {len(cells)} cells, expected {len(cols)}")
                continue
            row = dict(zip(cols, cells))
            rid = row[id_col]
            seen[rid] += 1
            if not ID_RE[id_col].match(rid):
                fail("I2 bad-id-format", f"{rid} does not match {id_col} format")
            if registry is not None and rid not in registry:
                fail("I3 unregistered-id", f"{rid} is not in the checklist registry")
            verdict = row.get("Verdict") or row.get("Confidence")
            if verdict not in verdicts:
                fail("V1 bad-verdict", f"{rid} has verdict {verdict!r}")
                continue
            counts[verdict] += 1
            if args.mode == "a" and row["Tier"] not in TIERS:
                fail("V1 bad-verdict", f"{rid} has tier {row['Tier']!r}")
            if args.mode == "c" and row["Kind"] not in KINDS_C:
                fail("V1 bad-verdict", f"{rid} has kind {row['Kind']!r}")
            if verdict not in NO_EVIDENCE:
                if not row["Evidence"] or not row["Quote"]:
                    fail("V2 missing-evidence", f"{rid} is {verdict} with no evidence or no quote")
                for did in re.findall(r"DOC-\d{2}", row["Evidence"]):
                    if doc_read.get(did) == "not-accessed":
                        fail("R2 coverage-too-weak", f"{rid} cites {did}, declared not-accessed")
            if verdict in ("Missing", "Unverifiable", "Open") and not row.get("Note", "").strip(" -"):
                fail("V3 missing-search-terms", f"{rid} is {verdict} without the searches it ran")
            if verdict == "Answerable" and not row.get("Note", "").strip(" -"):
                fail("V3 missing-search-terms", f"{rid} is Answerable without the answer in Note")
            if args.mode == "c" and verdict in MATERIAL_VERDICTS_C:
                material_ids.append(rid)
    for rid, n in seen.items():
        if n > 1:
            fail("I1 duplicate-id", f"{rid} appears on {n} rows")

    # --- R3 resolutions cover every material claim ---------------------------
    if args.mode == "c":
        body = "\n".join(sections.get("## Resolutions", []))
        resolved = set(re.findall(r"^###\s+(CLM-\d{3})\s*$", body, re.M))
        for cells in table(sections.get("## Knock-on and widening", []))[1]:
            if len(cells) >= 5 and cells[4] == "material":
                material_ids.append(cells[0])
        for rid in dict.fromkeys(material_ids):
            if rid not in resolved:
                fail("R3 resolution-missing", f"{rid} is material with no '### {rid}' in ## Resolutions")

    # --- round log: C1, C2, C3 -----------------------------------------------
    totals = []
    if "## Round log" in sections:
        hdr, data = table(sections["## Round log"])
        cols = HEADERS["## Round log"]
        for cells in data:
            row = dict(zip(cols, cells))
            if row.get("Reviewer") == "TOTAL":
                totals.append(row)
        if not totals:
            fail("C2 missing-round-log", "no TOTAL row — convergence cannot be recomputed")
    else:
        fail("C2 missing-round-log", "## Round log is absent")

    last_material = sum(as_int(totals[-1].get(c)) for c in MATERIAL_COLS) if totals else 0
    claims_converged = re.search(r"\bconverged\b", text, re.I) is not None
    if claims_converged and last_material:
        fail("C1 false-convergence",
             f"convergence claimed while the last TOTAL row still has {last_material} material")
    if args.rounds_cap is not None and totals:
        if len(totals) >= args.rounds_cap and last_material:
            if not first_line.startswith(STATUS_TOKENS):
                fail("C3 cap-without-status",
                     f"cap {args.rounds_cap} reached with {last_material} material and no status on line 1")

    # --- review team: M3 ------------------------------------------------------
    if "## Review team" in sections:
        hdr, data = table(sections["## Review team"])
        cols = HEADERS["## Review team"]
        degraded = any(dict(zip(cols, c)).get("Mode") == "degraded" for c in data)
        if degraded and "DEGRADED" not in first_line:
            fail("M3 degraded-unreported", "team ran degraded but line 1 does not say so")

    # --- assumptions: A1, I2 --------------------------------------------------
    assumptions = 0
    if "## Assumptions taken" in sections:
        hdr, data = table(sections["## Assumptions taken"])
        cols = HEADERS["## Assumptions taken"]
        for cells in data:
            row = dict(zip(cols, cells))
            assumptions += 1
            if not ID_RE["ASM ID"].match(row["ASM ID"]):
                fail("I2 bad-id-format", f"{row['ASM ID']} is not ASM-nnn")
            if not row.get("Falsifier", "").strip(" -"):
                fail("A1 assumption-no-falsifier", f"{row['ASM ID']} has no falsifier")

    # --- fixes: A2 ------------------------------------------------------------
    if "## Fixes applied" in sections:
        hdr, data = table(sections["## Fixes applied"])
        cols = HEADERS["## Fixes applied"]
        for cells in data:
            row = dict(zip(cols, cells))
            if not row["Req ID"].strip(" -") and not row["ASM ID"].strip(" -"):
                fail("A2 fix-untraced", f"a fix row traces to neither a Req ID nor an ASM ID: {cells}")

    # --- decision gates: D1, D2 ----------------------------------------------
    gates = re.findall(r"^### (D\d{1,2}) ·.*?(?=^### D\d|\Z)", text, re.M | re.S)
    blocks = re.split(r"^### (?=D\d{1,2} ·)", text, flags=re.M)[1:]
    needs_user = 0
    for b in blocks:
        gid = b.split(" ", 1)[0].strip()
        if not re.match(r"^D\d{1,2}$", gid):
            continue
        needs_user += 1
        ticked = len(re.findall(r"^- \[x\]", b, re.M))
        if ticked != 6:
            fail("D1 gate-incomplete", f"{gid} has {ticked} ticked preconditions, expected 6")
        for label in GATE_LABELS:
            if label not in b:
                fail("D1 gate-incomplete", f"{gid} is missing {label}")
    if needs_user > args.max_questions:
        fail("D2 too-many-questions",
             f"{needs_user} questions reach the user, cap is {args.max_questions}")

    # --- metrics: M1, M2 ------------------------------------------------------
    self_resolved = len(table(sections["## Self-resolved"])[1]) if "## Self-resolved" in sections else 0
    denom = self_resolved + needs_user
    ratio = self_resolved / denom if denom else 1.0
    if ratio < 0.7:
        warn("M1 escalation-heavy", f"self_resolve_ratio={ratio:.2f} — tiers 1–3 likely unexhausted")
    verdict_moves = sum(as_int(t.get("Verdict changes")) for t in totals)
    accounted = len(re.findall(r"^(?:REQ-[A-Z0-9]{2,8}|ASM|CLM|Q)-\d{3}\s*$",
                               "\n".join(sections.get("## Round findings", [])), re.M))
    if verdict_moves > accounted:
        warn("M2 zero-escalation-unstable",
             f"{verdict_moves} verdict changes but only {accounted} accounted for in "
             "## Round findings — a verdict that moved without a recorded reason is a decision "
             "nobody can audit")
    elif denom and ratio == 1.0 and assumptions == 0 and verdict_moves:
        pass  # every move is explained in Round findings; self-review rounds are meant to move verdicts

    # --- output ---------------------------------------------------------------
    print(f"{sum(counts.values())} rows: " + ", ".join(f"{v}={c}" for v, c in counts.most_common()))
    print(f"self_resolve_ratio={ratio:.2f} · self_resolved={self_resolved} · "
          f"needs_user={needs_user} · assumptions={assumptions} · waves={len(totals)}")
    for f in fails:
        print(f"  FAIL {f}")
    for w in warns:
        print(f"  WARN {w}")
    if not fails and not warns:
        print("  clean")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
