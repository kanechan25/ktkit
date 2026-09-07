#!/usr/bin/env python3
"""Decide where a reconnaissance run writes -- and refuse to guess silently.

A run produces a directory, not a file: a report, a `recon.json`, seven step
files, one evidence file per probe, and a scratch area. Every later phase cites
paths inside it, and so does whatever reads the report afterwards. So the one
thing that must not happen is the run choosing a location on its own and
mentioning it afterwards.

It used to. `--out` defaulted to the bare string `spec-recon.md`, which resolves
against the working directory -- putting the report and its whole directory at
the repository root, outside `.claude/`, in direct contradiction of the rule
every other skill in this plugin follows. Nothing failed; the files simply
appeared in the wrong place.

This script is the fix. It never writes anything. It resolves what the path
*should* be, prints the suggestion together with the tree that would be created,
and leaves the decision to a person -- the same discipline
`skills/ccompact/SKILL.md` already applies to its own output path, and the mirror
algorithm here is deliberately that one rather than a second convention.

    resolve_out.py --inputs <path>... [--repo <dir>] [--out <path>]

Exit codes:
    0   a path is settled (`--out` was given and is valid)
    3   no `--out`: a suggestion is printed and the run must ask before starting
    2   `--out` was given but is not usable, with the reason

Stdlib only, Python 3.9.
"""
import argparse
import os
import subprocess
import sys

ARTIFACT_ROOT = os.path.join(".claude", "claude")
OUTPUT_AREA = "analyze"          # reconnaissance produces analysis
SUFFIX = ".recon.md"

# Stripped in this order, longest-first, exactly as skills/ccompact/SKILL.md
# does it. A `<base>` is an exact string: never re-slugified, never replaced by
# a folder name.
STRIP = (".spec.md", ".be.pipeline.md", ".fe.pipeline.md", ".fs.pipeline.md",
         ".sqa.pipeline.md", ".pipeline.md", ".analyze.md", ".recon.md",
         ".compact.md", ".md")

TREE = """    recon.json                    freshness, surface, ambiguous artifact copies
    steps/manifest.md             the index -- read first if a run stops
         00-preflight.md .. 06-handoff.md
    evidence/probe-*.md           the measurements, each with a reproduce command
    scratch/                      removed after a clean run"""


def repo_root(explicit):
    if explicit:
        return os.path.abspath(explicit)
    try:
        out = subprocess.check_output(["git", "rev-parse", "--show-toplevel"],
                                      stderr=subprocess.DEVNULL)
        return out.decode("utf-8").strip()
    except (subprocess.CalledProcessError, OSError):
        return os.path.abspath(".")


def strip_suffix(name):
    for s in STRIP:
        if name.endswith(s):
            return name[:-len(s)]
    return name


def common_source(inputs):
    """The single path a set of inputs is 'about'.

    One input is itself. Several become their common ancestor directory --
    naming one of them would make the location depend on argument order.
    """
    absl = [os.path.abspath(p) for p in inputs]
    if len(absl) == 1:
        return absl[0]
    common = os.path.commonpath(absl)
    return common


def mirror(source, root):
    """(rel_dir, base, note) for a source path, per the ccompact algorithm."""
    base_dir = os.path.join(root, ARTIFACT_ROOT)
    src = os.path.abspath(source)
    name = os.path.basename(src.rstrip(os.sep))

    # <input-root>: the nearest ancestor whose parent is <artifact-base>.
    node, input_root = src, None
    while True:
        parent = os.path.dirname(node)
        if parent == node:
            break
        if os.path.abspath(parent) == os.path.abspath(base_dir):
            input_root = node
            break
        node = parent

    if input_root is None:
        return "_external", strip_suffix(name), (
            "input lives outside %s, so the run is filed under _external/"
            % os.path.join(ARTIFACT_ROOT))

    if os.path.abspath(src) == os.path.abspath(input_root):
        # The input *is* the area directory (`docs/`, `specs/`) -- there is no
        # sub-path to mirror and no name but the area's own.
        return "", strip_suffix(name), (
            "input is the area directory %s itself" % name)

    rel = os.path.relpath(os.path.dirname(src), input_root)
    rel = "" if rel == "." else rel
    return rel, strip_suffix(name), (
        "mirrored from %s under %s/"
        % (os.path.relpath(src, root), os.path.join(ARTIFACT_ROOT, OUTPUT_AREA)))


def suggest(inputs, root):
    src = common_source(inputs)
    rel, base, note = mirror(src, root)
    parts = [ARTIFACT_ROOT, OUTPUT_AREA]
    if rel:
        parts.append(rel)
    report = os.path.join(*(parts + [base + SUFFIX]))
    return report, note


def validate(out, root):
    """`--out` must land inside the artifact root, and must name a directory."""
    if not out.endswith(".md"):
        return "must end in .md (the report is a markdown file): %r" % out
    if os.path.dirname(out) in ("", "."):
        return ("is a bare filename, so it would resolve against the working "
                "directory instead of the artifact root: %r" % out)
    allowed = os.path.abspath(os.path.join(root, ".claude"))
    target = os.path.abspath(os.path.join(root, out)) if not os.path.isabs(out) \
        else os.path.abspath(out)
    if not (target == allowed or target.startswith(allowed + os.sep)):
        return ("resolves to %s, outside %s -- every artifact this plugin "
                "writes stays inside .claude/" % (target, allowed))
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="resolve_out.py",
        description="Resolve, or suggest, where a spec-recon run writes.")
    ap.add_argument("--inputs", nargs="+", required=True,
                    help="the documents, directories or repository roots the run reads")
    ap.add_argument("--repo", default=None,
                    help="repository root (default: git rev-parse --show-toplevel)")
    ap.add_argument("--out", default=None,
                    help="the report path, when the user has already given one")
    args = ap.parse_args(argv)

    root = repo_root(args.repo)

    if args.out:
        problem = validate(args.out, root)
        if problem:
            print("OUT-REJECTED  %s" % problem)
            print("Suggest instead:")
            report, _note = suggest(args.inputs, root)
            print("  %s" % report)
            return 2
        base = strip_suffix(os.path.basename(args.out))
        folder = os.path.join(os.path.dirname(args.out), base)
        print("OUT-SET")
        print("  report   %s" % args.out)
        print("  folder   %s/" % folder)
        print("OUT=%s" % args.out)
        return 0

    report, note = suggest(args.inputs, root)
    base = strip_suffix(os.path.basename(report))
    folder = os.path.join(os.path.dirname(report), base)
    print("OUT-UNSET  the run writes a directory, so the location is settled "
          "before anything is measured.")
    print("")
    print("Suggested:")
    print("  report   %s" % report)
    print("  folder   %s/" % folder)
    print("")
    print("Derived: %s" % note)
    print("")
    print("That folder will hold:")
    print(TREE)
    print("")
    print("Confirm this path, or give another under %s/."
          % os.path.join(ARTIFACT_ROOT))
    print("SUGGEST=%s" % report)
    return 3


if __name__ == "__main__":
    sys.exit(main())
