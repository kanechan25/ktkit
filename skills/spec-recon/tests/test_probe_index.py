#!/usr/bin/env python3
"""The search happens in a script, so the agent judges instead of sweeping.

`probe-code` was the most expensive role in the fleet and should have been the
cheapest. Its question is small -- does this identifier exist, and where -- but
the search ran *inside* the agent. Measured on a real repository: `src/` holds
14,627 tracked files, and one `Grep` for `export` returns 15,358 matching lines
across 3,801 files. That lands in the agent's context and an agentic loop
re-sends everything accumulated on every later call, so one unlucky search is
worth hundreds of thousands of tokens and keeps being paid for. A run reached
7.5M with `probe-code` skipped after being warned it would pass 8M -- the
questions it would have answered went unanswered, which is the expensive outcome.

  P1  every identifier gets a count, and the count is never capped
  P2  rows are capped, and the elision is stated rather than silent
  P3  zero occurrences are settled here -- no agent needed
  P4  the script states counts and lines, never EXISTS or NOT_FOUND
  P5  every row carries the command that produced it
  P6  --variants searches the spellings another house would have used
  P7  a search that failed is neither present nor absent
  P8  the planner no longer sizes the code fleet from the document count

P4 is the boundary that keeps this from being a shortcut. A count is a
measurement; what an absence *means* is a judgement, and moving the judgement
into a script would be trading cost for exactly the kind of confident wrong
answer this toolkit exists to prevent.

P8 is the defect that made it expensive in the first place: the number of
code-probe agents was `ceil_div(len(docs), 3)` -- derived from how many
*documents* there were, a quantity with nothing to do with how much code needs
looking at -- and those agents were handed no paths at all.

Run:  python3 skills/spec-recon/tests/test_probe_index.py
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SCRIPT = os.path.join(ROOT, "skills", "spec-recon", "scripts", "probe_index.py")
PLANNER = os.path.join(ROOT, "skills", "spec-recon", "scripts", "plan_fleet.py")
AGENT = os.path.join(ROOT, "agents", "spec-recon-probe-code.md")

sys.path.insert(0, os.path.join(ROOT, "skills", "spec-recon", "scripts"))
import probe_index                                            # noqa: E402

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


class Tree(object):
    """A small tree with known contents, so counts are checkable by hand."""

    FILES = {
        "src/a.cs": "public class Widget { }\nvar widget = new Widget();\n",
        "src/b.cs": "// widget mentioned in a comment\nWidget w;\n",
        "src/deep/c.ts": "export const widget = 1;\nexport const other = 2;\n",
        "src/snake.py": "widget_count = 0\nWIDGET_MAX = 9\n",
        "docs/notes.md": "widget appears here too\n",
    }

    def __enter__(self):
        self.d = tempfile.mkdtemp(prefix="probeidx-")
        for rel, body in self.FILES.items():
            p = os.path.join(self.d, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            io.open(p, "w", encoding="utf-8").write(body)
        return self

    def __exit__(self, *_exc):
        shutil.rmtree(self.d, ignore_errors=True)


def test_p1_every_identifier_gets_an_uncapped_count():
    with Tree() as t:
        rc, out = run("--repo", t.d, "--paths", "src", "--max-hits", "1",
                      "--ids", "widget", "Widget", "nosuchthing")
        check("P1 the index runs", rc == 0, out[:200])
        check("P1 it reports a total across identifiers",
              "occurrence(s) found" in out, out[:200])
        # widget: a.cs x1, b.cs x1, c.ts x1, snake.py x1 (case-sensitive)
        rows, _cmd, err = probe_index.search(t.d, "widget", ["src"], False)
        check("P1 the raw search is case-sensitive and complete",
              err is None and len(rows) == 4, (len(rows), err))
        check("P1 the cap did not change the count",
              "counted but not listed" in out, out[:300])


def test_p2_the_cap_is_stated_not_silent():
    with Tree() as t:
        rep = os.path.join(t.d, "idx.md")
        rc, out = run("--repo", t.d, "--paths", "src", "--max-hits", "2",
                      "--ids", "widget", "--out", rep)
        check("P2 exits 0", rc == 0, out[:200])
        body = io.open(rep, encoding="utf-8").read()
        check("P2 the report names how many rows it elided",
              "further occurrences are not listed" in body, body[:600])
        check("P2 and says the count is the measurement",
              "the measurement" in body, body[:900])
        listed = body.count("| `src/")
        check("P2 exactly the cap was listed", listed == 2, listed)


def test_p3_zero_occurrences_need_no_agent():
    with Tree() as t:
        rep = os.path.join(t.d, "idx.md")
        rc, out = run("--repo", t.d, "--paths", "src",
                      "--ids", "nosuchidentifier", "--out", rep)
        check("P3 exits 0", rc == 0, out[:200])
        check("P3 stdout says an agent is not needed",
              "no agent needed" in out, out[:300])
        body = io.open(rep, encoding="utf-8").read()
        check("P3 the report has a zero-occurrence section",
              "## Zero occurrences" in body, body[:400])
        check("P3 it still prints the commands it ran",
              "grep" in body, body[:600])
        check("P3 and leaves the meaning to the agent",
              "no agent" in body and "judgement" in body, body[:800])


def test_p4_the_script_never_returns_a_verdict():
    with Tree() as t:
        rep = os.path.join(t.d, "idx.md")
        run("--repo", t.d, "--paths", "src", "--ids", "widget", "nosuch",
            "--out", rep)
        body = io.open(rep, encoding="utf-8").read()
        for verdict in ("EXISTS", "NOT_FOUND", "PARTIAL"):
            # The words may appear in the sentence that forbids them, but never
            # as a row value.
            bad = [l for l in body.split("\n")
                   if l.startswith("|") and verdict in l]
            check("P4 no row states %s" % verdict, not bad, bad[:2])
        check("P4 the report says verdicts are the agent's",
              "makes none" in body or "agent's" in body, body[:400])
        src = io.open(SCRIPT, encoding="utf-8").read()
        check("P4 the script says so where the next reader looks",
              "never `EXISTS`, never `NOT_FOUND`" in src)


def test_p5_every_row_is_reproducible():
    with Tree() as t:
        rep = os.path.join(t.d, "idx.md")
        run("--repo", t.d, "--paths", "src", "--ids", "widget", "--out", rep)
        body = io.open(rep, encoding="utf-8").read()
        check("P5 the command is printed", "grep" in body, body[:600])
        check("P5 the report says any row can be re-run",
              "re-run" in body, body[:400])


def test_p6_variants_cover_the_other_spellings():
    v = probe_index.variants("retryBudgetMs")
    for want in ("retryBudgetMs", "retry_budget_ms", "retry-budget-ms",
                 "RetryBudgetMs"):
        check("P6 %s is searched" % want, want in v, v)
    check("P6 a single-word identifier is not expanded",
          probe_index.variants("widget") == ["widget"],
          probe_index.variants("widget"))
    with Tree() as t:
        rc, out = run("--repo", t.d, "--paths", "src", "--variants",
                      "--ids", "widgetCount")
        check("P6 --variants finds the snake_case spelling", rc == 0, out[:200])
        check("P6 and reports occurrences rather than zero",
              "1 occurrence" in out or "occurrence(s) found" in out, out[:200])


def test_p7_a_failed_search_is_not_an_absence():
    src = io.open(SCRIPT, encoding="utf-8").read()
    check("P7 errors are collected per identifier", '"errors": errs' in src)
    check("P7 a failed search gets its own section",
          "Could not be searched" in src)
    check("P7 and is called not-accessed rather than a finding",
          "not-accessed" in src)


def test_p8_the_planner_no_longer_sizes_code_probes_from_documents():
    body = io.open(PLANNER, encoding="utf-8").read()
    # Only executable lines: the comment above the change quotes the old formula
    # to explain why it went, and matching that would flag the explanation --
    # the same mistake this suite made once already.
    code = [l for l in body.split("\n") if l.strip() and not l.lstrip().startswith("#")]
    check("P8 the document-count formula is gone from the code",
          not [l for l in code if "ceil_div(len(docs)" in l],
          [l for l in code if "ceil_div(len(docs)" in l])
    check("P8 the reason is recorded next to the change",
          "with nothing to do with how much" in body)
    check("P8 the plan defers sizing until the index exists",
          "SIZE AFTER THE INDEX" in body)
    agent = io.open(AGENT, encoding="utf-8").read()
    check("P8 the agent is told to read the index first",
          "01c-code-index.md" in agent)
    check("P8 and told not to redo the sweep",
          "never to redo its sweep" in agent)
    check("P8 the agent body is still inside its budget",
          len(agent.split()) <= 800, len(agent.split()))


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
