#!/usr/bin/env python3
"""Every shipped skill must have frontmatter a YAML parser will actually accept.

This check exists because of a failure with no symptom. `confirm-with-me`
described its own protocol in its description:

    description: ... until user replies `confirm` / `abort` / `modify: <change>`.

`modify: <change>` is a colon followed by a space inside an unquoted YAML scalar,
which ends the scalar and starts a mapping key. A strict parser rejects the whole
document; a lenient one silently keeps whatever came before the colon. Either way
the skill is registered with a description that is not the one that was written,
and the only visible effect is that the skill stops being chosen for the work it
was written for. Nothing errors, nothing logs, and the skill looks fine when you
open it.

The rule, then: a description carrying `: ` must be quoted. That is the single
thing this file enforces, plus the two keys a skill cannot work without.

Stdlib only, like every other check here -- PyYAML is not a dependency of this
plugin and adding one to test a two-line rule would be a poor trade.

Run:  python3 skills/spec-recon/tests/test_skill_frontmatter.py
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SKILLS = os.path.join(ROOT, "skills")

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def skill_files():
    for d in sorted(os.listdir(SKILLS)):
        p = os.path.join(SKILLS, d, "SKILL.md")
        if os.path.isfile(p):
            yield d, p


def frontmatter(path):
    """Return the frontmatter lines, or None when the file has no frontmatter."""
    text = io.open(path, encoding="utf-8").read()
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    return text[4:end].split("\n")


def top_level_values(lines):
    """Yield (key, raw_value) for each top-level `key: value` line.

    Continuation lines of a folded or literal block are skipped: they are
    indented, and an indented line is never a new key.
    """
    for line in lines:
        if not line or line.startswith((" ", "\t", "#")):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        yield key.strip(), value.strip()


def is_quoted(value):
    return len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'"


def test_every_skill_has_frontmatter_with_name_and_description():
    missing = []
    for name, path in skill_files():
        lines = frontmatter(path)
        if lines is None:
            missing.append("%s: no frontmatter block" % name)
            continue
        keys = dict(top_level_values(lines))
        for required in ("name", "description"):
            if not keys.get(required):
                missing.append("%s: no %s" % (name, required))
        if keys.get("name") and keys["name"].strip("\"'") != name:
            missing.append("%s: name is %r, must match the directory"
                           % (name, keys["name"]))
    check("every skill declares a name matching its directory, and a description",
          not missing, "\n       " + "\n       ".join(missing))


def test_no_unquoted_value_contains_a_colon_space():
    """`key: a: b` is not the string it looks like. Quote it."""
    bad = []
    for name, path in skill_files():
        lines = frontmatter(path)
        if lines is None:
            continue
        for key, value in top_level_values(lines):
            if not value or is_quoted(value):
                continue
            if ": " in value:
                where = value.index(": ")
                bad.append("%s: %s is unquoted and contains ': ' near %r"
                           % (name, key, value[max(0, where - 25):where + 12]))
    check("no unquoted frontmatter value hides a mapping key",
          not bad, "\n       " + "\n       ".join(bad))


def spoken_triggers(description):
    """The quoted trigger phrases a description offers that are not slash commands."""
    import re
    quoted = re.findall(r"'([^']+)'|\"([^\"]+)\"", description)
    return [a or b for a, b in quoted if not (a or b).startswith("/")]


def test_a_skill_the_model_cannot_invoke_offers_no_spoken_trigger():
    """`disable-model-invocation: true` leaves the slash command as the only way in.

    A sentence such as 'raise issue này lên' reaches a skill only through the
    Skill tool, which that flag blocks. A description advertising one promises a
    call that always fails with "cannot be used with Skill tool due to
    disable-model-invocation". raise-issue and translate-file shipped exactly
    that. Either drop the flag or drop the spoken trigger.
    """
    bad = []
    for name, path in skill_files():
        lines = frontmatter(path)
        if lines is None:
            continue
        keys = dict(top_level_values(lines))
        if keys.get("disable-model-invocation", "").lower() != "true":
            continue
        desc = keys.get("description", "")
        if is_quoted(desc):
            desc = desc[1:-1]
        spoken = spoken_triggers(desc)
        if spoken:
            bad.append("%s: %s" % (name, spoken))
    check("no skill blocked from the Skill tool advertises a spoken trigger",
          not bad, "\n       " + "\n       ".join(bad))


def test_the_scan_actually_reads_every_shipped_skill():
    """A scan over nothing passes trivially."""
    found = [n for n, _ in skill_files()]
    check("the scan reaches every skill directory",
          len(found) >= 13, "%d found: %s" % (len(found), found))
    check("the scan reaches the two agent-team skills",
          "docs-review" in found and "spec-recon" in found, found)


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
