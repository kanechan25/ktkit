#!/usr/bin/env python3
"""The ledger is the only thing stopping the chain from re-asking itself.

Every property tested here corresponds to a way the chain would quietly get
worse rather than fail:

  * a lookup that misses a settled question => the resolver is spawned again,
    and the answer may come back different from the one already written into
    the artifact upstream;
  * a lookup that hits an OPEN row => the chain treats a question as an answer;
  * a superseded row that disappears => the record of what changed, and why,
    is gone, and the sync-back promise with it;
  * a T3.5 row with no falsifier => a guess wearing the label of an evidenced
    assumption, which is the one thing the ladder forbids;
  * a metric that is trusted rather than recomputed => the 0.70 floor stops
    meaning anything, which is exactly how the ratio failed before.

Run:  python3 skills/chain/tests/test_ledger.py
"""
import io
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(os.path.dirname(HERE), "scripts", "ledger.py")

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def run(path, *args):
    p = subprocess.Popen([sys.executable, LEDGER, path] + list(args),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate(timeout=20)
    return p.returncode, (out + err).decode("utf-8").strip()


def seed(path):
    """A ledger in the state a chain reaches part-way through phase B."""
    run(path, "--init")
    run(path, "--add", "--id", "Q01",
        "--question", "which handler owns the retry policy",
        "--tier", "T1", "--conclusion", "3 attempts, backoff 2^n",
        "--evidence", "src/http/client.ts:88", "--phase", "A")
    run(path, "--add", "--id", "Q02",
        "--question", "soft delete or hard delete for archived records",
        "--tier", "T3.5", "--conclusion", "soft",
        "--evidence", "migrations/004.sql:12",
        "--falsifier", "any row removed by a real DELETE", "--phase", "A")
    run(path, "--add", "--id", "Q03",
        "--question", "may an expired user still read old records",
        "--tier", "T4", "--phase", "B")


def test_ids_are_minted_in_sequence():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "resolved.md")
        rc, out = run(p, "--init")
        check("init creates the file", rc == 0 and os.path.exists(p), out)
        rc, out = run(p, "--next-id")
        check("the first id is Q01", out == "Q01", out)
        seed(p)
        rc, out = run(p, "--next-id")
        check("the next id follows the highest used", out == "Q04", out)


def test_a_reworded_question_still_hits():
    """The whole saving depends on this. An exact-string match would miss every
    time, because the phase that asks second phrases it its own way."""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "resolved.md")
        seed(p)
        rc, out = run(p, "--lookup", "who owns retry policy for the handler")
        check("a reworded question hits", rc == 0 and out.startswith("HIT"), out)
        check("the hit carries the citation", "src/http/client.ts:88" in out, out)


def test_an_unrelated_question_misses():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "resolved.md")
        seed(p)
        rc, out = run(p, "--lookup", "what timezone does the scheduler use")
        check("an unrelated question misses", rc == 1 and out.startswith("MISS"), out)


def test_an_open_question_is_never_a_hit():
    """An OPEN row is a question waiting on the user. Returning it as a hit
    would let the chain answer itself with its own unanswered question."""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "resolved.md")
        seed(p)
        rc, out = run(p, "--lookup", "may an expired user still read old records")
        check("an OPEN row does not hit even on an exact restatement",
              rc == 1, out)


def test_superseding_keeps_the_old_row():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "resolved.md")
        seed(p)
        rc, out = run(p, "--add", "--id", "Q02",
                      "--question", "soft delete or hard delete for archived records",
                      "--tier", "T1", "--conclusion", "hard, since the 004 migration",
                      "--evidence", "migrations/011.sql:4", "--phase", "C")
        check("superseding names the row it replaces", "supersedes" in out, out)
        text = io.open(p, encoding="utf-8").read()
        check("the old conclusion is still in the file", "soft" in text, text)
        check("the new conclusion is in the file too",
              "hard, since the 004 migration" in text, text)
        rc, out = run(p, "--lookup", "hard delete or soft delete for archived rows")
        check("lookup returns the newest belief",
              "migrations/011.sql:4" in out, out)


def test_a_t35_row_without_a_falsifier_is_refused():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "resolved.md")
        run(p, "--init")
        rc, out = run(p, "--add", "--id", "Q01", "--question", "rounding direction",
                      "--tier", "T3.5", "--conclusion", "half up")
        check("T3.5 with no falsifier exits 2", rc == 2, "rc=%d %s" % (rc, out))
        check("the row was not written",
              "Q01" not in io.open(p, encoding="utf-8").read())


def test_only_t4_may_be_open():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "resolved.md")
        run(p, "--init")
        rc, out = run(p, "--add", "--id", "Q01", "--question", "anything",
                      "--tier", "T1")
        check("a T1 row with no conclusion exits 2", rc == 2, "rc=%d %s" % (rc, out))


def test_the_metric_is_recomputed_and_gates():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "resolved.md")
        seed(p)
        rc, out = run(p, "--metric")
        check("2 self-resolved against 1 open is below the floor",
              rc == 1 and "0.67" in out and "BELOW-FLOOR" in out, out)

        # Answering the open question is what lifts the ratio -- not editing it.
        run(p, "--add", "--id", "Q03",
            "--question", "may an expired user still read old records",
            "--tier", "T4", "--conclusion", "no, reads stop at expiry",
            "--evidence", "user answered at the gate", "--phase", "B")
        rc, out = run(p, "--metric")
        check("answering the open row clears the floor",
              rc == 0 and "needs_user=0" in out, out)


def test_more_than_three_open_rows_is_not_a_gate():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "resolved.md")
        run(p, "--init")
        for i in range(1, 5):
            run(p, "--add", "--id", "Q%02d" % i,
                "--question", "open question number %d about scope" % i,
                "--tier", "T4", "--phase", "B")
        rc, out = run(p, "--metric")
        check("four open rows fail the gate check",
              rc == 1 and "TOO-MANY-OPEN" in out, out)


def test_a_malformed_ledger_is_reported_not_skipped():
    """A row that cannot be parsed means an unknown the chain would re-open
    without noticing. Failing loudly is the only safe answer."""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "resolved.md")
        seed(p)
        with io.open(p, "a", encoding="utf-8") as fh:
            fh.write("| Q99 | missing most of its columns |\n")
        rc, out = run(p, "--metric")
        check("a short row exits 2", rc == 2 and "malformed" in out, out)


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
