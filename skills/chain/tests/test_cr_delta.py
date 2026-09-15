#!/usr/bin/env python3
"""A change request knows what it undoes, or it stops.

`cr_delta.py` answers one question the rest of the pipeline cannot: a
requirement changed, so which already-finished work is now wrong? It answers it
from the run's task-state ledger rather than by re-reading the repository,
because every task recorded what it satisfied and what it touched at the moment
it finished.

The three stops are the design. A script that guessed its way past any of them
would produce a confident answer to a question only a person can settle:

  D1  a CR without both halves of the delta is refused, and the old behaviour is
      NOT reconstructed from anywhere
  D2  contradicted stops the run (exit 1) -- including the case a word-overlap
      score misses, where the new statement is the old one with the "not" taken
      out and three clauses added
  D3  an invalidation nobody can cite stops the run (exit 2)
  D4  a change reaching most of the plan stops the run (exit 3) -- it is a new
      requirement wearing a change request's clothes
  D5  `untouched` really is untouched: a task citing an unrelated requirement is
      not swept up
  D6  `impact.files` comes from the ledger's `touched` column and the repository
      is never consulted
  D7  invalidated and superseded are kept apart -- built-and-wrong needs code
      unwound, never-built needs a row rewritten

D6 is checked by running against a ledger whose `touched` paths do not exist on
disk. If the script ever started verifying them, that test fails -- which is the
point, because verifying them is the expensive pass this whole script exists to
avoid.

Run:  python3 skills/chain/tests/test_cr_delta.py
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
CR_DELTA = os.path.join(ROOT, "scripts", "cr_delta.py")
LEDGER = os.path.join(ROOT, "skills", "chain", "scripts", "ledger.py")

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def write(path, text):
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def ledger(path, *args):
    p = subprocess.Popen([sys.executable, LEDGER, path] + list(args),
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = p.communicate()
    return p.returncode, out.decode("utf-8")


def run(cr, spec, led, *extra):
    p = subprocess.Popen(
        [sys.executable, CR_DELTA, "--cr", cr, "--spec", spec,
         "--ledger", led, "--json"] + list(extra),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = p.communicate()
    text = out.decode("utf-8")
    try:
        return p.returncode, json.loads(text)
    except ValueError:
        return p.returncode, {"RAW": text}


def cr_file(d, old, new, name="cr.md"):
    return write(os.path.join(d, name),
                 "---\ntype: CR\n---\n\n"
                 "## §1. Vấn đề trong một câu\nsomething\n\n"
                 "## §2. Hiện trạng — behavior CŨ (bắt buộc)\n%s\n\n"
                 "## §3. Kỳ vọng — behavior MỚI (bắt buộc)\n%s\n"
                 % (old, new))


def spec_file(d, reqs):
    return write(os.path.join(d, "spec.md"),
                 "# Spec\n" + "".join("- %s: something\n" % r for r in reqs))


def seeded(d, tasks):
    """tasks: [(id, final_state, spec_refs, touched)]"""
    led = os.path.join(d, "resolved.md")
    for tid, state, refs, touched in tasks:
        chain = {"pending": ["pending"], "ready": ["ready"],
                 "running": ["ready", "running"],
                 "done": ["ready", "running", "done"]}[state]
        for step in chain:
            args = ["--task-state", "--id", tid, "--set", step]
            if refs:
                args += ["--spec-refs", refs]
            if touched:
                args += ["--touched", touched]
            rc, out = ledger(led, *args)
            if rc != 0:
                raise AssertionError("seed %s %s: %s" % (tid, step, out))
    return led


def test_d1_a_cr_without_both_halves_is_refused():
    d = tempfile.mkdtemp()
    try:
        bad = write(os.path.join(d, "bad.md"),
                    "---\ntype: CR\n---\n\n## §1. Vấn đề\nonly one section\n")
        spec = spec_file(d, ["FR-1"])
        led = seeded(d, [("T01", "done", "FR-1", "src/a.ts")])
        rc, res = run(bad, spec, led)
        check("D1 a CR with no §2/§3 exits 2", rc == 2, (rc, res))
        check("D1 and says what is missing",
              "not-a-cr" in res.get("RAW", ""), res.get("RAW", "")[:160])
        check("D1 it does not reconstruct the old behaviour from anywhere",
              "delta" not in res, sorted(res))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_d2_a_contradiction_stops_the_run():
    d = tempfile.mkdtemp()
    try:
        # The hard case on purpose: word overlap alone scores this 0.31, because
        # the new statement adds three clauses. Only comparing them with the
        # polarity words removed catches it.
        cr = cr_file(d,
                     "- The owner cannot change the expiry.",
                     "- The owner can change the expiry to at most 7 days (FR-2).")
        spec = spec_file(d, ["FR-1", "FR-2"])
        led = seeded(d, [("T01", "ready", "FR-9", "")])
        rc, res = run(cr, spec, led)
        check("D2 a contradiction exits 1", rc == 1, (rc, res))
        names = [s["name"] for s in res.get("stops", [])]
        check("D2 the stop is named contradicted", "contradicted" in names, names)
        rows = res["delta"]["contradicted"]
        check("D2 one contradiction, with both statements", len(rows) == 1, rows)
        check("D2 and it is not also counted as added or removed",
              not res["delta"]["added"] and not res["delta"]["removed"],
              res["delta"])
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_d3_an_invalidation_nobody_can_cite_stops_the_run():
    """A DONE task with no spec_refs is unknown, not untouched.

    `--set done` has demanded spec_refs since the task state existed, so a row
    without them predates that rule. It cannot be cleared and it cannot be
    explained, and "cannot tell" is a stop rather than a silent pass -- the
    difference between untouched and unknown is that somebody checked.
    """
    d = tempfile.mkdtemp()
    try:
        cr = cr_file(d, "- Export runs nightly (FR-1).",
                     "- Export runs hourly (FR-1).")
        spec = spec_file(d, ["FR-1"])
        led = seeded(d, [("T01", "done", "FR-1", "src/export.ts"),
                         ("T02", "ready", "FR-7", "")])
        rc, res = run(cr, spec, led)
        inval = res["impact"]["tasks"]["invalidated"]
        check("D3 the done task is invalidated", len(inval) == 1, inval)
        check("D3 and the invalidation cites the requirement that killed it",
              inval and inval[0]["by"] == ["FR-1"], inval)
        check("D3 a citable invalidation does not trigger stop 2",
              "uncitable-invalidation" not in
              [s["name"] for s in res.get("stops", [])], res.get("stops"))

        # A ledger written before spec_refs were mandatory: the row is appended
        # by hand, exactly as an older run would have left it.
        legacy = tempfile.mkdtemp()
        led2 = seeded(legacy, [("T01", "done", "FR-1", "a.ts"),
                               ("T02", "ready", "FR-1", "")])
        with io.open(os.path.join(legacy, "task-state.md"), "a",
                     encoding="utf-8") as fh:
            fh.write("| T09 | done | — | old/file.ts | — | 2026-01-01T00:00:00 | |\n")
        rc2, res2 = run(cr, spec, led2)
        names = [s["name"] for s in res2.get("stops", [])]
        check("D3 an uncitable done task stops the run",
              "uncitable-invalidation" in names, names)
        check("D3 with exit 2", rc2 == 2, (rc2, names))
        stop = [s for s in res2["stops"]
                if s["name"] == "uncitable-invalidation"][0]
        check("D3 and it names which task", stop["rows"] == ["T09"], stop)
        check("D3 it is not quietly filed as untouched",
              "T09" not in res2["impact"]["tasks"]["untouched"],
              res2["impact"]["tasks"])
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_d4_a_change_reaching_most_of_the_plan_stops_the_run():
    d = tempfile.mkdtemp()
    try:
        cr = cr_file(d, "- Export runs nightly (FR-1).",
                     "- Export runs hourly (FR-1).")
        spec = spec_file(d, ["FR-1"])
        led = seeded(d, [("T01", "done", "FR-1", "a.ts"),
                         ("T02", "ready", "FR-1", ""),
                         ("T03", "ready", "FR-1", "")])
        rc, res = run(cr, spec, led)
        check("D4 reaching every task exits 3", rc == 3, (rc, res.get("stops")))
        names = [s["name"] for s in res.get("stops", [])]
        check("D4 the stop says it is not a change request",
              "not-a-change-request" in names, names)
        stop = [s for s in res["stops"] if s["name"] == "not-a-change-request"][0]
        check("D4 and it reports the share rather than asserting it",
              stop.get("reached") == 3 and stop.get("total") == 3, stop)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_d5_untouched_really_is_untouched():
    d = tempfile.mkdtemp()
    try:
        cr = cr_file(d, "- Export runs nightly (FR-1).",
                     "- Export runs hourly (FR-1).")
        spec = spec_file(d, ["FR-1", "FR-2", "FR-3"])
        led = seeded(d, [("T01", "done", "FR-1", "a.ts"),
                         ("T02", "done", "FR-2", "b.ts"),
                         ("T03", "ready", "FR-3", "")])
        rc, res = run(cr, spec, led)
        t = res["impact"]["tasks"]
        check("D5 only the task citing FR-1 is invalidated",
              [x["task"] for x in t["invalidated"]] == ["T01"], t)
        check("D5 the others are untouched",
              sorted(t["untouched"]) == ["T02", "T03"], t)
        check("D5 and nothing unrelated is superseded",
              t["superseded"] == [], t)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_d6_files_come_from_the_ledger_not_the_repository():
    d = tempfile.mkdtemp()
    try:
        cr = cr_file(d, "- Export runs nightly (FR-1).",
                     "- Export runs hourly (FR-1).")
        spec = spec_file(d, ["FR-1", "FR-2"])
        # These paths do not exist, anywhere. If the script ever verified them,
        # this list would come back empty -- and verifying them is the expensive
        # pass the whole design exists to avoid.
        led = seeded(d, [("T01", "done", "FR-1", "src/does/not/exist.ts:12"),
                         ("T02", "ready", "FR-2", "")])
        rc, res = run(cr, spec, led)
        check("D6 the file list comes straight from the ledger",
              res["impact"]["files"] == ["src/does/not/exist.ts:12"],
              res["impact"]["files"])
        body = io.open(CR_DELTA, encoding="utf-8").read()
        for forbidden in ("os.walk", "glob.", "subprocess"):
            check("D6 cr_delta.py never reaches for %s" % forbidden,
                  forbidden not in body, forbidden)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_d7_invalidated_and_superseded_are_different_answers():
    d = tempfile.mkdtemp()
    try:
        cr = cr_file(d, "- Export runs nightly (FR-1).",
                     "- Export runs hourly (FR-1).")
        spec = spec_file(d, ["FR-1", "FR-2", "FR-3", "FR-4"])
        led = seeded(d, [("T01", "done", "FR-1", "a.ts"),
                         ("T02", "running", "FR-1", ""),
                         ("T03", "ready", "FR-2", ""),
                         ("T04", "ready", "FR-3", ""),
                         ("T05", "ready", "FR-4", "")])
        rc, res = run(cr, spec, led)
        t = res["impact"]["tasks"]
        check("D7 the built task is invalidated, not superseded",
              [x["task"] for x in t["invalidated"]] == ["T01"], t)
        check("D7 the unbuilt one is superseded, not invalidated",
              [x["task"] for x in t["superseded"]] == ["T02"], t)
        patch = res["patch"]["tasks.md"]
        check("D7 the patch tells them apart",
              any("unwind or rework" in line for line in patch)
              and any("never built" in line for line in patch), patch)
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
