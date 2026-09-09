#!/usr/bin/env python3
"""A specification that disagrees with the code must say so, and say why.

A spec that disagrees with the code is worse than no spec: it reads as
authoritative and is quietly wrong. `chain` had a sync-back step that could not
close this -- step 06 syncs "every conflict found in 04 or 05", 05 hands the work
to an execute skill, nothing extracted that skill's divergences, and the
`.implt.md` template had nowhere to put them.

Two designs were weighed. Writing the spec at the moment of divergence captures
the reason while it is still in context, but leaves an aborted run with a
specification describing code that was rolled back. Recording afterwards keeps
the spec stable, but the reason has left context by then, and a table
hand-written into two files is two authorings that can disagree. What ships is
neither: capture at the moment, write at the boundary, render once into both.

  V1  a row is recorded with its reason and its own line's text
  V2  a reason that is empty, `n/a` or `tbd` is refused
  V3  an anchor that is not a path:line is refused
  V4  an anchor that moved is re-resolved and marked
  V5  an anchor that is gone stops the sync
  V6  silence and "nothing diverged" are different facts
  V7  a contract-level row is a gate, not a sync
  V8  render is the single source for both destinations

V4 and V5 are the pair that matters. A `path:line` captured mid-phase drifts as
the implementation continues, so an anchor that is merely *was* true is worse
than none -- it reads as verified. Re-resolving a moved line is only possible
because the row keeps the line's own text.

V2 is the one that cannot be recovered by any later process. A diff shows that
the code differs; it never shows why somebody chose that.

Run:  python3 skills/chain/tests/test_deviation.py
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
SCRIPT = os.path.join(ROOT, "scripts", "deviation.py")
REF = os.path.join(ROOT, "references", "syncback.md")

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


class Work(object):
    """A tree with a known file, and a run directory beside it."""

    FILE = "src/api.cs"
    BODY = "class Export {\n  int status = 201;\n}\n"

    def __enter__(self):
        self.d = tempfile.mkdtemp(prefix="deviation-")
        self.repo = os.path.join(self.d, "repo")
        self.base = os.path.join(self.d, "run")
        os.makedirs(os.path.join(self.repo, "src"))
        os.makedirs(self.base)
        self.write(self.BODY)
        return self

    def __exit__(self, *_exc):
        shutil.rmtree(self.d, ignore_errors=True)

    def write(self, body):
        io.open(os.path.join(self.repo, self.FILE), "w",
                encoding="utf-8").write(body)

    def add(self, **kw):
        argv = ["add", "--base", self.base, "--repo", self.repo,
                "--source", kw.pop("source", "spec §4.2"),
                "--said", kw.pop("said", "POST /exports returns 202"),
                "--did", kw.pop("did", "returns 201"),
                "--why", kw.pop("why", "202 needs a queue the spec omits"),
                "--evidence", kw.pop("evidence", "%s:2" % self.FILE)]
        if kw.pop("contract", False):
            argv.append("--contract")
        return run(*argv)

    def lint(self):
        return run("lint", "--base", self.base, "--repo", self.repo)

    def render(self):
        return run("render", "--base", self.base, "--repo", self.repo)

    def rows(self):
        p = os.path.join(self.base, "deviations.jsonl")
        if not os.path.isfile(p):
            return []
        return [json.loads(l) for l in io.open(p, encoding="utf-8") if l.strip()]


def test_v1_a_row_keeps_its_reason_and_its_line():
    with Work() as w:
        rc, out = w.add()
        check("V1 recording exits 0", rc == 0, out[:200])
        check("V1 it says which row it is", "DEVIATION #1" in out, out[:200])
        rows = w.rows()
        check("V1 one row was written", len(rows) == 1, rows)
        if rows:
            r = rows[0]
            check("V1 the reason is stored", r["why"].startswith("202 needs"), r)
            check("V1 ⭐ the cited line's own text is stored",
                  r.get("line_text", "").strip() == "int status = 201;", r)
            check("V1 with the commit, or empty when there is no repo",
                  "head" in r, r)
        rc, out = w.lint()
        check("V1 the row lints clean", rc == 0, out[:200])


def test_v2_a_missing_reason_is_refused():
    """The one part no later process can reconstruct."""
    for why in ("", "n/a", "TBD", "  ", "none"):
        with Work() as w:
            w.add(why=why or "x")
            rows = w.rows()
            rows[0]["why"] = why
            io.open(os.path.join(w.base, "deviations.jsonl"), "w",
                    encoding="utf-8").write(json.dumps(rows[0]) + "\n")
            rc, out = w.lint()
            check("V2 why=%r is refused" % why, rc == 1, out[:200])
            check("V2 and the message says why it matters",
                  "reconstruct" in out or "why is empty" in out, out[:300])


def test_v3_an_anchor_must_be_a_path_and_a_line():
    with Work() as w:
        w.add(evidence="src/api.cs")            # no line
        rc, out = w.lint()
        check("V3 a path without a line is refused", rc == 1, out[:200])
        check("V3 and the message shows the offending value",
              "src/api.cs" in out, out[:300])


def test_v4_a_moved_anchor_is_re_resolved_and_marked():
    with Work() as w:
        w.add()
        w.write("// header\n// header\n" + Work.BODY)     # pushed down by 2
        rc, out = w.lint()
        check("V4 a moved line does not stop the sync", rc == 0, out[:300])
        check("V4 the move is reported", "line moved 2 -> 4" in out, out[:300])
        rc, body = w.render()
        check("V4 render exits 0", rc == 0, body[:200])
        check("V4 ⭐ the block carries the NEW number",
              "src/api.cs:4" in body, body[:600])
        check("V4 and says the line moved", "line moved" in body, body[:600])


def test_v5_a_dead_anchor_stops_the_sync():
    with Work() as w:
        w.add()
        w.write("// nothing like the recorded line\n")
        rc, out = w.lint()
        check("V5 a dead anchor exits 1", rc == 1, out[:300])
        check("V5 it says stop, not warn", "STOP" in out, out[:400])
        check("V5 and why: it reads as verified",
              "reads as" in out and "verified" in out, out[:400])


def test_v6_silence_and_nothing_diverged_are_different():
    with Work() as w:
        rc, out = w.lint()
        check("V6 an empty record is NOT-ANSWERED", "NOT-ANSWERED" in out, out[:300])
        check("V6 and says silence is not agreement",
              "not the same as" in out, out[:300])
        rc, body = w.render()
        check("V6 the rendered block refuses to read as clean",
              "Nothing was recorded" in body, body[:400])
        check("V6 it points at --none", "--none" in out, out[:300])

        rc, out = run("none", "--base", w.base, "--repo", w.repo)
        check("V6 --none exits 0", rc == 0, out[:200])
        rc, out = w.lint()
        check("V6 now it is DECLARED-NONE", "DECLARED-NONE" in out, out[:200])
        rc, body = w.render()
        check("V6 and the block says KHÔNG CÓ", "KHÔNG CÓ" in body, body[:300])
        check("V6 with when it was declared",
              "Recorded, not inferred" in body, body[:400])


def test_v7_a_contract_row_is_a_gate():
    with Work() as w:
        rc, out = w.add(contract=True, source="spec §7 AC-3",
                        said="export is async", did="synchronous only",
                        why="no queue infrastructure in this environment")
        check("V7 it is marked at record time", "contract-level" in out, out[:300])
        check("V7 and says it is a gate rather than a sync",
              "gate" in out, out[:400])
        rc, out = w.lint()
        check("V7 lint still passes the row", rc == 0, out[:300])
        check("V7 but reports it as a gate", "gate, not a sync" in out, out[:400])
        rc, body = w.render()
        check("V7 the block flags the row", "⚠️ contract" in body, body[:700])
        check("V7 and explains what contract-level means",
              "promises to somebody else" in body, body[:900])


def test_v8_render_is_the_single_source_for_both_files():
    body = io.open(SCRIPT, encoding="utf-8").read()
    check("V8 the script says both destinations come from it",
          "one source, both destinations" in body or "both destinations" in body)
    ref = io.open(REF, encoding="utf-8").read()
    check("V8 the reference states they cannot drift",
          "cannot drift" in ref, ref[:1])
    check("V8 and rejects hand-writing the second copy",
          "two hand-written tables" in ref or "two independent authorings" in ref)
    for skill in ("feat-req-execute", "bug-fix-execute"):
        s = io.open(os.path.join(ROOT, "skills", skill, "SKILL.md"),
                    encoding="utf-8").read()
        check("V8 %s forbids hand-writing the table" % skill,
              "never hand-written" in s, skill)
        check("V8 %s records at the moment, not at the end" % skill,
              "at the moment, not at the end" in s, skill)
    ch = io.open(os.path.join(ROOT, "skills", "chain", "SKILL.md"),
                 encoding="utf-8").read()
    check("V8 chain step 05 does not touch the spec",
          "The spec is not touched here" in ch)
    check("V8 chain step 06 stops on a lint failure",
          "STOP." in ch and "deviation.py" in ch)
    check("V8 the third gate is not counted against the two",
          "not counted here" in ch)


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
