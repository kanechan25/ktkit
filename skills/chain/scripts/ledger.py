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
import json
import os
import re
import subprocess
import time
import sys

TIERS = ("T1", "T2", "T3", "T3.5", "T4")
SELF_RESOLVED = ("T1", "T2", "T3", "T3.5")
OPEN = "OPEN"

HEADER = [
    "| ID | Question | Tier | Conclusion | Evidence | Falsifier | Phase | At | Head |",
    "| -- | -------- | ---- | ---------- | -------- | --------- | ----- | -- | ---- |",
]

PREAMBLE = """\
# Resolved unknowns

Append-only. One row per settling of one unknown; a later row for the same ID
supersedes the earlier one, and the earlier one stays. Written by
`ktkit:chain`; every phase of the run reads it before asking anything.

`Conclusion` of `OPEN` means the row reached T4 and is waiting on the user.

"""

ID_RE = re.compile(r"\AQ\d{2,}\Z")

# ---------------------------------------------------------------- task state
#
# A second append-only table, beside the ledger, holding what happened to each
# task rather than to each question. It exists for one question the chain could
# not answer without it: when a change request rewrites a requirement, WHICH
# tasks does that kill, and were they already built?
#
#     pending -> ready -> running -> done -> invalidated
#                                  \-> superseded
#
# The two end states are not synonyms and the difference is the whole point:
#
#   invalidated   the task was DONE, and it was done against a requirement that
#                 no longer says that. Work exists in the tree and is now wrong.
#   superseded    the task was NOT done, and its definition changed underneath
#                 it. Nothing was built; the row is simply stale.
#
# Treating them as one state loses the only fact that decides what to do next:
# one needs code unwound, the other needs a row rewritten.
#
# A `done` row must carry `spec_refs` and `touched`, written AT THE MOMENT it is
# marked done. Deriving them afterwards means re-reading the diff and the spec
# for every task -- the same argument `deviation.py` makes for recording a
# divergence when it happens rather than at the end, and for the same reason:
# the information is nearly free now and expensive later.
TASK_STATE_FILE = "task-state.md"
TASK_ID_RE = re.compile(r"\AT\d{2,}\Z")

TASK_STATES = ("pending", "ready", "running", "done", "invalidated",
               "superseded")
TASK_DONE = "done"
TASK_INVALIDATED = "invalidated"
TASK_SUPERSEDED = "superseded"

# Which transitions are legal. Absent entries are refused, so a typo produces a
# stop rather than a state nothing else understands.
TASK_NEXT = {
    None: ("pending", "ready"),
    "pending": ("ready", TASK_SUPERSEDED),
    "ready": ("running", TASK_SUPERSEDED),
    "running": (TASK_DONE, "ready", TASK_SUPERSEDED),
    TASK_DONE: (TASK_INVALIDATED,),
    TASK_INVALIDATED: (),
    TASK_SUPERSEDED: (),
}

TASK_HEADER = [
    "| Task | State | Spec refs | Touched | Why | At | Head |",
    "| ---- | ----- | --------- | ------- | --- | -- | ---- |",
]

TASK_PREAMBLE = """\
# Task state

Append-only. One row per transition; the last row for a task is its current
state. Written by `ktkit:chain`, read by `/ktkit:cr-delta` to answer which tasks
a changed requirement kills without re-reading the repository.

`invalidated` means the task was DONE against a requirement that has changed --
there is work in the tree that is now wrong. `superseded` means it was NOT done
and its definition changed -- nothing was built. They are different problems.

"""

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
            # Nine columns since provenance was added; seven is a ledger written
            # before that and is read as having none. Refusing it would crash a
            # `--resume` on any run started earlier, and dropping it would
            # silently re-open a settled question -- the failure this parser was
            # written strict to prevent.
            if len(parts) == 7:
                parts = parts + ["", ""]
            elif len(parts) != 9:
                raise ValueError("line %d: expected 7 or 9 columns, found %d"
                                 % (n, len(parts)))
            if parts[0] in ("ID", "--") or set(parts[0]) <= set("- "):
                continue
            if not ID_RE.match(parts[0]):
                raise ValueError("line %d: %r is not an ID like Q01" % (n, parts[0]))
            rows.append({
                "id": parts[0], "question": uncell(parts[1]), "tier": parts[2],
                "conclusion": uncell(parts[3]), "evidence": uncell(parts[4]),
                "falsifier": uncell(parts[5]), "phase": parts[6],
                "at": parts[7], "head": parts[8], "line": n,
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


def git_head(path):
    """The short SHA the answer was settled against, or "" if there is no repo.

    A conclusion is only as current as the tree it was drawn from. Without this
    there is no way to ask whether a row that cited code is still true after
    forty commits -- and no safe way to reuse a row from another run, which is
    why cross-run lookup depends on this column existing.
    """
    try:
        out = subprocess.check_output(
            ["git", "-C", os.path.dirname(os.path.abspath(path)) or ".",
             "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL, timeout=15)
        return out.decode("utf-8").strip()
    except Exception:                                          # noqa: BLE001
        return ""


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
    row = "| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
        args.id, cell(args.question), args.tier, cell(conclusion),
        cell(args.evidence or ""), cell(args.falsifier or ""), cell(args.phase or ""),
        args.at or time.strftime("%Y-%m-%dT%H:%M:%S"),
        args.head if args.head is not None else git_head(path))
    with io.open(path, "a", encoding="utf-8") as fh:
        fh.write(row + "\n")
    prior = latest(rows).get(args.id)
    if prior:
        print("appended %s (supersedes the row at line %d)" % (args.id, prior["line"]))
    else:
        print("appended %s" % args.id)
    return 0


def task_state_path(ledger_path):
    return os.path.join(os.path.dirname(os.path.abspath(ledger_path)),
                        TASK_STATE_FILE)


def read_task_rows(path):
    """Every transition in file order. A malformed row raises.

    Same reasoning as `read_rows`: a row quietly skipped is a task whose state
    silently reverts to whatever came before it, and nothing downstream can see
    that happened.
    """
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
                raise ValueError("line %d: expected 7 columns, found %d"
                                 % (n, len(parts)))
            if parts[0] in ("Task", "--") or set(parts[0]) <= set("- "):
                continue
            if not TASK_ID_RE.match(parts[0]):
                raise ValueError("line %d: %r is not a task id like T01"
                                 % (n, parts[0]))
            rows.append({
                "task": parts[0], "state": parts[1],
                "spec_refs": split_refs(uncell(parts[2])),
                "touched": split_refs(uncell(parts[3])),
                "why": uncell(parts[4]), "at": parts[5], "head": parts[6],
                "line": n,
            })
    return rows


# What `cell()` writes for an empty value. Reading it back as data is a real
# failure mode: a task with no spec_refs would come back citing a requirement
# called "—", match nothing, and be filed as untouched -- which reads as
# "checked and unaffected" when nothing was checked at all.
EMPTY_CELL = "—"


def split_refs(text):
    return [t.strip() for t in text.split(",")
            if t.strip() and t.strip() != EMPTY_CELL]


def task_latest(rows):
    out = {}
    for r in rows:
        out[r["task"]] = r
    return out


def do_task_state(ledger_path, args):
    """Record one transition, refusing the ones that lose information."""
    path = task_state_path(ledger_path)
    if not TASK_ID_RE.match(args.id or ""):
        print("FAIL bad-task-id: %r is not a task id like T01" % args.id)
        return 2
    state = args.set_state
    if state not in TASK_STATES:
        print("FAIL bad-state: %s not in %s" % (state, ", ".join(TASK_STATES)))
        return 2

    rows = read_task_rows(path)
    current = task_latest(rows).get(args.id)
    from_state = current["state"] if current else None
    allowed = TASK_NEXT.get(from_state, ())
    if state not in allowed:
        print("FAIL bad-transition: %s -> %s is not allowed (from %s: %s)"
              % (from_state or "(new)", state, from_state or "(new)",
                 ", ".join(allowed) or "nothing -- it is a terminal state"))
        return 2

    spec_refs = split_refs(args.spec_refs or "")
    touched = split_refs(args.touched or "")
    if state == TASK_DONE:
        # Recorded now or reconstructed later from a diff and a spec, for every
        # task. The second one is what this column exists to avoid.
        if not spec_refs:
            print("FAIL missing-spec-refs: a done task must say which "
                  "requirements it satisfies, recorded now rather than "
                  "reconstructed from a diff later")
            return 2
        if not touched:
            print("FAIL missing-touched: a done task must say what it changed, "
                  "or a later change request has to re-read the repository to "
                  "find out")
            return 2

    if not os.path.exists(path):
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with io.open(path, "w", encoding="utf-8") as fh:
            fh.write(TASK_PREAMBLE + "\n".join(TASK_HEADER) + "\n")

    row = "| %s | %s | %s | %s | %s | %s | %s |" % (
        args.id, state, cell(", ".join(spec_refs)), cell(", ".join(touched)),
        cell(args.why or ""),
        args.at or time.strftime("%Y-%m-%dT%H:%M:%S"),
        args.head if args.head is not None else git_head(path))
    with io.open(path, "a", encoding="utf-8") as fh:
        fh.write(row + "\n")
    print("%s %s -> %s" % (args.id, from_state or "(new)", state))
    return 0


def do_task_cites(ledger_path, ref):
    """Which tasks claim to satisfy this requirement, and in what state."""
    rows = read_task_rows(task_state_path(ledger_path))
    hits = [r for r in task_latest(rows).values() if ref in r["spec_refs"]]
    if not hits:
        print("no task cites %s" % ref)
        return 0
    for r in sorted(hits, key=lambda r: r["task"]):
        print("%s  %-12s %s" % (r["task"], r["state"],
                                ", ".join(r["touched"]) or "-"))
    return 0


def do_task_invalidate(ledger_path, ref, apply_it, why):
    """What a change to this requirement kills, split by whether it was built.

    Reports rather than guesses: `--invalidate --by FR-14` prints the two lists
    and exits 2 when either is non-empty, so a caller that ignores the exit code
    still cannot claim nothing happened. `--apply` writes the transitions.
    """
    path = task_state_path(ledger_path)
    rows = read_task_rows(path)
    current = task_latest(rows)
    built, unbuilt = [], []
    for r in sorted(current.values(), key=lambda r: r["task"]):
        if ref not in r["spec_refs"]:
            continue
        if r["state"] == TASK_DONE:
            built.append(r)
        elif r["state"] in ("pending", "ready", "running"):
            unbuilt.append(r)
    if not built and not unbuilt:
        print("nothing cites %s" % ref)
        return 0

    for r in built:
        print("invalidated %s  (done against %s; touched %s)"
              % (r["task"], ref, ", ".join(r["touched"]) or "-"))
    for r in unbuilt:
        print("superseded  %s  (%s, never built)" % (r["task"], r["state"]))

    if apply_it:
        class _A(object):
            pass
        for r in built + unbuilt:
            a = _A()
            a.id = r["task"]
            a.set_state = (TASK_INVALIDATED if r["state"] == TASK_DONE
                           else TASK_SUPERSEDED)
            a.spec_refs = ", ".join(r["spec_refs"])
            a.touched = ", ".join(r["touched"])
            a.why = why or ("%s changed" % ref)
            a.at = None
            a.head = None
            do_task_state(ledger_path, a)
    else:
        print("\n(nothing written -- pass --apply to record these transitions)")
    return 2


LOOKUP_LOG = "lookup.jsonl"
BASE_SPAWN_TOKENS = 6619          # measured, tool set A -- see cost-model.md


def lookup_log_path(ledger_path):
    return os.path.join(os.path.dirname(os.path.abspath(ledger_path)), LOOKUP_LOG)


def record_lookup(ledger_path, question, verdict, score, row_id):
    """Append what a lookup did, so the saving stops being an assertion.

    `chain/references/self-loop.md` lists the lookup as one of five places the
    tokens are saved and gives the arithmetic -- 6,619 tokens per spawn against
    one grep -- but nothing counted the hits, so the saving was never a figure.
    A near-miss is recorded too: it is the only evidence for whether the
    threshold is set where it should be.
    """
    try:
        with io.open(lookup_log_path(ledger_path), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                 "question": question, "verdict": verdict,
                                 "score": round(score, 3), "row": row_id},
                                ensure_ascii=False, sort_keys=True) + "\n")
    except (IOError, OSError):
        pass                          # a lookup must not fail because of its log


def sibling_rows(ledger_path):
    """Settled rows from other runs in the same directory, tagged with where
    they came from.

    Two chain runs on related requirements re-derive the same answers, and the
    ledger is per-run, so the second run pays for questions the first already
    settled. But a row from last week may simply be stale -- the code moved, the
    decision changed -- and a wrong HIT is worse than a MISS, because the chain
    cites an answer to a question nobody asked now and stops looking.

    So a sibling row is never a conclusion. It is returned marked `foreign`,
    reported with its age and the commit it was settled against, and it may not
    close anything: the caller dispatches a resolver *with the old answer as a
    starting point*, which is cheaper than a blind search and still a search.
    """
    here = os.path.abspath(ledger_path)
    parent = os.path.dirname(os.path.dirname(here))     # <base>/ -> <rel>/
    out = []
    if not os.path.isdir(parent):
        return out
    for name in sorted(os.listdir(parent)):
        cand = os.path.join(parent, name, os.path.basename(here))
        if not os.path.isfile(cand) or os.path.abspath(cand) == here:
            continue
        try:
            for r in read_rows(cand):
                r["foreign"] = name
                out.append(r)
        except ValueError:
            continue                    # a malformed sibling is not this run's problem
    return out


def do_lookup(rows, question, threshold, ledger_path=None, record=False,
              scope="run"):
    """Best current match, if any. Prints the row so the caller can cite it."""
    pool = list(latest(rows).values())
    foreign = []
    if scope == "dir" and ledger_path:
        foreign = [r for r in latest(sibling_rows(ledger_path)).values()
                   if r["conclusion"] != OPEN]
    best, score = None, 0.0
    for r in pool:
        if r["conclusion"] == OPEN:
            continue                      # still a question; it settles nothing
        s = similarity(question, r["question"])
        if s > score:
            best, score = r, s
    hit = best is not None and score >= threshold

    # A foreign row is reported only when this run has nothing, and it is
    # reported as a lead rather than an answer.
    if not hit and foreign:
        fbest, fscore = None, 0.0
        for r in foreign:
            s = similarity(question, r["question"])
            if s > fscore:
                fbest, fscore = r, s
        if fbest is not None and fscore >= threshold:
            if record and ledger_path:
                record_lookup(ledger_path, question, "FOREIGN", fscore, fbest["id"])
            print("FOREIGN %.2f %s [%s] %s — %s"
                  % (fscore, fbest["id"], fbest["tier"], fbest["conclusion"],
                     fbest["evidence"]))
            print("  from run `%s`, settled %s%s"
                  % (fbest["foreign"], fbest.get("at") or "at an unrecorded time",
                     " at " + fbest["head"] if fbest.get("head") else
                     " against an unrecorded commit"))
            print("  ⛔ NOT a conclusion. Dispatch a resolver with this as its starting")
            print("     point and mint a row in THIS ledger from what it returns.")
            print("     An answer from another run may have gone stale; a wrong HIT is")
            print("     worse than a MISS, because the chain then stops looking.")
            return 2
    if record and ledger_path:
        record_lookup(ledger_path, question, "HIT" if hit else "MISS", score,
                      best["id"] if best else "")
    if not hit:
        print("MISS %.2f — nothing settled covers this" % score)
        return 1
    stamp = ""
    if best.get("head") or best.get("at"):
        stamp = "  (settled %s%s)" % (best.get("at") or "?",
                                      " at " + best["head"] if best.get("head") else "")
    print("HIT %.2f %s [%s] %s — %s%s" % (score, best["id"], best["tier"],
                                          best["conclusion"], best["evidence"], stamp))
    return 0


def do_cache_metric(ledger_path):
    """What the lookup actually saved, as a floor and labelled as one."""
    p = lookup_log_path(ledger_path)
    if not os.path.isfile(p):
        print("NO-LOOKUPS  nothing recorded yet at %s" % p)
        print("  pass --record to --lookup so the saving stops being an assertion")
        return 0
    hits = misses = 0
    near = []
    for line in io.open(p, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("verdict") == "HIT":
            hits += 1
        else:
            misses += 1
            s = d.get("score") or 0.0
            if 0.45 <= s < 0.60:
                near.append((s, d.get("question", "")[:60]))
    total = hits + misses
    print("lookups=%d · hits=%d (%.0f%%) · misses=%d"
          % (total, hits, (100.0 * hits / total) if total else 0.0, misses))
    print("spawns avoided=%d  ⇒  ~%s tokens NOT spent   [derived: %d x %s base]"
          % (hits, format(hits * BASE_SPAWN_TOKENS, ","), hits,
             format(BASE_SPAWN_TOKENS, ",")))
    print("⚠️ base only. A resolver costs more than its base once it reads anything,")
    print("   so this is a FLOOR on what was saved, not the saving.")
    if near:
        print("")
        print("near-misses (0.45-0.60), the evidence for where --threshold belongs:")
        for s, q in sorted(near, reverse=True)[:8]:
            print("  %.2f  %s" % (s, q))
        print("  ⇒ many of these settled by the same row means the threshold is high;")
        print("    ⛔ raising or lowering it on a hunch is how a wrong HIT gets shipped.")
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
    ap.add_argument("--at", default=None,
                    help="when the row was settled (default: now)")
    ap.add_argument("--head", default=None,
                    help="the commit it was settled against (default: git HEAD)")
    ap.add_argument("--record", action="store_true",
                    help="log this lookup to lookup.jsonl, so the saving is countable")
    ap.add_argument("--cache-metric", action="store_true", dest="cache_metric",
                    help="what the lookups saved, as a floor, plus the near-misses")
    ap.add_argument("--task-state", action="store_true", dest="task_state",
                    help="record one task transition (needs --id and --set)")
    ap.add_argument("--set", dest="set_state",
                    help="the state to move to: %s" % ", ".join(TASK_STATES))
    ap.add_argument("--spec-refs", dest="spec_refs",
                    help="comma-separated requirement ids this task satisfies; "
                         "mandatory for --set done")
    ap.add_argument("--touched",
                    help="comma-separated paths this task changed; mandatory "
                         "for --set done")
    ap.add_argument("--why", help="one line: why this transition happened")
    ap.add_argument("--invalidate", action="store_true",
                    help="with --by: what a change to that requirement kills")
    ap.add_argument("--by", help="the requirement id that changed")
    ap.add_argument("--apply", action="store_true",
                    help="with --invalidate: write the transitions, not just "
                         "report them")
    ap.add_argument("--cites", help="which tasks claim to satisfy this "
                                    "requirement, and in what state")
    ap.add_argument("--ledger-scope", choices=("run", "dir"), default="run",
                    dest="ledger_scope",
                    help="`dir` also reads sibling runs' ledgers, as leads only "
                         "(exit 2), never as conclusions")
    args = ap.parse_args()

    if args.init:
        return do_init(args.path)

    # Task state lives in its own file beside the ledger, so a malformed ledger
    # does not block a task transition and the two tables never share a parser.
    try:
        if args.task_state:
            if not (args.id and args.set_state):
                ap.error("--task-state needs --id and --set")
            return do_task_state(args.path, args)
        if args.invalidate:
            if not args.by:
                ap.error("--invalidate needs --by <requirement id>")
            return do_task_invalidate(args.path, args.by, args.apply, args.why)
        if args.cites:
            return do_task_cites(args.path, args.cites)
    except ValueError as exc:
        print("FAIL malformed-task-state: %s" % exc)
        return 2

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
    if args.cache_metric:
        return do_cache_metric(args.path)
    if args.lookup is not None:
        return do_lookup(rows, args.lookup, args.threshold,
                         ledger_path=args.path, record=args.record,
                         scope=args.ledger_scope)
    if args.metric:
        return do_metric(rows, args.min_ratio)
    if args.show_open:
        return do_open(rows)
    ap.error("give one of --init, --next-id, --add, --lookup, --metric, "
             "--open, --task-state, --invalidate, --cites")


if __name__ == "__main__":
    sys.exit(main())
