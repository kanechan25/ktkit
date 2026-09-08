#!/usr/bin/env python3
"""A ledger row has an age, a lookup is counted, and a sibling run is a lead.

Three things the ledger did not do, each of which had a cost:

  * **A row had no age.** A conclusion is only as current as the tree it was
    drawn from, and nothing recorded which tree that was -- so there was no way
    to ask whether a row citing code survived forty commits, and no safe way to
    reuse one from another run.
  * **The lookup was an assertion.** `references/self-loop.md` lists it as one of
    five places the tokens are saved and gives the arithmetic, 6,619 per spawn
    against one grep. Nothing counted the hits, so the saving was never a figure.
  * **Every run started from nothing.** Two runs on related requirements
    re-derive the same answers.

  L1  --add stamps `At` and `Head`
  L2  a seven-column ledger still parses, as having no provenance
  L3  a HIT reports when the row was settled
  L4  --record counts lookups; --cache-metric reports a floor and says so
  L5  near-misses are listed, because they are the threshold's only evidence
  L6  a sibling row is FOREIGN with exit 2 -- neither HIT nor MISS
  L7  scope `run` cannot see a sibling at all

L6 is the safety property. A row settled last week may be stale, and a wrong HIT
is worse than a MISS: the chain cites an answer to a question nobody asked now
and stops looking. So `FOREIGN` gets its own exit code, is printed with its
provenance, and the text says outright that it closes nothing.

Run:  python3 skills/chain/tests/test_ledger_provenance.py
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
LEDGER = os.path.join(ROOT, "skills", "chain", "scripts", "ledger.py")

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def run(*args):
    p = subprocess.Popen([sys.executable, LEDGER] + list(args),
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = p.communicate()
    return p.returncode, out.decode("utf-8")


class Dir(object):
    """A `prompts/<rel>/` with room for sibling runs."""

    def __enter__(self):
        self.d = tempfile.mkdtemp(prefix="ledger-")
        self.rel = os.path.join(self.d, "rel")
        os.makedirs(self.rel)
        return self

    def __exit__(self, *_exc):
        shutil.rmtree(self.d, ignore_errors=True)

    def run_dir(self, name):
        p = os.path.join(self.rel, name)
        os.makedirs(p, exist_ok=True)
        led = os.path.join(p, "resolved.md")
        run(led, "--init")
        return led

    def add(self, led, ident, question, conclusion, **kw):
        argv = [led, "--add", "--id", ident, "--question", question,
                "--tier", kw.pop("tier", "T1"), "--conclusion", conclusion,
                "--evidence", kw.pop("evidence", "src/x.py:1"),
                "--phase", kw.pop("phase", "A")]
        for k, v in kw.items():
            argv += ["--" + k.replace("_", "-"), v]
        rc, out = run(*argv)
        assert rc == 0, out
        return out


def test_l1_a_row_is_stamped_with_when_and_against_what():
    with Dir() as d:
        led = d.run_dir("run-a")
        d.add(led, "Q01", "who owns the retry policy", "the gateway team",
              head="abc1234")
        body = io.open(led, encoding="utf-8").read()
        row = [l for l in body.split("\n") if l.startswith("| Q01")]
        check("L1 the row was written", row, body[-300:])
        if row:
            cells = [c.strip() for c in row[0].strip().strip("|").split("|")]
            check("L1 nine columns now", len(cells) == 9, cells)
            check("L1 the timestamp looks like an ISO stamp",
                  cells[7].count("-") == 2 and "T" in cells[7], cells[7])
            check("L1 the commit is recorded", cells[8] == "abc1234", cells[8])
        check("L1 the header names both columns",
              "| At | Head |" in body, body[:400])


def test_l2_a_seven_column_ledger_still_parses():
    """Refusing it would crash `--resume` on any run started earlier."""
    with Dir() as d:
        led = d.run_dir("legacy")
        io.open(led, "a", encoding="utf-8").write(
            "| Q09 | an older question | T1 | settled long ago | src/a:1 | — | A |\n")
        rc, out = run(led, "--lookup", "an older question")
        check("L2 the legacy row is found, not refused", rc == 0, out[:200])
        check("L2 and it is not reported as having provenance",
              "settled" not in out.split("—")[-1], out[:200])
        rc, out = run(led, "--next-id")
        check("L2 ids still allocate over a legacy ledger", rc == 0, out[:120])


def test_l3_a_hit_reports_when_the_row_was_settled():
    with Dir() as d:
        led = d.run_dir("run-a")
        d.add(led, "Q01", "who owns the retry policy", "the gateway team",
              head="abc1234")
        rc, out = run(led, "--lookup", "which team owns retry policy")
        check("L3 the lookup hits", rc == 0, out[:200])
        check("L3 the hit carries the commit", "abc1234" in out, out[:200])
        check("L3 and the date", "settled" in out, out[:200])


def test_l4_the_lookup_is_counted_and_reported_as_a_floor():
    with Dir() as d:
        led = d.run_dir("run-a")
        d.add(led, "Q01", "who owns the retry policy", "the gateway team")
        rc, _out = run(led, "--cache-metric")
        chk = run(led, "--cache-metric")[1]
        check("L4 with nothing recorded it says so", "NO-LOOKUPS" in chk, chk[:200])
        check("L4 and points at --record", "--record" in chk, chk[:200])
        run(led, "--lookup", "which team owns retry policy", "--record")
        run(led, "--lookup", "what is the deploy cadence", "--record")
        log = os.path.join(os.path.dirname(led), "lookup.jsonl")
        check("L4 a log was written", os.path.isfile(log))
        rows = [json.loads(l) for l in io.open(log, encoding="utf-8") if l.strip()]
        check("L4 both lookups are recorded", len(rows) == 2, rows)
        check("L4 with their verdicts",
              sorted(r["verdict"] for r in rows) == ["HIT", "MISS"], rows)
        rc, out = run(led, "--cache-metric")
        check("L4 the metric runs", rc == 0, out[:200])
        check("L4 it counts the hits", "hits=1" in out, out[:300])
        check("L4 it derives tokens not spent", "6,619" in out, out[:300])
        check("L4 labelled derived", "[derived" in out, out[:300])
        check("L4 ⭐ and calls itself a floor", "FLOOR" in out.upper(), out[:400])


def test_l5_near_misses_are_listed():
    with Dir() as d:
        led = d.run_dir("run-a")
        d.add(led, "Q01", "who owns the retry policy for exports",
              "the gateway team")
        # Measured against this row: 0.500, inside the 0.45-0.60 band and under
        # the 0.6 threshold. Picked by asking `similarity` rather than guessing,
        # because a fixture that lands outside the band tests nothing.
        run(led, "--lookup", "who owns the policy", "--record")
        rc, out = run(led, "--cache-metric")
        check("L5 the metric runs", rc == 0, out[:200])
        check("L5 near-misses are surfaced", "near-misses" in out, out[:500])
        check("L5 with the score that nearly hit", "0.50" in out, out[:600])
        check("L5 and the warning about moving the threshold",
              "threshold" in out, out[:700])


def test_l6_a_sibling_row_is_a_lead_not_an_answer():
    with Dir() as d:
        a = d.run_dir("run-a")
        d.add(a, "Q01", "who owns the retry policy", "the gateway team",
              head="abc1234")
        b = d.run_dir("run-b")
        rc, out = run(b, "--lookup", "which team owns retry policy",
                      "--ledger-scope", "dir", "--record")
        check("L6 exit 2 — neither HIT nor MISS", rc == 2, "rc=%d %s" % (rc, out[:200]))
        check("L6 the verdict is FOREIGN", "FOREIGN" in out, out[:200])
        check("L6 it names the run it came from", "run-a" in out, out[:300])
        check("L6 and when it was settled, against what",
              "abc1234" in out, out[:300])
        check("L6 ⭐ it says outright that it is not a conclusion",
              "NOT a conclusion" in out, out[:400])
        check("L6 and why a wrong HIT would be worse",
              "stops looking" in out, out[:500])
        log = os.path.join(os.path.dirname(b), "lookup.jsonl")
        rows = [json.loads(l) for l in io.open(log, encoding="utf-8") if l.strip()]
        check("L6 the FOREIGN lookup is recorded as such",
              rows and rows[0]["verdict"] == "FOREIGN", rows)


def test_l7_scope_run_cannot_see_a_sibling():
    with Dir() as d:
        a = d.run_dir("run-a")
        d.add(a, "Q01", "who owns the retry policy", "the gateway team")
        b = d.run_dir("run-b")
        rc, out = run(b, "--lookup", "which team owns retry policy")
        check("L7 the default scope misses", rc == 1, "rc=%d %s" % (rc, out[:200]))
        check("L7 and says nothing about the sibling",
              "run-a" not in out and "FOREIGN" not in out, out[:200])


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
