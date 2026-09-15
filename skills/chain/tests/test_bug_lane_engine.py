#!/usr/bin/env python3
"""The BUG lane says it runs on superpowers. This checks that it does.

`references/lanes.md` names five steps -- rca, systematic-debugging, a failing
test, the fix, verification -- and until C1.5 only two of them existed anywhere
in the plugin. The lane invoked `/speckit-specify`, investigated the same bug
twice (once in rca, once again in bug-fix-specs), stopped `systematic-debugging`
at Phase 2 so Phase 3 never ran, and changed code before any test was red.

None of that fails loudly. A lane that quietly does less than its contract says
produces a fix that looks like every other fix.

  B1  every step the contract names is claimed by a skill on the lane
  B2  the reverse: a superpowers skill invoked on the lane is one the contract
      names -- an engine nobody wrote down is as bad as a step nobody runs
  B3  rca runs Phases 1, 2 AND 3, and still refuses Phase 4
  B4  the red test comes before the fix -- test-driven-development is named
      ahead of the STEP 5 heading, in the file, in that order
  B5  the third failed attempt stops, and there is no fourth
  B6  the investigation happens once: bug-fix-specs reads the analysis instead
      of re-deriving it
  B7  the lane writes fix.md, and bug-fix-execute can still find the older
      artifacts it will meet in the wild

B2 is the half that is easy to leave out. Without it the test only proves the
contract is satisfied, not that the lane does nothing else -- and "nothing else"
is what makes a lane a lane.

Run:  python3 skills/chain/tests/test_bug_lane_engine.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

LANES = os.path.join(ROOT, "skills", "chain", "references", "lanes.md")
RCA = os.path.join(ROOT, "skills", "rca", "SKILL.md")
SPECS = os.path.join(ROOT, "skills", "bug-fix-specs", "SKILL.md")
EXEC = os.path.join(ROOT, "skills", "bug-fix-execute", "SKILL.md")

# The engine the contract names, and the skill that is supposed to run each part.
CONTRACT = {
    "systematic-debugging": RCA,
    "test-driven-development": EXEC,
    "verification-before-completion": EXEC,
}

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
    return re.sub(r"\s+", " ", read(path))


def rel(path):
    return os.path.relpath(path, ROOT)


def invoked(path):
    """Every `superpowers:<skill>` a file names."""
    return set(re.findall(r"superpowers:([a-z-]+)", read(path)))


def test_b1_every_contracted_step_is_claimed_by_a_skill():
    missing = []
    for skill, owner in sorted(CONTRACT.items()):
        if skill not in invoked(owner):
            missing.append("%s should be invoked by %s" % (skill, rel(owner)))
    check("B1 every superpowers step the contract names has an owner",
          not missing, missing)
    check("B1 the contract itself still names them",
          all(s in flat(LANES) for s in CONTRACT), sorted(CONTRACT))


def test_b2_nothing_on_the_lane_invokes_an_unnamed_engine():
    stray = []
    for path in (RCA, SPECS, EXEC):
        for skill in sorted(invoked(path)):
            if skill not in CONTRACT:
                stray.append("%s invokes superpowers:%s, which the contract "
                             "does not name" % (rel(path), skill))
    check("B2 no BUG-lane skill invokes a superpowers skill off the contract",
          not stray, stray)


def test_b3_rca_runs_phase_3_and_still_refuses_phase_4():
    body = flat(RCA)
    # Read the scope declaration itself, not the whole file: Step 3.9 mentions
    # "Phase 3" in passing, so a file-wide search passes even when Step 2 still
    # says Phases 1 and 2 ONLY. The first draft of this test did exactly that.
    raw = read(RCA)
    scope = raw[raw.index("### Step 2:"):raw.index("### Step 3:")]
    for phase in ("Phase 1", "Phase 2", "Phase 3"):
        check("B3 the scope note at Step 2 names %s" % phase,
              "**%s**" % phase in scope, scope[:200])
    check("B3 and it no longer stops at Phase 2",
          "ONLY" not in scope, scope[:200])
    check("B3 rca still refuses Phase 4 (Implementation)",
          "Do NOT follow Phase 4" in body, "")
    check("B3 Phase 3 lands as a step of its own, before classification",
          read(RCA).index("### Step 3.9")
          < read(RCA).index("### Step 4:"), "")
    check("B3 and its experiment is a failing test, not a fix",
          "the experiment is a failing test, not a fix" in body, "")


def test_b4_the_red_test_comes_before_the_fix():
    body = read(EXEC)
    try:
        red = body.index("### STEP 4.95")
        fix = body.index("### STEP 5 — FIX")
    except ValueError as exc:
        check("B4 both the RED step and the FIX step exist", False, str(exc))
        return
    check("B4 the RED step exists and precedes the FIX step", red < fix,
          (red, fix))
    red_block = body[red:fix]
    check("B4 the RED step invokes test-driven-development",
          "superpowers:test-driven-development" in red_block, "")
    check("B4 and demands the test be red for the right reason",
          "right reason" in red_block, "")
    check("B4 and forbids STEP 5 until it is",
          "may run until this test is red" in re.sub(r"\s+", " ", red_block), "")


def test_b5_the_fourth_attempt_does_not_exist():
    body = flat(EXEC)
    check("B5 failed attempts are counted", "failed attempt" in body.lower(), "")
    check("B5 three is the stop", "Do not attempt a fourth" in body, "")
    check("B5 the stop is recorded as a contract deviation",
          "add --contract" in body and "deviation.py" in body, "")
    check("B5 and it is named as an architectural question, not a bad guess",
          "wrong architecture" in body.lower(), "")


def test_b6_the_investigation_happens_once():
    body = flat(SPECS)
    check("B6 bug-fix-specs reads the analysis rather than investigating",
          "DO NOT INVESTIGATE AGAIN" in read(SPECS), "")
    check("B6 it stops when there is no analysis to read",
          "status: rca-complete" in body, "")
    check("B6 and points at the skill that owns the investigation",
          "/ktkit:rca" in body, "")
    # An invocation, not a mention: the step that replaced them explains what it
    # replaced, and a check that forbade the word would forbid the explanation.
    for tool in ("gitnexus_query", "gitnexus_impact", "gitnexus_context"):
        check("B6 it no longer invokes %s itself" % tool,
              "%s(" % tool not in read(SPECS), "")


def test_b7_the_lane_writes_fix_md_and_can_still_read_the_old_names():
    check("B7 bug-fix-specs writes fix.md", "fix.md" in flat(SPECS), "")
    check("B7 the chain layout records fix.md for the BUG lane",
          "fix.md" in flat(os.path.join(ROOT, "skills", "chain", "SKILL.md")), "")
    body = flat(EXEC)
    for name in ("fix.md", "spec.md", "*.spec.md"):
        check("B7 bug-fix-execute still resolves %s" % name, name in body, "")
    check("B7 and resolves by basename rather than by glob",
          "never by glob" in body, "")
    check("B7 older artifacts are read, not rewritten",
          "never renamed and never rewritten" in body, "")


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
