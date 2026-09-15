#!/usr/bin/env python3
"""A classification nobody downstream reads is a label, not a gate.

`analyze-feat` Phase 0d sorts a feature request into Spike, Bounded or
Architectural. That is only worth the tokens if the rest of the pipeline changes
behaviour because of it -- otherwise every request keeps paying the same
ceremony, which was the defect the classifier was added to fix.

So the three names have to appear in three places at once, and the checks here
are about the join rather than about any one file:

  T1  the classifier exists and names all three paths
  T2  the report template has a place to record the verdict
  T3  feat-req-specs gates STEP 5.5 and STEP 5.6 on the path, not on risk alone
  T4  the ratchet is one-way, and an unknown path resolves to the heavy end
  T5  a Spike stops at the analysis -- it is the only path whose consequence is
      a step NOT running, so it is the easiest to write down and forget
  T6  the classifier is attributed, and only the classifier was taken

T6 is scope, not manners. superpowers:brainstorming also carries a one-question-
at-a-time interview and a hard gate of its own; both collide with
escalation-ladder, which resolves first and opens exactly one gate. Importing
them would give ktkit two gate policies that disagree.

Run:  python3 skills/analyze-feat/tests/test_three_paths.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

ANALYZE = os.path.join(ROOT, "skills", "analyze-feat", "SKILL.md")
SPECS = os.path.join(ROOT, "skills", "feat-req-specs", "SKILL.md")

PATHS = ("Spike", "Bounded", "Architectural")

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def read(path):
    return io.open(path, encoding="utf-8").read()


def flat(path):
    return re.sub(r"\s+", " ", read(path))


def test_t1_the_classifier_exists_and_names_all_three():
    body = read(ANALYZE)
    check("T1 Phase 0d exists", "### 0d — Classify the path" in body, "")
    missing = [p for p in PATHS if "**%s**" % p not in body]
    check("T1 all three paths are named in the classifier", not missing, missing)
    check("T1 it runs before Phase 1",
          body.index("### 0d —") < body.index("## Phase 1:"), "")


def test_t2_the_report_records_the_verdict():
    body = read(ANALYZE)
    check("T2 the report template has a Path section",
          "## 0. Path" in body, "")
    i = body.index("## 0. Path")
    block = body[i:body.index("## 1. ", i)]
    missing = [p for p in PATHS if p not in block]
    check("T2 and offers all three as the answer", not missing, missing)
    check("T2 it asks for the reason, not only the label",
          "Because" in block, block[:200])


def test_t3_the_downstream_gates_read_the_path():
    body = flat(SPECS)
    check("T3 STEP 5.5 gates on the path", "path == Architectural" in body, "")
    check("T3 STEP 5.6 does too",
          body.count("path == Architectural") >= 2,
          body.count("path == Architectural"))
    check("T3 the path is read from the analysis report, not re-derived",
          "Phase 0d" in body and ".analyze.md" in body, "")
    check("T3 Bounded is named as the case that skips",
          "Bounded" in body, "")


def test_t4_the_ratchet_turns_one_way():
    body = flat(ANALYZE).lower()
    check("T4 ties go to the heavier path",
          "take the heavier" in body, "")
    check("T4 complexity found mid-run raises the path",
          "raise the path" in body, "")
    check("T4 and it never goes down", "never goes down" in body, "")
    spec = flat(SPECS)
    check("T4 an unknown path resolves to Architectural, not to the cheap end",
          "treat the path as **Architectural**" in spec, "")


def test_t5_a_spike_stops_at_the_analysis():
    body = flat(ANALYZE)
    check("T5 a Spike stops before the spec",
          "Stop at the analysis" in body, "")
    check("T5 and says so in the report section too",
          "no spec follows" in body, "")
    check("T5 what a spike builds is labelled throwaway",
          "throwaway" in body, "")
    check("T5 feat-req-specs knows a Spike should never reach it",
          "A Spike never reaches this file" in flat(SPECS), "")


def test_t6_only_the_classifier_was_taken():
    body = flat(ANALYZE)
    check("T6 the source is attributed",
          "adapted from `superpowers:brainstorming`" in body, "")
    check("T6 with the reason it was internalised rather than called",
          "escalation-ladder" in body, "")
    check("T6 and the interview is explicitly not imported",
          "interview" in body.lower(), "")
    check("T6 analyze-feat does not invoke brainstorming",
          "superpowers:brainstorming`" not in read(ANALYZE).replace(
              "adapted from `superpowers:brainstorming`", ""), "")


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
