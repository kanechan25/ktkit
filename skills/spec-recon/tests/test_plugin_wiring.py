#!/usr/bin/env python3
"""Check that what the skills tell the model to do is actually possible.

Every other test here checks a script against its own behaviour. This one checks
the *instructions* against the repository: a skill that names a script which
moved, an agent that was renamed, a flag that never existed, or a reference file
that is gone. None of those fail loudly at runtime -- the model reads the
instruction, the call fails or silently does nothing, and the run continues with
a hole in it.

The checks, in the order a run would hit them:

  W1  every ${CLAUDE_PLUGIN_ROOT}/... path named anywhere exists
  W2  every flag passed to one of those scripts is a flag it accepts
  W3  every `ktkit:<name>` invoked resolves to an agent file or a skill directory
  W4  every references/*.md a SKILL.md points at exists
  W5  no agent file is orphaned -- something has to dispatch it
  W6  every --groups value handed to preflight.py is one it knows
  W7  every script is importable and answers --help

Run:  python3 skills/spec-recon/tests/test_plugin_wiring.py
"""
import glob
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def read(path):
    return io.open(path, encoding="utf-8").read()


def instruction_files():
    """Everything a model is told to follow: skill bodies, references, agents."""
    pats = ("skills/*/SKILL.md", "skills/*/references/*.md", "agents/*.md")
    out = []
    for p in pats:
        out.extend(sorted(glob.glob(os.path.join(ROOT, p))))
    return out


def rel(path):
    return os.path.relpath(path, ROOT)


PLUGIN_PATH_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+)")
# A shell line, with $(...) removed first: a nested command's flags are not this
# script's flags, and `git rev-parse --show-toplevel` inside an argument is the
# case that taught us so.
SUBST_RE = re.compile(r"\$\([^)]*\)")
FLAG_RE = re.compile(r"(?<![\w-])--[a-z][a-z0-9-]+")


_help_cache = {}


def script_help(script_rel):
    if script_rel not in _help_cache:
        try:
            out = subprocess.check_output(
                [sys.executable, os.path.join(ROOT, script_rel), "--help"],
                stderr=subprocess.STDOUT)
            _help_cache[script_rel] = out.decode("utf-8")
        except Exception as exc:                                # noqa: BLE001
            _help_cache[script_rel] = "!! %s" % exc
    return _help_cache[script_rel]


def test_w1_every_plugin_path_exists():
    missing = []
    for f in instruction_files():
        for m in PLUGIN_PATH_RE.finditer(read(f)):
            p = m.group(1)
            if not os.path.exists(os.path.join(ROOT, p)):
                missing.append("%s -> %s" % (rel(f), p))
    check("W1 every ${CLAUDE_PLUGIN_ROOT} path named in an instruction exists",
          not missing, missing[:6])


def test_w2_every_documented_flag_is_a_real_flag():
    bad = []
    for f in instruction_files():
        # Join shell continuations so a multi-line invocation is one string.
        text = read(f).replace("\\\n", " ")
        for m in re.finditer(
                r'python3 "\$\{CLAUDE_PLUGIN_ROOT\}/([^"]+)"([^\n`]*)', text):
            script, args = m.group(1), SUBST_RE.sub(" ", m.group(2))
            if not os.path.isfile(os.path.join(ROOT, script)):
                continue                       # W1 owns that failure
            h = script_help(script)
            if h.startswith("!!"):
                bad.append("%s: --help failed %s" % (script, h))
                continue
            for flag in FLAG_RE.findall(args):
                if flag not in h:
                    bad.append("%s -> %s: %s" % (rel(f), os.path.basename(script), flag))
    check("W2 every flag an instruction passes is one the script accepts",
          not bad, bad[:6])


def test_w3_every_invoked_ktkit_name_resolves():
    """Case matters here, and the first version of this check got it wrong.

    Matching only lowercase let `ktkit:spec-recon-arbiter-GHOST` be read as the
    prefix `spec-recon-arbiter-`, which then looked like the legitimate
    placeholder `ktkit:spec-recon-probe-<kind>` and was skipped. So the pattern
    accepts any word character, and only a name genuinely followed by `<` counts
    as a placeholder.
    """
    unknown = []
    for f in instruction_files():
        for m in re.finditer(r"ktkit:([A-Za-z][\w-]*)(<?)", read(f)):
            name, placeholder = m.group(1), m.group(2)
            if placeholder == "<" and name.endswith("-"):
                continue                       # `ktkit:spec-recon-probe-<kind>`
            if (os.path.isfile(os.path.join(ROOT, "agents", name + ".md"))
                    or os.path.isdir(os.path.join(ROOT, "skills", name))):
                continue
            unknown.append("%s -> ktkit:%s" % (rel(f), name))
    check("W3 every ktkit:<name> resolves to an agent or a skill",
          not unknown, sorted(set(unknown))[:6])


def test_w4_every_named_reference_exists():
    missing = []
    for s in sorted(glob.glob(os.path.join(ROOT, "skills", "*", "SKILL.md"))):
        d = os.path.dirname(s)
        for r in set(re.findall(r"references/[a-z0-9-]+\.md", read(s))):
            here = os.path.join(d, r)
            shared = os.path.join(ROOT, "skills", "docs-review", r)
            if not (os.path.isfile(here) or os.path.isfile(shared)):
                missing.append("%s -> %s" % (rel(s), r))
    check("W4 every references/*.md a skill points at exists", not missing, missing[:6])


def test_w5_no_agent_is_orphaned():
    """An agent nothing dispatches is dead weight that still looks alive."""
    corpus = "\n".join(read(f) for f in instruction_files()
                       if "/agents/" not in f.replace(os.sep, "/"))
    orphans = []
    for a in sorted(glob.glob(os.path.join(ROOT, "agents", "*.md"))):
        name = os.path.basename(a)[:-3]
        if ("ktkit:" + name) not in corpus:
            orphans.append(name)
    check("W5 every agent file is dispatched by some skill", not orphans, orphans)


def test_w6_every_preflight_group_is_known():
    pf = os.path.join(ROOT, "scripts", "preflight.py")
    # GROUPS spans lines, so normalise whitespace before splitting; an element
    # that keeps its leading newline compares unequal to the same word.
    raw = re.search(r"^GROUPS = \(([^)]*)\)", read(pf), re.M).group(1)
    known = set(x.strip().strip("\"'") for x in raw.split(",") if x.strip())
    bad = []
    for f in instruction_files():
        for m in re.finditer(r"--groups[= ]([a-z,]+)", read(f)):
            for g in m.group(1).split(","):
                if g and g not in known:
                    bad.append("%s -> --groups %s" % (rel(f), g))
    check("W6 every --groups value an instruction uses is one preflight knows",
          not bad, bad[:6] + [sorted(known)])


def test_w7_every_script_answers_help():
    bad = []
    for p in (sorted(glob.glob(os.path.join(ROOT, "scripts", "*.py")))
              + sorted(glob.glob(os.path.join(ROOT, "skills", "*", "scripts", "*.py")))):
        h = script_help(rel(p))
        if h.startswith("!!"):
            bad.append("%s: %s" % (rel(p), h[:80]))
    check("W7 every shipped script is runnable and answers --help", not bad, bad)


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
