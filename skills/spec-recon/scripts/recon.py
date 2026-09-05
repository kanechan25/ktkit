#!/usr/bin/env python3
"""Measure the inputs before anything reads them, and emit recon.json.

Phase 0 of spec-recon. Cheap, deterministic, no agents. Two questions it exists
to answer, both of which cost a whole run when answered late:

  * Is anything here newer than the analysis that already exists? A run that
    audits a superseded revision produces a report that is wrong at the
    foundation, and nothing downstream can detect it.

  * Which file is the source, when one artifact appears several times in a
    repository? Build output under bin/ or dist/ is a copy; a fixture is a
    fake. Measuring the wrong copy and reporting it as the template is a
    finding about nothing.

Revision markers
    A revision marker is a per-section changelog token INSIDE the file, not a
    string in its name. In a document that carries them the signal is the
    LARGEST one, not the first: a file whose body runs from `rev-a` to `rev-o`
    is at o. Marker syntax varies by house style, so the patterns live in a
    table that can be extended without touching the logic, and a document that
    matches none of them is not an error -- mtime and git still answer the
    freshness question.

Usage
    recon.py <path>... [--repo <dir>] [--prior <report.md>] [--out recon.json]
                       [--patterns <file.json>]

Output
    recon.json on stdout (or --out), plus a human summary on stderr.

Exit status
    0  measured everything it was given
    1  an input could not be read
    2  the arguments are unusable
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

# ---------------------------------------------------------------------------
# Revision markers. Extend this table; do not add branches to the code.
#
# Each entry: (name, compiled regex with one capturing group, kind).
#   kind "alpha"  -> the group is a letter sequence; compare by length then value
#   kind "numeric"-> the group is dotted digits; compare component-wise
# The Japanese entry is one house style among several, not the default.
# ---------------------------------------------------------------------------
MARKER_PATTERNS = [
    ("ja-han",   re.compile(r"(?:初版|\d+版)-([a-z])"),            "alpha"),
    ("rev-dot",  re.compile(r"\bRev\.(\d+(?:\.\d+)*)"),            "numeric"),
    ("rev-alpha", re.compile(r"\brev-([a-z])\b", re.I),            "alpha"),
    ("v-semver", re.compile(r"\bv(\d+(?:\.\d+){1,3})\b"),          "numeric"),
    ("draft-n",  re.compile(r"\bDraft\s+(\d+)\b", re.I),           "numeric"),
]

# Path segments that mean "this file is a build product or a stand-in, not the
# source". A hit on any of these disqualifies a candidate from being the source
# copy of an artifact.
BUILD_SEGMENTS = {"bin", "obj", "dist", "build", "out", "target",
                  "node_modules", ".next", ".nuxt", "coverage", "__pycache__"}
STANDIN_HINTS = ("test", "tests", "fixture", "fixtures", "sample", "samples",
                 "example", "examples", "mock", "mocks", "_user-edited")

BINARY_EXTS = {".xlsx", ".xls", ".xlsm", ".docx", ".pptx", ".pdf", ".zip",
               ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2",
               ".ttf", ".otf", ".so", ".dylib", ".dll", ".exe", ".class"}

TEXT_READ_LIMIT = 4 * 1024 * 1024      # markers past 4 MB are not worth the read


def sh(cmd, cwd=None, timeout=20):
    try:
        p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        out, _ = p.communicate(timeout=timeout)
        return p.returncode, out.decode("utf-8", "replace").strip()
    except Exception:                                          # noqa: BLE001
        return 1, ""


def load_patterns(path):
    """Merge a caller-supplied pattern table over the built-in one.

    The file is a list of [name, regex, kind]. Supplying one is how a house
    style this table has never seen gets recognised without a code change.
    """
    if not path:
        return list(MARKER_PATTERNS)
    with open(path) as fh:
        extra = json.load(fh)
    out = list(MARKER_PATTERNS)
    for row in extra:
        name, rx, kind = row[0], row[1], row[2]
        if kind not in ("alpha", "numeric"):
            raise ValueError("pattern %r: kind must be alpha or numeric" % name)
        out.append((name, re.compile(rx), kind))
    return out


def _alpha_key(s):
    return (len(s), s.lower())


def _numeric_key(s):
    return tuple(int(x) for x in s.split("."))


def revision_markers(text, patterns):
    """Return the highest marker per pattern family found in the body.

    Families are kept separate on purpose: `5版-n` and `Rev.03` are not
    comparable, and picking a winner across them would invent an ordering.
    """
    found = {}
    for name, rx, kind in patterns:
        hits = rx.findall(text)
        if not hits:
            continue
        key = _alpha_key if kind == "alpha" else _numeric_key
        try:
            best = max(hits, key=key)
        except ValueError:
            continue
        found[name] = {"max": best, "count": len(hits),
                       "distinct": len(set(hits)), "kind": kind}
    return found


def is_binary(path, ext):
    if ext in BINARY_EXTS:
        return True
    try:
        with open(path, "rb") as fh:
            chunk = fh.read(8000)
        return b"\0" in chunk
    except (OSError, IOError):
        return False


def guess_lang(text):
    """Coarse script detection, used only to pick an extraction strategy."""
    sample = text[:20000]
    if not sample:
        return "unknown"
    cjk = sum(1 for c in sample if "぀" <= c <= "ヿ"
              or "一" <= c <= "鿿")
    viet = sum(1 for c in sample if c in "ăâđêôơưĂÂĐÊÔƠƯáàảãạấầẩẫậéèẻẽẹế"
               "ềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ")
    n = max(len(sample), 1)
    if cjk * 100 // n >= 3:
        return "ja"
    if viet * 100 // n >= 2:
        return "vi"
    return "en"


def md5(path):
    h = hashlib.md5()
    try:
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 16), b""):
                h.update(block)
    except (OSError, IOError):
        return None
    return h.hexdigest()


def measure(path, repo, patterns):
    st = os.stat(path)
    ext = os.path.splitext(path)[1].lower()
    binary = is_binary(path, ext)
    rec = {
        "path": path,
        "bytes": st.st_size,
        "mtime": int(st.st_mtime),
        "ext": ext,
        "is_binary": binary,
        "md5": md5(path),
        "lines": None,
        "lang": None,
        "revision_markers": {},
        "git_tracked": False,
        "last_commit": None,
    }
    if not binary and st.st_size <= TEXT_READ_LIMIT:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except (OSError, IOError):
            text = ""
        rec["lines"] = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        rec["lang"] = guess_lang(text)
        rec["revision_markers"] = revision_markers(text, patterns)
    elif not binary:
        rec["lang"] = "unread-too-large"

    rc, out = sh(["git", "-C", repo, "log", "-1", "--format=%H|%cI|%s", "--", path])
    if rc == 0 and out:
        sha, when, subject = (out.split("|", 2) + ["", ""])[:3]
        rec["git_tracked"] = True
        rec["last_commit"] = {"sha": sha, "date": when, "subject": subject}
    return rec


def expand(paths):
    """Walk directories into files; keep explicit file arguments as given."""
    out = []
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if d != ".git"]
                for f in sorted(files):
                    if f == ".DS_Store":
                        continue
                    out.append(os.path.join(root, f))
        else:
            out.append(p)
    return out


def duplicate_groups(records):
    """Group inputs that share a basename, and rank the candidates.

    One artifact commonly exists several times in a repository: the source, a
    copy under a build directory, a test fixture, a hand-edited spare. Choosing
    the first hit is how a run ends up measuring a stale copy and reporting it
    as the template.

    This function never picks a winner when the choice is not forced. It
    disqualifies what it can prove is not the source and hands the rest back as
    `ambiguous`, because guessing here is exactly the failure it is meant to
    prevent. When the survivors differ by md5, that is itself a finding: two
    copies of one artifact have drifted.
    """
    by_name = {}
    for r in records:
        by_name.setdefault(os.path.basename(r["path"]).lower(), []).append(r)

    groups = []
    for name, rows in sorted(by_name.items()):
        if len(rows) < 2:
            continue
        ranked = []
        for r in rows:
            segs = set(s.lower() for s in r["path"].split(os.sep))
            low = r["path"].lower()
            if segs & BUILD_SEGMENTS:
                verdict = "build-output"
            elif any(h in segs for h in STANDIN_HINTS) or \
                    any(h in low for h in ("_user-edited", "sample", "fixture")):
                verdict = "stand-in"
            else:
                verdict = "candidate"
            ranked.append({"path": r["path"], "md5": r["md5"],
                           "mtime": r["mtime"], "class": verdict})
        candidates = [x for x in ranked if x["class"] == "candidate"]
        digests = set(x["md5"] for x in ranked if x["md5"])
        groups.append({
            "basename": name,
            "members": ranked,
            "source": candidates[0]["path"] if len(candidates) == 1 else None,
            "status": ("resolved" if len(candidates) == 1
                       else "ambiguous" if candidates else "no-candidate"),
            "copies_differ": len(digests) > 1,
        })
    return groups


def summarise(recon):
    n = len(recon["inputs"])
    binary = sum(1 for r in recon["inputs"] if r["is_binary"])
    marked = sum(1 for r in recon["inputs"] if r["revision_markers"])
    amb = [g for g in recon["duplicates"] if g["status"] != "resolved"]
    drift = [g for g in recon["duplicates"] if g["copies_differ"]]
    lines = ["%d input(s): %d binary, %d text" % (n, binary, n - binary),
             "%d carry revision markers" % marked]
    if recon["stale_risk"]:
        lines.append("STALE RISK: %d input(s) are newer than the prior report"
                     % len(recon["stale_risk"]))
    if amb:
        lines.append("AMBIGUOUS SOURCE: %s" % ", ".join(g["basename"] for g in amb))
    if drift:
        lines.append("COPIES DIFFER (a finding): %s"
                     % ", ".join(g["basename"] for g in drift))
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--prior", help="path of an existing report, to date against")
    ap.add_argument("--out", help="write recon.json here instead of stdout")
    ap.add_argument("--patterns", help="JSON list of extra [name, regex, kind]")
    a = ap.parse_args(argv)

    try:
        patterns = load_patterns(a.patterns)
    except (ValueError, OSError, IOError, json.JSONDecodeError) as exc:
        sys.stderr.write("bad --patterns: %s\n" % exc)
        return 2

    files = expand(a.paths)
    missing = [p for p in files if not os.path.isfile(p)]
    if missing:
        sys.stderr.write("cannot read: %s\n" % ", ".join(missing))
        return 1

    records = [measure(p, a.repo, patterns) for p in files]

    prior_mtime = None
    if a.prior and os.path.isfile(a.prior):
        prior_mtime = int(os.stat(a.prior).st_mtime)
    stale = ([r["path"] for r in records if r["mtime"] > prior_mtime]
             if prior_mtime else [])

    recon = {
        "schema": 1,
        "repo": os.path.abspath(a.repo),
        "prior_report": a.prior if prior_mtime else None,
        "prior_report_mtime": prior_mtime,
        "stale_risk": stale,
        "patterns": [p[0] for p in patterns],
        "inputs": records,
        "duplicates": duplicate_groups(records),
        "totals": {
            "n_inputs": len(records),
            "n_binary": sum(1 for r in records if r["is_binary"]),
            "n_text": sum(1 for r in records if not r["is_binary"]),
            "n_with_markers": sum(1 for r in records if r["revision_markers"]),
            "bytes": sum(r["bytes"] for r in records),
            "lines": sum(r["lines"] or 0 for r in records),
        },
    }

    blob = json.dumps(recon, indent=1, ensure_ascii=False, sort_keys=False)
    if a.out:
        d = os.path.dirname(os.path.abspath(a.out))
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with open(a.out, "w") as fh:
            fh.write(blob + "\n")
    else:
        sys.stdout.write(blob + "\n")
    for line in summarise(recon):
        sys.stderr.write(line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
