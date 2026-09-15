#!/usr/bin/env python3
"""A worker is given a brief, not a conversation -- and the brief is late on purpose.

Two decisions the execution layer rests on, and both are invisible once they are
wrong.

**Timing.** Writing every task's detail up front is what a plan does, because a
plan is read by a person. A brief is executed by a worker, and a change request
can invalidate a third of the plan before the worker reaches it -- so detail
written early is paid for twice, once to write and once to work out what
survived. The brief is written when its task turns `ready`.

**Input.** A worker that inherits the conversation inherits the options that were
rejected, the half-formed design, and the reasoning that was later overturned. It
will occasionally build one of them. A brief carries the decisions; a transcript
carries the decisions and everything that lost.

  J1  the five slots are all named, and each says why a worker cannot proceed
      without it
  J2  the brief is written at `ready`, and the document says why not earlier
  J3  the worker gets the brief and nothing else, with both reasons given
  J4  `execution.yml` is a sidecar: it never rewrites `tasks.md`, and it never
      renumbers the ids it points at
  J5  the tiers exist, ratchet one way, and are not raised by the work itself
  J6  the batch threshold is NOT written down, and the file says it is waiting
      on a measurement rather than on an argument
  J7  step 05 actually dispatches the guard, before the reviewer

J6 is the one a later edit will quietly break: writing a plausible number is
easier than reading `cost.jsonl`, and a number in a document looks decided
whether or not anybody measured it.

Run:  python3 skills/chain/tests/test_jit_brief.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

EXECUTION = os.path.join(ROOT, "skills", "chain", "references", "execution.md")
CHAIN = os.path.join(ROOT, "skills", "chain", "SKILL.md")
GUARD = os.path.join(ROOT, "agents", "minimal-diff-guard.md")

SLOTS = ("files", "interfaces", "acceptance", "test", "verify")
TIERS = ("R0", "R1", "R2")

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def read(path):
    return io.open(path, encoding="utf-8").read()


def plain(text):
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", ""))


def flat(path):
    return plain(read(path))


def test_j1_five_slots_each_with_a_reason():
    # Read the slot table alone. The tier table below it has the same row shape,
    # so a file-wide search finds eight "slots" -- which is how the first draft
    # of this check reported a passing structure that did not exist.
    body = read(EXECUTION)
    start = body.index("| Slot |")
    end = body.index("\n##", start)
    rows = re.findall(r"^\|\s*\*\*(\w+)\*\*\s*\|([^|]*)\|([^|]*)\|",
                      body[start:end], re.M)
    names = [r[0] for r in rows]
    check("J1 the brief has exactly five slots", len(rows) == 5, names)
    check("J1 and they are the five", sorted(names) == sorted(SLOTS), names)
    thin = [r[0] for r in rows if len(r[2].strip()) < 25]
    check("J1 every slot says why a worker cannot proceed without it",
          not thin, thin)
    check("J1 a brief missing one is not treated as merely shorter",
          "not a short brief" in flat(EXECUTION), "")


def test_j2_the_brief_is_written_when_the_task_is_ready():
    f = flat(EXECUTION)
    check("J2 the brief is written at ready",
          "written when its task transitions to ready" in f, "")
    low = f.lower()
    check("J2 and explicitly not up front",
          "not at planning time" in low and "not in a batch" in low, "")
    check("J2 the reason is the double payment, not neatness",
          "paying twice" in f, "")
    check("J2 the trigger is the recorded task state, not a judgement",
          "ledger.py --task-state" in f, "")


def test_j3_the_worker_gets_the_brief_and_nothing_else():
    f = flat(EXECUTION)
    check("J3 the worker never inherits the conversation",
          "never inherits the conversation" in f, "")
    check("J3 the cost reason is given", "paid again on every spawn" in f, "")
    check("J3 and the correctness reason, which is the one people forget",
          "everything that lost" in f, "")
    c = flat(CHAIN)
    check("J3 step 05 says the same thing, where the dispatch happens",
          "brief and nothing else" in c, "")


def test_j4_execution_yml_is_a_sidecar_not_a_rewrite():
    f = flat(EXECUTION)
    check("J4 tasks.md stays canonical", "tasks.md WHAT" in f, "")
    check("J4 execution.yml holds the how", "execution.yml HOW" in f, "")
    check("J4 ids are never renumbered in the sidecar",
          "Never renumber them here" in f, "")
    check("J4 and a stale entry stops the run rather than executing",
          "stale entry, not a new task" in f, "")
    check("J4 the idea is credited and the dependency refused",
          "superspec" in f and "The dependency does not" in f, "")


def test_j5_tiers_exist_and_ratchet_one_way():
    body = read(EXECUTION)
    missing = [t for t in TIERS if "**%s**" % t not in body]
    check("J5 all three tiers are defined", not missing, missing)
    f = plain(body)
    check("J5 R2 is the one that earns the expensive reviewer",
          "requesting-code-review" in f, "")
    check("J5 the ratchet turns one way", "ratchet turns one way" in f, "")
    check("J5 a tier is never lowered", "never lowered" in f, "")
    check("J5 and never raised by the work it governs",
          "never by the work it governs" in f, "")


def test_j6_the_batch_threshold_is_not_invented():
    f = flat(EXECUTION)
    check("J6 batching is named as undecided",
          "not decided, because it has not been measured" in f, "")
    check("J6 no threshold is written until the data says one",
          "No threshold is written here until" in f, "")
    check("J6 and the file says the data already exists",
          "cost_log.py" in f, "")
    # A number presented as the answer is what this check exists to prevent. The
    # measured spawn costs are quoted as evidence, and are allowed; a sentence
    # naming a task count as the cutover is not.
    bad = re.findall(r"batch\w*\s+(?:at|above|over|when)\s+\d+", f, re.I)
    check("J6 no batch size is asserted anywhere", not bad, bad)


def test_j7_step_05_dispatches_the_guard_before_the_reviewer():
    body = read(CHAIN)
    block = body[body.index("### 05 — implement"):body.index("### 06 — sync back")]
    guard = block.find("ktkit:minimal-diff-guard")
    reviewer = block.find("#### Then, and only then, the reviewer")
    check("J7 the guard is dispatched in step 05", guard >= 0, guard)
    check("J7 before the reviewer", guard >= 0 and guard < reviewer,
          (guard, reviewer))
    f = plain(block)
    check("J7 a violation goes back to the worker, not into a review",
          "not a review finding" in f, "")
    check("J7 and the two downstream consumers are named",
          "cr-delta" in f and "deviation.py" in f, "")
    g = flat(GUARD)
    check("J7 the guard reports and never fixes",
          "reported, never fixed" in g, "")
    check("J7 and it refuses to widen the brief to fit the diff",
          "Never widen the brief" in g, "")


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
