#!/usr/bin/env python3
"""A conflict resolution may not lose a line either side added, unless somebody says why.

`line_survival.py` is the measurement behind the one promise this skill makes
that a model cannot keep by being careful: no code is lost in the merge. These
tests build real three-way histories in a throwaway repository -- every commit
on a detached HEAD, so not even the fixture creates a branch -- resolve them
well and badly, and check the script tells the two apart.

  L1  a union resolution that keeps both sides passes
  L2  taking one side of a conflict loses the other side's line
  L3  a conflict marker left in a file fails, even with every line present
  L4  a file neither side conflicted on, overwritten wholesale, is caught
  L5  a file the base side renamed is followed to its new path
  L6  a binary file is skipped and said to be skipped, not read
  L7  --result audits a committed merge instead of the working tree
  L8  a file deleted by the resolution loses everything that side added to it
  L9  lines with no letter or digit are not counted
  L10 a lone `=======` line is not a conflict marker
  L11 --json carries the same verdict as the exit status
  L12 a revision that does not exist is a usage error, not a pass

Run:  python3 skills/resolve-conflict-pr/tests/test_line_survival.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "scripts", "line_survival.py")

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def git(repo, *args):
    p = subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t",
                        "-c", "commit.gpgsign=false"] + list(args),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if p.returncode != 0:
        raise RuntimeError("git %s: %s" % (" ".join(args), p.stderr))
    return p.stdout.strip()


def write(repo, path, text, binary=False):
    full = os.path.join(repo, path)
    d = os.path.dirname(full)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(full, "wb" if binary else "w") as fh:
        fh.write(text)


def commit(repo, msg):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--allow-empty", "-m", msg)
    return git(repo, "rev-parse", "HEAD")


def history(base_files, ours_files, theirs_files, theirs_moves=()):
    """base -> ours and base -> theirs, as three SHAs on detached HEADs."""
    repo = tempfile.mkdtemp()
    git(repo, "init", "-q")
    for p, t in base_files.items():
        write(repo, p, t)
    base = commit(repo, "base")
    git(repo, "checkout", "-q", "--detach", base)
    for p, t in ours_files.items():
        write(repo, p, t)
    ours = commit(repo, "ours")
    git(repo, "checkout", "-q", "--detach", base)
    for src, dst in theirs_moves:
        d = os.path.dirname(os.path.join(repo, dst))
        if not os.path.isdir(d):
            os.makedirs(d)
        git(repo, "mv", src, dst)
    for p, t in theirs_files.items():
        write(repo, p, t)
    theirs = commit(repo, "theirs")
    git(repo, "checkout", "-q", "--detach", ours)
    return repo, base, ours, theirs


def merge(repo, theirs):
    subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t",
                    "merge", "--no-commit", "--no-ff", theirs],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def audit(repo, base, ours, theirs, *extra):
    p = subprocess.run([sys.executable, SCRIPT, "--repo", repo, "--base", base,
                        "--ours", ours, "--theirs", theirs] + list(extra),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    return p.returncode, p.stdout + p.stderr


BASE = "import a\n\ndef run():\n    return 1\n"
OURS = "import a\nimport feature_thing\n\ndef run():\n    return 1\n"
THEIRS = "import a\nimport dev_thing\n\ndef run():\n    return 1\n"


def test_union_passes():
    repo, b, o, t = history({"m.py": BASE}, {"m.py": OURS}, {"m.py": THEIRS})
    merge(repo, t)
    write(repo, "m.py", "import a\nimport dev_thing\nimport feature_thing\n\ndef run():\n    return 1\n")
    rc, out = audit(repo, b, o, t)
    check("L1 a union resolution passes", rc == 0, out)
    shutil.rmtree(repo)


def test_one_side_loses():
    repo, b, o, t = history({"m.py": BASE}, {"m.py": OURS}, {"m.py": THEIRS})
    merge(repo, t)
    write(repo, "m.py", OURS)
    rc, out = audit(repo, b, o, t)
    check("L2 taking ours exits 1", rc == 1, out)
    check("L2 and names the theirs line it lost", "LOST" in out and "theirs" in out
          and "import dev_thing" in out, out)
    check("L2 and does not blame ours", "import feature_thing" not in out, out)
    shutil.rmtree(repo)


def test_marker_fails():
    repo, b, o, t = history({"m.py": BASE}, {"m.py": OURS}, {"m.py": THEIRS})
    merge(repo, t)
    rc, out = audit(repo, b, o, t)
    check("L3 the raw conflicted file exits 1", rc == 1, out)
    check("L3 and reports the marker", "MARK" in out and "<<<<<<<" in out, out)
    shutil.rmtree(repo)


def test_wholesale_overwrite():
    repo, b, o, t = history({"m.py": BASE, "only_ours.py": "x = 1\n"},
                            {"m.py": BASE, "only_ours.py": "x = 1\nfeature_flag = True\n"},
                            {"m.py": THEIRS})
    merge(repo, t)
    write(repo, "only_ours.py", "x = 1\n")
    rc, out = audit(repo, b, o, t)
    check("L4 an overwritten non-conflicting file is caught", rc == 1
          and "feature_flag = True" in out, out)
    shutil.rmtree(repo)


def test_rename_followed():
    body = "def helper():\n    return compute()\n"
    repo, b, o, t = history({"old/h.py": body},
                            {"old/h.py": body + "\ndef added_by_feature():\n    return 2\n"},
                            {}, theirs_moves=[("old/h.py", "new/h.py")])
    merge(repo, t)
    rc, out = audit(repo, b, o, t)
    check("L5 git followed the rename, so does the audit", rc == 0
          and os.path.isfile(os.path.join(repo, "new/h.py")), out)
    shutil.rmtree(repo)


def test_binary_skipped():
    repo, b, o, t = history({"m.py": BASE}, {"m.py": OURS}, {"m.py": OURS})
    write(repo, "logo.bin", b"\x00\x01\x02feature", binary=True)
    o = commit(repo, "ours binary")
    merge(repo, t)
    rc, out = audit(repo, b, o, t)
    check("L6 a binary file does not fail the audit", rc == 0, out)
    check("L6 and is reported as skipped", "SKIP" in out and "logo.bin" in out, out)
    shutil.rmtree(repo)


def test_result_rev():
    repo, b, o, t = history({"m.py": BASE}, {"m.py": OURS}, {"m.py": THEIRS})
    merge(repo, t)
    write(repo, "m.py", OURS)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "bad merge")
    write(repo, "m.py", "import a\nimport dev_thing\nimport feature_thing\n\ndef run():\n    return 1\n")
    rc_tree, _ = audit(repo, b, o, t)
    rc_head, out = audit(repo, b, o, t, "--result", "HEAD")
    check("L7 the working tree is clean", rc_tree == 0)
    check("L7 the committed merge is not, and --result reads the commit", rc_head == 1, out)
    shutil.rmtree(repo)


def test_deleted_file():
    repo, b, o, t = history({"m.py": BASE, "svc.py": "a = 1\n"},
                            {"m.py": BASE, "svc.py": "a = 1\nfeature_call()\n"},
                            {"m.py": THEIRS})
    merge(repo, t)
    os.remove(os.path.join(repo, "svc.py"))
    rc, out = audit(repo, b, o, t)
    check("L8 deleting the file loses what ours added", rc == 1 and "feature_call()" in out, out)
    shutil.rmtree(repo)


def test_punctuation_ignored():
    base = "fn a() {\n  one();\n}\n"
    repo, b, o, t = history({"m.js": base}, {"m.js": base + "fn b() {\n  two();\n}\n"},
                            {"m.js": base})
    merge(repo, t)
    write(repo, "m.js", base + "fn b() {\n  two();\n")
    rc, out = audit(repo, b, o, t)
    check("L9 a dropped lone brace is not reported", rc == 0, out)
    shutil.rmtree(repo)


def test_setext_not_marker():
    text = "Title\n=======\n\nbody\n"
    repo, b, o, t = history({"m.py": BASE, "doc.md": "x\n"},
                            {"m.py": BASE, "doc.md": text}, {"m.py": THEIRS})
    merge(repo, t)
    rc, out = audit(repo, b, o, t)
    check("L10 a markdown underline is not a marker", rc == 0, out)
    shutil.rmtree(repo)


def test_json():
    repo, b, o, t = history({"m.py": BASE}, {"m.py": OURS}, {"m.py": THEIRS})
    merge(repo, t)
    write(repo, "m.py", OURS)
    rc, out = audit(repo, b, o, t, "--json")
    try:
        data = json.loads(out)
    except ValueError:
        data = {}
    check("L11 --json parses", bool(data), out)
    check("L11 and its verdict matches the exit status", rc == 1 and data.get("ok") is False
          and any(r.get("side") == "theirs" for r in data.get("lost", [])), out)
    shutil.rmtree(repo)


def test_bad_rev():
    repo, b, o, t = history({"m.py": BASE}, {"m.py": OURS}, {"m.py": THEIRS})
    rc, out = audit(repo, b, o, "does-not-exist")
    check("L12 an unknown revision exits 2", rc == 2, out)
    shutil.rmtree(repo)


if __name__ == "__main__":
    for fn in (test_union_passes, test_one_side_loses, test_marker_fails, test_wholesale_overwrite,
               test_rename_followed, test_binary_skipped, test_result_rev, test_deleted_file,
               test_punctuation_ignored, test_setext_not_marker, test_json, test_bad_rev):
        fn()
    print()
    if failures:
        print("%d failure(s)" % len(failures))
        sys.exit(1)
    print("all checks passed")
