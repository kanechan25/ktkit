#!/usr/bin/env python3
"""Arm the `confirm with me` marker for every session that has this plugin.

The `confirm-with-me` skill gates a single step until the user answers. Its
description says when to fire, but a description only ranks a skill for
selection -- it is a hint, not an instruction. What actually makes the gate
reliable is a rule in the reading context saying the marker MUST be honoured.

The obvious way to install such a rule is to append it to the user's own
`CLAUDE.md`. This plugin does not do that, for two reasons:

  * `skills/ccompact/SKILL.md` forbids writing to any shared rule file, and a
    plugin that both forbids and does it is not one anybody should trust;
  * a line written into someone's rule file survives uninstalling the plugin.
    Nothing removes it, and later they find a rule they did not write.

A SessionStart hook has neither problem. It prints the rule, the rule is in
context for that session only, and removing the plugin removes the rule.

Contract: whatever this writes to stdout is added to the session context. So it
must stay short -- it is paid for in every session, used or not -- and it must
never fail loudly: a hook that errors on session start is worse than a missing
rule. It reads nothing, writes nothing, and makes no network call.
"""
import sys

RULE = """\
[ktkit] Confirm-marker protocol — active while the ktkit plugin is installed.

When the literal phrase `confirm with me` appears anywhere in the active context
— a user message, a spec or plan file, a workflow step, a task instruction, or
another skill's body — invoke the skill `ktkit:confirm-with-me` BEFORE carrying
out the step that phrase annotates.

- One marker is one gate for one step. Approval of a larger task never covers a
  step that carries its own marker.
- The gate blocks until the user replies `confirm`, `abort`, or `modify: <x>`.
  Silence is not consent, and neither is an unrelated "ok, go on".
- Do not batch several markers into one confirm block.

Off for a session when the user says so, e.g. "stop confirm-with-me".
"""


def main():
    try:
        sys.stdout.write(RULE)
    except Exception:                                          # noqa: BLE001
        # A session must start whatever happens here. Losing the rule is
        # recoverable; refusing to start the session is not.
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
