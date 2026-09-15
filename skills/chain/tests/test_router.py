#!/usr/bin/env python3
"""Four lanes, three sources, and no fourth row.

C1 widened the chain from two arms to four lanes. The dangerous part is not the
width -- it is that a wider vocabulary invites a fourth routing source: reading
the prose and deciding. Step 00 has always refused to do that, because a wrong
lane produces a plausible artifact of the wrong kind and nobody notices until
phase 01 has been paid for. The refusal has to survive the widening.

These checks read the tables, not the sentences around them, so they fail when
the structure changes rather than when somebody rewords a paragraph:

  T1  the source table still has exactly three rows, and the last one asks
  T2  every lane flag names a lane the dispatch table can run
  T3  `--feature` is an alias, not a fifth lane
  T4  every lane flag is documented in `## Arguments`
  T5  TRIVIAL's two extra obligations -- `--execute`, and the lanes reference --
      are stated where the flag is defined, not only in prose further down

T3 matters more than it looks. `--feature` was the old name and will be typed
for years; if it ever became a lane of its own, two flags would produce two
different traces for the same request.

Run:  python3 skills/chain/tests/test_router.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
CHAIN = os.path.join(ROOT, "skills", "chain", "SKILL.md")

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

    SKILL.md is hard-wrapped, so a phrase is as likely to straddle two lines as
    not; matching raw text would fail on a reflow and pass on a rewording.
    """
    return re.sub(r"\s+", " ", read(path))


def table(header_prefix, ncols):
    """Rows of the first table whose header line starts with `header_prefix`."""
    rows, seen = [], False
    for line in read(CHAIN).splitlines():
        stripped = line.strip()
        if not seen:
            if stripped.startswith(header_prefix):
                seen = True
            continue
        if not stripped.startswith("|"):
            break
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) != ncols or set(cells[0]) <= set("- "):
            continue
        rows.append(cells)
    return rows


def dispatch_lanes():
    return [r[0] for r in table("| Lane | 01 | 03 |", 4)]


def source_rows():
    return table("| | Source | How |", 3)


def lane_flags():
    """Flags named in row 1 of the source table."""
    rows = source_rows()
    return sorted(re.findall(r"`(--[a-z-]+)`", rows[0][2] + rows[0][1])) if rows else []


def test_t1_the_source_table_is_still_three_rows_ending_in_a_question():
    rows = source_rows()
    check("T1 the source table has exactly three rows", len(rows) == 3,
          [r[0] for r in rows])
    check("T1 they are numbered 1, 2, 3",
          [r[0] for r in rows] == ["1", "2", "3"], [r[0] for r in rows])
    check("T1 the last row asks rather than deciding",
          bool(rows) and "Ask" in rows[-1][1], rows[-1][1] if rows else "")
    check("T1 and the no-fourth-row rule is still stated",
          "no fourth row" in flat(CHAIN).lower(), "")


def test_t2_every_lane_flag_names_a_lane_that_can_run():
    lanes = dispatch_lanes()
    flags = lane_flags()
    check("T2 row 1 names four lane flags", len(flags) == 4, flags)
    derived = sorted(f[2:].upper() for f in flags)
    check("T2 every lane flag maps onto a dispatch row",
          derived == sorted(lanes), (derived, sorted(lanes)))


def test_t3_feature_is_an_alias_not_a_fifth_lane():
    body = flat(CHAIN)
    check("T3 --feature is declared an alias for --nr",
          re.search(r"--feature[^|]{0,80}alias for `?--nr", body) is not None, "")
    check("T3 --feature is not a lane flag in row 1",
          "--feature" not in lane_flags(), lane_flags())
    check("T3 and FEATURE is not a lane the dispatch table runs",
          "FEATURE" not in dispatch_lanes(), dispatch_lanes())


def test_t4_every_lane_flag_is_documented_in_arguments():
    body = read(CHAIN)
    start = body.find("## Arguments")
    block = body[start:body.find("\n## ", start + 5)] if start >= 0 else ""
    check("T4 the Arguments section is found", bool(block), start)
    missing = [f for f in lane_flags() if f not in block]
    check("T4 every lane flag appears in Arguments", not missing, missing)


def test_t5_trivial_carries_its_two_extra_obligations():
    body = read(CHAIN)
    row = [l for l in body.splitlines()
           if l.startswith("| `--trivial` |")]
    check("T5 --trivial has a row of its own in the flag table",
          len(row) == 1, row)
    cell = row[0] if row else ""
    check("T5 that row says it requires --execute", "--execute" in cell, cell)
    check("T5 and points at the lanes reference",
          "references/lanes.md" in cell, cell)
    check("T5 and says the lane is never inferred",
          "never" in cell.lower() and "inferred" in cell.lower(), cell)


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
