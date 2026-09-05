#!/usr/bin/env python3
"""The anchor gate: a gap that names no real line is not a finding.

`gap-design` is the one role allowed to say where a change would go, which makes
it the most useful output of this toolkit and the easiest to fabricate. "Add a
column to the `estimates` table" reads exactly like analysis and costs a week
when that table does not exist.

So the rule is not advice in a prompt, it is a check that opens the file:

  * a GAP row with no <path>:<line>          -> fail
  * a GAP row anchored to a file that is gone -> fail
  * a GAP row anchored past the end of a file -> fail
  * a GAP row carrying an effort estimate     -> fail

The last one is here because an estimate produced without team context gets
quoted downstream as though it were measured.

Run:  python3 skills/spec-recon/tests/test_gap_anchor.py
"""
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
CHECK = os.path.join(ROOT, "skills", "docs-review", "scripts", "check_report.py")
FIX = os.path.join(ROOT, "skills", "docs-review", "tests", "fixtures")
AGENT = os.path.join(ROOT, "agents", "spec-recon-gap-design.md")

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def lint(fixture):
    p = subprocess.Popen([sys.executable, CHECK, os.path.join(FIX, fixture)],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, _ = p.communicate()
    return p.returncode, out.decode("utf-8")


def test_an_anchored_gap_passes():
    rc, out = lint("gap-anchored.md")
    check("a gap anchored to a real line is accepted", "R4" not in out, out)
    check("the anchored fixture lints clean", rc == 0, out)


def test_a_gap_with_no_anchor_fails():
    rc, out = lint("gap-unanchored.md")
    check("an unanchored gap fails the lint", rc == 1, "rc=%d" % rc)
    check("G-001 (no path:line at all) is caught",
          re.search(r"R4 gap-unanchored: G-001", out) is not None, out)


def test_a_gap_anchored_to_a_missing_file_fails():
    _rc, out = lint("gap-unanchored.md")
    check("G-002 (file does not exist) is caught",
          re.search(r"R4 gap-unanchored: G-002.*no such file", out) is not None, out)


def test_a_gap_anchored_past_end_of_file_fails():
    _rc, out = lint("gap-unanchored.md")
    check("G-003 (line beyond the file) is caught",
          re.search(r"R4 gap-unanchored: G-003.*lines", out) is not None, out)


def test_a_gap_carrying_an_effort_estimate_fails():
    _rc, out = lint("gap-unanchored.md")
    check("G-004 (effort estimate) is caught",
          re.search(r"R4 gap-estimated: G-004", out) is not None, out)


def test_the_agent_body_states_the_anchor_rule_and_its_escape():
    body = io.open(AGENT, encoding="utf-8").read()
    check("the body requires an anchor to be a line it read",
          "must be a line you opened and read" in body)
    check("the body routes an unanchorable gap to UNKNOWN",
          "you do **not** emit `GAP`" in body, body[:1])
    check("the body forbids effort estimates", "Never estimate effort" in body)
    check("the body forbids writing code", "Never write code" in body)
    check("the body carries the slice escape hatch", "NEEDS-WIDER" in body)
    check("the body is not given the specification",
          "not** given the specification" in body)
    words = len(body.split())
    check("the body fits the per-spawn budget", words <= 800, "%d words" % words)


def test_the_role_is_registered_where_the_lead_will_look():
    contracts = io.open(os.path.join(ROOT, "skills", "spec-recon", "references",
                                     "probe-contracts.md"), encoding="utf-8").read()
    check("gap-design has a row in the role table",
          "`ktkit:spec-recon-gap-design`" in contracts)
    arb = io.open(os.path.join(ROOT, "skills", "spec-recon", "references",
                               "arbitration.md"), encoding="utf-8").read()
    check("arbitration routes UPHELD onward to it",
          "spec-recon-gap-design" in arb)
    check("arbitration says a GAP row is input to feat-req-specs, not a decision",
          "feat-req-specs" in arb)
    check("arbitration says it never runs in parallel with the arbiter",
          "never runs in parallel" in arb)


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
