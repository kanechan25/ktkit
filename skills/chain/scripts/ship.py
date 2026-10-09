#!/usr/bin/env python3
"""The deterministic half of `/ktkit:chain --full`: commit each task, then hand off a PR.

`--full` carries a run past implementation. Both new steps write where other
people read, and `/ktkit:create-pr` writes the PR body from the commit bodies
without ever opening the diff -- so a commit that says less than the run knew is
a PR that says less too. Whatever has one right answer is decided here.

  gate      Before anything is spent: may this run end in a PR at all? The
            checked-out branch must be a feature branch -- not the target, not
            the default branch, not detached -- and the tree must be clean apart
            from the chain's own artifacts under `.claude/claude/`. The target
            is `--to`, else `dev`, else `develop`, the rule `/ktkit:create-pr`
            applies. This never creates or switches a branch; it says to.
  compose   One task's commit message, from the run's own files: subject, Why,
            What, the deviations anchored in the files the task touched, the
            verify command, the issue, and two trailers. The model writes only
            the Why and What prose, and only from the spec and the brief.
  lint      Refuse a message create-pr could not use: a non-conventional or long
            subject, a missing section or trailer, Vietnamese prose.
  staged    The index holds exactly the task's touched paths -- nothing the task
            did not touch, nothing under `.claude/claude/`.
  done      Is this task of this run already committed? Found by its trailers,
            so `--resume` never commits a task twice.
  context   The hand-off file create-pr reads with `--context`: tasks delivered,
            what the user decided at a gate, what is still open, assumptions and
            their falsifiers, every deviation, and the manifest's status column.

Usage
    ship.py gate     --repo <dir> --heads <b> [<b> ...] --default <branch> [--to <branch>]
    ship.py compose  --base <chain-dir> --run <rel/base> --task <id> --type <type>
                     [--scope <scope>] --subject <text> --why <text> --what <text>
                     --verify-cmd <cmd> [--issue <N|url>] [--touched <a,b>]
    ship.py lint     --file <message>
    ship.py staged   --repo <dir> --base <chain-dir> (--task <id> | --touched <a,b>)
    ship.py done     --repo <dir> --run <rel/base> --task <id>
    ship.py context  --base <chain-dir> --lane <lane> [--issue <N|url>] [--input <path>]

Exit status
    0  ok        1  refused (lint, staged) / not found (done)        2  unusable arguments
    gate: 3 both dev and develop exist -- ask     4 no target -- pass --to
          5 standing on the target or default branch    6 dirty tree or detached HEAD

Stdlib only, Python 3.9. Reads commit messages and the run's files, never a diff.
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ledger  # noqa: E402  -- same skill, same directory

PREFERRED = ("dev", "develop")
ARTIFACTS = ".claude/claude/"
SUBJECT_RE = re.compile(r"\A[a-z]+(\([^()\s][^()]*\))?!?: \S")
SUBJECT_MAX = 72
SECTIONS = ("Why:", "What:", "Verified:")
TRAILERS = ("Chain-Run:", "Chain-Task:")
# Vietnamese letters that no other Latin-script language a commit is written in
# uses: the Latin Extended Additional block, plus the letters with horn or breve.
VIET_RE = re.compile(u"[Ạ-ỹĐđƠơƯưĂă]")


class Usage(Exception):
    pass


def git(repo, *args):
    p = subprocess.run(["git", "-C", repo] + list(args), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise Usage("git %s: %s" % (" ".join(args), p.stderr.decode("utf-8", "replace").strip()))
    return p.stdout.decode("utf-8", "replace")


def paths_arg(text):
    return [p.strip() for p in (text or "").split(",") if p.strip()]


# ---------------------------------------------------------------- gate

def do_gate(a):
    current = git(a.repo, "branch", "--show-current").strip()
    if not current:
        print("detached HEAD -> check out the feature branch the PR is from", file=sys.stderr)
        return 6
    dirty = []
    for line in git(a.repo, "status", "--porcelain", "--untracked-files=all").split("\n"):
        path = line[3:].strip().strip('"')
        if line.strip() and not path.startswith(ARTIFACTS):
            dirty.append(path)
    if dirty:
        print("dirty tree -> a commit would sweep these in; commit or stash them first:",
              file=sys.stderr)
        for p in dirty:
            print("  %s" % p, file=sys.stderr)
        return 6
    if a.to:
        if a.to not in a.heads:
            print("--to %s: the remote has no such branch" % a.to, file=sys.stderr)
            return 4
        target = a.to
    else:
        present = [b for b in PREFERRED if b in a.heads]
        if len(present) == 2:
            print("both %s exist on the remote -> ask which one" % " and ".join(PREFERRED),
                  file=sys.stderr)
            return 3
        if not present:
            print("neither %s exists on the remote -> pass --to" % " nor ".join(PREFERRED),
                  file=sys.stderr)
            return 4
        target = present[0]
    if current in (target, a.default) or current in PREFERRED:
        print("on %s -> a PR needs a feature branch; check one out yourself, the chain "
              "never creates one" % current, file=sys.stderr)
        return 5
    print("target %s" % target)
    print("source %s" % current)
    return 0


# ---------------------------------------------------------------- compose

def task_touched(base, task):
    rows = ledger.read_task_rows(os.path.join(base, ledger.TASK_STATE_FILE))
    cur = ledger.task_latest(rows).get(task)
    if not cur or cur["state"] != ledger.TASK_DONE:
        return [], []
    return cur["touched"], cur["spec_refs"]


def deviations(base):
    p = os.path.join(base, "deviations.jsonl")
    out = []
    if os.path.isfile(p):
        for line in io.open(p, encoding="utf-8", errors="replace"):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def anchor_path(evidence):
    return (evidence or "").strip().rsplit(":", 1)[0]


def dev_line(r):
    tag = "  [contract-level]" if r.get("contract") else ""
    return "- %s said \"%s\", built \"%s\": %s (%s)%s" % (
        r.get("source", "?"), r.get("said", ""), r.get("did", ""), r.get("why", ""),
        r.get("evidence", ""), tag)


def issue_ref(issue):
    if not issue:
        return ""
    return issue if issue.startswith("http") or issue.startswith("#") else "#" + issue


def do_compose(a):
    touched = paths_arg(a.touched)
    refs = []
    if not touched:
        touched, refs = task_touched(a.base, a.task)
    if not touched:
        raise Usage("task %s has no done row with touched paths in %s; pass --touched"
                    % (a.task, ledger.TASK_STATE_FILE))
    scope = "(%s)" % a.scope if a.scope else ""
    lines = ["%s%s: %s" % (a.type, scope, a.subject.strip()), "",
             "Why: %s" % a.why.strip(), "", "What: %s" % a.what.strip(), ""]
    mine = [r for r in deviations(a.base) if r.get("kind") == "deviation"
            and anchor_path(r.get("evidence")) in touched]
    if mine:
        lines.append("Deviation from the spec:")
        lines += [dev_line(r) for r in mine]
    else:
        lines.append("Deviation: none recorded for these files")
    lines += ["", "Verified: `%s` -> pass" % a.verify_cmd.strip(),
              "Files: %s" % ", ".join(touched)]
    if refs:
        lines.append("Spec refs: %s" % ", ".join(refs))
    if a.issue:
        lines += ["", "Part of %s" % issue_ref(a.issue)]
    lines += ["", "Chain-Run: %s" % a.run, "Chain-Task: %s" % a.task]
    msg = "\n".join(lines) + "\n"
    problems = lint(msg)
    if problems:
        for p in problems:
            print("lint: %s" % p, file=sys.stderr)
        return 1
    sys.stdout.write(msg)
    return 0


# ---------------------------------------------------------------- lint

def lint(msg):
    problems = []
    lines = msg.split("\n")
    subject = lines[0] if lines else ""
    if not SUBJECT_RE.match(subject):
        problems.append("subject is not `<type>(<scope>): <text>`: %r" % subject)
    if len(subject) > SUBJECT_MAX:
        problems.append("subject is %d characters, over %d" % (len(subject), SUBJECT_MAX))
    if len(lines) < 2 or lines[1].strip():
        problems.append("the second line must be blank")
    for s in SECTIONS:
        hit = [l for l in lines if l.startswith(s)]
        if not hit or not hit[0][len(s):].strip():
            problems.append("missing or empty section %s" % s.rstrip(":"))
    for t in TRAILERS:
        if not any(l.startswith(t) and l[len(t):].strip() for l in lines):
            problems.append("missing trailer %s" % t.rstrip(":"))
    if "\\n" in msg:
        problems.append("a literal \\n -- the message must be real lines")
    if VIET_RE.search(msg):
        problems.append("Vietnamese prose -- commit messages are English")
    return problems


def do_lint(a):
    msg = io.open(a.file, encoding="utf-8").read()
    problems = lint(msg)
    for p in problems:
        print("lint: %s" % p)
    if not problems:
        print("lint ok")
    return 1 if problems else 0


# ---------------------------------------------------------------- staged

def do_staged(a):
    touched = paths_arg(a.touched)
    if not touched and a.task:
        touched, _ = task_touched(a.base, a.task)
    if not touched:
        raise Usage("no touched paths: pass --task with a done row, or --touched")
    staged = [p for p in git(a.repo, "diff", "--cached", "--name-only").split("\n") if p]
    artifacts = [p for p in staged if p.startswith(ARTIFACTS)]
    extra = [p for p in staged if p not in touched and p not in artifacts]
    missing = [p for p in touched if p not in staged]
    for p in artifacts:
        print("refused: %s is a chain artifact, never committed" % p)
    for p in extra:
        print("refused: %s is staged but the task never touched it" % p)
    for p in missing:
        print("note: %s was touched but is not staged (unchanged, or forgotten)" % p)
    if not staged:
        print("refused: nothing staged")
        return 1
    if artifacts or extra:
        return 1
    print("staged ok: %d path(s)" % len(staged))
    return 0


# ---------------------------------------------------------------- done

def do_done(a):
    log = git(a.repo, "log", "--format=%H%x00%B%x01", "--fixed-strings",
              "--grep=Chain-Task: %s" % a.task)
    for rec in log.split("\x01"):
        sha, _, body = rec.strip().partition("\x00")
        lines = [l.strip() for l in body.split("\n")]
        if "Chain-Run: %s" % a.run in lines and "Chain-Task: %s" % a.task in lines:
            print(sha)
            return 0
    print("not committed: %s of %s" % (a.task, a.run))
    return 1


# ---------------------------------------------------------------- context

NOT_RECORDED = "- not recorded"


def ledger_rows(base):
    try:
        return ledger.read_rows(os.path.join(base, "resolved.md"))
    except ValueError:
        return []


def manifest_rows(base):
    p = os.path.join(base, "manifest.md")
    out = []
    if os.path.isfile(p):
        for line in io.open(p, encoding="utf-8"):
            parts = [x.strip() for x in line.strip().strip("|").split("|")]
            if line.startswith("|") and len(parts) >= 3 and parts[0] not in ("Step",) \
                    and not set(parts[0]) <= set("- "):
                out.append("- %s %s: %s" % (parts[0], parts[1], parts[2]))
    return out


def do_context(a):
    out = ["# Chain run context", "",
           "Source material for `/ktkit:create-pr --context`, written by `ship.py context` "
           "from the run's own files. The PR is written in its own language from this; "
           "nothing here is PR prose as it stands.", "",
           "- run: %s" % a.base, "- lane: %s" % a.lane]
    if a.input:
        out.append("- input: %s" % a.input)
    if a.issue:
        out.append("- issue: %s" % issue_ref(a.issue))

    rows = ledger.task_latest(ledger.read_task_rows(os.path.join(a.base, ledger.TASK_STATE_FILE)))
    done = [r for _, r in sorted(rows.items()) if r["state"] == ledger.TASK_DONE]
    out += ["", "## Tasks delivered", ""]
    out += ["- %s  refs %s  touched %s" % (r["task"], ", ".join(r["spec_refs"]) or "-",
                                          ", ".join(r["touched"]) or "-") for r in done] \
        or [NOT_RECORDED]

    current = ledger.latest(ledger_rows(a.base))
    t4 = [r for r in current.values() if r["tier"] == "T4"]
    decided = [r for r in t4 if r["conclusion"] != ledger.OPEN]
    still_open = [r for r in t4 if r["conclusion"] == ledger.OPEN]
    assumed = [r for r in current.values() if r["tier"] == "T3.5"]
    out += ["", "## Decided by the user at a gate", ""]
    out += ["- %s %s -> %s" % (r["id"], r["question"], r["conclusion"]) for r in decided] \
        or [NOT_RECORDED]
    out += ["", "## Still open", ""]
    out += ["- %s %s" % (r["id"], r["question"]) for r in still_open] or ["- none"]
    out += ["", "## Assumptions with evidence", ""]
    out += ["- %s %s -> %s (%s); wrong if: %s" % (r["id"], r["question"], r["conclusion"],
                                                   r["evidence"], r["falsifier"])
            for r in assumed] or ["- none"]

    devs = deviations(a.base)
    real = [r for r in devs if r.get("kind") == "deviation"]
    none = [r for r in devs if r.get("kind") == "none"]
    out += ["", "## Deviations from the spec", ""]
    if real:
        out += [dev_line(r) for r in real]
    elif none:
        out.append("- none: declared at %s" % none[-1].get("at", "?"))
    else:
        out.append(NOT_RECORDED)

    out += ["", "## Manifest status", ""]
    out += manifest_rows(a.base) or [NOT_RECORDED]
    sys.stdout.write("\n".join(out) + "\n")
    return 0


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    g = sub.add_parser("gate", help="may this run end in a PR")
    g.add_argument("--repo", default=".")
    g.add_argument("--heads", nargs="+", default=[], help="branch names the remote has")
    g.add_argument("--default", required=True, help="the repository's default branch")
    g.add_argument("--to", help="the target branch the user named")
    c = sub.add_parser("compose", help="one task's commit message")
    c.add_argument("--base", required=True, help="the chain run directory")
    c.add_argument("--run", required=True, help="<rel>/<base>, the Chain-Run trailer")
    c.add_argument("--task", required=True, help="T03, or fix / trivial for one-commit lanes")
    c.add_argument("--type", required=True, help="feat, fix, refactor, test, ...")
    c.add_argument("--scope")
    c.add_argument("--subject", required=True)
    c.add_argument("--why", required=True, help="from the spec or fix.md, never invented")
    c.add_argument("--what", required=True, help="from the brief's acceptance slot")
    c.add_argument("--verify-cmd", dest="verify_cmd", required=True,
                   help="the free-gate command that passed")
    c.add_argument("--issue", help="the input's gh_issue")
    c.add_argument("--touched", help="comma-separated paths; default from task-state")
    l = sub.add_parser("lint", help="refuse a message create-pr could not use")
    l.add_argument("--file", required=True)
    s = sub.add_parser("staged", help="the index holds exactly the task's paths")
    s.add_argument("--repo", default=".")
    s.add_argument("--base", default=".")
    s.add_argument("--task")
    s.add_argument("--touched")
    d = sub.add_parser("done", help="is this task already committed")
    d.add_argument("--repo", default=".")
    d.add_argument("--run", required=True)
    d.add_argument("--task", required=True)
    x = sub.add_parser("context", help="the hand-off file for create-pr")
    x.add_argument("--base", required=True)
    x.add_argument("--lane", required=True)
    x.add_argument("--issue")
    x.add_argument("--input")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    if not a.cmd:
        ap.print_help()
        return 2
    try:
        return {"gate": do_gate, "compose": do_compose, "lint": do_lint, "staged": do_staged,
                "done": do_done, "context": do_context}[a.cmd](a)
    except Usage as e:
        print("usage error: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
