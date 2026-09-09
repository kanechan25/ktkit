#!/usr/bin/env python3
"""Record what the implementation did differently, the moment it does it.

A specification that disagrees with the code is worse than no specification: it
reads as authoritative and is quietly wrong. Three months later somebody opens
`spec.md`, believes it, and builds on a shape that was never shipped.

`chain` had a sync-back step and it could not close this. Step 06 syncs "every
conflict found in 04 or 05", but 05 hands the work to an execute skill, nothing
extracted that skill's deviations, and the `.implt.md` template had no place to
put them -- `Acceptance Criteria`, `Blast Radius`, `What Was Built`,
`Files Changed`, and no row anywhere saying *the spec said X, I did Y, because Z*.

Two designs were considered and both were half right.

  A  write the spec at the moment of deviation.
     The reason is captured while it is still in context, which is the half that
     matters -- but the spec stops being a stable reference during the very phase
     that reads it, a contract-level change lands before anyone approves it, and
     an aborted run leaves a specification describing code that was rolled back.
     That last one is worse than the original problem.

  B  record in `.implt.md`, sync afterwards.
     The spec stays stable and an abort is safe -- but nothing says when the
     reason is captured, so it gets written at the end of the phase, by which
     point the reason has left context and cannot be recovered. And a table
     hand-written into `.implt.md` and then hand-synced into `spec.md` is two
     independent authorings, which can disagree.

So: **capture at the moment, write at the boundary, render once into both.**

    deviation.py add    --base <dir> --source <where> --said <what> --did <what>
                        --why <reason> --evidence <path:line> [--contract]
    deviation.py lint   --base <dir> [--repo <root>]     0 = ok, 1 = a row is unsafe
    deviation.py render --base <dir> [--markdown]        one source, both files

⭐ `render` produces the block that goes into `spec.md` **and** the table that goes
into `.implt.md`. Neither is authored separately, so they cannot drift, and
reading `spec.md` alone is enough.

⛔ **This decides nothing.** Whether something counts as a deviation is the
agent's judgement; whether a change is contract-level is the agent's judgement;
what it means is the agent's judgement. This collects rows and refuses unsafe
ones -- the same boundary `probe_index.py` keeps between a count and a verdict.

Stdlib only, Python 3.9.
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys
import time

LEDGER = "deviations.jsonl"
ANCHOR_RE = re.compile(r"^(?P<path>[^\s:]+):(?P<line>\d+)$")
NO_REASON = {"", "-", "n/a", "na", "none", "tbd", "?", "unknown"}
BLOCK_TITLE = "Sai khác phát hiện lúc thi hành"


def ledger_path(base):
    return os.path.join(base, LEDGER)


def rows(base):
    p = ledger_path(base)
    if not os.path.isfile(p):
        return []
    out = []
    for line in io.open(p, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            out.append({"kind": "unparseable", "raw": line[:200]})
    return out


def append(base, row):
    if not os.path.isdir(base):
        os.makedirs(base)
    with io.open(ledger_path(base), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def head(repo):
    try:
        out = subprocess.check_output(
            ["git", "-C", repo or ".", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL, timeout=15)
        return out.decode("utf-8").strip()
    except Exception:                                          # noqa: BLE001
        return ""


def read_line(repo, path, n):
    """The nth line of a file, or None. 1-indexed, as a citation is."""
    full = path if os.path.isabs(path) else os.path.join(repo or ".", path)
    try:
        with io.open(full, encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh, 1):
                if i == n:
                    return line.rstrip("\n")
    except (IOError, OSError):
        return None
    return None


def find_line(repo, path, text):
    """Where `text` sits now, or None. Used when an anchor has drifted."""
    if not text:
        return None
    full = path if os.path.isabs(path) else os.path.join(repo or ".", path)
    want = text.strip()
    try:
        with io.open(full, encoding="utf-8", errors="replace") as fh:
            hits = [i for i, l in enumerate(fh, 1) if l.strip() == want]
    except (IOError, OSError):
        return None
    return hits[0] if len(hits) == 1 else None      # ambiguous is not resolved


def check_row(r, repo):
    """(status, note). status in ok | drifted | unsafe."""
    if r.get("kind") == "unparseable":
        return "unsafe", "the row is not valid JSON"
    for field in ("source", "said", "did", "evidence"):
        if not (r.get(field) or "").strip():
            return "unsafe", "%s is empty" % field
    if (r.get("why") or "").strip().lower() in NO_REASON:
        # The reason is the part that cannot be recovered later: a diff shows
        # that the code differs, never why somebody chose that.
        return "unsafe", "why is empty -- the one part nobody can reconstruct later"
    m = ANCHOR_RE.match((r.get("evidence") or "").strip())
    if not m:
        return "unsafe", "evidence %r is not a path:line" % r.get("evidence")
    path, n = m.group("path"), int(m.group("line"))
    now = read_line(repo, path, n)
    if now is None:
        moved = find_line(repo, path, r.get("line_text") or "")
        if moved:
            return "drifted", "line moved %d -> %d" % (n, moved)
        return "unsafe", "%s has no line %d any more" % (path, n)
    recorded = (r.get("line_text") or "").strip()
    if recorded and now.strip() != recorded:
        moved = find_line(repo, path, recorded)
        if moved:
            return "drifted", "line moved %d -> %d" % (n, moved)
        return "unsafe", ("%s:%d no longer holds the line that was recorded, and it "
                          "is not elsewhere in the file" % (path, n))
    return "ok", ""


def do_add(a):
    r = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": "deviation",
         "source": a.source, "said": a.said, "did": a.did, "why": a.why,
         "evidence": a.evidence, "contract": bool(a.contract),
         "head": a.head if a.head is not None else head(a.repo)}
    m = ANCHOR_RE.match((a.evidence or "").strip())
    if m:
        # The line's own text, so a drifted anchor can be re-resolved at the
        # boundary instead of being trusted or thrown away.
        r["line_text"] = read_line(a.repo, m.group("path"), int(m.group("line"))) or ""
    append(a.base, r)
    n = len([x for x in rows(a.base) if x.get("kind") == "deviation"])
    print("DEVIATION #%d recorded%s" % (n, "  ⚠️ contract-level" if a.contract else ""))
    if a.contract:
        print("  ⛔ a contract-level change is a gate at step 06, not a sync:")
        print("     somebody is integrating against what the spec promises.")
    if not r.get("line_text"):
        print("  ⚠️ the cited line could not be read; lint will refuse this row")
    return 0


def do_lint(a):
    rs = [r for r in rows(a.base) if r.get("kind") != "correction"]
    devs = [r for r in rs if r.get("kind") in ("deviation", "unparseable")]
    if not devs:
        declared = [r for r in rs if r.get("kind") == "none"]
        if declared:
            print("DECLARED-NONE  the code was stated to match the spec at %s"
                  % declared[-1].get("at", "?"))
            return 0
        # Silence and "nothing diverged" are different facts, and only one of
        # them is a finding. Saying so is the whole point of --none existing.
        print("NOT-ANSWERED  nothing recorded at %s" % ledger_path(a.base))
        print("  ⛔ An empty record is not the same as 'nothing diverged'. If the code")
        print("     matches the spec, say so with:  --none")
        return 0
    bad, drift = [], []
    for i, r in enumerate(devs, 1):
        st, note = check_row(r, a.repo)
        if st == "unsafe":
            bad.append((i, r, note))
        elif st == "drifted":
            drift.append((i, r, note))
    print("LINT  %d deviation(s) · %d drifted · %d unsafe"
          % (len(devs), len(drift), len(bad)))
    for i, r, note in drift:
        print("  ~ #%d %s — %s (re-resolved at render)"
              % (i, r.get("evidence"), note))
    for i, r, note in bad:
        print("  ⛔ #%d %s — %s" % (i, r.get("evidence"), note))
    if bad:
        print("")
        print("  ⛔ STOP. A deviation anchored to a line that is not there reads as")
        print("     verified and is not. Fix or withdraw the row; do not sync.")
        return 1
    contracts = [r for r in devs if r.get("contract")]
    if contracts:
        print("")
        print("  ⚠️ %d contract-level change(s): these are a gate, not a sync."
              % len(contracts))
        for r in contracts:
            print("     · %s — %s" % (r.get("source"), r.get("said")))
    return 0


def do_none(a):
    append(a.base, {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": "none",
                    "head": a.head if a.head is not None else head(a.repo)})
    print("NO-DEVIATION recorded — the code matches the spec")
    return 0


def do_render(a):
    rs = rows(a.base)
    devs = [r for r in rs if r.get("kind") == "deviation"]
    declared_none = [r for r in rs if r.get("kind") == "none"]
    out = ["## %s — %s" % (BLOCK_TITLE, time.strftime("%Y-%m-%d")), ""]

    if not devs:
        if declared_none:
            out += ["**KHÔNG CÓ** — the implementation matches this specification.",
                    "",
                    "Recorded, not inferred: `deviation.py --none` was called at %s%s."
                    % (declared_none[-1].get("at", "?"),
                       " (" + declared_none[-1]["head"] + ")"
                       if declared_none[-1].get("head") else ""), ""]
        else:
            out += ["⛔ **Nothing was recorded, and that is not the same as nothing",
                    "having diverged.** No row was written and no `--none` was",
                    "declared, so this block states only that the question was never",
                    "answered.", ""]
        text = "\n".join(out)
        print(text if a.markdown else text)
        return 0

    out += ["Every row was recorded **at the moment it happened**, while the reason was",
            "still known. Anchors are re-checked against the tree before this block is",
            "written; a row whose anchor could not be found stops the sync rather than",
            "being softened.", "",
            "| # | Nguồn | Spec nói | Thực tế | Vì sao | Bằng chứng | |",
            "| -: | ----- | -------- | ------- | ------ | ---------- | - |"]
    for i, r in enumerate(devs, 1):
        ev = r.get("evidence", "")
        st, note = check_row(r, a.repo)
        if st == "drifted":
            m = re.search(r"-> (\d+)", note)
            if m:
                ev = "%s:%s" % (ev.rsplit(":", 1)[0], m.group(1))
        flag = "⚠️ contract" if r.get("contract") else ""
        if st == "drifted":
            flag = (flag + " · line moved").strip(" ·")
        cel = lambda s: (s or "").replace("|", "\\|")
        out.append("| %d | %s | %s | %s | %s | `%s` | %s |"
                   % (i, cel(r.get("source")), cel(r.get("said")), cel(r.get("did")),
                      cel(r.get("why")), ev, flag))
    contracts = [r for r in devs if r.get("contract")]
    if contracts:
        out += ["", "⚠️ **%d row(s) marked contract-level.** Those change what this "
                "specification promises to somebody else — an acceptance criterion, an "
                "API shape, a dropped requirement — and were confirmed at the step 06 "
                "gate rather than synced silently." % len(contracts)]
    out.append("")
    text = "\n".join(out)
    print(text)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="deviation.py",
        description="Collect what the implementation did differently, and refuse "
                    "rows that cannot be checked.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""subcommands and their flags
  add     --base --repo --source --said --did --why --evidence [--contract] [--head]
  none    --base --repo [--head]          declare that nothing diverged
  lint    --base --repo                   0 = ok, 1 = a row cannot be checked
  render  --base --repo [--markdown]      one source, both destinations

`--why` is mandatory: a diff shows that the code differs, never why somebody
chose that, and nobody can reconstruct it afterwards.""")
    sub = ap.add_subparsers(dest="cmd")

    a = sub.add_parser("add", help="record one deviation, at the moment it happens")
    a.add_argument("--base", required=True, help="the chain run directory")
    a.add_argument("--source", required=True, help="what it diverges from, e.g. 'spec §4.2'")
    a.add_argument("--said", required=True, help="what the spec said, quoted")
    a.add_argument("--did", required=True, help="what was actually built")
    a.add_argument("--why", required=True,
                   help="why -- the one part nobody can reconstruct later")
    a.add_argument("--evidence", required=True, help="path:line in the code")
    a.add_argument("--contract", action="store_true",
                   help="this changes what the spec promises: a gate, not a sync")
    a.add_argument("--repo", default=".", help="repository root for the anchor")
    a.add_argument("--head", default=None)

    n = sub.add_parser("none", help="declare that nothing diverged")
    n.add_argument("--base", required=True)
    n.add_argument("--repo", default=".")
    n.add_argument("--head", default=None)

    l = sub.add_parser("lint", help="refuse rows that cannot be checked")
    l.add_argument("--base", required=True)
    l.add_argument("--repo", default=".")

    r = sub.add_parser("render", help="one source, both destinations")
    r.add_argument("--base", required=True)
    r.add_argument("--repo", default=".")
    r.add_argument("--markdown", action="store_true",
                   help="accepted for symmetry; the output is markdown either way")

    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_help()
        return 1
    return {"add": do_add, "none": do_none, "lint": do_lint,
            "render": do_render}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
