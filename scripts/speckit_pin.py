#!/usr/bin/env python3
"""Point spec-kit's persisted feature pointer at the feature directory in play.

Every script-backed speckit skill resolves its feature directory through the
same three-tier order, implemented in `.specify/scripts/bash/common.sh`:

    1. the SPECIFY_FEATURE_DIRECTORY environment variable
    2. the "feature_directory" key in .specify/feature.json
    3. a lookup by numeric prefix against the current git branch name

Tier 1 is the one a skill body naturally reaches for, and in this harness it is
the one that cannot work. An `export` runs inside one Bash invocation; the shell
that later runs `setup-plan.sh` -- from inside the speckit skill, one or more
tool calls afterwards -- is a different shell with a clean environment. So the
export evaporates and resolution silently falls through to tier 2, which is a
single mutable pointer written by whichever run touched it last. A pointer left
over from an unrelated feature is not a crash: the script resolves it happily,
copies the plan template over `plan.md` in the *wrong* directory, and reports
success. That is worse than an error.

Tier 2 is therefore the only channel that survives the gap between tool calls,
which makes writing it a step in its own right rather than a detail of tier 1.
Pinning it buys a second thing for free: `setup-plan.sh` and `setup-tasks.sh`
skip their branch-name gate entirely when the pin resolves to an existing
directory that matches the feature directory they resolved -- so an ordinary
branch name stops being a reason those two skills abort, with nothing renamed
and no git state touched. (`check-prerequisites.sh`, behind clarify / checklist
/ analyze, does not have that bypass and still needs SPECIFY_FEATURE.)

A repository with no `.specify/` is not an error here. The scaffolding lives in
the repository being worked on, it is never shipped on a user's behalf, and a
workflow that writes its own specification does not need it: this script reports
SKIP and exits 0, so one call site works on both paths.

Usage
    speckit_pin.py --dir <feature-dir> [--repo <root>]   pin, and report old -> new
    speckit_pin.py --print [--repo <root>]               report the current pin only
    speckit_pin.py --dir <feature-dir> --verify          check the pin, write nothing
                                       [--repo <root>]

    <feature-dir> is the directory holding spec.md -- absolute, or relative to
    the repository root. It must already exist: the branch-gate bypass above
    tests the pinned path with `-d`, so pinning a path nobody created yet buys
    the caller a pin that resolves and a gate that still fires.

Exit status
    0  pinned, already correct, verified, printed, or skipped (no .specify/)
    1  --verify and the pin does not match --dir
    2  usage error, or --dir does not exist
"""
import argparse
import json
import os
import shutil
import sys

SPECIFY_DIR = ".specify"
FEATURE_JSON = os.path.join(SPECIFY_DIR, "feature.json")
KEY = "feature_directory"


def read_pin(repo):
    """Return (raw_value, parsed_ok) for the pin, without raising.

    A missing file, unreadable bytes and malformed JSON all mean the same thing
    to a caller -- there is no usable pin -- but they mean different things to
    the writer, which must not discard keys it merely failed to parse. Hence the
    second element.
    """
    path = os.path.join(repo, FEATURE_JSON)
    if not os.path.isfile(path):
        return None, True
    try:
        with open(path, "r") as fh:
            doc = json.load(fh)
    except (ValueError, OSError, IOError):
        return None, False
    if not isinstance(doc, dict):
        return None, False
    value = doc.get(KEY)
    if not isinstance(value, str) or not value.strip():
        return None, True
    return value.strip(), True


def as_pin_value(repo, feature_dir):
    """Render one feature directory the way spec-kit's own writer renders it.

    Repository-relative with forward slashes, because that is what the tool
    writes itself and what stays valid when the checkout moves. A directory
    outside the repository keeps its absolute path -- spec-kit accepts both, and
    inventing a `../..` relative path would be a worse answer than the truth.
    """
    absolute = os.path.abspath(feature_dir)
    root = os.path.abspath(repo)
    rel = os.path.relpath(absolute, root)
    if rel.startswith(os.pardir):
        return absolute.replace(os.sep, "/")
    return rel.replace(os.sep, "/")


def same_target(repo, pin, feature_dir):
    """True when the pin and the feature directory name one directory.

    Compared by resolved path rather than by string: `./a/b`, `a/b` and an
    absolute path are the same pin, and a caller that normalises differently
    from the last writer must not be told the pin is wrong.
    """
    if not pin:
        return False
    pinned = pin if os.path.isabs(pin) else os.path.join(repo, pin)
    try:
        return os.path.realpath(pinned) == os.path.realpath(feature_dir)
    except OSError:
        return False


def write_pin(repo, value, parsed_ok):
    """Set the key, keep every other key, and never leave a half-written file.

    Written to a temporary file in the same directory and moved into place, so a
    reader either sees the old pin or the new one. Any sibling key is carried
    through untouched -- this script owns one key, not the file. When the
    previous content could not be parsed it is backed up rather than merged:
    silently dropping keys nobody could read is how a config file loses data.
    """
    path = os.path.join(repo, FEATURE_JSON)
    doc = {}
    backup = None
    if os.path.isfile(path):
        if parsed_ok:
            try:
                with open(path, "r") as fh:
                    loaded = json.load(fh)
                if isinstance(loaded, dict):
                    doc = loaded
            except (ValueError, OSError, IOError):
                doc = {}
        backup = path + ".bak"
        try:
            shutil.copyfile(path, backup)
        except (OSError, IOError):
            backup = None
    doc[KEY] = value
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        fh.write(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    return backup


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True,
                                 description=__doc__.split("\n")[0])
    ap.add_argument("--dir", dest="feature_dir",
                    help="feature directory holding spec.md")
    ap.add_argument("--repo", default=".", help="repository root")
    ap.add_argument("--print", dest="print_only", action="store_true",
                    help="report the current pin and exit")
    ap.add_argument("--verify", action="store_true",
                    help="check the pin against --dir, write nothing")
    a = ap.parse_args(argv)

    repo = os.path.abspath(a.repo)
    if not a.print_only and not a.feature_dir:
        sys.stderr.write("--dir is required unless --print is given\n")
        return 2

    scaffold = os.path.join(repo, SPECIFY_DIR)
    if not os.path.isdir(scaffold):
        sys.stdout.write("SKIP  speckit pin           no %s/ in %s -- nothing to "
                         "pin (internalised path)\n" % (SPECIFY_DIR, repo))
        return 0

    pin, parsed_ok = read_pin(repo)
    shown = pin if pin else "unset (branch-name fallback)"

    if a.print_only:
        note = "" if parsed_ok else "  [unparseable, will be backed up on write]"
        sys.stdout.write("PASS  speckit pin           %s%s\n" % (shown, note))
        return 0

    feature_dir = a.feature_dir
    if not os.path.isabs(feature_dir):
        feature_dir = os.path.join(repo, feature_dir)
    if not os.path.isdir(feature_dir):
        sys.stderr.write("FAIL  speckit pin           %s does not exist -- create "
                         "the feature directory first; the branch-gate bypass "
                         "tests the pinned path with -d\n" % feature_dir)
        return 2

    value = as_pin_value(repo, feature_dir)

    if a.verify:
        if same_target(repo, pin, feature_dir):
            sys.stdout.write("PASS  speckit pin           %s\n" % value)
            return 0
        sys.stderr.write("FAIL  speckit pin           pinned to %s, expected %s -- "
                         "run without --verify to repin\n" % (shown, value))
        return 1

    if same_target(repo, pin, feature_dir):
        sys.stdout.write("PASS  speckit pin           %s (unchanged)\n" % value)
        return 0

    backup = write_pin(repo, value, parsed_ok)
    tail = " (previous %s saved to %s)" % (shown, os.path.relpath(backup, repo)) \
        if backup else ""
    sys.stdout.write("PASS  speckit pin           %s -> %s%s\n"
                     % (shown, value, tail))
    return 0


if __name__ == "__main__":
    sys.exit(main())
