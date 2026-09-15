#!/usr/bin/env python3
"""TRIVIAL is the one lane where nobody reads a document before the code changes.

BUG, CR and NR all produce an analysis and a spec that a person reads. TRIVIAL
produces neither -- that is the point of it, and it is also the whole risk: a
request that was not trivial ships as a change with no review behind it.

Two things keep that from happening, and both are easy to soften by accident:

  * the entry is a **conjunction** -- four conditions, all required. The moment
    it reads as a judgement call ("mostly one file"), the lane takes work it
    should not.
  * the ceiling **escalates**, it does not stretch. Crossing it means the
    estimate was wrong, and the honest reading of a wrong estimate is that the
    change was never trivial.

  E1  the four conditions are enumerated, and stated as all-required
  E2  the ceiling is one number, and every file that quotes it quotes the same
      one -- two figures in two files is how a limit quietly doubles
  E3  crossing it escalates to CR, and the reason is recorded
  E4  the record survives the user saying "carry on anyway"

E2 is the check that catches the drift nobody notices: `50k` in a help page and
`50,000` in a reference read alike, and so would `500,000`.

Run:  python3 skills/chain/tests/test_trivial_ceiling.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

LANES = os.path.join(ROOT, "skills", "chain", "references", "lanes.md")
QUOTING = ("skills/chain/references/lanes.md",
           "skills/chain/references/help.md")

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
    """The file with every run of whitespace collapsed to one space.

    These documents are hard-wrapped at 100 columns, so a phrase the test looks
    for is as likely to be split across two lines as not. Matching the raw text
    would make the test fail on a reflow and pass on a rewording -- exactly
    backwards.
    """
    return re.sub(r"\s+", " ", read(path))


def ceilings(text):
    """Every token figure stated as a ceiling, normalised to an int."""
    out = set()
    for raw in re.findall(r"([0-9][0-9,]*)(?:\s|-)?(k\b|token)", text, re.I):
        n = int(raw[0].replace(",", ""))
        out.add(n * 1000 if raw[1].lower() == "k" else n)
    return out


def test_e1_the_entry_is_a_conjunction_of_four():
    body = read(LANES)
    numbered = re.findall(r"^\d+\. \*\*", body, re.M)
    check("E1 the conditions are an enumerated list", len(numbered) == 4, numbered)
    low = flat(LANES).lower()
    check("E1 they are stated as all-required",
          "all four" in low or "four conditions" in low, "")
    check("E1 and failing one is enough to disqualify",
          "fail any one" in low or "thiếu một" in low, "")
    check("E1 the lane is never inferred",
          "never inferred" in low, "")


def test_e2_one_ceiling_quoted_the_same_everywhere():
    found = {}
    for rel in QUOTING:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            check("E2 %s exists" % rel, False, "missing")
            continue
        block = read(path)
        near = [l for l in block.splitlines() if "ceiling" in l.lower()
                or "50" in l]
        found[rel] = ceilings("\n".join(near))
    check("E2 every file that mentions the ceiling states a figure",
          all(v for v in found.values()), found)
    values = set()
    for v in found.values():
        values |= v
    check("E2 and it is the same figure everywhere", len(values) == 1, found)
    check("E2 the figure is a token count, not a file count",
          values and max(values) >= 1000, values)


def test_e3_crossing_escalates_rather_than_stretches():
    low = flat(LANES).lower()
    check("E3 crossing the ceiling escalates to CR",
          "escalates to cr" in low, "")
    check("E3 it does not extend the ceiling",
          "does not extend the ceiling" in low, "")
    check("E3 it does not push through",
          "does not push through" in low or "not push through" in low, "")
    check("E3 and the reason is written into the manifest",
          "manifest.md" in flat(LANES) and "reason" in low, "")


def test_e4_the_record_survives_a_decision_to_continue():
    low = flat(LANES).lower()
    check("E4 the escalation is recorded even if the user continues anyway",
          "even when the user then asks to continue" in low
          or ("continue anyway" in low and "recorded even" in low), "")


def test_e5_the_lane_is_reachable_only_by_flag():
    low = flat(LANES).lower()
    check("E5 --trivial is named as the only way in",
          "--trivial` names it" in flat(LANES) or "--trivial names it" in low, "")
    check("E5 and it requires --execute",
        "requires `--execute`" in flat(LANES), "")


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
