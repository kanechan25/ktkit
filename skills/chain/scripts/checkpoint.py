#!/usr/bin/env python3
"""One checkpoint file per chain run, written as the work happens.

A run used to stop on a forecast: phase D was refused because the window left
was smaller than what phases A-C had cost, while 44% of the session was still
unspent. The fear behind that rule was real -- a run cut off mid-task leaves a
repository half-changed -- but the answer to it is a record precise enough to
resume from, not a refusal to start.

So every milestone is written the moment it is reached: which agent, which task,
which sub-step, what comes next, which files it touched. Six workers with five
sub-steps each still write to **one** file, one section per agent, one line per
milestone, every line stamped to the minute. If the window runs out before the
wind-down finishes, the last milestone is already on disk and at most the
sub-step in flight is lost.

The same file carries the run's status, so a worker needs nothing else to know
whether it should keep going:

    running     carry on
    wind-down   finish the sub-step in hand, mark it, return -- start nothing new
    paused      the run stopped at a recorded milestone; `--resume` continues it
    complete    the run finished; the watcher exits

Layout of `<chain-dir>/checkpoint.md`:

    # Checkpoint -- <run>
    Created: 2026-11-11 10:42 · Updated: 2026-11-11 14:05
    Status: running

    ## Run
    - 2026-11-11 14:05 | wind-down | session at 96.0% (resets 2026-11-11 15:19)

    ## worker-T03
    - 2026-11-11 14:01 | T03 | 2/5 write the failing test | done | next: implement | files: a.py

Usage
    checkpoint.py mark   --base <chain-dir> --agent <name> --task <id> --step <text>
                         --state <started|done|stopped> [--next <text>] [--files <a,b>]
    checkpoint.py status --base <chain-dir>
    checkpoint.py trip   --base <chain-dir> --reason <text>
    checkpoint.py pause  --base <chain-dir> --reason <text>
    checkpoint.py resume --base <chain-dir>
    checkpoint.py finish --base <chain-dir>
    checkpoint.py latest --base <chain-dir>

Exit status
    0  ok, and for `status`: running
    2  unusable arguments
    3  `status` only: wind-down -- finish the sub-step in hand and return
    4  `status` only: paused or complete -- start nothing

Writes are serialised with an exclusive lock on the run directory itself, so
concurrent workers never interleave a line and no lock file is left behind.

Stdlib only, Python 3.9.
"""
import argparse
import fcntl
import io
import os
import re
import sys
import time
from contextlib import contextmanager

FILE = "checkpoint.md"
STATES = ("running", "wind-down", "paused", "complete")
MARKS = ("started", "done", "stopped")
RUN_SECTION = "Run"
STATUS_EXIT = {"running": 0, "wind-down": 3, "paused": 4, "complete": 4}


def stamp(t=None):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(t))


def clean(text):
    """A field may not break the line format it lives in."""
    return re.sub(r"\s+", " ", (text or "").replace("|", "/")).strip()


@contextmanager
def locked(base):
    fd = os.open(base, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def path(base):
    return os.path.join(base, FILE)


def load(base):
    """(header dict, [(section, [lines])]) -- an absent file is an empty run."""
    p = path(base)
    head = {"title": os.path.basename(os.path.normpath(base)), "created": None,
            "status": "running"}
    sections = []
    if not os.path.isfile(p):
        return head, sections
    cur = None
    for raw in io.open(p, encoding="utf-8"):
        line = raw.rstrip("\n")
        if line.startswith("# Checkpoint -- "):
            head["title"] = line[len("# Checkpoint -- "):]
        elif line.startswith("Created: "):
            head["created"] = line[len("Created: "):].split(" · ")[0]
        elif line.startswith("Status: "):
            head["status"] = line[len("Status: "):].strip()
        elif line.startswith("## "):
            cur = (line[3:].strip(), [])
            sections.append(cur)
        elif line.startswith("- ") and cur is not None:
            cur[1].append(line)
    return head, sections


def save(base, head, sections):
    now = stamp()
    out = ["# Checkpoint -- %s" % head["title"],
           "Created: %s · Updated: %s" % (head["created"] or now, now),
           "Status: %s" % head["status"], ""]
    for name, lines in sections:
        out.append("## %s" % name)
        out.extend(lines)
        out.append("")
    tmp = path(base) + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    os.replace(tmp, path(base))


def append(sections, name, line):
    for sec, lines in sections:
        if sec == name:
            lines.append(line)
            return
    if name == RUN_SECTION:
        sections.insert(0, (name, [line]))
    else:
        sections.append((name, [line]))


def run_event(base, status, event, reason=""):
    with locked(base):
        head, sections = load(base)
        if status:
            head["status"] = status
        append(sections, RUN_SECTION, "- %s | %s%s"
               % (stamp(), event, (" | " + clean(reason)) if reason else ""))
        save(base, head, sections)


def parse_row(line):
    """A milestone line back into fields, for `latest` and for resume."""
    parts = [p.strip() for p in line[2:].split(" | ")]
    if len(parts) < 4:
        return None
    row = {"at": parts[0], "task": parts[1], "step": parts[2], "state": parts[3],
           "next": "", "files": ""}
    for p in parts[4:]:
        if p.startswith("next: "):
            row["next"] = p[len("next: "):]
        elif p.startswith("files: "):
            row["files"] = p[len("files: "):]
    return row


def main(argv=None):
    doc = __doc__ or ""
    ap = argparse.ArgumentParser(
        prog="checkpoint.py", description="One checkpoint file per chain run.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=doc[doc.index("Usage"):doc.index("Writes are serialised")])
    sub = ap.add_subparsers(dest="cmd")
    m = sub.add_parser("mark")
    m.add_argument("--agent", required=True)
    m.add_argument("--task", required=True)
    m.add_argument("--step", required=True, help='e.g. "2/5 write the failing test"')
    m.add_argument("--state", required=True, choices=MARKS)
    m.add_argument("--next", default="")
    m.add_argument("--files", default="")
    for name in ("status", "resume", "finish", "latest"):
        sub.add_parser(name)
    for name in ("trip", "pause"):
        sub.add_parser(name).add_argument("--reason", required=True)
    for p in sub.choices.values():
        p.add_argument("--base", required=True, help="the chain run directory")
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_usage()
        return 2
    if not os.path.isdir(a.base):
        print("BAD-BASE  %s is not a directory" % a.base)
        return 2

    if a.cmd == "mark":
        line = "- %s | %s | %s | %s" % (stamp(), clean(a.task), clean(a.step), a.state)
        if a.next:
            line += " | next: %s" % clean(a.next)
        if a.files:
            line += " | files: %s" % ", ".join(clean(f) for f in a.files.split(",") if f.strip())
        with locked(a.base):
            head, sections = load(a.base)
            append(sections, clean(a.agent), line)
            save(a.base, head, sections)
        print(line[2:])
        return 0

    if a.cmd == "status":
        head, _ = load(a.base)
        st = head["status"] if head["status"] in STATES else "running"
        print(st)
        return STATUS_EXIT[st]

    if a.cmd == "trip":
        head, _ = load(a.base)
        if head["status"] in ("wind-down", "paused", "complete"):
            print("already %s" % head["status"])
            return 0
        run_event(a.base, "wind-down", "wind-down", a.reason)
        print("wind-down  %s" % a.reason)
        return 0

    if a.cmd == "pause":
        run_event(a.base, "paused", "paused", a.reason)
        print("paused  %s" % a.reason)
        return 0

    if a.cmd == "resume":
        run_event(a.base, "running", "resumed")
        print("running")
        return 0

    if a.cmd == "finish":
        run_event(a.base, "complete", "complete")
        print("complete")
        return 0

    # latest: the last milestone of every task, which is where a resume starts
    head, sections = load(a.base)
    print("Status: %s" % head["status"])
    last = {}
    for name, lines in sections:
        if name == RUN_SECTION:
            continue
        for line in lines:
            row = parse_row(line)
            if row:
                last[(name, row["task"])] = row
    if not last:
        print("(no milestone recorded)")
    for (agent, task), r in sorted(last.items(), key=lambda kv: kv[1]["at"]):
        print("%s | %s | %s | %s | %s%s%s"
              % (r["at"], agent, task, r["step"], r["state"],
                 (" | next: " + r["next"]) if r["next"] else "",
                 (" | files: " + r["files"]) if r["files"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
