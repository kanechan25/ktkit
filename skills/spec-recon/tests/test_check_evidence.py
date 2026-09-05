#!/usr/bin/env python3
"""Tests for the evidence linter.

The linter is the only thing standing between a probe's output and a reviewer
who will read it as a document. Two failures matter enough to be locked down:

  * a derived number presented as an observation, which has already caused a
    retraction mid-run;
  * a file with nothing traceable in it, which reads exactly like a finished
    measurement and is an opinion.

A clean fixture that starts failing is as much a bug as a dirty one that starts
passing: a linter that cries wolf gets switched off, and then it protects
nothing.

Run:  python3 skills/spec-recon/tests/test_check_evidence.py
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
FIX = os.path.join(HERE, "fixtures")
sys.path.insert(0, os.path.join(SKILL, "scripts"))

import check_evidence as ce                                    # noqa: E402

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def kinds(path):
    return [k for k, _f, _l, _d in ce.problems_for(path)]


def test_clean_evidence_passes():
    k = kinds(os.path.join(FIX, "evidence-clean.md"))
    check("a well formed evidence file reports nothing", k == [], k)


def test_mixed_label_is_caught():
    k = kinds(os.path.join(FIX, "evidence-mixed-label.md"))
    check("a row carrying two label kinds is caught", "MIXED-LABEL" in k, k)


def test_unlabelled_number_is_caught():
    k = kinds(os.path.join(FIX, "evidence-mixed-label.md"))
    check("a table row with a number and no label is caught", "NO-LABEL" in k, k)


def test_bare_not_accessed_is_caught():
    k = kinds(os.path.join(FIX, "evidence-mixed-label.md"))
    check("'Not accessed' with no reason is caught", "NO-ACCESS-NOTE" in k, k)


def test_untraceable_file_is_caught():
    k = kinds(os.path.join(FIX, "evidence-no-citation.md"))
    check("prose with no citation and no reproduce line is caught",
          "NO-CITATION" in k, k)


def test_a_reproduce_line_alone_is_enough_traceability():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "probe-x.md")
    with open(p, "w") as fh:
        fh.write("# X\n\nReproduce: `probe_xlsx.py a.xlsx --sheets`\n\n"
                 "| Property | Value | Label |\n| - | - | - |\n"
                 "| sheets | 5 | [measured] |\n")
    check("a Reproduce line satisfies traceability on its own",
          "NO-CITATION" not in kinds(p), kinds(p))


def test_fenced_blocks_are_not_linted():
    """Sample output inside a code fence is illustration, not a claim."""
    d = tempfile.mkdtemp()
    p = os.path.join(d, "probe-y.md")
    with open(p, "w") as fh:
        fh.write("# Y\n\nSource: `a/b.py:12`\n\n```text\n"
                 "| rows | 900 |\n| other | 42 |\n```\n")
    check("numbers inside a fence are not required to carry labels",
          "NO-LABEL" not in kinds(p), kinds(p))


def test_prose_numbers_are_not_required_to_carry_labels():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "probe-z.md")
    with open(p, "w") as fh:
        fh.write("# Z\n\nSource: `a/b.py:12`\n\n"
                 "There are 5 sheets in the workbook, described below.\n")
    check("prose is not held to the ledger rule",
          "NO-LABEL" not in kinds(p), kinds(p))


def test_exit_status_and_directory_walk():
    rc = ce.main([FIX, "--quiet"])
    check("a directory with dirty fixtures exits 1", rc == 1, "rc=%s" % rc)
    rc = ce.main([os.path.join(FIX, "evidence-clean.md"), "--quiet"])
    check("a clean file exits 0", rc == 0, "rc=%s" % rc)
    rc = ce.main(["/nonexistent/dir", "--quiet"])
    check("a missing path exits 2", rc == 2, "rc=%s" % rc)


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
