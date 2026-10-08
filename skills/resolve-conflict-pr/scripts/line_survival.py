#!/usr/bin/env python3
"""Did the merge keep every line each side added? Measure it instead of believing it.

"Do not lose code" is the one promise a conflict resolution makes that a careful
model cannot keep by being careful: a hunk taken from the wrong side reads as
plausible, compiles more often than not, and drops the other side's work without
a trace. So the promise is measured. For each side of the merge, every line it
added since the merge base must still be present in the result -- or be reported,
so the caller has to say why it went.

  ours    = the PR's head (the feature)        theirs = the PR's base (dev)
  base    = their merge base                   result = the working tree, or --result <rev>

What counts
  * Every file either side changed is audited, not only the conflicted ones:
    `git checkout --theirs -- dir/` loses work in files git merged cleanly.
  * A line is compared stripped. A line with no letter or digit (`}`, `);`) is
    not counted -- it is present in every file and absent from no real loss.
  * Counts are a lower bound: a line one side added twice must appear at least
    twice. Two sides adding the same line are satisfied by one copy.
  * A file the other side renamed is followed to its new path.
  * Binary files are skipped and listed, never decoded.
  * A conflict marker fails the audit. `=======` alone is not one -- it is a
    markdown underline -- it counts only in a file that also has `<<<<<<<`.

Usage
    line_survival.py --repo <dir> --base <rev> --ours <rev> --theirs <rev>
                     [--result <rev>] [--json]

Exit status
    0  nothing lost, no marker
    1  at least one LOST line or MARK
    2  the arguments are unusable (not a repository, a revision that does not exist)

Stdlib only, Python 3.9.
"""
import argparse
import collections
import json
import os
import re
import subprocess
import sys

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
MARK_OPEN = re.compile(r"^<<<<<<<( |$)")
MARK_ANY = re.compile(r"^(<<<<<<<|\|\|\|\|\|\|\||>>>>>>>)( |$)|^=======$")


class Usage(Exception):
    pass


def git(repo, *args, check=True):
    p = subprocess.run(["git", "-C", repo] + list(args), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise Usage("git %s: %s" % (" ".join(args), p.stderr.decode("utf-8", "replace").strip()))
    return p


def commit_of(repo, rev):
    p = git(repo, "rev-parse", "--verify", "--quiet", rev + "^{commit}", check=False)
    if p.returncode != 0:
        raise Usage("not a commit: %s" % rev)
    return p.stdout.decode().strip()


def significant(line):
    return any(ch.isalnum() for ch in line)


def side_changes(repo, base, side):
    """Lines one side added, per path in that side's tree, plus its renames.

    Returns (added, renames, binary): added = {path: [(lineno, text)]},
    renames = {old_path: new_path}, binary = set of paths.
    """
    out = git(repo, "diff", "-U0", "-M", "--no-color", "--no-ext-diff", base, side).stdout
    added = collections.defaultdict(list)
    renames, binary = {}, set()
    path, old, lineno = None, None, 0
    for raw in out.decode("utf-8", "replace").split("\n"):
        if raw.startswith("diff --git "):
            path, old = None, None
        elif raw.startswith("rename from "):
            old = raw[len("rename from "):]
        elif raw.startswith("rename to "):
            renames[old] = raw[len("rename to "):]
        elif raw.startswith("--- "):
            continue
        elif raw.startswith("+++ "):
            target = raw[4:]
            path = None if target == "/dev/null" else target[2:]
        elif raw.startswith("Binary files "):
            m = re.search(r" and b/(.+) differ$", raw)
            if m:
                binary.add(m.group(1))
        elif raw.startswith("@@"):
            m = HUNK_RE.match(raw)
            lineno = int(m.group(1)) if m else 0
        elif raw.startswith("+") and path is not None:
            added[path].append((lineno, raw[1:]))
            lineno += 1
    return added, renames, binary


class Result(object):
    """The merged tree: the working tree by default, or a committed revision."""

    def __init__(self, repo, rev):
        self.repo, self.rev = repo, rev

    def read(self, path):
        if self.rev is None:
            full = os.path.join(self.repo, path)
            if not os.path.isfile(full):
                return None
            with open(full, "rb") as fh:
                return fh.read()
        p = git(self.repo, "show", "%s:%s" % (self.rev, path), check=False)
        return p.stdout if p.returncode == 0 else None


def audit(repo, base, ours, theirs, result_rev):
    base, ours, theirs = (commit_of(repo, r) for r in (base, ours, theirs))
    if result_rev is not None:
        result_rev = commit_of(repo, result_rev)
    result = Result(repo, result_rev)
    sides = {"ours": side_changes(repo, base, ours), "theirs": side_changes(repo, base, theirs)}
    other = {"ours": "theirs", "theirs": "ours"}

    lost, marks, skipped, seen = [], [], set(), {}
    for name, (added, renames, binary) in sides.items():
        inverse = {new: old for old, new in renames.items()}
        other_renames = sides[other[name]][1]
        skipped.update(binary)
        for path, lines in sorted(added.items()):
            origin = inverse.get(path, path)
            candidates = [path, other_renames.get(origin, origin)]
            found, data = None, None
            for cand in candidates:
                data = result.read(cand)
                if data is not None:
                    found = cand
                    break
            if data is not None and b"\x00" in data:
                skipped.add(found)
                continue
            text = data.decode("utf-8", "replace") if data is not None else ""
            if found is not None:
                seen[found] = text
            have = collections.Counter(l.strip() for l in text.split("\n"))
            need = collections.Counter()
            for _n, l in lines:
                if significant(l):
                    need[l.strip()] += 1
            short = {l: need[l] - have[l] for l in need if have[l] < need[l]}
            for lineno, l in lines:
                key = l.strip()
                if short.get(key, 0) > 0:
                    short[key] -= 1
                    lost.append({"side": name, "path": path, "line": lineno, "text": key,
                                 "result_path": found})

    for path, text in sorted(seen.items()):
        rows = text.split("\n")
        if not any(MARK_OPEN.match(r) for r in rows):
            continue
        for i, r in enumerate(rows, 1):
            if MARK_ANY.match(r):
                marks.append({"path": path, "line": i, "text": r})

    return {"ok": not lost and not marks, "lost": lost, "marks": marks,
            "skipped": sorted(skipped), "audited": len(seen)}


def render(report):
    out = []
    for r in report["lost"]:
        where = r["path"] if r["result_path"] else r["path"] + " (absent from the result)"
        out.append("LOST  %-6s  %s:%d  + %s" % (r["side"], where, r["line"], r["text"]))
    for m in report["marks"]:
        out.append("MARK  %s:%d  %s" % (m["path"], m["line"], m["text"]))
    for s in report["skipped"]:
        out.append("SKIP  binary  %s" % s)
    by_side = collections.Counter(r["side"] for r in report["lost"])
    out.append("---")
    out.append("files audited: %d · lost: ours %d, theirs %d · markers: %d · %s"
               % (report["audited"], by_side["ours"], by_side["theirs"], len(report["marks"]),
                  "OK" if report["ok"] else "NOT OK"))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=".", help="the repository (or worktree) holding the merge")
    ap.add_argument("--base", required=True, help="the merge base of ours and theirs")
    ap.add_argument("--ours", required=True, help="the PR's head revision")
    ap.add_argument("--theirs", required=True, help="the PR's base-branch revision")
    ap.add_argument("--result", help="audit this commit instead of the working tree")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        report = audit(a.repo, a.base, a.ours, a.theirs, a.result)
    except Usage as e:
        print("usage error: %s" % e, file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2) if a.json else render(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
