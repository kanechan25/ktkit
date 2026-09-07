#!/usr/bin/env python3
"""Decide which inputs the question can actually be answered from -- and say
which ones were left out.

A run measured on a real corpus read 3,489 KB across 65 files. Fifty-four of
those files contained not one occurrence of anything the question was about,
and together they carried 1,336 KB. The planner spawned agents to read all of
them, because nothing in the pipeline asked whether a document had anything to
do with the scope.

This script asks. It turns `--scope` into a search vocabulary, counts how often
that vocabulary occurs per kilobyte of each input, and keeps the inputs above a
threshold. On that corpus, at 0.01 hits/KB, 45 shards become 14.

Presence alone is not enough, and that is the whole reason this measures density
instead. A 456 KB reference table containing two incidental matches looks
relevant to a keyword filter and is not; giving it its own agent to find those
two matches is how a run reaches fifteen million tokens.

    relevance.py <recon.json> --scope "<text>" [--threshold 0.01]
                 [--add <term>]... [--report <path>]

⛔ **This may never narrow a run silently.** `SKILL.md` already carries the rule:
"Silently narrowing the scope and then reporting as though the whole job was done
is the one outcome worse than stopping." So every run writes the list of what was
excluded, with its size and its hit count, and the report carries it. An
excluded region also poisons one specific verdict: an absence claim can no
longer be `UPHELD` from a region nobody read. It becomes
`not-accessed: cut by the relevance gate`, which is the same discipline
`NEEDS-WIDER` applies to a shard boundary.

`--threshold 0` keeps everything and still writes the table, so the gate can be
audited without being trusted.

Two things were wrong in the first version of this, and both failed in the safe
direction while looking like they had worked -- which is the failure this whole
file exists to prevent:

  * paths in `recon.json` are relative to the repository it measured, not to
    wherever this runs. Resolved against the wrong root, every file was
    unreadable, so every file was kept, and the summary read like a gate that had
    found the whole corpus relevant. Paths are now resolved against `repo` from
    the recon file itself.
  * an unreadable file was counted as kept with no mark on it. Silence about a
    file nobody could open is the same defect as silence about a file nobody
    read, so unreadable files are now their own row in the summary and their own
    section in the report.

A scope sentence also contains words naming *where to look* rather than *what to
look for* -- "code", "spec", "docs", "implementation". Those are stopped: left in
the vocabulary they match nearly everything and the gate stops discriminating.

⭐ **And the gate declines rather than guess.** Measured on the corpus this was
built against, a scope written in Vietnamese and English produced four ASCII
terms and then cut the two main Japanese specification documents -- 729 KB and
223 KB, zero hits each, because the question said "export" and the document says
"出力". A gate that removes the specification because the question was asked in
another language is worse than no gate at all.

Two signals mean the whole vocabulary is wrong, and either one makes the gate
keep everything and say why:

  * **script mismatch** -- most of the corpus is in a writing system no term
    covers;
  * **the vocabulary matched nothing** -- not in one file, in any of them.

A third signal was tried and removed, and the reason is worth keeping. "More
than 85% of the corpus was cut" looks like a symptom of a bad vocabulary and is
not: on the corpus this was built against, the reference tables genuinely are
most of the bytes, and excluding them is the entire saving. Cutting a large share
is what a *correct* vocabulary does to a corpus whose bulk is irrelevant. The
share says nothing about whether the terms fit; whether the terms match anything
at all does.

A third case is narrower and gets a narrower answer. A document carrying revision
markers is a specification, and cutting a specification on a question about the
specification is almost always the gate being wrong -- but declining the whole
gate because one document out of fifty-six looks like a spec throws away the
saving to fix a single row. So specifications are **rescued**: kept regardless of
their density, named as rescued in the report, while the reference tables that
cost the tokens are still excluded. That is strictly better than declining, and
it is where the saving actually comes from.

Declining prints the terms it had and asks for the ones it wants. Neither
declining nor rescuing is a failure state: both are the gate refusing to be the
reason a finding was missed.

Stdlib only, Python 3.9.
"""
import argparse
import io
import json
import os
import re
import sys

DEFAULT_THRESHOLD = 0.01          # hits per KB; measured sweet spot, one corpus
MIN_TERM = 3                      # shorter tokens match everything

# Refusal thresholds. Deliberately cautious: the gate is a saving, and a saving
# that can remove the specification is not one.
CJK_SHARE_DECLINE = 0.40          # of corpus bytes, with no CJK term present
SPEC_BYTES = 50 * 1024            # a revision-marked file this big is a spec
CJK_RE = re.compile(r"[぀-ヿ㐀-䶿一-鿿豈-﫿]")

# Words that carry no discriminating power in a scope sentence. Kept small on
# purpose: a stop list that grows starts deciding what the question was about.
STOP = set("""
and or not the a an of to in on for with from by is are was were be been being
what which where when how why does do did has have had can could should would
must may might this that these those it its as at than then there here also
about into over under after before between during without within
cai gi nao co khong la va hoac cua cho tu den voi theo neu thi ma nhung
""".split())

# Words that name where to look rather than what to look for. Left in the
# vocabulary they match nearly every file in a software repository, and the gate
# stops discriminating -- measured: adding `code` and `spec` to a scope's terms
# moved the cut from 54 files to 17 on the same corpus.
META = set("""
code codebase source spec specs specification specifications doc docs document
documents documentation impl implement implementation implemented feature
requirement requirements repo repository file files function functions class
classes method methods module modules test tests
""".split())


def vocabulary(scope, extra):
    """Terms worth searching for, longest first so overlaps favour specificity.

    Three kinds of token survive: identifier-shaped runs (`ES0021`,
    `calcEngineVersion`), CJK runs, and ordinary words that are not stop words.
    """
    terms = set(extra or [])
    for m in re.finditer(r"[A-Za-z][A-Za-z0-9_.-]*[A-Za-z0-9]|[0-9]+[A-Za-z]+[A-Za-z0-9]*",
                         scope or ""):
        w = m.group(0)
        lo = w.lower()
        if len(w) >= MIN_TERM and lo not in STOP and lo not in META:
            terms.add(w)
    for m in re.finditer(r"[぀-ヿ㐀-䶿一-鿿豈-﫿]{2,}",
                         scope or ""):
        terms.add(m.group(0))
    return sorted(terms, key=lambda s: (-len(s), s))


def count(path, terms):
    """(hits, bytes). A file that cannot be read counts as unknown, not absent."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return None, 0
    try:
        text = io.open(path, encoding="utf-8", errors="replace").read()
    except (IOError, OSError):
        return None, size
    low = text.lower()
    hits = 0
    for t in terms:
        hits += low.count(t.lower()) if t.isascii() else text.count(t)
    return hits, size


def classify(records, terms, threshold, root=None):
    """`root` comes from recon.json's own `repo`: its paths are relative to the
    repository it measured, which is not necessarily where this runs."""
    rows = []
    for r in records:
        p = r.get("path")
        if not p:
            continue
        full = p if os.path.isabs(p) or not root else os.path.join(root, p)
        hits, size = count(full, terms)
        kb = (size / 1024.0) or 1.0
        # A binary is never excluded on text density: its content is not text,
        # and the artifact probe is the only thing that can read it at all.
        binary = bool(r.get("is_binary") or r.get("binary"))
        if hits is None:
            verdict, why = "unreadable", "could not be opened as text here"
        elif binary:
            verdict, why = "keep", "binary; density is not measurable here"
        elif threshold <= 0:
            verdict, why = "keep", "threshold 0: nothing is excluded"
        elif hits / kb > threshold:
            verdict, why = "keep", ""
        else:
            verdict, why = "cut", "%d hit%s in %.0f KB" % (hits, "" if hits == 1 else "s", kb)
        if verdict == "cut" and size >= SPEC_BYTES and r.get("revision_markers"):
            # A revision-marked document of this size is a specification. The
            # question is about the specification, so density does not get to
            # remove it -- see the module docstring.
            verdict, why = "rescued", ("revision markers make this a "
                                       "specification; kept despite %d hit%s"
                                       % (hits, "" if hits == 1 else "s"))
        rows.append({"path": p, "bytes": size, "hits": hits,
                     "density": (hits / kb) if hits is not None else None,
                     "verdict": verdict, "why": why, "binary": binary})
    return rows


def decline_reasons(rows, records, terms):
    """Why the exclusions should not stand. Empty means they may."""
    total = float(sum(r["bytes"] for r in rows)) or 1.0
    cut = [r for r in rows if r["verdict"] == "cut"]
    reasons = []

    have_cjk_term = any(CJK_RE.search(t) for t in terms)
    cjk_bytes = sum(r.get("bytes", 0) for r in records
                    if (r.get("lang") or "") in ("ja", "zh", "ko"))
    if not have_cjk_term and cjk_bytes / total >= CJK_SHARE_DECLINE:
        reasons.append(
            "script mismatch: %.0f%% of the corpus is CJK and no term is, so a "
            "document saying 出力 cannot match a question saying export"
            % (100.0 * cjk_bytes / total))

    # A share test was here and was wrong -- see the module docstring. What
    # actually distinguishes a bad vocabulary is matching nothing anywhere.
    hits = sum(r["hits"] or 0 for r in rows if r["hits"] is not None)
    if not hits:
        reasons.append("the vocabulary matched nothing: not one occurrence in any "
                       "input, so it cannot be telling relevant from irrelevant")
    if not [r for r in rows if r["verdict"] in ("keep", "rescued")]:
        reasons.append("every input would be excluded, which cannot be right")
    return reasons


def render(rows, terms, threshold, declined=None):
    keep = [r for r in rows if r["verdict"] == "keep"]
    cut = [r for r in rows if r["verdict"] == "cut"]
    bad = [r for r in rows if r["verdict"] == "unreadable"]
    saved = [r for r in rows if r["verdict"] == "rescued"]
    kb = lambda rs: sum(r["bytes"] for r in rs) / 1024.0
    out = ["# Relevance gate", "",
           "Threshold **%.3f hits/KB**. Vocabulary derived from `--scope`:" % threshold, "",
           "```", " ".join(terms) or "(none -- nothing was excluded)", "```", ""]
    if declined:
        out += ["## ⛔ The gate declined. Nothing was excluded.", "",
                "Every input is being read. The exclusions this gate computed are shown below",
                "for audit, but they are **not** in effect, because:", ""]
        out += ["- %s" % r for r in declined]
        out += ["", "Widen the vocabulary with `--relevance-add <term>` -- a term in the corpus's",
                "own language -- and the gate becomes useful again. Until then it is off, and",
                "the run costs what it would have cost without it.", ""]
    out += [
           "| | Files | KB | Share |", "| - | ----: | -: | ----: |"]
    total = kb(rows) or 1.0
    out += ["| Read | %d | %.0f | %.0f%% | [measured]" % (len(keep), kb(keep), 100*kb(keep)/total),
            "| **Not read** | **%d** | **%.0f** | **%.0f%%** | [measured]"
            % (len(cut), kb(cut), 100*kb(cut)/total)]
    if saved:
        out.append("| Rescued (revision-marked) | %d | %.0f | %.0f%% | [measured]"
                   % (len(saved), kb(saved), 100*kb(saved)/total))
    if bad:
        out.append("| ⚠️ Unreadable here | %d | %.0f | %.0f%% | [measured]"
                   % (len(bad), kb(bad), 100*kb(bad)/total))
    out.append("")
    if bad:
        out += ["## ⚠️ Could not be opened", "",
                "These were neither read nor excluded: the gate could not open them, so it",
                "cannot say whether they matter. They are passed through to the planner, and",
                "an absence claim resting on one of them is `not-accessed`, not a finding.", "",
                "| KB | Path |", "| -: | ---- |"]
        for r in sorted(bad, key=lambda x: -x["bytes"]):
            out.append("| %.0f | `%s` |" % (r["bytes"]/1024.0, r["path"]))
        out.append("")
    if saved:
        out += ["", "## Rescued", "",
                "Below the threshold, kept anyway: each carries revision markers, which makes",
                "it a specification. Density does not get to remove the document the question",
                "is about.", "",
                "| KB | Hits | Path |", "| -: | ---: | ---- |"]
        for r in sorted(saved, key=lambda x: -x["bytes"]):
            out.append("| %.0f | %s | `%s` |"
                       % (r["bytes"]/1024.0, r["hits"], r["path"]))
        out.append("")
    if cut:
        out += ["## Not read" if not declined else "## Would have been excluded", "",
                "Every row below was excluded by the gate, not by a judgement about its content.",
                "An absence claim may **not** be `UPHELD` from any of these files: the correct",
                "verdict is `not-accessed: cut by the relevance gate`.", "",
                "| KB | Hits | Path |", "| -: | ---: | ---- |"]
        for r in sorted(cut, key=lambda x: -x["bytes"]):
            out.append("| %.0f | %s | `%s` |"
                       % (r["bytes"]/1024.0,
                          "?" if r["hits"] is None else r["hits"], r["path"]))
        out += ["", "Re-run with `--relevance 0` to read everything, or",
                "`--relevance-add <term>` to widen the vocabulary.", ""]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="relevance.py",
        description="Keep the inputs the scope actually occurs in; list the rest.")
    ap.add_argument("recon", help="recon.json from recon.py")
    ap.add_argument("--scope", default="", help="the business question, verbatim")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                    help="minimum hits per KB (0 keeps everything)")
    ap.add_argument("--add", action="append", default=[],
                    help="extra term the scope wording does not contain")
    ap.add_argument("--report", default=None,
                    help="write the keep/cut table here (steps/01b-relevance.md)")
    ap.add_argument("--out", default=None,
                    help="write a filtered recon.json here for the planner")
    a = ap.parse_args(argv)

    try:
        recon = json.load(io.open(a.recon, encoding="utf-8"))
    except (IOError, ValueError) as e:
        print("RECON-UNREADABLE  %s: %s" % (a.recon, e))
        return 2

    records = recon.get("inputs") or recon.get("records") or []
    if not records:
        print("NO-INPUTS  %s carries no input records" % a.recon)
        return 2

    terms = vocabulary(a.scope, a.add)
    if not terms:
        print("NO-VOCABULARY  --scope produced no searchable term; nothing excluded")
        a.threshold = 0.0

    root = recon.get("repo") or None
    rows = classify(records, terms, a.threshold, root)
    declined = decline_reasons(rows, records, terms) if a.threshold > 0 else []
    if declined:
        keep, cut, bad = rows, [], [r for r in rows if r["verdict"] == "unreadable"]
    else:
        keep = [r for r in rows if r["verdict"] != "cut"]   # unreadable, rescued pass on
        cut = [r for r in rows if r["verdict"] == "cut"]
        bad = [r for r in rows if r["verdict"] == "unreadable"]
    text = render(rows, terms, a.threshold, declined)

    if a.report:
        d = os.path.dirname(a.report)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        io.open(a.report, "w", encoding="utf-8").write(text)

    if a.out:
        kept = set(r["path"] for r in keep)
        filtered = dict(recon)
        key = "inputs" if recon.get("inputs") else "records"
        filtered[key] = [r for r in records if r.get("path") in kept]
        filtered["relevance"] = {
            "threshold": a.threshold, "terms": terms,
            "kept": len(keep), "cut": len(cut),
            "cut_paths": [r["path"] for r in cut],
        }
        io.open(a.out, "w", encoding="utf-8").write(json.dumps(filtered, indent=2))

    kb = lambda rs: sum(r["bytes"] for r in rs) / 1024.0
    if declined:
        print("GATE-DECLINED  nothing excluded · terms: %s" % (" ".join(terms) or "(none)"))
        for r in declined:
            print("  - %s" % r)
        print("  ⇒ every input is read; add a term in the corpus's own language with")
        print("    --relevance-add <term>, or accept the cost of reading everything")
        if a.report:
            print("  report    %s   (the exclusions are listed there, not in effect)" % a.report)
        if a.out:
            print("  filtered  %s   (unchanged: all %d inputs)" % (a.out, len(records)))
        return 0
    saved = [r for r in rows if r["verdict"] == "rescued"]
    print("RELEVANCE  threshold %.3f hits/KB · %d terms" % (a.threshold, len(terms)))
    print("  read      %3d files  %7.0f KB" % (len(keep), kb(keep)))
    if saved:
        print("  · rescued %3d files  %7.0f KB   <- revision-marked: a spec is never "
              "cut on density" % (len(saved), kb(saved)))
    print("  not read  %3d files  %7.0f KB   <- listed in the report, never silent"
          % (len(cut), kb(cut)))
    if bad:
        print("  ⚠️ unreadable %3d files %7.0f KB   <- neither read nor excluded; "
              "check the paths resolve" % (len(bad), kb(bad)))
    if a.report:
        print("  report    %s" % a.report)
    if a.out:
        print("  filtered  %s" % a.out)
    if cut:
        print("  ⛔ an absence claim from a cut file is `not-accessed`, never `UPHELD`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
