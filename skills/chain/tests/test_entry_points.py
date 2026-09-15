#!/usr/bin/env python3
"""Four skills stopped being entry points. One deliberately did not.

`feat-req-specs`, `feat-req-execute`, `bug-fix-specs` and `bug-fix-execute` are
phases of a lane now. Run directly they still work and still write the same files
at the same paths -- what a direct run does not get is the ledger, so questions
settled in phase 01 are asked again in phase 03; the budget gate at each
boundary; the deviation record; and step 07, which is the only step that reads
the delivered code.

`/ktkit:rca` keeps its entry point on purpose. "Find the root cause and stop" is
a complete piece of work somebody wants on its own, and demoting it would force a
whole chain run to answer one question.

  P1  each of the four carries the banner, in the skill and in its help page
  P2  each banner names the lane and the flags that actually reach it -- a
      banner pointing at the wrong flag is worse than none, because it is
      followed
  P3  rca does NOT carry it, and neither does anything else
  P4  the four are still dispatched by the chain: a deprecation that also
      unhooked them would take the feature away rather than move its door
  P5  the banner says the skill still works today -- a notice that reads like a
      removal gets treated as one

P2 is the check that earns its keep. The banner is four near-identical blocks,
which is exactly the shape where a copy-paste leaves `--bug` on a feature skill.

Run:  python3 skills/chain/tests/test_entry_points.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
CHAIN = os.path.join(ROOT, "skills", "chain", "SKILL.md")

BANNER = "Not an entry point"

# skill -> (lane it belongs to, the flags that reach it)
DEMOTED = {
    "feat-req-specs": ("NR and CR", "--nr"),
    "feat-req-execute": ("NR and CR", "--nr --execute"),
    "bug-fix-specs": ("BUG", "--bug"),
    "bug-fix-execute": ("BUG", "--bug --execute"),
}

# Kept as an entry point, deliberately. Listed rather than inferred so that
# demoting it later is a decision somebody makes here, not a side effect.
KEPT = ("rca",)

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


def skill_body(name):
    return read(os.path.join(ROOT, "skills", name, "SKILL.md"))


def help_body(name):
    p = os.path.join(ROOT, "skills", name, "references", "help.md")
    return read(p) if os.path.isfile(p) else ""


def test_p1_the_four_carry_the_banner_in_both_places():
    for name in sorted(DEMOTED):
        check("P1 %s/SKILL.md carries the banner" % name,
              BANNER in skill_body(name), "")
        check("P1 %s help page carries it too" % name,
              BANNER in help_body(name), "")
        body = skill_body(name)
        i = body.find(BANNER)
        check("P1 %s puts it before the body, not buried" % name,
              0 <= i < body.find("## Purpose"), i)


def test_p2_each_banner_names_its_own_lane_and_flags():
    for name, (lane, flags) in sorted(DEMOTED.items()):
        for where, body in (("SKILL.md", skill_body(name)),
                            ("help", help_body(name))):
            flat = plain(body)
            check("P2 %s %s names the %s lane" % (name, where, lane),
                  lane in flat, "")
            check("P2 %s %s names the flags %s" % (name, where, flags),
                  "/ktkit:chain" in flat and flags in flat, "")
            # The failure this exists for: a copy-paste leaving a bug flag on a
            # feature skill. Check the OTHER lane's flag is absent.
            other = "--bug" if flags.startswith("--nr") else "--nr"
            near = flat[flat.find(BANNER):flat.find(BANNER) + 700]
            check("P2 %s %s does not also carry %s" % (name, where, other),
                  other not in near, near[:200])


def test_p3_rca_keeps_its_entry_point():
    for name in KEPT:
        check("P3 %s does not carry the banner" % name,
              BANNER not in skill_body(name), "")
    stray = []
    base = os.path.join(ROOT, "skills")
    for name in sorted(os.listdir(base)):
        if name in DEMOTED or not os.path.isdir(os.path.join(base, name)):
            continue
        if BANNER in skill_body(name):
            stray.append(name)
    check("P3 and nothing else does either", not stray, stray)


def test_p4_the_chain_still_dispatches_all_four():
    body = read(CHAIN)
    missing = [n for n in DEMOTED if ("/ktkit:%s" % n) not in body]
    check("P4 every demoted skill is still dispatched by the chain",
          not missing, missing)
    seen, start = {}, False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("| Lane | 01 | 03 |"):
            start = True
            continue
        if not start:
            continue
        if not stripped.startswith("|"):
            break
        for skill in re.findall(r"`/ktkit:([a-z-]+)`", stripped):
            seen.setdefault(skill, 0)
            seen[skill] += 1
    absent = [n for n in DEMOTED if n not in seen]
    check("P4 and each appears in the dispatch table itself", not absent,
          (absent, sorted(seen)))


def test_p5_the_banner_says_it_still_works():
    for name in sorted(DEMOTED):
        flat = plain(skill_body(name))
        check("P5 %s says a direct run still works" % name,
              "still works" in flat, "")
        check("P5 %s names what a direct run loses" % name,
              "ledger" in flat and "07" in flat, "")
        check("P5 %s says nothing is being removed today" % name,
              "nothing is being taken away today" in flat, "")


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
