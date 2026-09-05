#!/usr/bin/env python3
"""Every skill that can produce an open question must route it through the ladder.

Two of the four analysis skills adopted the ladder and two did not, and nothing
said so. `analyze-feat` and `feat-req-specs` dispatched resolvers and opened one
capped gate; `rca` and `bug-fix-specs` still interviewed the user, and `rca`
carried a constraint saying the opposite in as many words:

    If the expected behavior/requirement is ambiguous, STOP and ask the user.

Half a policy is worse than none: a workflow that chains these skills inherits
whichever half it happens to touch, and the user cannot tell which. So the
adoption is a test, not a promise.

What is asserted, per skill:
  * it invokes the ladder skill by its plugin-qualified name;
  * it dispatches the resolver by its plugin-qualified name, never the bare one,
    which would silently pick up a user-level agent that may not exist;
  * it closes its artifact with the escalation metric and states the 0.70 rule;
  * it does not tell the model to stop and ask before the tiers are exhausted.

Run:  python3 skills/escalation-ladder/tests/test_ladder_adoption.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

# The skills that turn a request into an artifact a human reads and can disagree
# with. The execute skills are deliberately absent: they carry out a spec that
# has already been through the gate, so an unknown there is a defect in the
# spec, not a question to re-open.
ADOPTERS = ["analyze-feat", "rca", "feat-req-specs", "bug-fix-specs"]

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def body(skill):
    with io.open(os.path.join(ROOT, "skills", skill, "SKILL.md"), encoding="utf-8") as fh:
        return fh.read()


def test_each_adopter_invokes_the_ladder():
    for skill in ADOPTERS:
        check("%s invokes /ktkit:escalation-ladder" % skill,
              "/ktkit:escalation-ladder" in body(skill))


def test_the_resolver_is_dispatched_plugin_qualified():
    """A bare `escalation-resolver` resolves to whatever the machine happens to
    have. On a clean install that is nothing, and the dispatch fails at the one
    moment the workflow depends on it."""
    bare = re.compile(r'subagent_type:\s*"escalation-resolver"')
    qualified = re.compile(r'subagent_type:\s*"ktkit:escalation-resolver"')
    for skill in ADOPTERS:
        text = body(skill)
        check("%s dispatches ktkit:escalation-resolver" % skill,
              bool(qualified.search(text)))
        check("%s never dispatches the bare name" % skill,
              not bare.search(text), bare.findall(text))


def test_each_adopter_reports_the_metric_and_its_threshold():
    for skill in ADOPTERS:
        text = body(skill)
        check("%s prints self_resolve_ratio" % skill, "self_resolve_ratio" in text)
        check("%s states the 0.70 rule" % skill, "0.70" in text,
              "a metric with no threshold is decoration")


def test_no_adopter_stops_to_ask_before_the_tiers_are_exhausted():
    """The exact sentence that made `rca` contradict the ladder, and the shape
    of it. Matching the shape rather than the sentence keeps the test useful
    after a rewording."""
    pattern = re.compile(
        r"ambiguous[^.\n]*STOP and ask the user|STOP and ask the user[^.\n]*ambiguous",
        re.I)
    for skill in ADOPTERS:
        hits = pattern.findall(body(skill))
        check("%s does not stop-and-ask on ambiguity" % skill, not hits, hits)


def test_the_resolver_agent_ships_with_the_plugin():
    """The dispatch above is only real if the agent file is in this repository."""
    path = os.path.join(ROOT, "agents", "escalation-resolver.md")
    check("agents/escalation-resolver.md exists", os.path.isfile(path))
    if not os.path.isfile(path):
        return
    with io.open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(r"^tools:\s*(.+)$", text, re.M)
    check("the agent declares a tool set", bool(m))
    if not m:
        return
    tools = m.group(1).strip()
    # Granting Bash removes Grep and Glob on this harness, silently. Declaring
    # all four is how an agent ends up search-blind while its prompt still tells
    # it to grep. See skills/spec-recon/SKILL.md.
    check("the agent does not declare Bash next to Grep/Glob",
          not ("Bash" in tools and ("Grep" in tools or "Glob" in tools)), tools)
    check("the agent's tool set is one that was probed",
          tools in ("Read, Grep, Glob", "Read, Bash", "Read, Write, Grep, Glob"), tools)


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
