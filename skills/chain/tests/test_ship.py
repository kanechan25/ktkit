#!/usr/bin/env python3
"""`--full` carries a run past implementation: a commit per task, then a PR.

Both new steps write to places other people read. A commit body is the main
source `/ktkit:create-pr` writes the PR from, and it never opens the diff, so a
commit that says less than the run knew is a PR that says less too. `ship.py`
does the parts with one right answer: whether the run may start, what each
commit message is built from, which paths it stages, whether a task is already
committed, and the context file handed to create-pr. Every fixture commit sits
on a detached HEAD or the branch `git init` made, so not even the tests create
a branch.

  G1  on a feature branch with a clean tree: exit 0, target and source named
  G2  standing on the target branch: exit 5 -- the run would PR into itself
  G3  standing on the default branch: exit 5, even when it is not the target
  G4  a dirty tree is exit 6; chain's own artifacts under .claude/claude/ are not dirt
  G5  both dev and develop and no --to: exit 3; neither: exit 4
  G6  --to a branch the remote does not have: exit 4
  G7  a detached HEAD: exit 6
  M1  compose builds subject, Why, What, Verified, issue and trailers, and lints clean
  M2  touched paths come from task-state when --touched is not given
  M3  a deviation anchored in a touched file is quoted; one elsewhere is not
  M4  no deviation recorded for the task's files says so, it is not left out
  M5  lint refuses a long subject, a missing section, a missing trailer, Vietnamese
  M6  lint accepts a Japanese domain term
  S1  staged exactly the touched paths: exit 0
  S2  a staged path the task never touched: exit 1, named
  S3  anything staged under .claude/claude/: exit 1
  D1  done finds the commit carrying this run's and this task's trailers
  D2  another run's commit for the same task id is not this one
  X1  context lists done tasks, user decisions, open rows, T3.5 assumptions, deviations
  X2  context says when nothing was recorded rather than dropping the section

Run:  python3 skills/chain/tests/test_ship.py
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "scripts", "ship.py")

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


def run(*args):
    p = subprocess.run([sys.executable, SCRIPT] + list(args), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, universal_newlines=True)
    return p.returncode, p.stdout, p.stderr


def write(path, text):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def new_repo(branch="feature/x"):
    """A repository whose initial branch is named by `git init` itself."""
    repo = tempfile.mkdtemp()
    git(repo, "init", "-q", "--initial-branch=%s" % branch)
    write(os.path.join(repo, "a.txt"), "a\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "chore: base")
    return repo


def gate(repo, *extra):
    return run("gate", "--repo", repo, "--default", "main", *extra)


def test_gate():
    repo = new_repo("feature/x")
    rc, out, err = gate(repo, "--heads", "main", "dev", "feature/x")
    check("G1 feature branch, clean: exit 0", rc == 0, out + err)
    check("G1 names target and source", "target dev" in out and "source feature/x" in out, out)

    rc, out, err = gate(repo, "--heads", "main", "dev", "feature/x", "--to", "feature/x")
    check("G2 on the target branch: exit 5", rc == 5, out + err)
    shutil.rmtree(repo)

    repo = new_repo("main")
    rc, out, err = gate(repo, "--heads", "main", "dev")
    check("G3 on the default branch: exit 5", rc == 5, out + err)
    shutil.rmtree(repo)

    repo = new_repo("feature/x")
    write(os.path.join(repo, ".claude", "claude", "chain", "x", "manifest.md"), "m\n")
    rc, out, err = gate(repo, "--heads", "dev")
    check("G4 chain artifacts are not dirt", rc == 0, out + err)
    write(os.path.join(repo, "a.txt"), "changed\n")
    rc, out, err = gate(repo, "--heads", "dev")
    check("G4 a modified file is exit 6, named", rc == 6 and "a.txt" in out + err, out + err)
    git(repo, "checkout", "-q", "--", "a.txt")

    rc, out, err = gate(repo, "--heads", "main", "dev", "develop")
    check("G5 both dev and develop: exit 3", rc == 3, out + err)
    rc, out, err = gate(repo, "--heads", "main", "feature/x")
    check("G5 neither: exit 4", rc == 4, out + err)
    rc, out, err = gate(repo, "--heads", "main", "dev", "--to", "release")
    check("G6 --to the remote lacks: exit 4", rc == 4, out + err)

    git(repo, "checkout", "-q", "--detach", "HEAD")
    rc, out, err = gate(repo, "--heads", "dev")
    check("G7 detached HEAD: exit 6", rc == 6, out + err)
    shutil.rmtree(repo)


def chain_dir():
    base = tempfile.mkdtemp()
    write(os.path.join(base, "task-state.md"),
          "# Task state\n\n"
          "| Task | State | Spec refs | Touched | Why | At | Head |\n"
          "| ---- | ----- | --------- | ------- | --- | -- | ---- |\n"
          "| T03 | running | — | — | started | 2026-10-09T10:00:00 | abc1234 |\n"
          "| T03 | done | FR-002 | src/export.py, tests/test_export.py | gate pass | 2026-10-09T10:30:00 | abc1234 |\n"
          "| T04 | ready | — | — | next | 2026-10-09T10:31:00 | abc1234 |\n")
    rows = [
        {"kind": "deviation", "source": "spec §4.2", "said": "POST /exports returns 202",
         "did": "returns 201", "why": "202 needs a job queue the spec does not describe",
         "evidence": "src/export.py:88", "contract": True, "at": "2026-10-09T10:20:00"},
        {"kind": "deviation", "source": "spec §5", "said": "log to stderr",
         "did": "log to a file", "why": "the host closes stderr",
         "evidence": "src/other.py:3", "contract": False, "at": "2026-10-09T10:21:00"},
    ]
    write(os.path.join(base, "deviations.jsonl"), "".join(json.dumps(r) + "\n" for r in rows))
    write(os.path.join(base, "resolved.md"),
          "# Resolved unknowns\n\n"
          "| ID | Question | Tier | Conclusion | Evidence | Falsifier | Phase | At | Head |\n"
          "| -- | -------- | ---- | ---------- | -------- | --------- | ----- | -- | ---- |\n"
          "| Q01 | soft or hard delete for archived exports | T4 | OPEN | — | — | A | t | h |\n"
          "| Q01 | soft or hard delete for archived exports | T4 | soft delete, kept 30 days | user answered at the gate | — | B | t | h |\n"
          "| Q02 | which encoding the CSV uses | T3.5 | UTF-8 with BOM | docs/csv.md:4 | a consumer that rejects a BOM | A | t | h |\n"
          "| Q03 | who approves a bulk export | T4 | OPEN | — | — | B | t | h |\n"
          "| Q04 | where the export module lives | T1 | src/export.py | src/export.py:1 | — | A | t | h |\n")
    write(os.path.join(base, "manifest.md"),
          "| Step | File | Status | Consumed by |\n| ---- | ---- | ------ | ----------- |\n"
          "| 05 | steps/05-implement.md | complete | 06 |\n"
          "| 07 | steps/07-converge.md | complete: round 1 clean | — |\n")
    return base


def compose(base, *extra):
    return run("compose", "--base", base, "--run", "exports/csv-export", "--task", "T03",
               "--type", "feat", "--scope", "export",
               "--subject", "stream CSV exports instead of buffering them",
               "--why", "Exports over 50k rows ran the worker out of memory (FR-002).",
               "--what", "Rows are written to the response as they are read.",
               "--verify-cmd", "pytest tests/test_export.py", "--issue", "123", *extra)


def test_compose_and_lint():
    base = chain_dir()
    rc, out, err = compose(base)
    check("M1 compose exit 0", rc == 0, err)
    lines = out.split("\n")
    check("M1 subject first", lines[0] == "feat(export): stream CSV exports instead of buffering them", lines[:1])
    for part in ("Why: Exports over 50k rows", "What: Rows are written",
                 "Verified: `pytest tests/test_export.py` -> pass", "Part of #123",
                 "Chain-Run: exports/csv-export", "Chain-Task: T03"):
        check("M1 has %r" % part.split(":")[0], part in out, out)
    check("M2 touched from task-state", "src/export.py" in out and "tests/test_export.py" in out, out)
    check("M3 deviation in a touched file is quoted",
          "returns 201" in out and "202 needs a job queue" in out and "contract-level" in out, out)
    check("M3 deviation elsewhere is not", "log to a file" not in out, out)

    msg = os.path.join(base, "msg.txt")
    write(msg, out)
    rc, out2, err2 = run("lint", "--file", msg)
    check("M1 composed message lints clean", rc == 0, out2 + err2)

    rc, out, err = compose(base, "--touched", "src/new.py")
    check("M4 no deviation for these files is said", "Deviation: none recorded" in out, out)
    shutil.rmtree(base)


def lint_text(text):
    d = tempfile.mkdtemp()
    p = os.path.join(d, "m.txt")
    write(p, text)
    rc, out, err = run("lint", "--file", p)
    shutil.rmtree(d)
    return rc, out + err


GOOD = ("fix(api): keep the retry budget per request\n\n"
        "Why: retries shared one budget across requests.\n"
        "What: the budget is created per request.\n"
        "Verified: `make test` -> pass\n\n"
        "Chain-Run: a/b\nChain-Task: T01\n")


def test_lint():
    rc, out = lint_text(GOOD)
    check("M5 baseline good message passes", rc == 0, out)
    rc, out = lint_text(GOOD.replace("keep the retry budget per request",
                                     "keep the retry budget per request so nothing ever shares it again"))
    check("M5 long subject refused", rc == 1 and "72" in out, out)
    rc, out = lint_text(GOOD.replace("What: the budget is created per request.\n", ""))
    check("M5 missing What refused", rc == 1 and "What" in out, out)
    rc, out = lint_text(GOOD.replace("Chain-Task: T01\n", ""))
    check("M5 missing trailer refused", rc == 1 and "Chain-Task" in out, out)
    rc, out = lint_text(GOOD.replace("retries shared one budget", "retry dùng chung một budget"))
    check("M5 Vietnamese refused", rc == 1 and "English" in out, out)
    rc, out = lint_text(GOOD.replace("retries shared one budget", "the 見積 retries shared one budget"))
    check("M6 Japanese domain term accepted", rc == 0, out)
    rc, out = lint_text(GOOD.replace("fix(api): keep", "Fix the api: keep"))
    check("M5 non-conventional subject refused", rc == 1, out)


def test_staged():
    repo = new_repo()
    base = chain_dir()
    for p in ("src/export.py", "tests/test_export.py"):
        write(os.path.join(repo, p), "x\n")
    git(repo, "add", "src/export.py", "tests/test_export.py")
    rc, out, err = run("staged", "--repo", repo, "--base", base, "--task", "T03")
    check("S1 exactly the touched paths: exit 0", rc == 0, out + err)
    write(os.path.join(repo, "b.txt"), "b\n")
    git(repo, "add", "b.txt")
    rc, out, err = run("staged", "--repo", repo, "--base", base, "--task", "T03")
    check("S2 untouched path staged: exit 1, named", rc == 1 and "b.txt" in out + err, out + err)
    git(repo, "reset", "-q", "--", "b.txt")
    write(os.path.join(repo, ".claude", "claude", "specs", "s.md"), "s\n")
    git(repo, "add", "-f", ".claude/claude/specs/s.md")
    rc, out, err = run("staged", "--repo", repo, "--base", base, "--touched",
                       "src/export.py,tests/test_export.py,.claude/claude/specs/s.md")
    check("S3 artifacts staged: exit 1", rc == 1 and ".claude/claude" in out + err, out + err)
    shutil.rmtree(repo)
    shutil.rmtree(base)


def test_done():
    repo = new_repo()
    write(os.path.join(repo, "a.txt"), "b\n")
    git(repo, "commit", "-q", "-am", "feat: x\n\nWhy: y\n\nChain-Run: other/run\nChain-Task: T03\n")
    rc, out, _ = run("done", "--repo", repo, "--run", "exports/csv-export", "--task", "T03")
    check("D2 another run's T03 is not this one", rc == 1, out)
    write(os.path.join(repo, "a.txt"), "c\n")
    git(repo, "commit", "-q", "-am", "feat: z\n\nWhy: y\n\nChain-Run: exports/csv-export\nChain-Task: T03\n")
    sha = git(repo, "rev-parse", "HEAD")
    rc, out, _ = run("done", "--repo", repo, "--run", "exports/csv-export", "--task", "T03")
    check("D1 this run's T03 found", rc == 0 and sha in out, out)
    shutil.rmtree(repo)


def test_context():
    base = chain_dir()
    rc, out, err = run("context", "--base", base, "--lane", "NR", "--issue", "123",
                       "--input", ".claude/claude/prompts/exports/csv-export.md")
    check("X1 exit 0", rc == 0, err)
    check("X1 lane and issue", "lane: NR" in out and "#123" in out, out)
    check("X1 done task with refs", "T03" in out and "FR-002" in out and "T04" not in out, out)
    check("X1 user decision, latest row", "soft delete, kept 30 days" in out, out)
    check("X1 open row listed as open", "who approves a bulk export" in out, out)
    check("X1 assumption with falsifier", "UTF-8 with BOM" in out and "rejects a BOM" in out, out)
    check("X1 repo-settled T1 rows are left out", "where the export module lives" not in out, out)
    check("X1 deviations, both", "returns 201" in out and "log to a file" in out, out)
    check("X1 manifest status carried", "round 1 clean" in out, out)
    empty = tempfile.mkdtemp()
    rc, out, err = run("context", "--base", empty, "--lane", "BUG")
    check("X2 empty run says not recorded", rc == 0 and out.count("not recorded") >= 3, out + err)
    shutil.rmtree(empty)
    shutil.rmtree(base)


if __name__ == "__main__":
    for fn in (test_gate, test_compose_and_lint, test_lint, test_staged, test_done, test_context):
        fn()
    print()
    if failures:
        print("%d failure(s)" % len(failures))
        sys.exit(1)
    print("all checks passed")
