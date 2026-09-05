#!/usr/bin/env python3
"""Prove the two docs-review extensions are inert when unused.

`docs-review` remains a skill people run on its own. Adding `--evidence` to it
was allowed on exactly one condition: a run that does not pass the flag behaves
exactly as before. This test is that condition, kept as a test rather than as a
release process, so it keeps holding after everyone has forgotten the promise.

What "inert" means here, concretely:
  * the flag is additive -- every pre-existing flag is still documented;
  * no existing instruction was reworded to mention evidence;
  * the fifth tier-1 source is guarded by the flag, so a run without it still
    has exactly four;
  * no docs-review agent gained a tool, which is the way a "small" change to a
    reviewer turns into a different reviewer.

Run:  python3 skills/spec-recon/tests/test_docs_review_untouched.py
"""
import glob
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
DR = os.path.join(ROOT, "skills", "docs-review")

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def read(*parts):
    return io.open(os.path.join(DR, *parts), encoding="utf-8").read()


def test_every_preexisting_flag_survives():
    """The change was additive. Nothing was renamed, nothing was dropped."""
    skill = read("SKILL.md")
    for flag in ("--rounds", "--team off", "--max-questions", "--ask-only",
                 "--fix", "--out", "--silent", "--keep-scratch"):
        check("%s is still documented" % flag, "`%s" % flag in skill)


def test_evidence_flag_is_documented_as_optional():
    skill = read("SKILL.md")
    row = [l for l in skill.split("\n") if l.startswith("| `--evidence")]
    check("--evidence has exactly one row in the flag table", len(row) == 1, row)
    if row:
        check("the row says the flag is optional and inert",
              "inert" in row[0] or "Optional" in row[0], row[0])


def test_the_fifth_t1_source_is_conditional():
    """Without --evidence there must still be four sources, not five."""
    sc = read("references", "self-clarify.md")
    m = re.search(r"^5\. \*\*(.+?)\*\*", sc, re.M)
    check("a fifth tier-1 source exists", m is not None)
    if m:
        block = sc[sc.index("5. **"):]
        block = block.split("\n\n")[0]
        check("the fifth source is gated on --evidence",
              "--evidence" in block, block[:160])
    check("the count sentence names the condition",
          "five when the run was given `--evidence`" in sc,
          sc[sc.index("## T1"):sc.index("## T1") + 220])


def test_no_docs_review_instruction_was_reworded_around_the_flag():
    """The flag may be named where it is defined, and nowhere else.

    A mention inside a procedure step would mean the procedure now behaves
    differently, which is exactly what was promised would not happen. Match the
    flag itself, not the word "evidence" -- that word is the name of a reviewer
    role and appears throughout for reasons that predate this change.
    """
    skill = read("SKILL.md")
    stray = [(i, l) for i, l in enumerate(skill.split("\n"), 1)
             if "--evidence" in l and not l.startswith("| `--evidence")]
    check("SKILL.md names --evidence only in the flag table row",
          not stray, stray[:3])


def test_no_reviewer_gained_a_tool():
    """The invariant the whole handoff rests on: reviewers still have no shell."""
    for path in sorted(glob.glob(os.path.join(ROOT, "agents", "docs-review-*.md"))):
        fm = io.open(path, encoding="utf-8").read().split("---")[1]
        tools = re.search(r"^tools:\s*(.+)$", fm, re.M).group(1).strip()
        role = os.path.basename(path)
        check("%s has no Bash" % role, "Bash" not in tools, tools)
        check("%s has no WebFetch" % role, "WebFetch" not in tools, tools)


def test_reviewers_still_declare_they_have_no_shell():
    """The sentence a reviewer reads about its own limits must not have moved."""
    hits = 0
    for path in sorted(glob.glob(os.path.join(ROOT, "agents", "docs-review-*.md"))):
        if "no shell" in io.open(path, encoding="utf-8").read():
            hits += 1
    check("reviewers still state they have no shell", hits >= 1, "%d files" % hits)


# `upsert_block.py` gained a `--marker` parameter so the chain workflow can own
# a second block in the same document. The change is additive and the default is
# the old marker name, so docs-review behaviour is unchanged -- but "unchanged"
# is asserted by skills/docs-review/tests/test_upsert_block.py running the
# script, not by diffing it. Every other script here is still frozen.
SCRIPTS_ALLOWED = {
    "skills/docs-review/scripts/upsert_block.py",
}


def test_scripts_are_byte_identical_to_the_last_commit():
    """The strongest form of "unchanged", for every script but the one listed.

    The evidence extensions are documentation-only: they touched no script at
    all. Ask git rather than grepping for a word, because `evidence` is also the
    name of a reviewer role and appears in these files for older reasons.
    """
    import subprocess
    rel = "skills/docs-review/scripts"
    try:
        p = subprocess.Popen(["git", "-C", ROOT, "diff", "--name-only", "HEAD", "--", rel],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, _ = p.communicate(timeout=20)
    except Exception as exc:                                   # noqa: BLE001
        check("git is available to compare against HEAD", False, str(exc))
        return
    if p.returncode != 0:
        check("git could compare against HEAD", False, "rc=%d" % p.returncode)
        return
    changed = [l for l in out.decode("utf-8").split("\n") if l.strip()]
    unexpected = [l for l in changed if l not in SCRIPTS_ALLOWED]
    check("no unlisted docs-review script differs from HEAD", not unexpected, unexpected)


def test_only_two_docs_review_files_changed():
    """Exactly the two extensions, and nothing else in the skill."""
    import subprocess
    allowed = {
        # the two extensions themselves
        "skills/docs-review/SKILL.md",
        "skills/docs-review/references/self-clarify.md",
        # the agent-table checker was generalised to cover a second suite;
        # its docs-review behaviour is asserted by running it, not by diffing.
        "skills/docs-review/tests/check_agent_table.py",
        # portability, not behaviour: test_no_project_strings.py found example
        # paths using a directory convention private to one machine, and a
        # pointer to a file that is gitignored and therefore absent for anyone
        # who installs this. Both predate the evidence work. Neither changes
        # what the skill does; they are listed here rather than excused,
        # because a scope expansion that nobody can see is the thing this test
        # exists to prevent.
        "skills/docs-review/references/critique-mode.md",
        "skills/docs-review/references/solo-loop.md",
        # the marker parameter, and the test that proves the default did not
        # move. Listed for the same reason as the two above: a scope expansion
        # nobody can see is exactly what this test exists to prevent.
        "skills/docs-review/scripts/upsert_block.py",
        "skills/docs-review/tests/test_upsert_block.py",
    }
    p = subprocess.Popen(["git", "-C", ROOT, "diff", "--name-only", "HEAD", "--",
                          "skills/docs-review"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, _ = p.communicate(timeout=20)
    changed = set(l for l in out.decode("utf-8").split("\n") if l.strip())
    check("no unexpected docs-review file changed", changed <= allowed,
          sorted(changed - allowed))


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
