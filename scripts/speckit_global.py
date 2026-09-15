#!/usr/bin/env python3
"""Install speckit's Claude skills once, for every repository, instead of into each one.

speckit's Claude integration writes its skills **into the project**:

    IntegrationBase.skills_dest  ->  project_root / config["folder"] / commands_subdir
    ClaudeIntegration.config     ->  {"folder": ".claude/", "commands_subdir": "skills"}

There is no flag that changes it. For a repository whose `.claude/skills/` is a
personal scratch directory that is fine. For one whose `.claude/skills/` is
checked in and shared -- 76 tracked files in one real case, 81 in another -- it
is not: `specify init` drops fifteen untracked directories in the middle of a
directory the whole team commits to, and the next `git add -A` puts speckit in
their repository.

The skills themselves are project-agnostic. They reference `.specify/` relative
to the repository root and resolve it at run time -- "Run
`.specify/scripts/bash/check-prerequisites.sh` ... once from repo root". Only the
*scaffolding* is per-project. So a single copy under `~/.claude/skills/` serves
every repository, and no repository gains a file.

    speckit_global.py --dry-run     what would change, and nothing else
    speckit_global.py               install, replacing what is there
    speckit_global.py --list        what is installed now

**Rendered by speckit, not by this script.** The skills are produced by running
`specify init` into a throwaway directory and copying the result out. Rebuilding
the frontmatter here would be a second renderer to keep in step with the first,
and it would drift the first time speckit changed a field.

Two layouts exist and this removes the older one. speckit before 1.0 installed
`~/.claude/skills/speckit.<name>/` (a dot); 1.0 and later write
`<repo>/.claude/skills/speckit-<name>/` (a hyphen). Leaving both in place means
every speckit skill appears twice in the picker, half of them from a release that
has no `converge`.

Nothing outside `~/.claude/skills/speckit*` is touched, ever. A directory that
does not match that prefix is not this script's business even when it looks
related.

Stdlib only, Python 3.9.
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile

HOME_SKILLS = os.path.expanduser(os.path.join("~", ".claude", "skills"))
# The two prefixes speckit has shipped. `.` is the pre-1.0 layout and is removed;
# `-` is what current speckit renders and is what gets installed.
PREFIX_NEW = "speckit-"
PREFIX_OLD = "speckit."


def installed(prefix):
    return sorted(os.path.basename(p) for p in
                  glob.glob(os.path.join(HOME_SKILLS, prefix + "*"))
                  if os.path.isdir(p))


def render(tmp):
    """Let speckit render its own skills into a throwaway project."""
    proj = os.path.join(tmp, "render")
    os.makedirs(proj)
    cmd = ["specify", "init", "--here", "--force", "--non-interactive",
           "--integration", "claude"]
    try:
        p = subprocess.Popen(cmd, cwd=proj, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        out, _ = p.communicate(timeout=180)
    except OSError:
        return None, ("`specify` not found on PATH -> uv tool install specify-cli, "
                      "or brew install specify")
    except subprocess.TimeoutExpired:
        return None, "`specify init` did not finish within 180s"
    if p.returncode != 0:
        return None, ("`specify init` exited %d:\n%s"
                      % (p.returncode, out.decode("utf-8", "replace")[-800:]))
    src = os.path.join(proj, ".claude", "skills")
    if not os.path.isdir(src):
        return None, ("`specify init` wrote no %s -- was --integration claude "
                      "accepted?" % os.path.join(".claude", "skills"))
    found = sorted(n for n in os.listdir(src) if n.startswith(PREFIX_NEW)
                   and os.path.isdir(os.path.join(src, n)))
    if not found:
        return None, "`specify init` wrote no %s* skills" % PREFIX_NEW
    return (src, found), None


def plan(found):
    """(to_install, to_replace, to_remove) -- what the run would change."""
    have_new, have_old = set(installed(PREFIX_NEW)), set(installed(PREFIX_OLD))
    to_replace = sorted(set(found) & have_new)
    to_install = sorted(set(found) - have_new)
    # A `speckit-*` that current speckit no longer renders is stale too.
    to_remove = sorted(have_old) + sorted(have_new - set(found))
    return to_install, to_replace, to_remove


def apply(src, found, to_remove):
    for name in to_remove:
        shutil.rmtree(os.path.join(HOME_SKILLS, name), ignore_errors=True)
    for name in found:
        dest = os.path.join(HOME_SKILLS, name)
        shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(os.path.join(src, name), dest)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="speckit_global.py",
        description="Install speckit's Claude skills into ~/.claude/skills, "
                    "so no repository gains a file.")
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would change and stop")
    ap.add_argument("--list", action="store_true",
                    help="print what is installed now and stop")
    a = ap.parse_args(argv)

    if a.list:
        new, old = installed(PREFIX_NEW), installed(PREFIX_OLD)
        print("%s" % HOME_SKILLS)
        for n in new:
            print("  %s" % n)
        for n in old:
            print("  %s   [pre-1.0 layout -- run without --list to replace]" % n)
        if not new and not old:
            print("  (no speckit skills installed)")
        return 0

    if not os.path.isdir(HOME_SKILLS):
        try:
            os.makedirs(HOME_SKILLS)
        except OSError as e:
            print("FAIL  cannot create %s (%s)" % (HOME_SKILLS, e))
            return 1

    tmp = tempfile.mkdtemp(prefix="speckit-global-")
    try:
        rendered, err = render(tmp)
        if err:
            print("FAIL  %s" % err)
            return 1
        src, found = rendered
        to_install, to_replace, to_remove = plan(found)

        for n in to_install:
            print("install  %s" % n)
        for n in to_replace:
            print("replace  %s" % n)
        for n in to_remove:
            print("remove   %s   (stale layout or no longer rendered)" % n)
        if not (to_install or to_replace or to_remove):
            print("nothing to do -- %d skills already current" % len(found))
            return 0

        if a.dry_run:
            print("\n--dry-run: nothing was written")
            return 0
        apply(src, found, to_remove)
        print("\n%d skills in %s" % (len(installed(PREFIX_NEW)), HOME_SKILLS))
        print("No repository gained a file. `.specify/` scaffolding is still "
              "per-repository -- run `specify init --here` there for that.")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
