#!/usr/bin/env python3
"""The gate that runs before a ktkit skill starts, and what it must not block.

README has always listed spec-kit and superpowers as required. Nothing enforced
it, so the first sign of a missing one was a skill failing somewhere in the
middle, after agents had been dispatched and half a trace directory written.
`hooks/prereq-gate.py` moves that discovery to before the Skill tool runs.

A gate is only as good as the things it refuses to block. Most of these checks
are about the allow side:

  P1  a non-ktkit skill, and a non-Skill tool, pass untouched
  P2  a missing superpowers denies, and the message carries the install command
  P3  a superpowers older than the minimum denies too
  P4  `/ktkit:help` is never blocked -- it is where the fix is written down
  P5  a skill that does not use speckit is not blocked for speckit's absence
  P6  one that does use it is
  P7  input the hook cannot parse means allow, not deny
  P8  SPECKIT_SKILLS matches the skills that actually preflight that group
  P9  the hook is wired into plugin.json as a PreToolUse hook on Skill

P4 is the one that would be most embarrassing to get wrong: a gate that hides
the instructions for clearing it leaves the user with no way forward.

P8 is the two-way half. The list in the hook and the `--groups` lines in the
skill bodies are edited by different people at different times, and the failure
when they drift is silent in the worst direction -- a skill that needs speckit
and is allowed to start without it.

Run:  python3 skills/chain/tests/test_prereq_gate.py
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
HOOK = os.path.join(ROOT, "hooks", "prereq-gate.py")
MANIFEST = os.path.join(ROOT, ".claude-plugin", "plugin.json")

sys.path.insert(0, os.path.join(ROOT, "hooks"))

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def read(path):
    return io.open(path, encoding="utf-8").read()


def fake_home(superpowers=None, speckit=None):
    """A HOME with the plugin record and skills directory we want it to see."""
    home = tempfile.mkdtemp(prefix="pg-home-")
    plugins = os.path.join(home, ".claude", "plugins")
    os.makedirs(plugins)
    record = {"plugins": {}}
    if superpowers is not None:
        record["plugins"]["superpowers@claude-plugins-official"] = [
            {"scope": "user", "version": superpowers}]
    io.open(os.path.join(plugins, "installed_plugins.json"), "w",
            encoding="utf-8").write(json.dumps(record))
    skills = os.path.join(home, ".claude", "skills")
    os.makedirs(skills)
    if speckit:
        os.makedirs(os.path.join(skills, speckit))
    return home


def run(payload, home, project=None):
    """(rc, parsed stdout or None). An empty stdout means allow."""
    env = dict(os.environ)
    env["HOME"] = home
    env["CLAUDE_PROJECT_DIR"] = project or tempfile.mkdtemp(prefix="pg-proj-")
    p = subprocess.Popen([sys.executable, HOOK], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    out, _err = p.communicate(payload.encode("utf-8"))
    text = out.decode("utf-8").strip()
    if not text:
        return p.returncode, None
    try:
        return p.returncode, json.loads(text)
    except ValueError:
        return p.returncode, {"UNPARSEABLE": text}


def call(skill, home, project=None):
    return run(json.dumps({"tool_name": "Skill",
                           "tool_input": {"skill": skill}}), home, project)


def decision(res):
    return ((res or {}).get("hookSpecificOutput") or {}).get("permissionDecision")


def test_p1_nothing_outside_ktkit_is_touched():
    home = fake_home()                       # nothing installed at all
    try:
        for payload in (
                json.dumps({"tool_name": "Skill",
                            "tool_input": {"skill": "superpowers:brainstorming"}}),
                json.dumps({"tool_name": "Read", "tool_input": {"file_path": "x"}}),
                json.dumps({"tool_name": "Skill", "tool_input": {}}),
        ):
            rc, res = run(payload, home)
            check("P1 passes through: %s" % payload[:46],
                  rc == 0 and res is None, (rc, res))
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_p2_a_missing_superpowers_denies_with_the_command():
    home = fake_home(speckit="speckit-specify")
    try:
        rc, res = call("ktkit:chain", home)
        check("P2 a missing superpowers denies", decision(res) == "deny", res)
        msg = (res or {}).get("systemMessage", "")
        check("P2 the message names superpowers", "superpowers" in msg, msg[:120])
        check("P2 and carries the install command",
              "claude plugin install superpowers@claude-plugins-official" in msg,
              msg[:200])
        check("P2 and says nothing was spent", "No tokens were spent" in msg,
              msg[:200])
        check("P2 the hook still exits 0 -- the decision is in the payload",
              rc == 0, rc)
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_p3_an_old_superpowers_denies_too():
    home = fake_home(superpowers="6.2.9", speckit="speckit-specify")
    try:
        rc, res = call("ktkit:chain", home)
        check("P3 a superpowers below the minimum denies",
              decision(res) == "deny", res)
        msg = (res or {}).get("systemMessage", "")
        check("P3 the message names the version found", "6.2.9" in msg, msg[:160])
        check("P3 and tells you to update, not to install",
              "claude plugin update" in msg, msg[:200])
    finally:
        shutil.rmtree(home, ignore_errors=True)
    ok = fake_home(superpowers="6.3.0", speckit="speckit-specify")
    try:
        _rc, res = call("ktkit:chain", ok)
        check("P3 exactly the minimum is accepted", res is None, res)
    finally:
        shutil.rmtree(ok, ignore_errors=True)


def test_p4_help_is_never_blocked():
    home = fake_home()                       # neither dependency present
    try:
        rc, res = call("ktkit:help", home)
        check("P4 /ktkit:help runs with nothing installed",
              rc == 0 and res is None, (rc, res))
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_p5_speckit_is_only_required_where_it_is_used():
    home = fake_home(superpowers="6.3.0")    # no speckit anywhere
    try:
        for skill in ("ccompact", "docs-review", "rca", "raise-issue"):
            _rc, res = call("ktkit:%s" % skill, home)
            check("P5 /ktkit:%s is not blocked for speckit" % skill,
                  res is None, res)
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_p6_the_skills_that_use_speckit_are_blocked_without_it():
    home = fake_home(superpowers="6.3.0")
    try:
        for skill in speckit_skills_declared():
            _rc, res = call("ktkit:%s" % skill, home)
            check("P6 /ktkit:%s is blocked without speckit" % skill,
                  decision(res) == "deny", res)
            msg = (res or {}).get("systemMessage", "")
            check("P6 and is told how to install it",
                  "speckit_global.py" in msg, msg[:200])
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_p7_unparseable_input_allows():
    home = fake_home()
    try:
        for payload in ("not json", "", "[]", '"a string"'):
            rc, res = run(payload, home)
            check("P7 allows on input it cannot use: %r" % payload,
                  rc == 0 and res is None, (rc, res))
    finally:
        shutil.rmtree(home, ignore_errors=True)


def speckit_skills_declared():
    m = re.search(r"^SPECKIT_SKILLS = \(([^)]*)\)", read(HOOK), re.M)
    return sorted(re.findall(r'"([a-z-]+)"', m.group(1))) if m else []


def speckit_skills_observed():
    """Skills whose body runs preflight with the speckit group."""
    found = set()
    base = os.path.join(ROOT, "skills")
    for name in sorted(os.listdir(base)):
        body_path = os.path.join(base, name, "SKILL.md")
        if not os.path.isfile(body_path):
            continue
        for line in read(body_path).splitlines():
            m = re.search(r"--groups ([a-z,]+)", line)
            if m and "speckit" in m.group(1).split(","):
                found.add(name)
                break
    return sorted(found)


def test_p8_the_declared_list_matches_the_skills_that_preflight_speckit():
    declared, observed = speckit_skills_declared(), speckit_skills_observed()
    check("P8 the hook declares a non-empty list", bool(declared), declared)
    check("P8 the sweep found skills preflighting the speckit group",
          bool(observed), observed)
    check("P8 and the two agree", declared == observed, (declared, observed))


def test_p9_the_hook_is_wired_in():
    manifest = json.loads(read(MANIFEST))
    hooks = (manifest.get("hooks") or {}).get("PreToolUse") or []
    entries = [e for e in hooks
               if "prereq-gate.py" in json.dumps(e.get("hooks") or [])]
    check("P9 plugin.json declares a PreToolUse entry for the gate",
          len(entries) == 1, hooks)
    if not entries:
        return
    check("P9 and it matches the Skill tool",
          entries[0].get("matcher") == "Skill", entries[0].get("matcher"))
    cmd = json.dumps(entries[0].get("hooks"))
    check("P9 through ${CLAUDE_PLUGIN_ROOT}, not an absolute path",
          "${CLAUDE_PLUGIN_ROOT}" in cmd, cmd[:160])


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
