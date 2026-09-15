#!/usr/bin/env python3
"""The value `raise-issue` writes must be a value `chain` routes on.

`/ktkit:raise-issue` writes `type: BUG`, `type: NR` or `type: CR`. Step 00 of
`chain` used to accept `bug`, `bug-analysis` and `feature` and nothing else, so
every file `raise-issue` produced fell past row 2 to row 3 -- "⛔ Ask" -- and the
chain stopped to ask a question the file had already answered. Worse, two of the
three values the table did accept were written by nobody: `/ktkit:rca` emits
`bug-analysis`, and `bug`/`feature` only ever come from a person typing
frontmatter by hand.

A vocabulary split across two skills drifts the moment either side is edited,
and it drifts quietly: nothing crashes, the chain just asks. So this holds the
two ends together in both directions:

  R1  every `type:` a raise-issue form emits appears in the routing table
  R2  the value `/ktkit:rca` emits appears there too
  R3  every row that names a producing skill is telling the truth -- that
      skill's directory really does emit that value somewhere
  R4  every arm named in the table is an arm the dispatch table can run
  R5  two rows that fold to the same value agree about the arm, because the
      match is case-insensitive and `BUG` and `bug` are the same token
  R6  raise-issue's own handoff table sends each type to the same arm chain
      routes it to -- the two tables are written independently and read by
      different people, and the day they disagree one of them is lying

R3 is the direction that catches an invented row. R1 catches a form added
without a routing entry. Neither alone is enough: the table and the forms can
each be edited without the other.

Run:  python3 skills/chain/tests/test_route_vocab.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

CHAIN = os.path.join(ROOT, "skills", "chain", "SKILL.md")
FORMS_DIR = os.path.join(ROOT, "skills", "raise-issue", "references")
RCA = os.path.join(ROOT, "skills", "rca", "SKILL.md")
RAISE = os.path.join(ROOT, "skills", "raise-issue", "SKILL.md")

BY_HAND = "a person, by hand"
TYPE_LINE = re.compile(r"^type:\s*(\S+)\s*$", re.M)

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def read(path):
    return io.open(path, encoding="utf-8").read()


def vocabulary():
    """[(value, arm, source)] parsed from the routing table in step 00."""
    rows = []
    seen_header = False
    for line in read(CHAIN).splitlines():
        stripped = line.strip()
        if stripped.startswith("| `type:` | Arm | Written by |"):
            seen_header = True
            continue
        if not seen_header:
            continue
        if not stripped.startswith("|"):
            break                                   # table ended
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) != 3 or set(cells[0]) <= set("- "):
            continue                                # separator row
        value = cells[0].strip("`")
        rows.append((value, cells[1], cells[2].strip("`")))
    return rows


def emitted_types(path):
    """Every `type:` value a file writes in a frontmatter block."""
    return set(TYPE_LINE.findall(read(path)))


def test_r0_the_table_parses_at_all():
    rows = vocabulary()
    check("R0 the routing table is found and parses",
          len(rows) >= 4, rows)
    check("R0 and every row has a value, an arm and a source",
          all(v and a and s for v, a, s in rows), rows)


def test_r1_every_form_type_is_routable():
    rows = vocabulary()
    known = set(v.lower() for v, _a, _s in rows)
    missing = []
    for name in sorted(os.listdir(FORMS_DIR)):
        if not name.startswith("form-") or not name.endswith(".md"):
            continue
        path = os.path.join(FORMS_DIR, name)
        for value in sorted(emitted_types(path)):
            if value.startswith("<"):               # a placeholder, not a value
                continue
            if value.lower() not in known:
                missing.append("%s emits type: %s" % (name, value))
    check("R1 every raise-issue form emits a type the table routes",
          not missing, missing)


def test_r2_the_rca_type_is_routable():
    rows = vocabulary()
    known = set(v.lower() for v, _a, _s in rows)
    emitted = emitted_types(RCA)
    check("R2 rca emits exactly one type", len(emitted) == 1, emitted)
    check("R2 and the table routes it",
          all(v.lower() in known for v in emitted), emitted)


def skill_emits(skill):
    """Every `type:` value written anywhere under `skills/<name>/`.

    The table names the producing SKILL rather than a file path on purpose: a
    skill must not point into another skill's `references/`, which is what W4 of
    test_plugin_wiring.py enforces. The test is free to look -- it reads the
    whole repository by definition -- so the mapping from skill to file lives
    here instead of in the instruction the model reads.
    """
    base = os.path.join(ROOT, "skills", skill)
    if not os.path.isdir(base):
        return None
    found = set()
    for dirpath, _dirs, names in os.walk(base):
        for n in names:
            if n.endswith(".md"):
                found |= emitted_types(os.path.join(dirpath, n))
    return found


def test_r3_every_named_producer_really_emits_that_value():
    bad = []
    for value, _arm, source in vocabulary():
        if source == BY_HAND:
            continue
        m = re.match(r"^/ktkit:([a-z-]+)$", source)
        if not m:
            bad.append("%s: not a ktkit skill reference" % source)
            continue
        emitted = skill_emits(m.group(1))
        if emitted is None:
            bad.append("%s: no such skill directory" % source)
        elif value not in emitted:
            bad.append("%s does not emit type: %s" % (source, value))
    check("R3 every producer named in the table really emits its value",
          not bad, bad)


def test_r4_every_arm_is_one_the_chain_can_run():
    body = read(CHAIN)
    # The dispatch table at the end of step 00: `| feature | ... |`, `| bug | ... |`.
    arms = set()
    for line in body.splitlines():
        m = re.match(r"^\|\s*(\w+)\s*\|\s*`/ktkit:", line)
        if m:
            arms.add(m.group(1))
    check("R4 the dispatch table names at least two arms", len(arms) >= 2, arms)
    unknown = sorted(set(a for _v, a, _s in vocabulary()) - arms)
    check("R4 every arm in the vocabulary is one the dispatch table runs",
          not unknown, (unknown, arms))


def test_r5_rows_that_fold_together_agree():
    byfold = {}
    for value, arm, _s in vocabulary():
        byfold.setdefault(value.lower(), set()).add(arm)
    clashes = sorted(k for k, v in byfold.items() if len(v) > 1)
    check("R5 values that differ only in case agree about the arm",
          not clashes, [(k, sorted(byfold[k])) for k in clashes])


def arm_by_skill():
    """{`/ktkit:rca`: "bug", ...} from the dispatch table at the end of step 00."""
    out = {}
    for line in read(CHAIN).splitlines():
        m = re.match(r"^\|\s*(\w+)\s*\|\s*(`/ktkit:.+)\|\s*$", line)
        if not m:
            continue
        for cell in m.group(2).split("|"):
            for skill in re.findall(r"`(/ktkit:[a-z-]+)`", cell):
                out[skill] = m.group(1)
    return out


def test_r6_the_handoff_table_agrees_with_the_routing_table():
    arm_of = arm_by_skill()
    check("R6 the dispatch table maps skills to arms", len(arm_of) >= 4, arm_of)
    vocab = dict((v.lower(), a) for v, a, _s in vocabulary())

    disagree, checked = [], 0
    seen_header = False
    for line in read(RAISE).splitlines():
        stripped = line.strip()
        if stripped.startswith("| `type` | Suggested next |"):
            seen_header = True
            continue
        if not seen_header:
            continue
        if not stripped.startswith("|"):
            break
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) != 2 or set(cells[0]) <= set("- "):
            continue
        value = cells[0].strip("`")
        if value == "any":                          # the chain row, not a type
            continue
        arms = set(arm_of[s] for s in re.findall(r"`(/ktkit:[a-z-]+)`", cells[1])
                   if s in arm_of)
        if not arms:
            continue
        checked += 1
        if value.lower() not in vocab:
            disagree.append("%s is not in the routing table" % value)
        elif arms != set([vocab[value.lower()]]):
            disagree.append("%s -> handoff %s, routing %s"
                            % (value, sorted(arms), vocab[value.lower()]))
    check("R6 the handoff table was read", checked >= 3, checked)
    check("R6 both tables send each type to the same arm", not disagree, disagree)


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
