#!/usr/bin/env python3
"""The append-only record of every unknown the chain has settled.

A chain runs analyse -> spec -> plan as separate skills, and each one owns its
own escalation ladder. Without a shared record they re-derive the same unknowns:
the spec step asks what the analyse step already answered, pays for a resolver
again, and can reach a different conclusion than the artifact upstream of it.

So the chain keeps one file. Every unknown that was settled goes in it, with the
tier that settled it and the citation. Before dispatching a resolver, the caller
asks this file first -- a lookup costs nothing, a resolver spawn does not.

Three properties matter more than convenience, and each one is a subcommand
constraint rather than a convention:

  * **Append-only.** Changing your mind writes a new row for the same id. The
    old row stays, marked superseded by the newer one. What was believed, and
    when it stopped being believed, is part of the record.
  * **Ids are minted once.** `--next-id` is the only way to get one, and it
    reads the file. Two callers that mint concurrently get the same id, which is
    why the chain mints in the lead and never inside a subagent.
  * **The ratio is computed, never asserted.** `--metric` recounts from the rows
    rather than trusting a number some agent wrote down.

Usage
    ledger.py <path> --init
    ledger.py <path> --next-id
    ledger.py <path> --add --id Q01 --question Q --tier T1 --conclusion C
                     --evidence path:line [--falsifier F] [--phase A]
    ledger.py <path> --lookup "question text" [--threshold 0.6]
    ledger.py <path> --metric [--min-ratio 0.70]
    ledger.py <path> --open

Exit status
    0  done, or lookup found a match, or the metric is at/above the floor
    1  lookup found nothing, or the metric is below the floor
    2  bad usage, or the file is malformed
"""
import argparse
import io
import os
import re
import sys

TIERS = ("T1", "T2", "T3", "T3.5", "T4")
SELF_RESOLVED = ("T1", "T2", "T3", "T3.5")
OPEN = "OPEN"

HEADER = [
    "| ID | Question | Tier | Conclusion | Evidence | Falsifier | Phase |",
    "| -- | -------- | ---- | ---------- | -------- | --------- | ----- |",
]

PREAMBLE = """\
# Resolved unknowns

Append-only. One row per settling of one unknown; a later row for the same ID
supersedes the earlier one, and the earlier one stays. Written by
`ktkit:chain`; every phase of the run reads it before asking anything.

`Conclusion` of `OPEN` means the row reached T4 and is waiting on the user.

"""

ID_RE = re.compile(r"\AQ\d{2,}\Z")

# Words that carry no discriminating weight in a question. Kept short and
# closed: a long stopword list starts deciding which questions are "the same",
# which is not this file's job.
STOP = frozenset("""
a an the is are was were be been being do does did done of to in on at by for
with from as that this these those it its and or not no if then than what
which who whom whose when where why how can could should would will shall may
""".split())


def norm(text):
    """Token set used for matching. Deliberately crude and deterministic."""
    words = re.findall(r"[a-z0-9_]+", text.lower())
    return frozenset(w for w in words if len(w) > 2 and w not in STOP)


def similarity(a, b):
    """Jaccard over the token sets. 1.0 is identical, 0.0 shares nothing."""
    sa, sb = norm(a), norm(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / float(len(sa | sb))


def cell(text):
    """Make a string safe inside a markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ").strip() or "—"


def uncell(text):
    return text.replace("\\|", "|").strip()


def read_rows(path):
    """Every row in file order. Malformed rows raise rather than being skipped:
    a row silently dropped is an unknown silently re-opened."""
    if not os.path.exists(path):
        return []
    rows = []
    with io.open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.rstrip("\n")
            if not line.startswith("|"):
                continue
            parts = [p.strip() for p in line.strip().strip("|").split("|")]
            if len(parts) != 7:
                raise ValueError("line %d: expected 7 columns, found %d" % (n, len(parts)))
            if parts[0] in ("ID", "--") or set(parts[0]) <= set("- "):
                continue
            if not ID_RE.match(parts[0]):
                raise ValueError("line %d: %r is not an ID like Q01" % (n, parts[0]))
            rows.append({
                "id": parts[0], "question": uncell(parts[1]), "tier": parts[2],
                "conclusion": uncell(parts[3]), "evidence": uncell(parts[4]),
                "falsifier": uncell(parts[5]), "phase": parts[6], "line": n,
            })
    return rows


def latest(rows):
    """The current belief for each id: the last row that mentions it."""
    out = {}
    for r in rows:
        out[r["id"]] = r
    return out


def do_init(path):
    if os.path.exists(path):
        print("exists %s" % path)
        return 0
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write(PREAMBLE + "\n".join(HEADER) + "\n")
    print("created %s" % path)
    return 0


def do_next_id(rows):
    used = [int(r["id"][1:]) for r in rows]
    print("Q%02d" % ((max(used) + 1) if used else 1))
    return 0


def do_add(path, rows, args):
    if args.tier not in TIERS:
        print("FAIL bad-tier: %s not in %s" % (args.tier, ", ".join(TIERS)))
        return 2
    if not ID_RE.match(args.id):
        print("FAIL bad-id: %r is not an ID like Q01" % args.id)
        return 2
    conclusion = args.conclusion or OPEN
    if args.tier == "T3.5" and not args.falsifier:
        # The whole difference between an evidenced assumption and a guess is
        # that someone wrote down what would disprove it.
        print("FAIL missing-falsifier: a T3.5 row without a falsifier is a guess")
        return 2
    if args.tier != "T4" and conclusion == OPEN:
        print("FAIL open-non-t4: only a T4 row may be OPEN")
        return 2
    if not os.path.exists(path):
        do_init(path)
    row = "| %s | %s | %s | %s | %s | %s | %s |" % (
        args.id, cell(args.question), args.tier, cell(conclusion),
        cell(args.evidence or ""), cell(args.falsifier or ""), cell(args.phase or ""))
    with io.open(path, "a", encoding="utf-8") as fh:
        fh.write(row + "\n")
    prior = latest(rows).get(args.id)
    if prior:
        print("appended %s (supersedes the row at line %d)" % (args.id, prior["line"]))
    else:
        print("appended %s" % args.id)
    return 0


def do_lookup(rows, question, threshold):
    """Best current match, if any. Prints the row so the caller can cite it."""
    best, score = None, 0.0
    for r in latest(rows).values():
        if r["conclusion"] == OPEN:
            continue                      # still a question; it settles nothing
        s = similarity(question, r["question"])
        if s > score:
            best, score = r, s
    if best is None or score < threshold:
        print("MISS %.2f — nothing settled covers this" % score)
        return 1
    print("HIT %.2f %s [%s] %s — %s" % (score, best["id"], best["tier"],
                                        best["conclusion"], best["evidence"]))
    return 0


def do_metric(rows, floor):
    cur = latest(rows).values()
    self_resolved = sum(1 for r in cur if r["tier"] in SELF_RESOLVED)
    needs_user = sum(1 for r in cur if r["tier"] == "T4" and r["conclusion"] == OPEN)
    assumptions = sum(1 for r in cur if r["tier"] == "T3.5")
    denom = self_resolved + needs_user
    ratio = (self_resolved / float(denom)) if denom else 1.0
    print("self_resolve_ratio=%.2f · self_resolved=%d · needs_user=%d · assumptions=%d"
          % (ratio, self_resolved, needs_user, assumptions))
    # Report every violation, not the first one. A caller that fixes what it was
    # told about and re-runs, only to be told about the next thing, spends a
    # round-trip per problem -- which is the cost this whole design removes.
    bad = False
    if ratio < floor:
        print("BELOW-FLOOR tiers 1-3 were not exhausted (floor %.2f)" % floor)
        bad = True
    if needs_user > 3:
        # The gate is answer-by-exception. More than three rows is not a gate,
        # it is the interview this whole design exists to remove.
        print("TOO-MANY-OPEN %d rows are OPEN; a gate takes at most 3" % needs_user)
        bad = True
    return 1 if bad else 0


def do_open(rows):
    for r in latest(rows).values():
        if r["conclusion"] == OPEN:
            print("%s %s" % (r["id"], r["question"]))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--next-id", action="store_true", dest="next_id")
    ap.add_argument("--add", action="store_true")
    ap.add_argument("--lookup")
    ap.add_argument("--metric", action="store_true")
    ap.add_argument("--open", action="store_true", dest="show_open")
    ap.add_argument("--id")
    ap.add_argument("--question")
    ap.add_argument("--tier")
    ap.add_argument("--conclusion")
    ap.add_argument("--evidence")
    ap.add_argument("--falsifier")
    ap.add_argument("--phase")
    ap.add_argument("--threshold", type=float, default=0.6)
    ap.add_argument("--min-ratio", type=float, default=0.70, dest="min_ratio")
    args = ap.parse_args()

    if args.init:
        return do_init(args.path)

    try:
        rows = read_rows(args.path)
    except ValueError as exc:
        print("FAIL malformed-ledger: %s" % exc)
        return 2

    if args.next_id:
        return do_next_id(rows)
    if args.add:
        if not (args.id and args.question and args.tier):
            ap.error("--add needs --id, --question and --tier")
        return do_add(args.path, rows, args)
    if args.lookup is not None:
        return do_lookup(rows, args.lookup, args.threshold)
    if args.metric:
        return do_metric(rows, args.min_ratio)
    if args.show_open:
        return do_open(rows)
    ap.error("give one of --init, --next-id, --add, --lookup, --metric, --open")


if __name__ == "__main__":
    sys.exit(main())
