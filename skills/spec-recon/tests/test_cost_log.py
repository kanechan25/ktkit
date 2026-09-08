#!/usr/bin/env python3
"""What a run cost is written down, and nothing on that page is invented.

A run of this skill can spend millions of tokens, and the only record of it used
to be a line of chat: `Wave 2: 5 agents · ~340k tokens · running ~1.2M`. Scroll
past it, or compact the conversation, and the number is gone -- while the report
it paid for lives on and gets cited. So cost became an artifact, and this file
holds it to the same standard as the evidence files:

  C1  a wave is recorded in one call, not one per agent -- tracking that costs a
      noticeable slice of what it tracks is not worth keeping
  C2  an agent that reported nothing is recorded as reporting nothing, and the
      total says how many it excludes
  C3  cost.jsonl is append-only; a re-run wave adds rows and rewrites none
  C4  a malformed row is rejected, not stored half-parsed
  C5  every number on the rendered page carries exactly one label
  C6  the rendered page states that the lead's own turns are not in the total
  C7  the instructions still say to batch, and still forbid averaging

C2 and C6 are the two that matter. A cost total is quoted downstream by whoever
reads it, so a figure that silently omits agents -- or silently omits the largest
term, the lead -- is worse than no figure at all.

Run:  python3 skills/spec-recon/tests/test_cost_log.py
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SCRIPT = os.path.join(ROOT, "scripts", "cost_log.py")
SKILL = os.path.join(ROOT, "skills", "spec-recon", "SKILL.md")
MODEL = os.path.join(ROOT, "skills", "spec-recon", "references", "cost-model.md")

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def read(path):
    return io.open(path, encoding="utf-8").read()


def run(*args):
    p = subprocess.Popen([sys.executable, SCRIPT] + list(args),
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = p.communicate()
    return p.returncode, out.decode("utf-8")


class Run(object):
    """A throwaway run directory."""

    def __enter__(self):
        self.d = tempfile.mkdtemp(prefix="costlog-")
        return self

    def __exit__(self, *_exc):
        shutil.rmtree(self.d, ignore_errors=True)

    def wave(self, n, *rows):
        argv = ["wave", "--base", self.d, "--wave", str(n)]
        for r in rows:
            argv += ["--row", r]
        return run(*argv)

    def jsonl(self):
        p = os.path.join(self.d, "cost.jsonl")
        if not os.path.isfile(p):
            return []
        return [json.loads(l) for l in io.open(p, encoding="utf-8") if l.strip()]

    def md(self):
        return read(os.path.join(self.d, "cost.md"))


def test_c1_a_whole_wave_lands_in_one_call():
    with Run() as r:
        rc, out = r.wave(1, "probe-code,A,148200,3100,14,96",
                         "probe-artifact,B,92400,2050,9,61",
                         "state-extract,C,301500,8800,31,203")
        check("C1 one call records the wave", rc == 0, out)
        check("C1 every agent got a row", len(r.jsonl()) == 3, r.jsonl())
        check("C1 it returns a running total for the chat",
              re.search(r"Wave 1: 3 agents · [\d,]+ tokens", out) is not None, out)
        check("C1 the total is the sum of what was reported",
              "556,050" in out, out)          # 151,300 + 94,450 + 310,300


def test_c2_an_agent_that_reported_nothing_is_recorded_as_such():
    with Run() as r:
        r.wave(1, "probe-code,A,148200,3100,14,96",
               "probe-vcs,B,,,,,no usage returned")
        rows = r.jsonl()
        silent = [x for x in rows if x["agent"] == "probe-vcs"]
        check("C2 the silent agent still has a row", len(silent) == 1, rows)
        if silent:
            check("C2 its numbers are null, not zero and not guessed",
                  silent[0]["tokens_in"] is None
                  and silent[0]["tokens_out"] is None, silent[0])
            check("C2 the reason it gave is kept",
                  silent[0]["note"] == "no usage returned", silent[0])
        md = r.md()
        check("C2 the page marks it not reported", "**not reported**" in md)
        check("C2 the total says how many agents it excludes",
              "1 of 2 agents reported no usage" in md,
              [l for l in md.split("\n") if "reported no usage" in l])
        check("C2 and calls itself a floor",
              "floor, not the bill" in md)
        check("C2 the total excludes it rather than inflating",
              "151,300" in md, [l for l in md.split("\n") if "Tokens (total)" in l])


def test_c3_the_log_is_append_only():
    with Run() as r:
        r.wave(1, "probe-code,A,100,10,1,1")
        first = read(os.path.join(r.d, "cost.jsonl"))
        r.wave(1, "probe-code,A,200,20,2,2")        # the same wave, re-run
        second = read(os.path.join(r.d, "cost.jsonl"))
        check("C3 a re-run appends", second.startswith(first), second[:200])
        check("C3 and keeps both attempts", len(r.jsonl()) == 2, r.jsonl())
        check("C3 the total counts both, rather than replacing",
              "330" in r.md(), [l for l in r.md().split("\n") if "Tokens (total)" in l])
        rc, _out = run("correct", "--base", r.d, "--reason", "wave 1 rerun after a crash")
        check("C3 a correction is a row, not an edit", rc == 0)
        check("C3 the correction is rendered with its reason",
              "wave 1 rerun after a crash" in r.md())


def test_c4_a_malformed_row_is_rejected():
    with Run() as r:
        rc, out = r.wave(1, ",A,1,2,3,4")
        check("C4 a row with no agent name is rejected", rc == 2, out)
        check("C4 and says why", "no agent name" in out, out)
        rc, out = r.wave(1, "probe-code,Z,1,2,3,4")
        check("C4 an unknown tool set is rejected", rc == 2, out)
        check("C4 and names the offending value", "'Z'" in out, out)
        check("C4 nothing was written", not os.path.isfile(
            os.path.join(r.d, "cost.jsonl")))


def test_c5_every_number_on_the_page_carries_one_label():
    with Run() as r:
        r.wave(1, "probe-code,A,148200,3100,14,96")
        for line in r.md().split("\n"):
            if not line.startswith("|") or "---" in line:
                continue
            if not re.search(r"\d", line):
                continue
            if line.startswith("| #") or "Value | Label" in line:
                continue
            n = len(re.findall(r"\[measured\]|\[derived\]|\[quoted\]", line))
            if line.count("|") == 4 and "|" in line:   # the Total table
                check("C5 %r carries exactly one label" % line[:40], n == 1, line)


def test_c6_the_page_says_the_lead_is_not_counted():
    with Run() as r:
        r.wave(1, "probe-code,A,148200,3100,14,96")
        md = r.md()
        check("C6 the page excludes the lead explicitly",
              "lead's own turns are not in this file" in md)
        check("C6 and explains why the total is not the whole bill",
              "cannot measure the session that dispatched it" in md)
        check("C6 it names cost.jsonl as the source of every figure",
              "cost.jsonl" in md)


def test_c7_the_instructions_batch_and_forbid_averaging():
    body, model = read(SKILL), read(MODEL)
    check("C7 the skill calls the batched subcommand",
          "cost_log.py\" wave" in body)
    check("C7 the skill does not put the per-agent form on the hot path",
          "cost_log.py\" append" not in body)
    check("C7 the skill forbids filling a missing figure",
          "Never fill a gap with an average" in body)
    check("C7 a stop rule covers estimating a reported figure",
          "fill a" in body and "average" in body)
    check("C7 the cost model records what the tracking itself costs",
          "The tracking must not cost what it tracks" in model)
    check("C7 with a measured comparison, not a claim",
          "one call per wave**" in model and "0.019%" in model)
    check("C7 the run directory layout names both files",
          "cost.jsonl" in read(os.path.join(
              ROOT, "skills", "spec-recon", "references", "step-protocol.md")))


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
