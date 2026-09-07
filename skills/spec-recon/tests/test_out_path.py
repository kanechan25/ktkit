#!/usr/bin/env python3
"""The output path is asked for, never assumed -- and never outside `.claude/`.

The defect this file exists to prevent already shipped once. `--out` defaulted to
the bare string `spec-recon.md`, which resolves against the working directory, so
a run put its report and its entire directory at the repository root -- outside
`.claude/`, contradicting the one layout rule every skill in this plugin follows.
Nothing failed. No check fired. The files simply appeared in the wrong place, and
the only way to notice was to look.

Two things are asserted here, because either alone would let it back:

  * the *script* resolves and validates correctly -- a bare filename is
    rejected, a path outside `.claude/` is rejected, and the suggestion is
    derived from the inputs rather than invented;
  * the *instructions* still say to ask. A skill whose script refuses to guess
    is no better if its SKILL.md reinstates a default in prose.

Run:  python3 skills/spec-recon/tests/test_out_path.py
"""
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SCRIPT = os.path.join(ROOT, "skills", "spec-recon", "scripts", "resolve_out.py")
SKILL = os.path.join(ROOT, "skills", "spec-recon", "SKILL.md")

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def read(path):
    return io.open(path, encoding="utf-8").read()


def run(*args):
    p = subprocess.Popen([sys.executable, SCRIPT, "--repo", ROOT] + list(args),
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = p.communicate()
    return p.returncode, out.decode("utf-8")


# --------------------------------------------------------------- the script

def test_no_out_asks_instead_of_choosing():
    rc, out = run("--inputs", ".claude/claude/docs/batch-01/")
    check("O1 a run with no --out exits 3 (ask, do not proceed)", rc == 3, out[:200])
    check("O1 it says the path is unset", "OUT-UNSET" in out, out[:120])
    check("O1 it prints a machine-readable suggestion",
          "SUGGEST=" in out, out[-200:])
    check("O1 the suggestion is inside the artifact root",
          re.search(r"SUGGEST=\.claude/claude/", out) is not None, out[-200:])
    check("O1 it shows the tree that would be created",
          "evidence/probe-*.md" in out and "steps/manifest.md" in out, out[:400])


def test_the_suggestion_mirrors_the_input():
    """Derived from the inputs, per the ccompact algorithm -- not invented."""
    rc, out = run("--inputs", ".claude/claude/specs/issue-123/sub/123.spec.md")
    check("O2 a nested input keeps its sub-path", rc == 3
          and "analyze/issue-123/sub/123.recon.md" in out, out[:300])
    rc, out = run("--inputs", ".claude/claude/docs/batch-01/")
    check("O2 a directory input names itself",
          "analyze/batch-01.recon.md" in out, out[:300])
    check("O2 the folder drops the .recon marker the report carries",
          "analyze/batch-01/" in out, out[:300])


def test_several_inputs_do_not_depend_on_argument_order():
    a = ".claude/claude/docs/batch-01/one.md"
    b = ".claude/claude/docs/batch-01/sub/two.md"
    _rc1, out1 = run("--inputs", a, b)
    _rc2, out2 = run("--inputs", b, a)
    s1 = re.search(r"SUGGEST=(\S+)", out1)
    s2 = re.search(r"SUGGEST=(\S+)", out2)
    check("O3 several inputs resolve to one path", s1 and s2, (out1[-80:], out2[-80:]))
    if s1 and s2:
        check("O3 that path does not depend on argument order",
              s1.group(1) == s2.group(1), (s1.group(1), s2.group(1)))


def test_an_input_outside_the_artifact_root_is_filed_and_flagged():
    rc, out = run("--inputs", "src/backend/Templates/")
    check("O4 an external input goes under _external/",
          "_external/Templates.recon.md" in out, out[:300])
    check("O4 and the reason is stated",
          "outside" in out, out[:300])


def test_the_old_default_is_now_rejected():
    """`spec-recon.md` is the exact string that caused the defect."""
    rc, out = run("--inputs", ".claude/claude/docs/batch-01/",
                  "--out", "spec-recon.md")
    check("O5 the old bare-filename default is rejected", rc == 2, out[:200])
    check("O5 the rejection names the reason",
          "bare filename" in out, out[:200])
    check("O5 and offers a usable path instead",
          ".claude/claude/analyze/" in out, out[:300])


def test_a_path_outside_dot_claude_is_rejected():
    for bad in ("reports/x.md", "../x.md", "/tmp/x.md"):
        rc, out = run("--inputs", ".claude/claude/docs/batch-01/", "--out", bad)
        check("O6 %s is rejected" % bad, rc == 2, out[:160])
    rc, out = run("--inputs", ".claude/claude/docs/batch-01/",
                  "--out", ".claude/claude/analyze/x")
    check("O6 a path that is not a .md report is rejected", rc == 2, out[:160])


def test_a_good_path_is_accepted_and_its_folder_derived():
    rc, out = run("--inputs", ".claude/claude/docs/batch-01/",
                  "--out", ".claude/claude/analyze/batch-01/export.recon.md")
    check("O7 a path inside the artifact root is accepted", rc == 0, out[:200])
    check("O7 it echoes the report path", "OUT=" in out, out[:200])
    check("O7 and the folder beside it",
          "analyze/batch-01/export/" in out, out[:200])


# ---------------------------------------------------------- the instructions

def test_the_skill_still_says_to_ask():
    body = read(SKILL)
    check("O8 the Arguments row no longer declares a silent default",
          "| `--out <path>` | **asked, never assumed** |" in body,
          [l for l in body.split("\n") if "`--out <path>`" in l][:1])
    check("O8 the old default string is gone from the flag table",
          "| `spec-recon.md` |" not in body)
    check("O8 step 0 runs the resolver",
          "resolve_out.py" in body)
    check("O8 exit 3 is documented as a stop",
          re.search(r"`3`.*STOP", body) is not None)
    check("O8 preflight now asks for the artifacts group",
          "runtime,write,read,vcs,forge,artifacts" in body)
    check("O8 a stop rule forbids measuring before the path is confirmed",
          "before the output path is confirmed" in body)


def test_the_handoff_passes_the_confirmed_path_through():
    h = read(os.path.join(ROOT, "skills", "spec-recon", "references", "handoff.md"))
    check("O9 the handoff uses the settled path, not a default",
          "the path Phase 0 step 0 settled" in h)


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
