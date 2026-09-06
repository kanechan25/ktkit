#!/usr/bin/env python3
"""Help must describe the skill that ships, not the skill somebody remembers.

Documentation rots quietly. A flag is renamed and the help keeps the old name; a
flag is added and the help never hears about it. Either way the page still reads
as authoritative, and the person following it types something that does not
work. Prose cannot enforce prose -- the same lesson `test_no_project_strings.py`
was written for -- so the pages are checked against the skills themselves.

The checks, in the order a page is built:

  H1  every skill has a page, and the page names the skill it lives in
  H2  every flag a page documents is one that skill (or a skill named on the
      same line) actually mentions          -- catches an invented flag
  H3  every flag in a skill's `## Arguments` appears in its page
                                            -- catches a forgotten flag
  H4  every `ktkit:<name>` a page points at resolves to a real skill
  H5  `help.py --list` is exactly the set of skill directories
  H6  `help.py <name>` succeeds for every skill; an unknown name fails
  H7  the index lists every skill once, with a real tagline
  H8  a page stays inside the budget it is paid from
  H9  the SessionStart hook names the script it tells the model to run

H2 and H3 are the pair that matters. One direction alone lets help drift; both
directions together mean a flag can only be renamed in two places at once.

Run:  python3 skills/spec-recon/tests/test_help.py
"""
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SKILLS = os.path.join(ROOT, "skills")
HELP_PY = os.path.join(ROOT, "scripts", "help.py")
HOOK = os.path.join(ROOT, "hooks", "confirm-marker.py")

# `--help` and `-h` are the protocol itself, installed by the SessionStart hook
# rather than declared by any skill. Every page may name them.
UNIVERSAL = {"--help", "--h"}
FLAG_RE = re.compile(r"(?<![\w-])--[a-z][a-z0-9-]+")
KTKIT_RE = re.compile(r"ktkit:([a-z][a-z0-9-]*)")
MAX_PAGE_LINES = 220

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def read(path):
    return io.open(path, encoding="utf-8").read()


def skill_names():
    return sorted(n for n in os.listdir(SKILLS)
                  if os.path.isfile(os.path.join(SKILLS, n, "SKILL.md")))


def page(name):
    return os.path.join(SKILLS, name, "references", "help.md")


def skill_md(name):
    return read(os.path.join(SKILLS, name, "SKILL.md"))


def arguments_section(name):
    """The `## Arguments` block of a SKILL.md, or '' when it has none."""
    text = skill_md(name)
    m = re.search(r"^## Arguments\s*$(.*?)(?=^## )", text, re.M | re.S)
    return m.group(1) if m else ""


def declared_flags(name):
    """The flags a skill *defines*, not every flag its Arguments prose mentions.

    An argument table explains a flag in its third column, and that explanation
    may legitimately name another skill's flag -- `--handoff` is documented as
    handing off to `docs-review --evidence <dir>`. Reading that as a flag of
    this skill made the first version of H3 demand a page document a flag that
    belongs to a different skill entirely. So: flags come from the synopsis
    block, where every flag on the line is this skill's, and from the first cell
    of a table row, where the flag is being defined rather than mentioned.
    """
    section = arguments_section(name)
    if not section:
        return set()
    found = set()
    for block in re.findall(r"```.*?```", section, re.S):
        found.update(FLAG_RE.findall(block))
    for line in section.split("\n"):
        if not line.lstrip().startswith("|"):
            continue
        cells = line.split("|")
        if len(cells) > 1:
            found.update(FLAG_RE.findall(cells[1]))
    return found


def skills_named_on(line):
    """Skills this line refers to -- prefixed or bare.

    `/ktkit:help chain` names chain as an argument, with no prefix of its own,
    which the first version of this check missed: it looked only for
    `ktkit:<name>` and so read the line as naming nothing but `help`.
    """
    named = set(KTKIT_RE.findall(line))
    for n in skill_names():
        if re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(n), line):
            named.add(n)
    return named


def run_help(*args):
    p = subprocess.Popen([sys.executable, HELP_PY] + list(args),
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = p.communicate()
    return p.returncode, out.decode("utf-8")


def test_h1_every_skill_has_a_page_that_names_itself():
    missing, mislabelled = [], []
    for name in skill_names():
        p = page(name)
        if not os.path.isfile(p):
            missing.append(name)
            continue
        first = read(p).split("\n")
        h1 = next((l for l in first if l.startswith("# ")), "")
        if ("ktkit:%s " % name) not in h1:
            mislabelled.append("%s -> %r" % (name, h1[:70]))
    check("H1 every skill has references/help.md", not missing, missing)
    check("H1 every page's H1 names the skill it lives in",
          not mislabelled, mislabelled[:4])


def test_h2_no_page_documents_a_flag_its_skill_does_not_mention():
    """A flag may belong to the page's own skill, or to one named on that line.

    The second case is real and worth allowing: a `See also` line pointing at
    `--lang` on `/ktkit:spec-recon` is correct help, and rejecting it would push
    pages towards saying less than they usefully could.
    """
    bad = []
    for name in skill_names():
        if not os.path.isfile(page(name)):
            continue
        own = skill_md(name)
        for line in read(page(name)).split("\n"):
            for flag in FLAG_RE.findall(line):
                if flag in UNIVERSAL or flag in own:
                    continue
                elsewhere = [o for o in skills_named_on(line)
                             if o != name and flag in skill_md(o)]
                if not elsewhere:
                    bad.append("%s: %s  (%s)" % (name, flag, line.strip()[:60]))
    check("H2 every flag a page documents is one its skill accepts",
          not bad, bad[:6])


def test_h3_no_documented_flag_is_missing_from_the_page():
    """The other direction. Only skills that declare `## Arguments` can be held
    to it -- the rest have no machine-readable argument surface to compare."""
    bad, covered = [], []
    for name in skill_names():
        section = arguments_section(name)
        if not section:
            continue
        covered.append(name)
        text = read(page(name)) if os.path.isfile(page(name)) else ""
        for flag in sorted(declared_flags(name)):
            if flag not in text:
                bad.append("%s: %s documented in SKILL.md, absent from help"
                           % (name, flag))
    check("H3 every flag in a `## Arguments` section appears in its page",
          not bad, bad[:6])
    check("H3 covered the skills that carry an argument surface",
          len(covered) >= 3, covered)


def test_h4_every_cross_reference_resolves():
    known = set(skill_names())
    unknown = []
    for name in skill_names():
        if not os.path.isfile(page(name)):
            continue
        for ref in KTKIT_RE.findall(read(page(name))):
            if ref not in known:
                unknown.append("%s -> ktkit:%s" % (name, ref))
    check("H4 every ktkit:<name> a page points at is a real skill",
          not unknown, sorted(set(unknown))[:6])


def test_h5_the_script_sees_exactly_the_skills_on_disk():
    rc, out = run_help("--list")
    check("H5 --list exits 0", rc == 0, out[:200])
    check("H5 --list is exactly the skill directories",
          out.split() == skill_names(), out.split())


def test_h6_every_page_renders_and_an_unknown_name_fails():
    for name in skill_names():
        rc, out = run_help(name)
        check("H6 help.py %s renders" % name, rc == 0 and len(out) > 200,
              "rc=%d len=%d" % (rc, len(out)))
    rc, out = run_help("no-such-skill")
    check("H6 an unknown name exits non-zero", rc != 0, out[:120])
    check("H6 an unknown name lists what is known", "Known:" in out, out[:120])
    rc, _out = run_help("--all")
    check("H6 --all exits 0", rc == 0)


def test_h7_the_index_carries_every_skill_with_a_written_tagline():
    rc, out = run_help()
    check("H7 the index exits 0", rc == 0, out[:200])
    for name in skill_names():
        hits = len(re.findall(r"^  ktkit:%s\s" % re.escape(name), out, re.M))
        check("H7 %s appears in the index exactly once" % name, hits == 1, hits)
    # The fallback summary is the frontmatter description, which always starts
    # with a capital or ends up truncated. A written tagline is neither.
    fallback = [l for l in out.split("\n")
                if l.startswith("  ktkit:") and l.rstrip().endswith("...")]
    check("H7 no skill is falling back to a truncated description",
          not fallback, [f.strip()[:60] for f in fallback])


def test_h8_a_page_stays_inside_its_budget():
    """A page is read in full when it is asked for. Long pages are the failure
    mode where help costs more than reading the skill would have."""
    over = []
    for name in skill_names():
        if not os.path.isfile(page(name)):
            continue
        n = len(read(page(name)).split("\n"))
        if n > MAX_PAGE_LINES:
            over.append("%s: %d lines" % (name, n))
    check("H8 no page exceeds %d lines" % MAX_PAGE_LINES, not over, over)


def test_h9_the_hook_points_at_a_script_that_exists():
    text = read(HOOK)
    check("H9 the hook installs a help protocol", "Help protocol" in text)
    m = re.search(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+)", text)
    check("H9 the hook names a script path", m is not None)
    if m:
        check("H9 the script the hook names exists",
              os.path.isfile(os.path.join(ROOT, m.group(1))), m.group(1))


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
