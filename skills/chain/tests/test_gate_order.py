#!/usr/bin/env python3
"""The free gate runs before the expensive one, and nothing may reorder them.

A code reviewer dispatched over code that does not compile returns findings
about a file the compiler would have rejected in a second. The run pays model
usage -- the thing that actually runs out -- to be told something free. Build,
test, lint and typecheck cost nothing and answer first.

Ordering in a document is not enforced by anything except a check that reads the
order. This is that check:

  G1  the deterministic gate exists, in step 05, and names all four of its parts
  G2  it appears BEFORE the reviewer is dispatched -- by file position, not by
      the order somebody listed them in prose
  G3  a failing gate sends work back rather than producing a finding
  G4  the test command is read from the repository, never guessed, and the
      preflight group that locates it exists
  G5  SKIP means ask once and record the answer, not fall back to a default

G2 is the one that breaks silently. Reword the section and the sentences still
read correctly while the order they describe has reversed, so the check compares
offsets in the file rather than looking for words.

G4 matters more than it looks: a green from the wrong command is worse than no
gate, because a gate nobody trusts gets removed, while a gate that is trusted
and wrong gets believed.

Run:  python3 skills/chain/tests/test_gate_order.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

CHAIN = os.path.join(ROOT, "skills", "chain", "SKILL.md")
PREFLIGHT = os.path.join(ROOT, "scripts", "preflight.py")

# The four checks that cost nothing. Named individually because "run the tests"
# is the one people remember and the other three are the ones that catch the
# code a reviewer should never see.
FREE_CHECKS = ("build", "test", "lint", "typecheck")

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def read(path):
    return io.open(path, encoding="utf-8").read()


def step_05():
    body = read(CHAIN)
    return body[body.index("### 05 — implement"):body.index("### 06 — sync back")]


def test_g1_the_gate_exists_and_names_all_four_checks():
    block = step_05()
    check("G1 step 05 has a deterministic gate section",
          "The free gate runs first" in block, "")
    missing = [c for c in FREE_CHECKS if c not in block.lower()]
    check("G1 it names build, test, lint and typecheck", not missing, missing)
    check("G1 and says the gate costs nothing",
          "0 tokens" in block or "costs nothing" in block.lower(), "")


def test_g2_the_free_gate_precedes_the_reviewer():
    block = step_05()
    # Compare the two HEADINGS, not the first mention of each. The gate section
    # contains a diagram that names the reviewer, so comparing first-mentions
    # put both inside one block and passed however they were ordered -- which is
    # how the first draft of this test passed a mutation that moved the gate
    # after the dispatch.
    gate = block.find("#### ⛔ The free gate runs first")
    reviewer = block.find("#### Then, and only then, the reviewer")
    check("G2 the gate section exists", gate >= 0, gate)
    check("G2 the reviewer has a step of its own, not just a mention",
          reviewer >= 0, reviewer)
    if gate < 0 or reviewer < 0:
        return
    check("G2 the gate section comes before the dispatch section",
          gate < reviewer, (gate, reviewer))
    check("G2 the dispatch really invokes the reviewer",
          "superpowers:requesting-code-review" in block[reviewer:], "")
    check("G2 and the rule is stated outright, not implied",
          "never be dispatched over code that does not compile" in block, "")
    check("G2 a failed gate skips the dispatch entirely",
          "this step does not run at all" in block[reviewer:], "")


def test_g3_a_failed_gate_returns_work_rather_than_reporting_it():
    block = step_05()
    flat = re.sub(r"\s+", " ", block)
    check("G3 a failing gate sends the work back to the worker",
          "back to the worker" in flat, "")
    check("G3 it is not recorded as a finding or a deviation",
          "not a finding" in flat and "not a deviation" in flat, "")
    check("G3 and it is named as unfinished work",
          "unfinished work" in flat, "")


def test_g4_the_command_comes_from_the_repository():
    block = re.sub(r"\s+", " ", step_05())
    check("G4 the command is read from the repository",
          "comes from the repository, never from a guess" in block, "")
    check("G4 the preflight group that locates it is named",
          "--groups testcmd" in block, "")
    pre = read(PREFLIGHT)
    # Both halves: declared in GROUPS and wired into CHECKS. Searching for the
    # bare name matched a renamed function, so this reads the two structures.
    groups = re.search(r"GROUPS = \(([^)]*)\)", pre)
    checks = re.search(r"CHECKS = \{(.*?)\n\}", pre, re.S)
    check("G4 testcmd is declared in GROUPS",
          bool(groups) and '"testcmd"' in groups.group(1), "")
    check("G4 and wired into CHECKS",
          bool(checks) and '"testcmd": lambda' in checks.group(1), "")
    check("G4 with a checker that exists",
          "\ndef check_testcmd(" in pre, "")
    check("G4 preflight reports where the command is written, not what it is",
          "never what it is" in pre, "")
    check("G4 inferring npm test from a package.json is forbidden",
          "Never infer `npm test`" in block, "")


def test_g5_skip_means_ask_once():
    block = re.sub(r"\s+", " ", step_05())
    check("G5 SKIP is handled explicitly", "`SKIP` means ask, once" in block, "")
    check("G5 the answer is recorded so it is asked once",
          "<chain-dir>/testcmd" in block, "")
    check("G5 and asked inside the existing step-00 block, not as a new gate",
          "same block as the other" in block, "")
    pre = read(PREFLIGHT)
    check("G5 preflight returns SKIP rather than guessing",
          'Result("SKIP", "test command"' in pre, "")


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
