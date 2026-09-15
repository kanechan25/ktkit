#!/usr/bin/env python3
"""A change request arriving mid-implement must not land silently.

This is the one case where two people edit the same contract at once. The worker
is building against spec.md, plan.md and tasks.md as they were when the phase
started; the change request rewrites them. Nothing crashes. The worker finishes
something that satisfies a spec nobody approves any more, and the run reports
success -- which is worse than failing, because failing is visible.

  F1  freezing records a hash per artifact and marks the run EXECUTING
  F2  an unchanged tree is exit 0; a moved artifact is exit 3, naming it
  F3  a block without a reason is refused -- a block nobody can explain is
      indistinguishable from a crash
  F4  a resume without an affected list is refused, because a resume that
      re-runs everything discards the progress the block was protecting
  F5  re-freezing while BLOCKED is refused: it would adopt the new contract
      without anybody deciding to
  F6  the history is append-only, so what happened survives the resume
  F7  an artifact appearing or disappearing counts as drift

F5 is the quiet one. Every other failure here is loud; that one looks like
tidying up, and it silently replaces the contract the block existed to defend.

Run:  python3 skills/chain/tests/test_contract_freeze.py
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SCRIPT = os.path.join(ROOT, "scripts", "contract_freeze.py")

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def run(*args):
    p = subprocess.Popen([sys.executable, SCRIPT] + list(args),
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = p.communicate()
    return p.returncode, out.decode("utf-8")


def sandbox():
    d = tempfile.mkdtemp()
    base = os.path.join(d, "run")
    feat = os.path.join(d, "feat")
    os.makedirs(base)
    os.makedirs(feat)
    for name, body in (("spec.md", "spec v1\n"), ("plan.md", "plan v1\n"),
                       ("tasks.md", "tasks v1\n")):
        io.open(os.path.join(feat, name), "w", encoding="utf-8").write(body)
    return d, base, feat


def state(base):
    return json.load(io.open(os.path.join(base, "contract.json"),
                             encoding="utf-8"))


def test_f1_freezing_records_a_hash_per_artifact():
    d, base, feat = sandbox()
    try:
        rc, out = run("--base", base, "--dir", feat, "--freeze")
        check("F1 freeze exits 0", rc == 0, out)
        s = state(base)
        check("F1 the run is EXECUTING", s["state"] == "EXECUTING", s["state"])
        check("F1 all three artifacts are hashed",
              sorted(s["artifacts"]) == ["plan.md", "spec.md", "tasks.md"],
              sorted(s["artifacts"]))
        check("F1 and every hash is real, not a placeholder",
              all(v and len(v) == 64 for v in s["artifacts"].values()),
              s["artifacts"])
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_f2_drift_is_exit_3_and_says_which_file():
    d, base, feat = sandbox()
    try:
        run("--base", base, "--dir", feat, "--freeze")
        rc, out = run("--base", base, "--check")
        check("F2 an unchanged tree is exit 0", rc == 0, out)
        check("F2 and says so", "unchanged" in out, out)

        io.open(os.path.join(feat, "spec.md"), "w",
                encoding="utf-8").write("spec v2\n")
        rc, out = run("--base", base, "--check")
        check("F2 a moved artifact is exit 3", rc == 3, out)
        check("F2 and it is named", "spec.md" in out, out)
        check("F2 the untouched ones are not",
              "plan.md" not in out and "tasks.md" not in out, out)
        check("F2 it refuses to decide whether the drift matters",
              "do not choose a side" in out.lower(), out)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_f3_a_block_needs_a_reason():
    d, base, feat = sandbox()
    try:
        run("--base", base, "--dir", feat, "--freeze")
        rc, out = run("--base", base, "--block")
        check("F3 a block with no reason is refused", rc == 2, out)
        check("F3 and it says why that matters",
              "indistinguishable from a crash" in out, out)
        rc, out = run("--base", base, "--block", "--reason", "CR arrived")
        check("F3 a block with a reason is recorded", rc == 0, out)
        check("F3 the state is BLOCKED", state(base)["state"] == "BLOCKED",
              state(base))
        check("F3 and the reason is kept",
              state(base)["reason"] == "CR arrived", state(base))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_f4_a_resume_must_name_what_it_re_runs():
    d, base, feat = sandbox()
    try:
        run("--base", base, "--dir", feat, "--freeze")
        rc, out = run("--base", base, "--resume", "--affected", "T01")
        check("F4 resuming a run that is not blocked is refused",
              rc == 2 and "not-blocked" in out, out)
        run("--base", base, "--block", "--reason", "CR arrived")
        rc, out = run("--base", base, "--resume")
        check("F4 a resume with no affected list is refused", rc == 2, out)
        check("F4 and it says what that would cost",
              "discards exactly the progress" in out, out)
        rc, out = run("--base", base, "--resume", "--affected", "T03,T07")
        check("F4 a resume naming the affected tasks is allowed", rc == 0, out)
        s = state(base)
        check("F4 the state is EXECUTING again", s["state"] == "EXECUTING", s)
        check("F4 and only those tasks are recorded as affected",
              s["affected"] == ["T03", "T07"], s.get("affected"))
        rc, out = run("--base", base, "--check")
        check("F4 the resume re-froze against the amended artifacts", rc == 0,
              out)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_f5_re_freezing_while_blocked_is_refused():
    d, base, feat = sandbox()
    try:
        run("--base", base, "--dir", feat, "--freeze")
        run("--base", base, "--block", "--reason", "CR arrived")
        io.open(os.path.join(feat, "spec.md"), "w",
                encoding="utf-8").write("spec v2\n")
        rc, out = run("--base", base, "--dir", feat, "--freeze")
        check("F5 freezing while BLOCKED is refused", rc == 2, out)
        check("F5 and it names what that would do",
              "without anybody deciding" in out, out)
        check("F5 the run is still BLOCKED",
              state(base)["state"] == "BLOCKED", state(base))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_f6_the_history_survives_the_resume():
    d, base, feat = sandbox()
    try:
        run("--base", base, "--dir", feat, "--freeze")
        run("--base", base, "--block", "--reason", "CR: owner override")
        run("--base", base, "--resume", "--affected", "T01")
        h = state(base)["history"]
        check("F6 every event is kept", len(h) == 3, h)
        check("F6 in order", [e["event"] for e in h]
              == ["freeze", "block", "resume"], h)
        check("F6 and the resume remembers what it was blocked for",
              h[-1].get("was_blocked_for") == "CR: owner override", h[-1])
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_f7_an_artifact_appearing_or_vanishing_is_drift():
    d, base, feat = sandbox()
    try:
        os.remove(os.path.join(feat, "tasks.md"))
        run("--base", base, "--dir", feat, "--freeze")
        check("F7 an absent artifact is recorded as absent, not as an error",
              state(base)["artifacts"]["tasks.md"] is None, state(base))
        io.open(os.path.join(feat, "tasks.md"), "w",
                encoding="utf-8").write("tasks v1\n")
        rc, out = run("--base", base, "--check")
        check("F7 an artifact appearing counts as drift", rc == 3, out)
        check("F7 and it is reported as having been absent",
              "(absent)" in out, out)

        run("--base", base, "--block", "--reason", "x")
        run("--base", base, "--resume", "--affected", "T01")
        os.remove(os.path.join(feat, "spec.md"))
        rc, out = run("--base", base, "--check")
        check("F7 an artifact vanishing counts too", rc == 3, out)
        check("F7 and is reported as deleted", "(deleted)" in out, out)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
