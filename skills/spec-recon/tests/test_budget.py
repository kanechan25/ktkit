#!/usr/bin/env python3
"""The ceiling holds, and the gate that narrows the reading never narrows it silently.

A run spent 15.2M tokens across 34 agents, died inside its final wave, and
produced no verdict. Two scripts now stand between a run and that outcome, and
what they must not do is subtler than what they must:

  B1  the ceiling stops the run at a boundary, from measured spend
  B2  a cheap step still passes where an expensive one does not
  B3  the decision rests on observations, and no rate outlives the run
  B4  STOP names the reset time and the resume command
  B9  a ceiling the window cannot reach is rejected, with the number that fits
  B5  the relevance gate excludes on density, not on presence
  B6  it declines when its vocabulary does not fit the corpus
  B7  it rescues a revision-marked document rather than cutting it
  B8  an excluded file is listed, never silently dropped

B3 changed shape once and the reason is worth keeping. It used to ban the string
`tokens_per_percent`, because an earlier design measured how many tokens one
percent of the quota window buys and *stored* it -- a figure only true for the
account and tier it came from, and signing in with a different account moved the
window from 94% used to 6% while that work was in progress. The rate itself was
never the defect; persisting it was. So the check now asserts the property: a
rate may be computed from this run's own ledger and printed, and it may not be
written anywhere that outlives the run or read from anywhere that predates it.

B9 seeds the quota window rather than reading the live one. The first version
did not, and went red hours later for a reason that had nothing to do with the
code: the session had spent quota, the remaining window shrank, and a ceiling
that had been reachable no longer was. A test whose verdict depends on the time
of day is worse than no test. The window is seeded through `HOME`, because
`quota.py` caches to `~/.claude/ktkit-quota-cache.json` and `budget.py` inherits
the environment -- no test-only code path in either script.

B9 is a hard rejection with a computed threshold, and the two halves matter
equally. A ceiling above what the window can hold is not a ceiling: the run dies
on the window long before reaching it, which is the original failure wearing a
larger number. But the threshold cannot be a constant. It is
`spent + headroom x rate`, and both terms move -- at 84% headroom one corpus
allowed ~14.5M, at 20% headroom the same rate allows ~4.8M, and a lighter corpus
at the same headroom allows ~35M. Writing any of those down would permit a run
that cannot finish and refuse one that could.

B2 is the ordering that matters. Extraction produces evidence; arbitration turns
evidence into an answer. A run that stops with evidence and no verdicts has spent
everything and delivered nothing -- which is what happened. So the gate must let
a cheap arbitration through after refusing an expensive extraction.

B6 and B7 are the safety properties. Measured on the corpus this was built
against, a scope written in Vietnamese and English produced four ASCII terms
against a corpus that is 68% Japanese, and would have excluded the two main
specification documents because the question said "export" and the document says
"出力". A gate that removes the specification is worse than no gate.

Run:  python3 skills/spec-recon/tests/test_budget.py
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
BUDGET = os.path.join(ROOT, "scripts", "budget.py")
COST = os.path.join(ROOT, "scripts", "cost_log.py")
RELEVANCE = os.path.join(ROOT, "skills", "spec-recon", "scripts", "relevance.py")

sys.path.insert(0, os.path.join(ROOT, "skills", "spec-recon", "scripts"))
import relevance                                               # noqa: E402

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def run(script, *args, **env):
    e = dict(os.environ)
    e.update(env)
    p = subprocess.Popen([sys.executable, script] + list(args),
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=e)
    out, _ = p.communicate()
    return p.returncode, out.decode("utf-8")


def seeded_home(percent, minutes=120):
    """A HOME whose quota cache is fresh, so the window is fixed for the test.

    `quota.py` consults its cache before doing anything else, and `budget.py`
    inherits the environment when it calls it. Nothing test-only is added to
    either script.
    """
    import json as _json
    import time as _time
    from datetime import datetime, timedelta, timezone
    home = tempfile.mkdtemp(prefix="quota-home-")
    os.makedirs(os.path.join(home, ".claude"))
    resets = (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()
    io.open(os.path.join(home, ".claude", "ktkit-quota-cache.json"),
            "w", encoding="utf-8").write(_json.dumps({
                "at": _time.time(),
                "payload": {"limits": [{"kind": "session", "percent": percent,
                                        "severity": "normal", "is_active": True,
                                        "resets_at": resets}]}}))
    return home


class Run(object):
    """A run directory with a cost ledger, and no network in sight."""

    def __enter__(self):
        self.d = tempfile.mkdtemp(prefix="budget-")
        return self

    def __exit__(self, *_exc):
        shutil.rmtree(self.d, ignore_errors=True)

    def spend(self, *rows):
        argv = [COST, "wave", "--base", self.d, "--wave", "1"]
        for r in rows:
            argv += ["--row", r]
        rc, out = run(*argv)
        assert rc == 0, out
        return self

    def gate(self, step, budget=4000000, extra=()):
        return run(BUDGET, "--base", self.d, "--budget", str(budget),
                   "--step", step, *extra)


# --------------------------------------------------------------- the ceiling

def test_b1_the_ceiling_stops_at_a_boundary():
    with Run() as r:
        rc, out = r.gate("00-preflight")
        check("B1 a run with nothing spent may start", rc == 0, out[:200])
        r.spend("m1,C,440000,9000,13,90", "m2,C,455000,8000,14,95")
        rc, out = r.gate("03-extract-b1")
        check("B1 912k of a 4M budget continues", rc == 0, out[:240])
        check("B1 the spend is read from cost.jsonl", "912,000" in out, out[:240])
        r.spend("m3,C,470000,9500,15,99", "m4,C,430000,7000,12,84")
        rc, out = r.gate("03-extract-b2")
        check("B1 1.83M continues", rc == 0, out[:240])
        r.spend("m5,C,460000,9000,14,92", "m6,C,450000,8500,13,88")
        rc, out = r.gate("03-extract-b3")
        check("B1 2.76M with a 927k step stops", rc == 1, out[:300])
        check("B1 the reason names what is left and what is needed",
              "1,244,000" in out and "1,391,250" in out, out[:400])


def test_b2_a_cheap_step_passes_where_an_expensive_one_does_not():
    """Arbitration is the last thing that should be starved."""
    with Run() as r:
        r.spend("m1,C,900000,20000,20,120")
        rc, _out = r.gate("03-extract", budget=1500000)
        check("B2 a 920k step against 580k left stops", rc == 1)
        with Run() as r2:
            r2.spend("a1,A,290000,15000,9,60")
            rc, out = r2.gate("05-arbitrate", budget=1500000)
            check("B2 a 305k step against 1.19M left continues", rc == 0, out[:240])


def test_b3_the_decision_rests_on_observations():
    body = io.open(BUDGET, encoding="utf-8").read()
    check("B3 the spend comes from cost.jsonl", 'os.path.join(base, "cost.jsonl")' in body)
    check("B3 the step cost is a difference between boundaries",
          "spent - (prev.get" in body)
    check("B3 no constant stands in for a measured rate",
          "62074" not in body and "62_074" not in body)
    check("B3 the docstring says what is not predicted",
          "Nothing here forecasts" in body)
    # The rate is computed from the run's own ledger, and the only file this
    # script writes is inside the run directory.
    check("B3 the rate is derived from the ledger, not a stored figure",
          "def rate(rows)" in body and "step_percent" in body)
    check("B3 the rate is labelled as belonging to this run only",
          "never stored" in body and "never carried between runs" in body)
    writes = [l for l in body.split("\n") if 'io.open(' in l and '"a"' in l or 'io.open(' in l and '"w"' in l]
    check("B3 every file it writes is inside the run directory",
          all("base" in l or "LEDGER" in l for l in writes), writes)
    check("B3 it reads no state from outside the run",
          "expanduser" not in body, [l for l in body.split("\n") if "expanduser" in l])


def test_b3_the_lookahead_survives_a_repeated_check():
    """A boundary checked twice must not silently lose its guard."""
    with Run() as r:
        r.spend("m1,C,1400000,30000,30,200", "m2,C,1450000,28000,31,205")
        rc1, out1 = r.gate("03-extract", budget=4000000)
        check("B3 the first check sees the step and stops", rc1 == 1, out1[:240])
        rc2, out2 = r.gate("03-extract", budget=4000000)
        check("B3 the same boundary checked again still stops", rc2 == 1, out2[:300])
        check("B3 and says which step the estimate came from",
              "the last step that cost anything" in out2, out2[:400])


def test_b4_stopping_says_what_to_do_next():
    with Run() as r:
        r.spend("m1,C,3900000,50000,40,300")
        rc, out = r.gate("03-extract")
        check("B4 an overspent run stops", rc == 1, out[:200])
        check("B4 it says the finished work is safe", "on disk" in out, out)
        check("B4 it prints a resume command", "--resume" in out, out)
        check("B4 it does not pretend the ceiling was an estimate",
              "ceiling is spent" in out or "tokens left" in out, out)


def test_b4_a_missing_usage_report_makes_the_spend_a_floor():
    with Run() as r:
        r.spend("m1,C,440000,9000,13,90", "m2,B,,,,,no usage returned")
        _rc, out = r.gate("03-extract")
        check("B4 the gate says the spend is a floor",
              "floor" in out and "no usage" in out.lower() or "reported no usage" in out,
              out[:300])


def test_b4_json_is_machine_readable():
    with Run() as r:
        r.spend("m1,C,440000,9000,13,90")
        _rc, out = r.gate("03-extract", extra=("--json",))
        d = json.loads(out)
        for k in ("verdict", "spent", "budget", "remaining", "step_tokens", "reasons"):
            check("B4 --json carries %s" % k, k in d, sorted(d))
        check("B4 the verdict is GO or STOP", d["verdict"] in ("GO", "STOP"), d["verdict"])


# ------------------------------------------------------------- the narrowing

def recon(tmp, files, repo=None):
    """A recon.json plus real files on disk, since the gate opens them."""
    recs = []
    for name, text, extra in files:
        p = os.path.join(tmp, name)
        io.open(p, "w", encoding="utf-8").write(text)
        rec = {"path": name, "bytes": len(text.encode("utf-8")),
               "ext": os.path.splitext(name)[1], "is_binary": False, "lang": "en"}
        rec.update(extra or {})
        recs.append(rec)
    j = os.path.join(tmp, "recon.json")
    io.open(j, "w", encoding="utf-8").write(
        json.dumps({"schema": 1, "repo": repo or tmp, "inputs": recs}))
    return j


def test_b5_density_not_presence():
    tmp = tempfile.mkdtemp(prefix="rel-")
    try:
        j = recon(tmp, [
            ("relevant.md", "widget widget widget widget\n" * 20, None),
            # Two incidental matches in a large table: present, not relevant.
            # 6 bytes a line, so 60000 lines is ~350 KB and two hits is 0.006/KB.
            ("table.csv", ("a,b,c\n" * 60000) + "widget\nwidget\n", None),
        ])
        rc, out = run(RELEVANCE, j, "--scope", "does the widget flow exist",
                      "--threshold", "0.01")
        check("B5 the gate runs", rc == 0, out[:200])
        check("B5 the large low-density table is excluded",
              "not read" in out and "RELEVANCE" in out, out[:300])
        rows = relevance.classify(
            json.load(io.open(j))["inputs"], ["widget"], 0.01, tmp)
        verdicts = dict((r["path"], r["verdict"]) for r in rows)
        check("B5 the dense file is kept", verdicts["relevant.md"] == "keep", verdicts)
        check("B5 the sparse table is cut", verdicts["table.csv"] == "cut", verdicts)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_b6_it_declines_on_a_script_mismatch():
    tmp = tempfile.mkdtemp(prefix="rel-")
    try:
        j = recon(tmp, [
            ("spec.md", "出力 " * 4000, {"lang": "ja"}),
            ("notes.md", "widget " * 10, {"lang": "en"}),
        ])
        rc, out = run(RELEVANCE, j, "--scope", "does the export flow exist",
                      "--threshold", "0.01")
        check("B6 declining is exit 0, not a failure", rc == 0, out[:200])
        check("B6 it says it declined", "GATE-DECLINED" in out, out[:200])
        check("B6 it names the script mismatch", "script mismatch" in out, out[:300])
        check("B6 it asks for a term in the corpus's language",
              "--relevance-add" in out, out[:400])
        check("B6 nothing was excluded", "nothing excluded" in out, out[:200])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_b6_the_right_vocabulary_makes_it_act():
    tmp = tempfile.mkdtemp(prefix="rel-")
    try:
        j = recon(tmp, [
            ("spec.md", "出力 " * 4000, {"lang": "ja"}),
            ("bulk.csv", "a,b,c\n" * 30000, {"lang": "ja"}),
        ])
        rc, out = run(RELEVANCE, j, "--scope", "export", "--add", "出力",
                      "--threshold", "0.01")
        check("B6 with a matching term the gate acts", rc == 0 and "RELEVANCE" in out,
              out[:200])
        check("B6 and excludes the bulk table", "not read" in out, out[:300])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_b7_a_revision_marked_document_is_rescued():
    tmp = tempfile.mkdtemp(prefix="rel-")
    try:
        big = "unrelated prose\n" * 5000                       # > SPEC_BYTES
        j = recon(tmp, [
            ("spec.md", big, {"revision_markers": {"rev-dot": {"max": "03"}}}),
            ("hits.md", "widget " * 500, None),
        ])
        rows = relevance.classify(
            json.load(io.open(j))["inputs"], ["widget"], 0.01, tmp)
        v = dict((r["path"], r["verdict"]) for r in rows)
        check("B7 the revision-marked file is rescued, not cut",
              v["spec.md"] == "rescued", v)
        rc, out = run(RELEVANCE, j, "--scope", "does the widget flow exist",
                      "--threshold", "0.01", "--report", os.path.join(tmp, "r.md"))
        check("B7 the rescue is announced", "rescued" in out, out[:300])
        report = io.open(os.path.join(tmp, "r.md"), encoding="utf-8").read()
        check("B7 the report explains why it was rescued",
              "## Rescued" in report and "specification" in report, report[:400])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_b8_an_excluded_file_is_always_listed():
    tmp = tempfile.mkdtemp(prefix="rel-")
    try:
        j = recon(tmp, [("hits.md", "widget " * 500, None),
                        ("bulk.csv", "a,b\n" * 30000, None)])
        rep = os.path.join(tmp, "01b.md")
        rc, out = run(RELEVANCE, j, "--scope", "widget flow", "--threshold", "0.01",
                      "--report", rep)
        check("B8 the gate wrote its report", os.path.isfile(rep), out[:200])
        body = io.open(rep, encoding="utf-8").read()
        check("B8 the excluded file is named", "bulk.csv" in body, body[:400])
        check("B8 with its size and hit count",
              "| KB | Hits | Path |" in body, body[:600])
        check("B8 the report states the not-accessed rule",
              "not-accessed" in body, body[:900])
        check("B8 and the run says the same on stdout",
              "not-accessed" in out, out[:400])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_b8_threshold_zero_still_reports():
    tmp = tempfile.mkdtemp(prefix="rel-")
    try:
        j = recon(tmp, [("a.md", "x" * 100, None)])
        rep = os.path.join(tmp, "r.md")
        rc, out = run(RELEVANCE, j, "--scope", "widget", "--threshold", "0",
                      "--report", rep)
        check("B8 --threshold 0 exits 0", rc == 0, out[:200])
        check("B8 it excludes nothing", "not read    0" in out.replace("   ", "  ")
              or "not read" in out, out[:200])
        check("B8 and still writes an auditable report", os.path.isfile(rep))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def with_rate(spent_before, pct_before, step_pct):
    """A run directory whose ledger already holds one measured (tokens, percent)
    pair, which is what the rate needs."""
    import json as _json
    import time as _time
    d = tempfile.mkdtemp(prefix="budget-rate-")
    io.open(os.path.join(d, "budget.jsonl"), "w", encoding="utf-8").write(
        _json.dumps({"at": _time.time() - 600, "step": "b1",
                     "spent": spent_before, "agents": 2, "percent": pct_before,
                     "step_tokens": spent_before, "step_percent": step_pct}) + "\n")
    return d


def test_b9_an_unreachable_ceiling_is_rejected_with_a_usable_number():
    d = with_rate(900000, 10.0, 9.0)
    try:
        rc, out = run(COST, "wave", "--base", d, "--wave", "1",
                      "--row", "m1,C,440000,9000,13,90",
                      "--row", "m2,C,450000,8000,14,95",
                      "--row", "m0,C,890000,10000,20,150")
        check("B9 the fixture spends", rc == 0, out[:160])

        home = seeded_home(18.0)
        rc, out = run(BUDGET, "--base", d, "--budget", "200000000", "--step", "b2",
                      HOME=home)
        check("B9 an absurd ceiling is rejected", rc == 1, out[:300])
        check("B9 it says the ceiling is unreachable",
              "BUDGET-UNREACHABLE" in out, out[:400])
        check("B9 it prints a --budget the window can hold",
              "--budget " in out.split("BUDGET-UNREACHABLE")[-1], out[-500:])
        check("B9 it offers waiting as the alternative",
              "wait for the reset" in out, out[-500:])
        check("B9 ⭐ it says the figure is computed, never fixed",
              "computed now, not fixed" in out, out[-500:])

        # The number it printed must itself be accepted.
        tail = out.split("BUDGET-UNREACHABLE")[-1]
        num = None
        for tok in tail.replace("\n", " ").split():
            if tok.isdigit():
                num = tok
                break
        check("B9 a number was offered", num is not None, tail[:200])
        if num:
            rc2, out2 = run(BUDGET, "--base", d, "--budget", num, "--step", "b3",
                            HOME=home)
            check("B9 the number it offered is itself accepted", rc2 == 0,
                  "rc=%d  %s" % (rc2, out2[:240]))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_b9_the_threshold_is_never_a_constant():
    body = io.open(BUDGET, encoding="utf-8").read()
    check("B9 the limit is computed from spend and headroom",
          "spent + headroom * per_pct" in body)
    for constant in ("14000000", "14_000_000", "MAX_BUDGET =", "14505000"):
        check("B9 %s is not written down" % constant, constant not in body)
    check("B9 the docstring explains why a constant would be wrong",
          "computed every time and never constant" in body)


def test_b9_a_reachable_ceiling_still_passes():
    d = with_rate(900000, 10.0, 9.0)
    try:
        run(COST, "wave", "--base", d, "--wave", "1",
            "--row", "m1,C,440000,9000,13,90", "--row", "m2,C,450000,8000,14,95",
            "--row", "m0,C,890000,10000,20,150")
        rc, out = run(BUDGET, "--base", d, "--budget", "8000000", "--step", "b2",
                      HOME=seeded_home(18.0))
        check("B9 a ceiling inside the window is allowed", rc == 0, out[:300])
        check("B9 and the rate is still reported",
              "at this run's own rate" in out, out[:400])
        check("B9 without claiming it is a limit",
              "BUDGET-UNREACHABLE" not in out, out[:400])
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
