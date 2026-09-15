#!/usr/bin/env python3
"""Stop a ktkit skill before it spends anything, when a prerequisite is missing.

ktkit has exactly two external dependencies, and both are deliberate: spec-kit
owns the truth artifacts and `converge`, superpowers owns execution discipline.
The README states them as requirements. Nothing enforced them.

A skill that discovers halfway through that `speckit-specify` is not installed
has already dispatched agents, already written half a trace directory, and the
person reading the failure has to work out which of sixteen skills to blame. The
run should never have started.

`scripts/preflight.py` is the in-run gate and stays where it is -- it proves a
capability with a real request, and it reports far more than this. This hook is
the outer one: it fires before the Skill tool runs at all, costs one stat per
directory, and answers one question -- may this skill start.

Two scopes, because the two dependencies are not needed by the same skills:

  superpowers   every ktkit skill except `help`. It is the execution discipline
                the whole plugin defers to, and `help` is exempt because a gate
                that hides the instructions for clearing it is a trap.
  speckit       only the skills that preflight the `speckit` group. Listed in
                SPECKIT_SKILLS and kept honest by
                skills/chain/tests/test_prereq_gate.py, which reads the skill
                bodies and fails when the two disagree.

Fail-open on anything this script cannot measure -- unreadable JSON, an
unexpected payload, an exception. A hook that blocks because it could not parse
its own input would make the plugin unusable for a reason nobody can see.
Fail-closed only on the thing it CAN measure: the dependency is absent.

Contract (plugin-dev/skills/hook-development/SKILL.md): stdin carries
`tool_name` and `tool_input`; stdout carries
`{"hookSpecificOutput": {"permissionDecision": "allow|deny|ask"}, ...}`.

Stdlib only, Python 3.9.
"""
import json
import os
import sys

HOME_SKILLS = os.path.expanduser(os.path.join("~", ".claude", "skills"))
INSTALLED = os.path.expanduser(
    os.path.join("~", ".claude", "plugins", "installed_plugins.json"))

# The minimum this plugin was written against. README lists both.
SUPERPOWERS_MIN = (6, 3, 0)

# The two layouts speckit has shipped its Claude skills under. Project-local
# hyphenated is what 1.0 and later write; user-level dotted is what older
# releases installed and is still on machines that have not re-run the install.
SPECKIT_PROBE = ("speckit-specify", "speckit.specify")

# The skills that run `preflight.py --groups ...speckit...`. Anything else does
# not touch speckit and must not be blocked for its absence.
#
# `bug-fix-specs` was on this list until the BUG lane moved onto superpowers. It
# came off because it stopped preflighting the group -- not because anybody
# remembered this line: P8 of test_prereq_gate.py compares the two and failed
# until it was edited.
# `cr-delta` joined it the same way, in the other direction: it reads a spec-kit
# feature directory, so it preflights the group, so it belongs here. Neither
# edit was remembered -- both were demanded.
SPECKIT_SKILLS = ("chain", "cr-delta", "feat-req-specs", "feat-req-execute")

# `help` prints the install commands. Gating it would hide the way out.
EXEMPT = ("help",)

PREFIX = "ktkit:"


def allow():
    return 0


def deny(message):
    json.dump({"hookSpecificOutput": {"permissionDecision": "deny"},
               "systemMessage": message}, sys.stdout)
    sys.stdout.write("\n")
    return 0


def skill_name(payload):
    """The bare skill name a ktkit invocation names, or None.

    `tool_input.skill` is the Skill tool's own parameter. A payload shaped any
    other way is not something this script understands, and not understanding is
    a reason to stand aside, not to block.
    """
    if payload.get("tool_name") != "Skill":
        return None
    value = (payload.get("tool_input") or {}).get("skill")
    if not isinstance(value, str) or not value.startswith(PREFIX):
        return None
    return value[len(PREFIX):].strip()


def speckit_present():
    repo = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    for name in SPECKIT_PROBE:
        if os.path.isdir(os.path.join(repo, ".claude", "skills", name)):
            return True
        if os.path.isdir(os.path.join(HOME_SKILLS, name)):
            return True
    return False


def parse_version(text):
    parts = []
    for chunk in str(text).split(".")[:3]:
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def superpowers_version():
    """(version_tuple, raw) for an installed superpowers, or (None, None).

    Read from the installed-plugin record rather than from a directory listing:
    a cache directory can be left behind by an uninstall, and this must answer
    "is it installed", not "was it ever".
    """
    try:
        with open(INSTALLED, "r") as fh:
            data = json.load(fh)
    except Exception:                                          # noqa: BLE001
        return None, None
    for key, entries in (data.get("plugins") or {}).items():
        if key.split("@")[0] != "superpowers":
            continue
        for entry in entries or []:
            raw = entry.get("version")
            if raw and raw != "unknown":
                return parse_version(raw), raw
            return (0, 0, 0), raw or "unknown"
    return None, None


def missing(name):
    """The prerequisites this skill needs and does not have."""
    gaps = []
    version, raw = superpowers_version()
    if version is None:
        gaps.append(
            "superpowers is not installed\n"
            "      claude plugin install superpowers@claude-plugins-official")
    elif version < SUPERPOWERS_MIN:
        gaps.append(
            "superpowers %s is older than %s\n"
            "      claude plugin update superpowers@claude-plugins-official"
            % (raw, ".".join(str(n) for n in SUPERPOWERS_MIN)))
    if name in SPECKIT_SKILLS and not speckit_present():
        gaps.append(
            "speckit's Claude skills are not installed\n"
            "      uv tool install specify-cli     (or: brew install specify)\n"
            "      python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/speckit_global.py\"")
    return gaps


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:                                          # noqa: BLE001
        return allow()
    if not isinstance(payload, dict):
        return allow()
    try:
        name = skill_name(payload)
        if not name or name in EXEMPT:
            return allow()
        gaps = missing(name)
        if not gaps:
            return allow()
        lines = ["⛔ /ktkit:%s did not start. ktkit has two required "
                 "dependencies and one is missing:" % name, ""]
        for gap in gaps:
            lines.append("  ✗ %s" % gap)
        lines += ["",
                  "Nothing ran. No tokens were spent.",
                  "`/ktkit:help` still works and lists both."]
        return deny("\n".join(lines))
    except Exception:                                          # noqa: BLE001
        # Measuring failed, which is not the same as the dependency being
        # absent. Standing aside is recoverable; blocking on a bug is not.
        return allow()


if __name__ == "__main__":
    sys.exit(main())
