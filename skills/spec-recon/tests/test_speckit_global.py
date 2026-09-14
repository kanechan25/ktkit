#!/usr/bin/env python3
"""speckit's skills belong to the machine, not to somebody's shared repository.

`specify init --integration claude` writes fifteen directories into
`<repo>/.claude/skills/`, and there is no flag that changes it -- the Claude
integration hard-codes `folder: ".claude/"` and `commands_subdir: "skills"`.

That is harmless where `.claude/skills/` is a scratch directory. It is not where
the directory is checked in: two real repositories here track 76 and 81 files
under it, shared across a team, and `specify init` dropped fifteen untracked
directories into the middle of them. Nothing was committed, but the next
`git add -A` would have committed speckit into somebody else's project.

So the skills are installed once, globally, and no repository gains a file.

  G1  installing touches `~/.claude/skills` and nothing else
  G2  the pre-1.0 dotted layout is removed, not left alongside the new one
  G3  a second run changes nothing that matters -- it is safe to re-run
  G4  nothing outside the `speckit` prefix is ever touched
  G5  --dry-run writes nothing at all
  G6  --help lists the flags, so the wiring check can see them

G4 is the one that matters most. This script runs against the directory holding
every skill the user has, and the blast radius of a wrong prefix match is all of
them. The check is written against a directory seeded with decoys.

The rendering itself is speckit's job, not this script's: it runs `specify init`
into a throwaway directory and copies the result. Tests that would need the real
CLI are marked and skipped when it is absent, so this file still runs on a
machine that has never installed speckit.

Run:  python3 skills/spec-recon/tests/test_speckit_global.py
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SCRIPT = os.path.join(ROOT, "scripts", "speckit_global.py")

sys.path.insert(0, os.path.join(ROOT, "scripts"))
import speckit_global as sg                                    # noqa: E402

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


def skill_dir(root, name, body="x"):
    d = os.path.join(root, name)
    os.makedirs(d)
    io.open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8").write(body)
    return d


def has_specify():
    return shutil.which("specify") is not None


def test_g4_nothing_outside_the_speckit_prefix_is_touched():
    """The blast radius is every skill the user owns. Seed decoys and prove it."""
    home = tempfile.mkdtemp(prefix="sg-home-")
    old = sg.HOME_SKILLS
    try:
        sg.HOME_SKILLS = home
        # Decoys: names that share a prefix, a substring, or a theme.
        # No case decoy: macOS mounts a case-insensitive filesystem by default,
        # so `Speckit-Analyze` and `speckit-analyze` are the same directory there
        # and the assertion would test the filesystem rather than the script.
        for n in ("speckitchen", "my-speckit-fork", "spec-kit", "analyze-comments",
                  "check-pr", "speckit"):
            skill_dir(home, n)
        # The two layouts that ARE ours.
        skill_dir(home, "speckit-analyze")
        skill_dir(home, "speckit.plan")

        found = sg.installed(sg.PREFIX_NEW)
        check("G4 `speckit-*` matches only the hyphenated layout",
              found == ["speckit-analyze"], found)
        old_found = sg.installed(sg.PREFIX_OLD)
        check("G4 `speckit.*` matches only the dotted layout",
              old_found == ["speckit.plan"], old_found)
        check("G4 `speckitchen` is not mistaken for one of ours",
              "speckitchen" not in found + old_found)
        check("G4 a bare `speckit` directory is not matched",
              "speckit" not in found + old_found)
        # And the plan built from that never proposes removing a decoy.
        _ins, _rep, rm = sg.plan(["speckit-analyze", "speckit-converge"])
        check("G4 the removal plan names only speckit skills",
              all(n.startswith(("speckit-", "speckit.")) for n in rm), rm)
        check("G4 a decoy is never scheduled for removal",
              "speckitchen" not in rm and "spec-kit" not in rm, rm)
    finally:
        sg.HOME_SKILLS = old
        shutil.rmtree(home, ignore_errors=True)


def test_g2_the_pre_1_0_layout_is_removed_not_left_alongside():
    """Both layouts present means every speckit skill appears twice, half of them
    from a release with no `converge`."""
    home = tempfile.mkdtemp(prefix="sg-home-")
    old = sg.HOME_SKILLS
    try:
        sg.HOME_SKILLS = home
        for n in ("speckit.analyze", "speckit.plan", "speckit.specify"):
            skill_dir(home, n)
        rendered = ["speckit-analyze", "speckit-plan", "speckit-converge"]
        ins, rep, rm = sg.plan(rendered)
        check("G2 every dotted skill is scheduled for removal",
              sorted(rm) == ["speckit.analyze", "speckit.plan", "speckit.specify"], rm)
        check("G2 all rendered skills are scheduled for install",
              sorted(ins) == sorted(rendered), ins)
        check("G2 nothing is scheduled for replacement on a clean machine",
              rep == [], rep)
    finally:
        sg.HOME_SKILLS = old
        shutil.rmtree(home, ignore_errors=True)


def test_g2_a_skill_speckit_no_longer_renders_is_removed_too():
    """A command dropped upstream must not linger as a stale hyphenated copy."""
    home = tempfile.mkdtemp(prefix="sg-home-")
    old = sg.HOME_SKILLS
    try:
        sg.HOME_SKILLS = home
        for n in ("speckit-analyze", "speckit-retired"):
            skill_dir(home, n)
        _ins, rep, rm = sg.plan(["speckit-analyze"])
        check("G2 a no-longer-rendered skill is removed",
              rm == ["speckit-retired"], rm)
        check("G2 one that still renders is replaced, not removed",
              rep == ["speckit-analyze"], rep)
    finally:
        sg.HOME_SKILLS = old
        shutil.rmtree(home, ignore_errors=True)


def test_g1_apply_writes_only_inside_the_skills_directory():
    home = tempfile.mkdtemp(prefix="sg-home-")
    src = tempfile.mkdtemp(prefix="sg-src-")
    old = sg.HOME_SKILLS
    try:
        sg.HOME_SKILLS = home
        skill_dir(home, "analyze-comments", "the user's own skill")
        skill_dir(home, "speckit.plan", "stale")
        skill_dir(src, "speckit-plan", "fresh")
        skill_dir(src, "speckit-converge", "fresh")

        sg.apply(src, ["speckit-plan", "speckit-converge"], ["speckit.plan"])
        now = sorted(os.listdir(home))
        check("G1 the rendered skills are installed",
              "speckit-plan" in now and "speckit-converge" in now, now)
        check("G1 the stale layout is gone", "speckit.plan" not in now, now)
        check("G1 the user's own skill is untouched",
              "analyze-comments" in now, now)
        body = io.open(os.path.join(home, "analyze-comments", "SKILL.md"),
                       encoding="utf-8").read()
        check("G1 and its contents are unchanged", body == "the user's own skill")
        fresh = io.open(os.path.join(home, "speckit-plan", "SKILL.md"),
                        encoding="utf-8").read()
        check("G1 a replaced skill carries the new content", fresh == "fresh")
    finally:
        sg.HOME_SKILLS = old
        shutil.rmtree(home, ignore_errors=True)
        shutil.rmtree(src, ignore_errors=True)


def test_g3_a_second_run_is_safe():
    """Re-running refreshes from the current CLI; it must not accumulate."""
    home = tempfile.mkdtemp(prefix="sg-home-")
    src = tempfile.mkdtemp(prefix="sg-src-")
    old = sg.HOME_SKILLS
    try:
        sg.HOME_SKILLS = home
        skill_dir(src, "speckit-plan", "v1")
        sg.apply(src, ["speckit-plan"], [])
        first = sorted(os.listdir(home))
        shutil.rmtree(os.path.join(src, "speckit-plan"))
        skill_dir(src, "speckit-plan", "v2")
        _ins, rep, rm = sg.plan(["speckit-plan"])
        sg.apply(src, ["speckit-plan"], rm)
        check("G3 the set of skills is unchanged by a second run",
              sorted(os.listdir(home)) == first, os.listdir(home))
        body = io.open(os.path.join(home, "speckit-plan", "SKILL.md"),
                       encoding="utf-8").read()
        check("G3 and the content is refreshed from the source", body == "v2", body)
        check("G3 the second run reports a replacement, not an install",
              rep == ["speckit-plan"], rep)
    finally:
        sg.HOME_SKILLS = old
        shutil.rmtree(home, ignore_errors=True)
        shutil.rmtree(src, ignore_errors=True)


def test_g5_dry_run_writes_nothing():
    if not has_specify():
        print("ok   G5 skipped: `specify` is not installed")
        return
    home = tempfile.mkdtemp(prefix="sg-home-")
    before = sorted(os.listdir(os.path.expanduser("~/.claude/skills"))
                    if os.path.isdir(os.path.expanduser("~/.claude/skills")) else [])
    rc, out = run("--dry-run")
    after = sorted(os.listdir(os.path.expanduser("~/.claude/skills"))
                   if os.path.isdir(os.path.expanduser("~/.claude/skills")) else [])
    check("G5 --dry-run exits 0", rc == 0, out[-300:])
    check("G5 --dry-run says it wrote nothing",
          "nothing was written" in out, out[-200:])
    check("G5 and the real skills directory is unchanged", before == after,
          set(before) ^ set(after))
    shutil.rmtree(home, ignore_errors=True)


def test_g6_help_lists_the_flags():
    rc, out = run("--help")
    check("G6 --help exits 0", rc == 0, out[:200])
    for flag in ("--dry-run", "--list"):
        check("G6 --help names %s" % flag, flag in out, out[:400])


def test_g1_the_destination_is_the_users_skills_directory():
    check("G1 the destination is ~/.claude/skills",
          sg.HOME_SKILLS == os.path.expanduser(os.path.join("~", ".claude", "skills")),
          sg.HOME_SKILLS)
    body = io.open(SCRIPT, encoding="utf-8").read()
    check("G1 the docstring explains why project-local is the problem",
          "shared" in body and "git add -A" in body)
    check("G1 and states that rendering is speckit's job, not this script's",
          "Rendered by speckit, not by this script" in body)


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
