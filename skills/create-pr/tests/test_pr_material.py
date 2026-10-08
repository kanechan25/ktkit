#!/usr/bin/env python3
"""The material a PR body is written from, gathered the same way every time.

`pr_material.py` does the two things in /ktkit:create-pr that have one right
answer and must not be re-decided by a model on every run: which branch the PR
targets when --to is not given, and which commits the PR carries -- grouped by
the pull request they arrived in, with the merges that only synced the base
branch back in recognised and set aside. Every fixture commit sits on a detached
HEAD, so not even the tests create a branch.

  B1  --to wins over everything the remote has
  B2  without --to, `dev` is chosen when it exists
  B3  `develop` is chosen when only it exists
  B4  both exist: exit 3, both named -- the skill asks
  B5  neither exists: exit 4 -- the skill stops, it never falls back
  C1  plain commits come back newest first, with full bodies
  C2  a merged PR becomes one entry, its commits as children
  C3  a merge that only brought the target branch back in is a sync merge, childless
  C4  a squash-merged PR is recognised by its `(#N)` suffix
  C5  issue references are collected from bodies -- `#N` and issue/pull URLs --
      but not markdown headings, not `C#`, not a hex colour
  C6  an empty range says so, with count 0
  C7  a revision that does not exist is a usage error

Run:  python3 skills/create-pr/tests/test_pr_material.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "scripts", "pr_material.py")

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
           GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")


def git(repo, *args):
    p = subprocess.run(["git", "-C", repo, "-c", "commit.gpgsign=false"] + list(args),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=True, env=ENV)
    if p.returncode != 0:
        raise RuntimeError("git %s: %s" % (" ".join(args), p.stderr))
    return p.stdout.strip()


def commit(repo, path, text, msg):
    with open(os.path.join(repo, path), "a") as fh:
        fh.write(text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg)
    return git(repo, "rev-parse", "HEAD")


def merge(repo, other, msg):
    git(repo, "merge", "-q", "--no-ff", "-m", msg, other)
    return git(repo, "rev-parse", "HEAD")


def run(*args):
    p = subprocess.run([sys.executable, SCRIPT] + list(args), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, universal_newlines=True)
    return p.returncode, p.stdout, p.stderr


def material(repo, to, frm):
    rc, out, err = run("commits", "--repo", repo, "--to", to, "--from", frm)
    try:
        return rc, json.loads(out), err
    except ValueError:
        return rc, {}, out + err


def new_repo():
    repo = tempfile.mkdtemp()
    git(repo, "init", "-q")
    base = commit(repo, "f.txt", "base\n", "chore: base")
    git(repo, "checkout", "-q", "--detach", base)
    return repo, base


def test_base():
    rc, out, _ = run("base", "--to", "release", "--heads", "dev", "develop", "main")
    check("B1 --to wins", rc == 0 and out.strip() == "release", out)
    rc, out, _ = run("base", "--heads", "main", "dev", "feature/x")
    check("B2 dev when it exists", rc == 0 and out.strip() == "dev", out)
    rc, out, _ = run("base", "--heads", "main", "develop")
    check("B3 develop when only it exists", rc == 0 and out.strip() == "develop", out)
    rc, out, err = run("base", "--heads", "dev", "develop", "main")
    check("B4 both: exit 3", rc == 3, out + err)
    check("B4 and both are named", "dev" in out + err and "develop" in out + err, out + err)
    rc, out, err = run("base", "--heads", "main", "master")
    check("B5 neither: exit 4, no fallback", rc == 4 and "main" not in out, out + err)


def test_plain():
    repo, base = new_repo()
    commit(repo, "f.txt", "a\n", "feat: first\n\nWhy the first change was needed.")
    head = commit(repo, "f.txt", "b\n", "fix: second\n\nMeasured 3 of 7 wrong.")
    rc, m, err = material(repo, base, head)
    entries = m.get("entries", [])
    check("C1 exit 0", rc == 0, err)
    check("C1 two entries, newest first", [e.get("subject") for e in entries]
          == ["fix: second", "feat: first"], entries)
    check("C1 full bodies kept", entries and "Measured 3 of 7 wrong." in entries[0].get("body", ""))
    check("C1 plain commits are kind=commit", all(e.get("kind") == "commit" for e in entries))
    shutil.rmtree(repo)


def test_pr_merge_and_sync():
    repo, base = new_repo()
    # the target branch moves on by itself
    git(repo, "checkout", "-q", "--detach", base)
    target = commit(repo, "g.txt", "t\n", "feat: landed on the target separately")
    # a feature line, merged as PR #12 into an integration line
    git(repo, "checkout", "-q", "--detach", base)
    f1 = commit(repo, "h.txt", "1\n", "feat: part one\n\nBody one.")
    f2 = commit(repo, "h.txt", "2\n", "feat: part two\n\nBody two.")
    git(repo, "checkout", "-q", "--detach", base)
    commit(repo, "i.txt", "x\n", "chore: integration tip")
    m12 = merge(repo, f2, "Merge pull request #12 from someone/feature-x\n\nAdd the x thing")
    # the integration line pulls the target back in: a sync merge
    sync = merge(repo, target, "Merge branch 'main' into dev")
    rc, m, err = material(repo, target, sync)
    entries = m.get("entries", [])
    kinds = {e.get("sha"): e for e in entries}
    pr = [e for e in entries if e.get("kind") == "pr-merge"]
    check("C2 exit 0", rc == 0, err)
    check("C2 the PR merge is one entry with number 12", len(pr) == 1 and pr[0].get("pr") == 12, entries)
    check("C2 its children are the PR's two commits",
          pr and sorted(c.get("subject") for c in pr[0].get("children", []))
          == ["feat: part one", "feat: part two"], pr)
    check("C2 the PR's commits are not also top-level entries",
          f1 not in kinds and f2 not in kinds, list(kinds))
    check("C3 the sync merge is recognised", kinds.get(sync, {}).get("kind") == "sync-merge", kinds.get(sync))
    check("C3 and carries no children", not kinds.get(sync, {}).get("children"), kinds.get(sync))
    check("C2 counts every commit the PR carries", m.get("stats", {}).get("commits") == 5, m.get("stats"))
    shutil.rmtree(repo)


def test_squash():
    repo, base = new_repo()
    head = commit(repo, "f.txt", "s\n", "feat(api): accept partial refunds (#341)\n\nBody.")
    rc, m, _ = material(repo, base, head)
    e = (m.get("entries") or [{}])[0]
    check("C4 squash PR recognised", e.get("kind") == "squash-pr" and e.get("pr") == 341, e)
    shutil.rmtree(repo)


def test_issue_refs():
    repo, base = new_repo()
    body = ("fix: wording\n\n## 1. Heading is not a ref\n\nPart of #88, see also "
            "https://github.com/acme/widgets/issues/91 and https://github.com/acme/widgets/pull/90.\n"
            "Written in C# with colour #ffcc00 and #1a2b3c.\n(#77)")
    head = commit(repo, "f.txt", "r\n", body)
    rc, m, _ = material(repo, base, head)
    refs = m.get("issue_refs", [])
    check("C5 #N and URLs collected", "#88" in refs and "#77" in refs
          and "https://github.com/acme/widgets/issues/91" in refs
          and "https://github.com/acme/widgets/pull/90" in refs, refs)
    check("C5 no heading, C#, or hex colour", not any(r in refs for r in ("#1", "#ffcc00", "#1a2b3c")), refs)
    shutil.rmtree(repo)


def test_empty():
    repo, base = new_repo()
    rc, m, _ = material(repo, base, base)
    check("C6 empty range has count 0", rc == 0 and m.get("stats", {}).get("commits") == 0, m)
    shutil.rmtree(repo)


def test_bad_rev():
    repo, base = new_repo()
    rc, _, _ = run("commits", "--repo", repo, "--to", base, "--from", "nope")
    check("C7 unknown revision exits 2", rc == 2)
    shutil.rmtree(repo)


if __name__ == "__main__":
    for fn in (test_base, test_plain, test_pr_merge_and_sync, test_squash, test_issue_refs,
               test_empty, test_bad_rev):
        fn()
    print()
    if failures:
        print("%d failure(s)" % len(failures))
        sys.exit(1)
    print("all checks passed")
