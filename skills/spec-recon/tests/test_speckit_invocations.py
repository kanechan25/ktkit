#!/usr/bin/env python3
"""A skill body must call speckit by the name speckit actually installs.

speckit renamed its Claude skills at 1.0: `speckit.plan` became `speckit-plan`,
because `build_command_invocation` strips the `speckit.` prefix and the
integration joins what is left with a hyphen. `scripts/speckit_global.py`
installs the current layout and *removes* the dotted one, so on a machine this
plugin has set up, `/speckit.plan` names nothing at all.

That failure is quiet in the worst way. `scripts/preflight.py` accepts both
layouts on purpose -- it answers "is speckit here", and a machine that has not
migrated yet still has a working speckit. So preflight says PASS, the run
starts, and STEP 6 invokes a skill that does not exist. The gate answered a
different question from the one the step depends on.

  S1  no skill body invokes the dotted layout
  S2  every invoked name is one speckit really ships -- catches a typo, which
      fails exactly like a stale name and reads exactly like a working one
  S3  a dotted name may still appear in prose, but only where the surrounding
      line says it is the old layout
  S4  preflight still probes BOTH layouts -- the counterpart to S1, and the
      reason S1 is safe to enforce

S4 is not decoration. S1 and S4 pull in opposite directions, and someone
tidying up after reading only one of them would break a machine that has not
migrated. Written down together, they cannot be half-applied.

Run:  python3 skills/spec-recon/tests/test_speckit_invocations.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

# What `specify init --integration claude` renders, measured against spec-kit
# 1.0.7.dev0 via `python3 scripts/speckit_global.py --list`. A name outside this
# set is a typo or a command this plugin has not seen; either way the run would
# invoke nothing, so the test fails rather than guessing.
SPECKIT_SKILLS = (
    "analyze", "checklist", "clarify", "constitution", "converge",
    "implement", "plan", "specify", "tasks", "taskstoissues",
)

# A dotted name is allowed to survive only where the line it sits on says so.
OLD_LAYOUT_WORDS = ("older", "predates", "pre-1.0", "old layout", "previous")

DOTTED = re.compile(r"speckit\.(?:%s|\*)" % "|".join(SPECKIT_SKILLS))
INVOKED = re.compile(r"/speckit-([a-z][a-z-]*)")

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def markdown_files():
    out = []
    for base in (os.path.join(ROOT, "skills"), os.path.join(ROOT, "agents")):
        for dirpath, _dirs, names in os.walk(base):
            for n in names:
                if n.endswith(".md"):
                    out.append(os.path.join(dirpath, n))
    out.append(os.path.join(ROOT, "README.md"))
    return sorted(out)


def rel(path):
    return os.path.relpath(path, ROOT)


def test_s1_no_skill_body_invokes_the_dotted_layout():
    bad = []
    for path in markdown_files():
        if rel(path) == "README.md":
            continue                      # covered by S3
        for i, line in enumerate(io.open(path, encoding="utf-8"), 1):
            if DOTTED.search(line):
                bad.append("%s:%d" % (rel(path), i))
    check("S1 no skill or agent body names speckit with a dot",
          not bad, bad[:6])


def test_s2_every_invoked_name_is_one_speckit_ships():
    unknown, seen = [], set()
    for path in markdown_files():
        for i, line in enumerate(io.open(path, encoding="utf-8"), 1):
            for m in INVOKED.finditer(line):
                name = m.group(1)
                if name == "":            # the `/speckit-*` glob
                    continue
                seen.add(name)
                if name not in SPECKIT_SKILLS:
                    unknown.append("%s:%d %s" % (rel(path), i, name))
    check("S2 every invoked speckit skill is one speckit ships",
          not unknown, unknown[:6])
    check("S2 and the sweep actually found invocations to check",
          len(seen) >= 5, sorted(seen))


def test_s3_a_dotted_name_survives_only_where_it_is_explained():
    unexplained = []
    path = os.path.join(ROOT, "README.md")
    for i, line in enumerate(io.open(path, encoding="utf-8"), 1):
        if not DOTTED.search(line):
            continue
        low = line.lower()
        if not any(w in low for w in OLD_LAYOUT_WORDS):
            unexplained.append("README.md:%d" % i)
    check("S3 a dotted name in README is on a line that calls it the old layout",
          not unexplained, unexplained[:6])


def test_s4_preflight_still_probes_both_layouts():
    body = io.open(os.path.join(ROOT, "scripts", "preflight.py"),
                   encoding="utf-8").read()
    for const in ("SPECKIT_SKILL_NAMES", "SPECKIT_CONVERGE_NAMES"):
        line = [l for l in body.splitlines() if l.startswith(const + " =")]
        check("S4 %s is still defined" % const, len(line) == 1, line)
        if len(line) != 1:
            continue
        check("S4 %s keeps the hyphenated layout" % const,
              "speckit-" in line[0], line[0])
        check("S4 %s keeps the dotted layout too" % const,
              "speckit." in line[0], line[0])
    # And the remediation must not send the reader back to the command that
    # drops fifteen directories into a shared, checked-in `.claude/skills/`.
    check("S4 the skills FAIL points at the global installer",
          "speckit_global.py" in body, "no speckit_global.py in preflight.py")


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
