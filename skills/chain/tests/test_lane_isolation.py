#!/usr/bin/env python3
"""The BUG lane must not walk into spec-driven development.

A bug is a disagreement between code and a specification that already exists.
Writing a second specification to describe the disagreement adds a document that
has to be kept true, while the failing test says the same thing in a form that
cannot drift. So the BUG lane runs rca, systematic-debugging, a failing test,
the fix, and verification -- and none of speckit's specify/plan/tasks/analyze/
converge.

Prose cannot enforce a boundary. This can:

  L1  the lane contract is stated in `references/lanes.md`, naming the speckit
      steps it excludes
  L2  no skill the BUG lane dispatches reaches for speckit -- except the ones
      declared below, by name and with a reason
  L3  every declared exception is still an exception. A file that has been
      cleaned up must be removed from the list, and this fails until it is.
  L4  the CR and NR lanes are NOT constrained -- they are the lanes speckit is
      for, and a check that silently covered them would be enforcing something
      nobody decided

L3 is the half that makes L2 honest. An allow-list with no expiry is a way of
never fixing anything; one that fails when the exception stops being needed is a
reminder that arrives by itself.

Run:  python3 skills/chain/tests/test_lane_isolation.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
CHAIN = os.path.join(ROOT, "skills", "chain", "SKILL.md")
LANES = os.path.join(ROOT, "skills", "chain", "references", "lanes.md")

# The speckit steps the BUG lane excludes. `constitution`, `checklist` and
# `taskstoissues` are not listed: they are not part of the spec->plan->tasks
# spine this lane is avoiding, and banning them would be enforcing a decision
# nobody made.
SDD_STEPS = ("specify", "plan", "tasks", "analyze", "converge")

# Skills the BUG lane dispatches that have NOT been brought in line with the
# contract yet, each with the reason it is still here. The owner has said rca
# and bug-fix-specs will move to superpowers separately; until then the gap is
# named here rather than passed over.
DECLARED = {
    "skills/bug-fix-specs/SKILL.md":
        "still carries a `speckit` mode from before the lanes existed; "
        "scheduled to move to the superpowers path with /ktkit:rca",
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


def dispatch_lanes():
    """{lane: [skills]} from the dispatch table at the end of step 00."""
    out, seen = {}, False
    for line in read(CHAIN).splitlines():
        stripped = line.strip()
        if not seen:
            if stripped.startswith("| Lane | 01 | 03 |"):
                seen = True
            continue
        if not stripped.startswith("|"):
            break
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) != 4 or set(cells[0]) <= set("- "):
            continue
        out[cells[0]] = re.findall(r"`/ktkit:([a-z-]+)`", " ".join(cells[1:]))
    return out


def skill_files(name):
    base = os.path.join(ROOT, "skills", name)
    out = []
    for dirpath, _dirs, names in os.walk(base):
        for n in names:
            if n.endswith(".md"):
                out.append(os.path.join(dirpath, n))
    return sorted(out)


def sdd_hits(path):
    """Lines that invoke one of the excluded speckit steps.

    An invocation is `/speckit-<step>`. A bare mention in an attribution -- "the
    taxonomy is adapted from `speckit-clarify`" -- is not a call and does not
    count; the boundary is about what the lane runs, not what it learned from.
    """
    hits = []
    for i, line in enumerate(read(path).splitlines(), 1):
        for step in SDD_STEPS:
            if "/speckit-%s" % step in line:
                hits.append((i, step))
                break
    return hits


def rel(path):
    return os.path.relpath(path, ROOT)


def test_l1_the_contract_is_written_down():
    body = flat(LANES)
    check("L1 lanes.md states that BUG does not touch SDD",
          "BUG does not touch SDD" in body, "")
    missing = [s for s in SDD_STEPS if "speckit-%s" % s not in body]
    check("L1 and names every step it excludes", not missing, missing)
    check("L1 it names the path the lane runs instead",
          "systematic-debugging" in body
          and "verification-before-completion" in body, "")
    check("L1 and keeps the one exception: a wrong spec is a CR",
          "spec** is\nwhat is wrong" in read(LANES)
          or "spec** is what is wrong" in body, "")


def test_l2_no_bug_lane_skill_reaches_for_speckit():
    lanes = dispatch_lanes()
    check("L2 the BUG lane is in the dispatch table", "BUG" in lanes, sorted(lanes))
    offenders = []
    for skill in lanes.get("BUG", []):
        for path in skill_files(skill):
            if rel(path) in DECLARED:
                continue
            for line, step in sdd_hits(path):
                offenders.append("%s:%d /speckit-%s" % (rel(path), line, step))
    check("L2 no undeclared BUG-lane file invokes an SDD step",
          not offenders, offenders[:8])


def test_l3_every_declared_exception_is_still_needed():
    stale, unknown = [], []
    for declared, reason in sorted(DECLARED.items()):
        path = os.path.join(ROOT, declared)
        if not os.path.isfile(path):
            unknown.append("%s: no such file" % declared)
            continue
        if not sdd_hits(path):
            stale.append(declared)
        if len(reason) < 30:
            unknown.append("%s: reason too thin to be a reason" % declared)
    check("L3 every declared exception names a file that exists",
          not unknown, unknown)
    check("L3 and every one of them still invokes an SDD step -- "
          "remove it from DECLARED once it does not",
          not stale, stale)
    check("L3 lanes.md admits the gap rather than hiding it",
          "Not yet true of" in read(LANES), "")


def test_l4_the_cr_and_nr_lanes_are_left_alone():
    lanes = dispatch_lanes()
    for lane in ("CR", "NR"):
        check("L4 the %s lane is in the dispatch table" % lane,
              lane in lanes, sorted(lanes))
    uses = []
    for lane in ("CR", "NR"):
        for skill in lanes.get(lane, []):
            for path in skill_files(skill):
                if sdd_hits(path):
                    uses.append(skill)
                    break
    check("L4 the CR/NR lanes do use speckit, and are not being constrained",
          bool(uses), uses)


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
