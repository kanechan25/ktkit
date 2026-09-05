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


def test_speckit_group_fails_with_both_ways_out():
    """Missing scaffolding must name `specify init` AND `--no-speckit`.

    Naming only the first strands anyone who does not want speckit at all; the
    internalised path is a supported way to run, not a fallback to discover.
    """
    d = tempfile.mkdtemp()
    rc, out, _ = run(["--groups", "speckit", "--repo", d])
    check("missing .specify/ exits 1", rc == 1, "rc=%d\n%s" % (rc, out))
    check("missing .specify/ is reported FAIL",
          "FAIL" in out and "speckit scaffolding" in out, out)
    check("the fix names `specify init`", "specify init" in out, out)
    check("the fix also names --no-speckit", "--no-speckit" in out, out)


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
