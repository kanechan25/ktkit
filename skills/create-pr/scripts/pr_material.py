#!/usr/bin/env python3
"""The deterministic half of /ktkit:create-pr: the target branch, and the commits a PR carries.

Two questions have one right answer and must not be re-decided by a model on
every run.

  base     Which branch does the PR target? `--to` when given. Otherwise `dev`
           if the remote has it, else `develop`. Both present is ambiguous
           (exit 3) and neither is a stop (exit 4) -- never a silent fallback
           to the default branch, because a PR aimed at `main` by accident is
           the expensive mistake.

  commits  What does the range <to>..<from> carry? Walked along the first
           parent, so a release PR (`dev` -> `main`) reads as the pull requests
           it bundles rather than as hundreds of loose commits:

             commit      an ordinary commit
             squash-pr   a commit whose subject ends `(#N)` -- a squash-merged PR
             pr-merge    `Merge pull request #N ...`, its commits as children
             merge       any other merge that brought commits in
             sync-merge  a merge that brought nothing new -- the target branch
                         pulled back in. It carries no work and is set aside.

           Plus every issue reference in the subjects and bodies: `#N` and
           issue / pull URLs. A markdown heading, `C#` or a hex colour is not one.

Usage
    pr_material.py base [--to <branch>] --heads <branch> [<branch> ...]
    pr_material.py commits --repo <dir> --to <rev> --from <rev>

Exit status
    0  answered            2  unusable arguments (a revision that does not exist)
    3  base: both `dev` and `develop` exist -- ask
    4  base: neither exists and no --to -- stop

Stdlib only, Python 3.9. Reads commit messages only, never a diff.
"""
import argparse
import json
import re
import subprocess
import sys

PREFERRED = ("dev", "develop")
PR_MERGE_RE = re.compile(r"^Merge pull request #(\d+)\b")
SQUASH_RE = re.compile(r"\(#(\d+)\)\s*$")
HASH_REF_RE = re.compile(r"(?<![\w&#/])#(\d+)(?![\w])")
URL_REF_RE = re.compile(r"https?://[^\s/]+/[^\s/]+/[^\s/]+/(?:issues|pull)/\d+")


class Usage(Exception):
    pass


def pick_base(to, heads):
    if to:
        return 0, to
    present = [b for b in PREFERRED if b in heads]
    if len(present) == 2:
        return 3, "both %s exist on the remote -> ask which one" % " and ".join(PREFERRED)
    if not present:
        return 4, "neither %s exists on the remote -> pass --to" % " nor ".join(PREFERRED)
    return 0, present[0]


def git(repo, *args):
    p = subprocess.run(["git", "-C", repo] + list(args), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise Usage("git %s: %s" % (" ".join(args), p.stderr.decode("utf-8", "replace").strip()))
    return p.stdout.decode("utf-8", "replace")


def verify(repo, rev):
    p = subprocess.run(["git", "-C", repo, "rev-parse", "--verify", "--quiet", rev + "^{commit}"],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise Usage("not a commit: %s" % rev)
    return p.stdout.decode().strip()


def message(repo, sha):
    subject, _, body = git(repo, "show", "-s", "--format=%s%x00%b", sha).partition("\x00")
    return {"sha": sha, "subject": subject.strip(), "body": body.strip()}


def revs(repo, *spec):
    return [l for l in git(repo, "rev-list", *spec).split("\n") if l]


def issue_refs(texts):
    seen = []
    for t in texts:
        for url in URL_REF_RE.findall(t):
            if url not in seen:
                seen.append(url)
        for n in HASH_REF_RE.findall(t):
            ref = "#" + n
            if ref not in seen:
                seen.append(ref)
    return seen


def collect(repo, to, frm):
    to, frm = verify(repo, to), verify(repo, frm)
    entries, texts = [], []
    for sha in revs(repo, "--first-parent", "%s..%s" % (to, frm)):
        e = message(repo, sha)
        texts += [e["subject"], e["body"]]
        parents = git(repo, "rev-list", "--parents", "-n", "1", sha).split()[1:]
        if len(parents) > 1:
            kids = revs(repo, *(parents[1:] + ["^" + parents[0], "^" + to]))
            e["children"] = [message(repo, k) for k in kids]
            for c in e["children"]:
                texts += [c["subject"], c["body"]]
            m = PR_MERGE_RE.match(e["subject"])
            e["kind"] = "sync-merge" if not kids else ("pr-merge" if m else "merge")
            e["pr"] = int(m.group(1)) if m and kids else None
        else:
            m = SQUASH_RE.search(e["subject"])
            e["kind"] = "squash-pr" if m else "commit"
            e["pr"] = int(m.group(1)) if m else None
        entries.append(e)
    count = len(revs(repo, "%s..%s" % (to, frm)))
    size = sum(len(t) for t in texts)
    return {"to": to, "from": frm, "entries": entries, "issue_refs": issue_refs(texts),
            "stats": {"commits": count, "entries": len(entries), "message_bytes": size}}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("base", help="pick the target branch")
    b.add_argument("--to", help="the target branch the user named; wins outright")
    b.add_argument("--heads", nargs="+", default=[], help="branch names the remote has")
    c = sub.add_parser("commits", help="the commits <to>..<from> carries, as JSON")
    c.add_argument("--repo", default=".", help="the repository")
    c.add_argument("--to", required=True, help="the target revision")
    c.add_argument("--from", dest="frm", required=True, help="the source revision")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    if a.cmd == "base":
        rc, text = pick_base(a.to, a.heads)
        print(text, file=sys.stdout if rc == 0 else sys.stderr)
        return rc
    if a.cmd == "commits":
        try:
            print(json.dumps(collect(a.repo, a.to, a.frm), ensure_ascii=False, indent=2))
        except Usage as e:
            print("usage error: %s" % e, file=sys.stderr)
            return 2
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
