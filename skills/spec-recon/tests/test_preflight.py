#!/usr/bin/env python3
"""Tests for the shared preflight gate.

These lock down the two behaviours the gate exists for, both of which were
learned the expensive way and are easy to undo by accident:

  1. A missing capability makes the process exit non-zero AND prints a command
     the operator can run. A gate that fails without saying how to fix it just
     moves the debugging session, it does not shorten it.

  2. A capability that is merely unreachable here -- an SSH remote inside a
     sandbox that denies the SSH agent -- is a SKIP, not a FAIL. Turning it into
     a FAIL stops runs that could have finished; turning it into a silent PASS
     lets a later step report "not found" about data it never looked at.

Run:  python3 skills/spec-recon/tests/test_preflight.py
"""
import io
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
PREFLIGHT = os.path.join(ROOT, "scripts", "preflight.py")

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


sys.path.insert(0, os.path.join(ROOT, "scripts"))

def run(args, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.Popen([sys.executable, PREFLIGHT] + args,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=e)
    out, err = p.communicate()
    return p.returncode, out.decode("utf-8"), err.decode("utf-8")


def test_script_exists():
    check("preflight.py is at the plugin root, not inside a skill",
          os.path.isfile(PREFLIGHT), PREFLIGHT)


def test_unreadable_input_fails_with_a_reason():
    rc, out, _ = run(["--groups", "read", "--inputs", "/nonexistent/x.md"])
    check("missing input exits 1", rc == 1, "rc=%d" % rc)
    check("missing input is reported FAIL", "FAIL" in out and "read inputs" in out, out)
    check("missing input names the path", "/nonexistent/x.md" in out, out)


def test_unwritable_out_fails_with_a_fix():
    rc, out, _ = run(["--groups", "write", "--out", "/dev/null/cannot/exist"])
    check("unwritable --out exits 1", rc == 1, "rc=%d" % rc)
    check("unwritable --out suggests a fix", "/sandbox" in out or "--out" in out, out)


def test_write_group_creates_the_step_directories():
    d = tempfile.mkdtemp()
    target = os.path.join(d, "report-base")
    rc, out, _ = run(["--groups", "write", "--out", target])
    check("writable --out exits 0", rc == 0, out)
    check("write group creates steps/", os.path.isdir(os.path.join(target, "steps")))
    check("write group creates evidence/", os.path.isdir(os.path.join(target, "evidence")))


def test_forge_without_a_token_fails_and_says_how():
    # Both variables are blanked; `gh auth token` is only consulted when they are
    # empty, so on a machine with gh logged in this still exercises the branch
    # only when gh is absent. Assert on the shape of the output either way.
    rc, out, _ = run(["--groups", "forge"], env={"GH_TOKEN": "", "GITHUB_TOKEN": ""})
    if "FAIL  forge token" in out:
        check("no token exits 1", rc == 1, "rc=%d" % rc)
        check("no token prints the login command", "gh auth login" in out, out)
    else:
        # gh supplied a token from the keyring: the gate must then have proved
        # reachability with a real request rather than trusting `gh auth status`.
        check("forge gate proves reachability with a real request",
              "forge api" in out, out)


def test_forge_never_shells_out_to_gh_api():
    """`gh api` dies on TLS inside the sandbox. The gate must not depend on it."""
    src = io.open(PREFLIGHT, encoding="utf-8").read()
    # Match the argv list a subprocess call would build, not the bare word:
    # "status" also appears as a dict key and an attribute name.
    gh_calls = re.findall(r'\[\s*"gh"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"', src)
    check("preflight never runs `gh api`",
          not any(c[0] == "api" for c in gh_calls), str(gh_calls))
    check("preflight never runs `gh auth status`",
          ("auth", "status") not in gh_calls, str(gh_calls))
    check("the only gh call is the credential read",
          gh_calls == [("auth", "token")], str(gh_calls))
    check("preflight uses urllib as the forge transport",
          "urllib.request" in src)


def test_ssh_remote_is_skip_not_fail():
    """An SSH remote unreachable inside the sandbox must not block the run."""
    rc, out, _ = run(["--groups", "vcs", "--repo", ROOT])
    lines = [l for l in out.splitlines() if "remote" in l or "ls-remote" in l]
    if any(l.startswith("SKIP") for l in lines):
        check("ssh remote unreachable here is SKIP", True)
        check("a SKIP does not fail the gate", rc == 0, "rc=%d\n%s" % (rc, out))
        check("the SKIP explains itself",
              any("not-accessed" in l for l in lines), out)
    else:
        # Reachable remote, or none configured: the gate must still be green.
        check("vcs group green when the remote is reachable", rc == 0, out)


def test_report_file_is_written():
    d = tempfile.mkdtemp()
    rep = os.path.join(d, "steps", "00-preflight.md")
    run(["--groups", "runtime", "--report", rep])
    check("--report writes the step file", os.path.isfile(rep))
    if os.path.isfile(rep):
        body = io.open(rep, encoding="utf-8").read()
        check("step file names the groups probed", "Groups probed" in body, body[:200])


def test_artifacts_group_creates_the_layout_and_repeats_cleanly():
    """The layout is a rule, so the gate creates it rather than complaining.

    The second run matters as much as the first: a gate that reports "created"
    every time is a gate that is doing something it should not, and a skill that
    runs it twice in one session would see its own artifacts as new.
    """
    d = tempfile.mkdtemp()
    rc, out, _ = run(["--groups", "artifacts", "--repo", d])
    check("artifacts group exits 0 on a bare repository", rc == 0, out)
    root = os.path.join(d, ".claude", "claude")
    missing = [s for s in ("prompts", "analyze", "specs", "pipeline",
                           "implemented", "compacts")
               if not os.path.isdir(os.path.join(root, s))]
    check("artifacts group creates every artifact directory", not missing, missing)
    check("the first run says what it created", "created" in out, out)

    rc2, out2, _ = run(["--groups", "artifacts", "--repo", d])
    check("re-running is idempotent", rc2 == 0, out2)
    check("the second run creates nothing", "created" not in out2, out2)


def test_artifacts_group_never_writes_outside_dot_claude():
    """The only filesystem change permitted is inside `<repo>/.claude/`."""
    d = tempfile.mkdtemp()
    run(["--groups", "artifacts", "--repo", d])
    stray = [n for n in os.listdir(d) if n != ".claude"]
    check("nothing is created beside .claude/", not stray, stray)


def test_speckit_group_fails_with_a_way_out():
    """Missing scaffolding must name the command that creates it -- and only that.

    spec-kit is a prerequisite, so there is no second way out to offer. A fix
    line that still mentioned `--no-speckit` would be describing an escape hatch
    that no longer exists, which is worse than naming none.
    """
    d = tempfile.mkdtemp()
    rc, out, _ = run(["--groups", "speckit", "--repo", d])
    check("missing .specify/ exits 1", rc == 1, "rc=%d\n%s" % (rc, out))
    check("missing .specify/ is reported FAIL",
          "FAIL" in out and "speckit scaffolding" in out, out)
    check("the fix names `specify init`", "specify init" in out, out)
    check("and offers no --no-speckit escape hatch, which no longer exists",
          "--no-speckit" not in out, out)


def test_speckit_skills_are_found_under_either_layout():
    """speckit has shipped its Claude skills two ways; both must be recognised.

    The check that knew only `~/.claude/skills/speckit.converge` could never be
    satisfied by a current speckit, which writes
    `<repo>/.claude/skills/speckit-converge` instead -- so a machine that had
    upgraded correctly kept being told to upgrade. A warning that cannot be
    cleared is a warning people learn to scroll past.

    HOME is faked throughout. A machine that ran `scripts/speckit_global.py` has
    speckit installed at user level on purpose, and without the fake every "not
    present" assertion here would be answered by that real installation instead
    of by the fixture -- passing or failing according to what the developer
    happened to have installed.
    """
    import preflight                                            # noqa: E402

    old_home = os.environ.get("HOME")
    empty = tempfile.mkdtemp()
    try:
        os.environ["HOME"] = empty

        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, ".specify"))
        check("neither layout present -> converge is not found",
              preflight.speckit_skill(d, preflight.SPECKIT_CONVERGE_NAMES) is None)

        # The layout a current `specify init --integration claude` writes.
        hyphen = os.path.join(d, ".claude", "skills", "speckit-converge")
        os.makedirs(hyphen)
        found = preflight.speckit_skill(d, preflight.SPECKIT_CONVERGE_NAMES)
        check("project-local hyphenated layout is found", found == hyphen, found)

        rc, out, _ = run(["--groups", "speckit", "--repo", d], env={"HOME": empty})
        check("and it reports PASS rather than WARN",
              "PASS  speckit converge" in out, out)
        check("a repo with converge does not tell you to upgrade",
              "predates 1.0.0" not in out, out)

        # The older user-level dotted layout still answers when nothing else does.
        e2 = tempfile.mkdtemp()
        os.makedirs(os.path.join(e2, ".specify"))
        home = tempfile.mkdtemp()
        os.makedirs(os.path.join(home, ".claude", "skills", "speckit.converge"))
        os.environ["HOME"] = home
        found = preflight.speckit_skill(e2, preflight.SPECKIT_CONVERGE_NAMES)
        check("user-level dotted layout is still found",
              found is not None and found.startswith(home), found)

        # The fix text must name the thing that actually installs the skills,
        # and it must not be `specify init --here`: that renders fifteen
        # directories into THIS repository's `.claude/skills/`, which is checked
        # in and shared on the repositories this plugin is used against. The
        # remediation for a missing skill is the global installer.
        f = tempfile.mkdtemp()
        os.makedirs(os.path.join(f, ".specify"))
        rc, out, _ = run(["--groups", "speckit", "--repo", f], env={"HOME": empty})
        skills_row = [l for l in out.splitlines() if "speckit skills" in l]
        check("the missing-skills row is the one reporting the failure",
              len(skills_row) == 1 and skills_row[0].startswith("FAIL"), skills_row)
        row = skills_row[0] if skills_row else ""
        check("the skills fix names the global installer",
              "speckit_global.py" in row, row)
        check("and does not send the reader back to a project-local init",
              "specify init" not in row, row)
    finally:
        if old_home is not None:
            os.environ["HOME"] = old_home


def test_converge_is_a_fail_not_a_warning_since_5_0():
    """`converge` stopped being optional when step 07 started closing the loop.

    It was a WARN while the chain could still produce a spec and some code and
    call that finished. From 5.0.0 step 07 is the only step that opens the
    delivered code and asks whether it satisfies the spec, so its absence is the
    difference between a loop and a pipeline -- and a difference that size is
    not a warning.
    """
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, ".specify"))
    os.makedirs(os.path.join(d, ".claude", "skills", "speckit-specify"))
    empty = tempfile.mkdtemp()
    rc, out, _ = run(["--groups", "speckit", "--repo", d], env={"HOME": empty})
    row = [l for l in out.splitlines() if "speckit converge" in l]
    check("converge has a row of its own", len(row) == 1, out)
    if not row:
        return
    check("a missing converge is FAIL, not WARN",
          row[0].startswith("FAIL"), row[0])
    check("and it fails the run", rc == 1, "rc=%d\n%s" % (rc, out))
    check("the fix names the upgrade and the installer",
          "uv tool upgrade specify-cli" in row[0]
          and "speckit_global.py" in row[0], row[0])


def test_testcmd_group_reports_where_not_what():
    """The gate that costs nothing needs a command this plugin cannot supply.

    Reporting WHERE it is written is honest; reporting what it is would mean
    guessing, and a green from the wrong command is worse than no gate at all --
    a gate nobody trusts gets removed, a gate that is trusted and wrong gets
    believed.
    """
    bare = tempfile.mkdtemp()
    rc, out, _ = run(["--groups", "testcmd", "--repo", bare])
    check("a repository that states no command is SKIP, not FAIL",
          "SKIP" in out and "FAIL" not in out, out)
    check("SKIP never blocks", rc == 0, "rc=%d\n%s" % (rc, out))
    check("and it says the skill asks once rather than guessing",
          "asks once" in out and "never guesses" in out, out)

    mk = tempfile.mkdtemp()
    io.open(os.path.join(mk, "Makefile"), "w",
            encoding="utf-8").write("test:\n\techo hi\n")
    rc, out, _ = run(["--groups", "testcmd", "--repo", mk])
    check("a Makefile with a test target is found", "PASS" in out, out)
    check("and the row names the file, not a command",
          "Makefile" in out and "echo hi" not in out, out)

    # A package.json with no test script must NOT be reported as a source.
    nope = tempfile.mkdtemp()
    io.open(os.path.join(nope, "package.json"), "w",
            encoding="utf-8").write('{"scripts": {"build": "tsc"}}')
    rc, out, _ = run(["--groups", "testcmd", "--repo", nope])
    check("a package.json without a test script is not mistaken for one",
          "SKIP" in out, out)


def test_superpowers_group_fails_loudly_when_absent():
    """The BUG lane has no spec to fall back on, so this is FAIL and never WARN.

    A missing `systematic-debugging` does not leave a lesser version of
    `/ktkit:rca` -- it leaves improvisation under the same name, which is the one
    thing every other group in this file exists to prevent.
    """
    empty = tempfile.mkdtemp()
    os.makedirs(os.path.join(empty, ".claude", "plugins"))
    io.open(os.path.join(empty, ".claude", "plugins",
                         "installed_plugins.json"), "w",
            encoding="utf-8").write('{"plugins": {}}')
    rc, out, _ = run(["--groups", "superpowers"], env={"HOME": empty})
    check("a missing superpowers exits 1", rc == 1, "rc=%d\n%s" % (rc, out))
    check("it is FAIL, not WARN", "FAIL" in out and "WARN" not in out, out)
    check("and the fix text is the install command",
          "claude plugin install superpowers@claude-plugins-official" in out, out)

    # Installed, but without the skills the lane calls: a different failure, and
    # the fix is an update rather than an install.
    half = tempfile.mkdtemp()
    os.makedirs(os.path.join(half, ".claude", "plugins"))
    root = tempfile.mkdtemp()
    os.makedirs(os.path.join(root, "skills", "systematic-debugging"))
    io.open(os.path.join(half, ".claude", "plugins",
                         "installed_plugins.json"), "w",
            encoding="utf-8").write(
        '{"plugins": {"superpowers@claude-plugins-official": '
        '[{"installPath": "%s"}]}}' % root)
    rc, out, _ = run(["--groups", "superpowers"], env={"HOME": half})
    check("an incomplete superpowers exits 1 too", rc == 1,
          "rc=%d\n%s" % (rc, out))
    check("it names the skills that are absent",
          "test-driven-development" in out, out)
    check("and tells you to update, not to install",
          "claude plugin update" in out, out)


def test_mcp_group_never_tells_the_user_to_install_the_server():
    """The plugin ships the server, so the fix is never "go install it".

    A hand-installed second copy registers under a different tool name, and the
    skills call the plugin's name. Telling a user to install it would produce a
    server that runs and a skill that still cannot see it.
    """
    rc, out, _ = run(["--groups", "mcp"])
    check("mcp group runs", rc in (0, 1), "rc=%d" % rc)
    lowered = out.lower()
    check("mcp group never suggests installing the server by hand",
          "install sequential-thinking" not in lowered
          and "add the sequential-thinking" not in lowered, out)
    check("mcp group names the plugin as the owner of the server",
          ".mcp.json" in out or "do not add a second copy" in out, out)


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
