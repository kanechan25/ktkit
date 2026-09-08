#!/usr/bin/env python3
"""Grep in a script, so the agent judges instead of searching.

`probe-code` was the most expensive role in the fleet and it should have been the
cheapest. Its job is small -- does this identifier exist, and where -- but the
search happened *inside* the agent, and that is what cost the money.

Measured on a real repository: `src/` holds 14,627 tracked files, and one `Grep`
for `export` returns **15,358 matching lines across 3,801 files**. That result
lands in the agent's context, and an agentic loop re-sends everything accumulated
on every subsequent call, so a single unlucky search is worth hundreds of
thousands of tokens and keeps being paid for. A run reached 7.5M with `probe-code`
skipped entirely, having been warned it would push past 8M -- so the questions it
would have answered went unanswered, which is the expensive outcome.

Nothing about the job requires a model to do the searching. `git grep` costs no
tokens at all. So this script does the searching and writes an index the agent
can read in one go:

    probe_index.py --repo <dir> --paths src/ --ids <file|identifier>...
                   [--max-hits 20] [--variants] [--out <base>/probe-index.md]

For each identifier it emits a count, and up to `--max-hits` `path:line` rows
with the line's own text. Above the cap it says how many were elided rather than
truncating in silence -- an identifier with 3,801 hits is a different fact from
one with 3, and the count is the part that matters.

⭐ **An identifier with zero hits needs no agent at all.** The script settles it,
with the exact commands it ran, and the fleet drops one item instead of paying a
base charge plus a search to be told the same thing. That is the whole saving:
the expensive part was never the judging.

The agent still owns every judgement. This writes counts, lines and the commands
that produced them -- never `EXISTS`, never `NOT_FOUND`, never an opinion about
what an absence means. `--variants` widens each identifier the way
`agents/spec-recon-probe-code.md` requires (`retryBudgetMs` also as
`retry_budget_ms`, `RetryBudgetMs`, `retry-budget-ms`), because an absence that
was only searched one way is not an absence.

Stdlib only, Python 3.9. `git grep` when the tree is a repository, `grep -rn`
otherwise; both are reported so a reader can re-run them.
"""
import argparse
import io
import os
import re
import subprocess
import sys

MAX_HITS = 20
LINE_CLIP = 160
TIMEOUT = 120


def variants(ident):
    """The same identifier as another house would have spelled it."""
    out = {ident}
    parts = re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+", ident)
    if len(parts) > 1:
        low = [p.lower() for p in parts]
        out.add("_".join(low))
        out.add("-".join(low))
        out.add("".join(p.capitalize() for p in parts))
        out.add(low[0] + "".join(p.capitalize() for p in parts[1:]))
    return sorted(out, key=lambda s: (-len(s), s))


def is_repo(root):
    try:
        subprocess.check_output(["git", "-C", root, "rev-parse", "--git-dir"],
                                stderr=subprocess.DEVNULL, timeout=15)
        return True
    except Exception:                                          # noqa: BLE001
        return False


def search(root, term, paths, repo):
    """(rows, command, error). Rows are (path, line_no, text)."""
    if repo:
        cmd = ["git", "-C", root, "grep", "-n", "--fixed-strings", "-I", "--", term]
        if paths:
            cmd += ["--"] + list(paths) if "--" not in cmd else list(paths)
            # `git grep -- <term> -- <paths>` is not valid; rebuild cleanly.
            cmd = (["git", "-C", root, "grep", "-n", "--fixed-strings", "-I",
                    "-e", term, "--"] + list(paths))
    else:
        cmd = ["grep", "-rnI", "--fixed-strings", "--", term] + (list(paths) or ["."])
    shown = " ".join(cmd if repo else ["grep", "-rnI", "-F", term] + list(paths or ["."]))
    try:
        p = subprocess.Popen(cmd, cwd=root, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        out, err = p.communicate(timeout=TIMEOUT)
    except Exception as e:                                     # noqa: BLE001
        return [], shown, "%s: %s" % (type(e).__name__, e)
    if p.returncode not in (0, 1):                             # 1 == no matches
        return [], shown, (err.decode("utf-8", "replace").strip() or
                           "exit %d" % p.returncode)
    rows = []
    for line in out.decode("utf-8", "replace").split("\n"):
        if not line.strip():
            continue
        bits = line.split(":", 2)
        if len(bits) == 3 and bits[1].isdigit():
            rows.append((bits[0], int(bits[1]), bits[2].strip()[:LINE_CLIP]))
    return rows, shown, None


def load_ids(items):
    """Identifiers given directly, or one per line in a file."""
    ids = []
    for it in items:
        if os.path.isfile(it):
            for line in io.open(it, encoding="utf-8"):
                line = line.strip()
                if line and not line.startswith("#"):
                    ids.append(line)
        else:
            ids.append(it)
    seen, out = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def render(results, paths, max_hits):
    settled = [r for r in results if r["total"] == 0 and not r["errors"]]
    found = [r for r in results if r["total"] > 0]
    broken = [r for r in results if r["errors"]]

    out = ["# Code index", "",
           "Searched by `scripts/probe_index.py`, not by an agent: the same sweep inside an",
           "agent puts every matching line into its context and re-sends it on every later",
           "call. Counts and lines below are `[measured]`; every command is printed so any",
           "row can be re-run.", "",
           "Paths: `%s`" % "`, `".join(paths or ["(whole tree)"]), "",
           "| Identifier | Hits | Files | Verdict is the agent's |",
           "| ---------- | ---: | ----: | ---------------------- |"]
    for r in results:
        nf = len(set(p for p, _l, _t in r["rows"]))
        note = "⛔ errors" if r["errors"] else ("no occurrence" if not r["total"] else "")
        out.append("| `%s` | %d | %d | %s |" % (r["id"], r["total"], nf, note))
    out.append("")

    if settled:
        out += ["## Zero occurrences", "",
                "⭐ These need **no agent**: the search is done and the commands are below. An",
                "absence is still the agent's to interpret -- what it *means* that something is",
                "missing is a judgement, and this file makes none.", ""]
        for r in settled:
            out.append("**`%s`** — searched as: %s" % (r["id"], ", ".join("`%s`" % v for v in r["terms"])))
            for c in r["commands"]:
                out.append("    %s" % c)
            out.append("")

    for r in found:
        out += ["## `%s` — %d occurrence%s in %d file%s"
                % (r["id"], r["total"], "" if r["total"] == 1 else "s",
                   len(set(p for p, _l, _t in r["rows"])),
                   "" if len(set(p for p, _l, _t in r["rows"])) == 1 else "s"), ""]
        out += ["searched as: %s" % ", ".join("`%s`" % v for v in r["terms"]), ""]
        out += ["| path:line | line |", "| --------- | ---- |"]
        for p, l, txt in r["rows"][:max_hits]:
            out.append("| `%s:%d` | `%s` |" % (p, l, txt.replace("|", "\\|")))
        if r["total"] > max_hits:
            out += ["", "⚠️ **%d further occurrences are not listed** (cap %d). The count above is"
                    % (r["total"] - max_hits, max_hits),
                    "the measurement; the rows are a sample. An identifier with thousands of hits",
                    "is a different fact from one with three, and truncating without saying so",
                    "would hide exactly that."]
        out += [""] + ["    %s" % c for c in r["commands"]] + [""]

    if broken:
        out += ["## ⛔ Could not be searched", "",
                "Neither present nor absent: the search itself failed. An absence claim resting",
                "on one of these is `not-accessed`, not a finding.", ""]
        for r in broken:
            out.append("- `%s`: %s" % (r["id"], "; ".join(r["errors"])))
        out.append("")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="probe_index.py",
        description="Index where identifiers occur, so an agent judges instead of searching.")
    ap.add_argument("--repo", default=".", help="repository or tree root")
    ap.add_argument("--paths", nargs="*", default=[],
                    help="restrict the search (e.g. src/ src/api)")
    ap.add_argument("--ids", nargs="+", required=True,
                    help="identifiers, or a file with one per line")
    ap.add_argument("--max-hits", type=int, default=MAX_HITS,
                    help="rows listed per identifier (the count is never capped)")
    ap.add_argument("--variants", action="store_true",
                    help="also search snake_case, kebab-case, PascalCase, camelCase")
    ap.add_argument("--out", default=None, help="write the index here")
    a = ap.parse_args(argv)

    root = os.path.abspath(a.repo)
    if not os.path.isdir(root):
        print("NO-REPO  %s" % root)
        return 2
    repo = is_repo(root)
    ids = load_ids(a.ids)
    if not ids:
        print("NO-IDS  nothing to search for")
        return 2

    results = []
    for ident in ids:
        terms = variants(ident) if a.variants else [ident]
        rows, cmds, errs = [], [], []
        seen = set()
        for term in terms:
            r, cmd, err = search(root, term, a.paths, repo)
            cmds.append(cmd)
            if err:
                errs.append("%s: %s" % (term, err))
                continue
            for row in r:
                key = (row[0], row[1])
                if key not in seen:
                    seen.add(key)
                    rows.append(row)
        rows.sort()
        results.append({"id": ident, "terms": terms, "rows": rows,
                        "total": len(rows), "commands": cmds, "errors": errs})

    text = render(results, a.paths, a.max_hits)
    if a.out:
        d = os.path.dirname(a.out)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        io.open(a.out, "w", encoding="utf-8").write(text)

    zero = [r for r in results if r["total"] == 0 and not r["errors"]]
    listed = sum(min(r["total"], a.max_hits) for r in results)
    total = sum(r["total"] for r in results)
    print("INDEX  %d identifier(s) · %s occurrence(s) found · %d row(s) listed"
          % (len(results), format(total, ","), listed))
    print("  searcher  %s" % ("git grep" if repo else "grep -rn"))
    if zero:
        print("  ⭐ %d identifier(s) with zero occurrences: settled here, no agent needed"
              % len(zero))
    if total > listed:
        print("  ⚠️ %s occurrence(s) counted but not listed (cap %d/identifier); the count "
              "is the measurement" % (format(total - listed, ","), a.max_hits))
    if a.out:
        print("  index     %s" % a.out)
    print("  ⛔ verdicts are the agent's: this file states counts and lines, never EXISTS "
          "or NOT_FOUND")
    return 0


if __name__ == "__main__":
    sys.exit(main())
