#!/usr/bin/env python3
"""Two rounds of convergence, and the third does not exist.

`/speckit-converge` is the only step in the whole path that opens the delivered
code and asks whether it satisfies the spec. Everything before it compares one
document with another, and documents can agree perfectly with each other while
the code does something else.

Its loop is also the one place in this plugin where spending can run away
without anybody deciding to spend. Each round costs a converge pass plus an
implement pass, and the loop terminates on a condition the loop itself cannot
influence -- whether the spec is clear. Two rounds that still leave work
outstanding is not missing code; it is a spec that reads differently each pass,
and a third round pays to chase a target that moves every time it is reached.

  C1  the step exists, in both places that can run it
  C2  the cap is two rounds, and round 3 is named as not existing
  C3  at the cap: append nothing, record the reason, escalate to a human
  C4  the round count is recorded either way -- a run that converged clean and
      one that hit the cap silently are otherwise indistinguishable
  C5  append-only is honoured: the plugin does not claim to enforce it, and does
      not permit anything to break it
  C6  the lanes without a tasks.md do not run it, and the reason is stated
  C7  converge runs AFTER the sync-back step, not before

C7 is the ordering nobody would question and everybody would get wrong. Sync
back records what the author still remembers; converge reads the code cold. The
other way round, converge measures against a spec that is about to change.

Run:  python3 skills/chain/tests/test_converge_cap.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

CHAIN = os.path.join(ROOT, "skills", "chain", "SKILL.md")
LOOP = os.path.join(ROOT, "skills", "chain", "references", "converge-loop.md")
EXEC = os.path.join(ROOT, "skills", "feat-req-execute", "SKILL.md")

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def read(path):
    return io.open(path, encoding="utf-8").read()


def flat(path):
    return plain(read(path))


def plain(text):
    """Whitespace collapsed and markdown emphasis stripped.

    These documents are hard-wrapped and liberally emphasised, so a phrase is as
    likely to be split across two lines or to carry a stray ** or ` as not.
    Matching the raw text fails on a reflow and passes on a rewording.
    """
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", ""))


def step_07():
    body = read(CHAIN)
    return body[body.index("### 07 — converge"):body.index("## The gate")]


def exec_step():
    body = read(EXEC)
    return body[body.index("### STEP 8.7 — CONVERGE"):
                body.index("### STEP 9 — DOCUMENT")]


def test_c1_the_step_exists_in_both_places_that_can_run_it():
    check("C1 chain has step 07", "### 07 — converge" in read(CHAIN), "")
    check("C1 feat-req-execute has its own converge step",
          "### STEP 8.7 — CONVERGE" in read(EXEC), "")
    for name, block in (("chain", step_07()), ("feat-req-execute", exec_step())):
        check("C1 %s invokes /speckit-converge" % name,
              "/speckit-converge" in block, "")
    check("C1 the reference explains the loop",
          os.path.isfile(LOOP) and "convergence loop" in read(LOOP).lower(), "")


def test_c2_the_cap_is_two_rounds():
    for name, block in (("chain", step_07()), ("feat-req-execute", exec_step())):
        f = plain(block)
        check("C2 %s caps the loop at two rounds" % name,
              "Two rounds, and the third does not exist" in f, "")
        check("C2 %s shows round 1 and round 2 and no round 3" % name,
              "round 1" in f and "round 2" in f and "round 3" not in f.lower()
              .replace("round 3 is not", "").replace("round 3 is", ""), f[:200])
    loop = flat(LOOP)
    check("C2 the reference says why the third round is a different problem",
          "different one" in loop or "different problem" in loop, "")


def test_c3_the_cap_appends_nothing_and_escalates():
    for name, block in (("chain", step_07()), ("feat-req-execute", exec_step())):
        f = plain(block)
        check("C3 %s appends nothing at the cap" % name,
              "append nothing" in f.lower(), "")
        check("C3 %s records the reason rather than just stopping" % name,
              "survived both rounds" in f, "")
    f = plain(step_07())
    check("C3 chain escalates through the confirm gate",
          "/ktkit:confirm-with-me" in f, "")
    check("C3 and writes the reason into the manifest",
          "manifest.md" in f, "")
    check("C3 the escalation does not consume the run's question budget",
          "does not count" in flat(LOOP), "")


def test_c4_the_round_count_is_always_recorded():
    f = plain(step_07())
    check("C4 chain records the round count as it goes",
          "Record the round count" in f, "")
    check("C4 and names what goes wrong when it is not",
          "becomes a spiral" in f, "")
    e = plain(exec_step())
    check("C4 feat-req-execute reports the round count either way",
          "round count either way" in e, "")


def test_c5_append_only_is_honoured_not_reimplemented():
    for name, block in (("chain", step_07()), ("feat-req-execute", exec_step())):
        f = plain(block)
        check("C5 %s says append-only is converge's own contract" % name,
              "own contract" in f, "")
        check("C5 %s forbids renumbering or reordering what it appended" % name,
              "renumber" in f and "reorder" in f, "")
        check("C5 %s forbids rewriting tasks.md wholesale" % name,
              "tasks.md wholesale" in f, "")
    check("C5 the reference states it is not ours to enforce",
          "not ours to enforce" in flat(LOOP), "")


def test_c6_lanes_without_tasks_do_not_run_it():
    f = plain(step_07())
    check("C6 the BUG lane does not run converge",
          "The BUG lane does not run it" in f, "")
    check("C6 and the reason is its failing test, not an exemption",
          "failing test" in f, "")
    loop = flat(LOOP)
    for lane in ("NR", "CR", "BUG", "TRIVIAL"):
        check("C6 the reference says whether %s runs it" % lane, lane in loop, "")


def test_c7_converge_runs_after_sync_back():
    body = read(CHAIN)
    check("C7 in chain, 07 comes after 06",
          body.index("### 06 — sync back") < body.index("### 07 — converge"), "")
    e = read(EXEC)
    check("C7 in feat-req-execute, converge comes after the deviation record",
          e.index("### STEP 8.5 — RECORD WHAT DIVERGED")
          < e.index("### STEP 8.7 — CONVERGE"), "")
    check("C7 and the ordering is justified, not incidental",
          "reads the finished code cold" in flat(EXEC), "")
    check("C7 the reference gives the same reason",
          "about to change" in flat(LOOP), "")


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
