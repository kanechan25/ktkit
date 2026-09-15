#!/usr/bin/env python3
"""What a change request actually changes -- and which finished work it kills.

A change request is not a feature request with different wording. A feature
starts from nothing; a CR starts from a spec somebody already approved, a plan
somebody already made, and tasks somebody may already have built. The expensive
question is not "what do we want now" but "what did we already do that this
undoes".

Answering it by re-reading the repository costs a full pass over the code for a
change that may touch two files. This script does not do that. It reads:

    the CR       `§2 behavior CU` and `§3 behavior MOI` -- the two halves of a
                 delta, already separated by `raise-issue`
    the spec     the requirement ids that currently exist
    the ledger   `task-state.md`, which recorded `spec_refs` and `touched` at
                 the moment each task was marked done

and produces three sections, never more:

    delta        added / modified / removed / contradicted / ambiguous
    impact       requirements, files, tasks split into invalidated / superseded
                 / untouched
    patch        what to append to spec.md, plan.md and tasks.md

`impact.files` comes from the ledger's `touched` column. That is the entire
saving: the repository is never re-read to find out what a task changed, because
the task said so when it finished.

Three conditions stop the run. They are exit codes, not advice:

    1  `contradicted` is non-empty -- two requirements cannot both hold, and
       choosing between them is the user's call, not a script's
    2  a `done` task is being invalidated with no requirement id to point at --
       the ledger is missing `spec_refs`, so nothing can show WHY it died
    3  the impact touches more than 60% of tasks -- this is a new requirement
       wearing a change request's clothes, and it should be routed as one

Stdlib only, Python 3.9.
"""
import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "skills", "chain",
                                "scripts"))

# The share of tasks above which a change request stops being one. Not tuned --
# chosen so that a change rewriting most of the plan is refused rather than
# absorbed. A CR is a delta; when the delta is most of the thing, the thing is
# new.
NEW_REQUIREMENT_SHARE = 0.60

# Requirement ids, as spec-kit writes them and as the ledger cites them.
REQ_RE = re.compile(r"\b((?:FR|NFR|SC|CHK)-\d+)\b")

# The two halves of the delta, as `raise-issue`'s CR form lays them out. Matched
# on the section number, not on the prose: the headings are Vietnamese and will
# be reworded, the numbers are structural.
# The whole heading line is consumed, not just the number: leaving the rest
# of it in the body makes the heading itself look like a behaviour statement.
SECTION_RE = re.compile(r"^##\s*§(\d+)\..*$", re.M)
OLD_SECTION = "2"
NEW_SECTION = "3"

# A line that says something is no longer wanted. Deliberately small: a longer
# list starts deciding what the author meant, which is the user's job.
REMOVAL_WORDS = ("no longer", "remove", "drop", "stop ", "bỏ ", "không còn",
                 "xoá", "xóa")


def read(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


def sections(text):
    """{section number: body} for a `raise-issue` form."""
    out, marks = {}, list(SECTION_RE.finditer(text))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out[m.group(1)] = text[m.end():end].strip()
    return out


def requirements(text):
    """Requirement ids in the order they first appear."""
    seen, out = set(), []
    for m in REQ_RE.finditer(text):
        if m.group(1) not in seen:
            seen.add(m.group(1))
            out.append(m.group(1))
    return out


def statements(body):
    """Non-empty, non-heading lines -- one behaviour claim per line."""
    out = []
    for line in body.splitlines():
        line = line.strip().lstrip("-*+ ").strip()
        if not line or line.startswith("#") or line.startswith("|"):
            continue
        if line.startswith("<") and line.endswith(">"):
            continue                              # an unfilled template slot
        out.append(line)
    return out


def norm(line):
    return re.sub(r"[^a-z0-9]+", " ", line.lower()).strip()


def overlap(a, b):
    """Jaccard over words. Same measure `ledger.py --lookup` uses, on purpose:
    two similarity scores in one plugin that disagree is one too many."""
    wa, wb = set(norm(a).split()), set(norm(b).split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / float(len(wa | wb))


def containment(a, b):
    """How much of the SHORTER statement the longer one covers.

    Jaccard punishes length, and the pair that matters most here is exactly the
    one where length differs: "the owner cannot change the expiry" against "the
    owner can change the expiry to at most 7 days". Every word of the old
    statement survives in the new one, and Jaccard still scores it 0.31 because
    of the detail that was added. Containment scores it 1.0.
    """
    wa, wb = set(norm(a).split()), set(norm(b).split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / float(min(len(wa), len(wb)))


# How much of the shorter statement must survive, once polarity words are
# stripped, before a disagreement about polarity is called a contradiction.
# High on purpose: a contradiction STOPS the run, so a loose reading here makes
# the stop meaningless, while a strict one still catches the case it exists for
# -- the same sentence with the "not" taken out.
NEG_CONTAINMENT = 0.8


def build_delta(old_body, new_body, threshold):
    """Which statements were added, modified, removed, contradicted, ambiguous.

    `contradicted` is the one that stops the run, so it is drawn narrowly: a new
    statement that closely matches an old one AND negates it. A wide reading
    here would stop every run; a missing one would let two incompatible
    requirements into the same spec.
    """
    old, new = statements(old_body), statements(new_body)
    added, modified, contradicted, ambiguous = [], [], [], []
    matched_old = set()

    for n in new:
        best, score = None, 0.0
        for i, o in enumerate(old):
            sc = overlap(o, n)
            if sc > score:
                best, score = i, sc
        # A statement and its negation share few words once the extra detail is
        # added, so a plain overlap misses exactly the pair that matters most.
        # Compare again with the polarity words removed: if THAT matches and the
        # polarities disagree, the two cannot both hold.
        if best is not None and is_negated(old[best]) != is_negated(n):
            bare = containment(strip_neg(old[best]), strip_neg(n))
            if bare >= NEG_CONTAINMENT:
                matched_old.add(best)
                contradicted.append({"old": old[best], "new": n,
                                     "similarity": round(bare, 2),
                                     "why": "one of these is negated and the "
                                            "other is not"})
                continue
        if best is None or score < threshold:
            added.append(n)
            continue
        matched_old.add(best)
        if score >= 0.95:
            ambiguous.append({"old": old[best], "new": n,
                              "why": "restates the old behaviour almost exactly "
                                     "-- say what changed, or drop the line"})
        else:
            modified.append({"old": old[best], "new": n,
                             "similarity": round(score, 2)})

    removed = [o for i, o in enumerate(old)
               if i not in matched_old and not says_removal(o)]
    for n in new:
        if says_removal(n):
            removed.append(n)
    return {"added": added, "modified": modified, "removed": removed,
            "contradicted": contradicted, "ambiguous": ambiguous}


# Words that flip a statement's polarity. A pair that matches closely once
# these are stripped, and disagrees on whether they are present, is the one
# contradiction this script is confident about.
NEG_WORDS = (" not ", " never ", " no ", " cannot ", " can't ", " khong ",
             " không ", " chưa ", " n't ")


def strip_neg(text):
    low = " %s " % text.lower()
    for w in NEG_WORDS:
        low = low.replace(w, " ")
    return low


def is_negated(text):
    low = " %s " % text.lower()
    return any(w in low for w in NEG_WORDS)


def says_removal(line):
    low = line.lower()
    return any(w in low for w in REMOVAL_WORDS)


def load_tasks(ledger_path):
    """Current state of every task, from the ledger's task-state table."""
    import ledger                                              # noqa: E402
    path = ledger.task_state_path(ledger_path)
    rows = ledger.read_task_rows(path)
    return ledger.task_latest(rows), ledger


def build_impact(delta, spec_reqs, tasks, mod):
    """Which requirements, files and tasks the delta reaches.

    Files come from the ledger's `touched` column and from nowhere else. The
    repository is not searched: a task that finished said what it changed, and
    asking the tree again would cost a full pass to learn something already
    written down.
    """
    changed_lines = ([d["new"] for d in delta["modified"]]
                     + [d["new"] for d in delta["contradicted"]]
                     + delta["added"] + delta["removed"])
    touched_reqs = []
    for line in changed_lines:
        for r in requirements(line):
            if r not in touched_reqs:
                touched_reqs.append(r)
    # A CR that names no requirement still reaches every requirement its own
    # changed statements overlap with -- but that is a judgement, so it is not
    # made here. What IS reported is that the CR cited nothing.
    invalidated, superseded, untouched, files = [], [], [], []
    for task_id in sorted(tasks):
        row = tasks[task_id]
        hit = [r for r in row["spec_refs"] if r in touched_reqs]
        if not hit:
            # A DONE task that cites nothing cannot be cleared either. It is not
            # "untouched" -- it is unknown, and the difference matters because
            # untouched means somebody checked. `--set done` has required
            # spec_refs since the task state existed, so this is a row from
            # before that, and it reports as an invalidation nobody can cite so
            # the run stops rather than guessing.
            if (row["state"] == mod.TASK_DONE and not row["spec_refs"]
                    and touched_reqs):
                invalidated.append({"task": task_id, "by": [],
                                    "touched": row["touched"]})
                for f in row["touched"]:
                    if f not in files:
                        files.append(f)
                continue
            untouched.append(task_id)
            continue
        if row["state"] == mod.TASK_DONE:
            invalidated.append({"task": task_id, "by": hit,
                                "touched": row["touched"]})
            for f in row["touched"]:
                if f not in files:
                    files.append(f)
        elif row["state"] in ("pending", "ready", "running"):
            superseded.append({"task": task_id, "by": hit,
                               "state": row["state"]})
        else:
            untouched.append(task_id)
    return {
        "requirements": {"cited_by_cr": touched_reqs,
                         "in_spec": spec_reqs,
                         "cited_but_absent": [r for r in touched_reqs
                                              if r not in spec_reqs]},
        "files": files,
        "tasks": {"invalidated": invalidated, "superseded": superseded,
                  "untouched": untouched},
    }


def build_patch(delta, impact):
    """What to append where. Append-only, and never a rewrite.

    Same rule `speckit-converge` follows for tasks.md: an existing requirement
    keeps its id and gains a revision note, because renumbering breaks every
    citation anybody has already made to it.
    """
    spec = []
    for d in delta["added"]:
        spec.append("append a new requirement: %s" % d)
    for d in delta["modified"]:
        spec.append("revise in place, keeping the id: %s -> %s"
                    % (d["old"], d["new"]))
    for d in delta["removed"]:
        spec.append("mark withdrawn, do not delete: %s" % d)
    plan = []
    if impact["files"]:
        plan.append("revisit the sections covering: %s"
                    % ", ".join(impact["files"]))
    tasks = []
    for t in impact["tasks"]["invalidated"]:
        tasks.append("%s was built against %s -- append a task to unwind or "
                     "rework %s" % (t["task"], ", ".join(t["by"]),
                                    ", ".join(t["touched"]) or "it"))
    for t in impact["tasks"]["superseded"]:
        tasks.append("%s was never built -- append its replacement; leave the "
                     "superseded row in place" % t["task"])
    return {"spec.md": spec, "plan.md": plan, "tasks.md": tasks}


def stops(delta, impact, tasks):
    """The three conditions that end the run, in the order they are checked."""
    out = []
    if delta["contradicted"]:
        out.append({
            "code": 1, "name": "contradicted",
            "detail": "%d statement(s) contradict the current behaviour. Two "
                      "requirements cannot both hold, and choosing between them "
                      "is not a script's call." % len(delta["contradicted"]),
            "rows": delta["contradicted"],
        })
    unciteable = [t["task"] for t in impact["tasks"]["invalidated"]
                  if not t["by"]]
    if unciteable:
        out.append({
            "code": 2, "name": "uncitable-invalidation",
            "detail": "%s was done and is being invalidated, but no requirement "
                      "id explains why. The ledger is missing spec_refs, so "
                      "nothing can show what killed it."
                      % ", ".join(unciteable),
            "rows": unciteable,
        })
    total = len(tasks)
    reached = (len(impact["tasks"]["invalidated"])
               + len(impact["tasks"]["superseded"]))
    if total and reached > NEW_REQUIREMENT_SHARE * total:
        out.append({
            "code": 3, "name": "not-a-change-request",
            "detail": "%d of %d tasks (%.0f%%) are reached. Above %.0f%% this "
                      "is a new requirement wearing a change request's clothes "
                      "-- route it as NR." % (reached, total,
                                              100.0 * reached / total,
                                              100 * NEW_REQUIREMENT_SHARE),
            "rows": [], "reached": reached, "total": total,
        })
    return out


def render(result):
    lines = ["# CR delta", ""]
    d = result["delta"]
    lines.append("## delta")
    for key in ("added", "modified", "removed", "contradicted", "ambiguous"):
        rows = d[key]
        lines.append("")
        lines.append("### %s (%d)" % (key, len(rows)))
        for r in rows:
            lines.append("- %s" % (r if isinstance(r, str)
                                   else json.dumps(r, ensure_ascii=False)))
    i = result["impact"]
    lines += ["", "## impact", "",
              "- requirements cited by the CR: %s"
              % (", ".join(i["requirements"]["cited_by_cr"]) or "none"),
              "- cited but absent from the spec: %s"
              % (", ".join(i["requirements"]["cited_but_absent"]) or "none"),
              "- files, from the ledger's touched column: %s"
              % (", ".join(i["files"]) or "none"),
              "- tasks invalidated (built, now wrong): %s"
              % (", ".join(t["task"] for t in i["tasks"]["invalidated"]) or "none"),
              "- tasks superseded (never built): %s"
              % (", ".join(t["task"] for t in i["tasks"]["superseded"]) or "none"),
              "- tasks untouched: %s"
              % (", ".join(i["tasks"]["untouched"]) or "none")]
    lines += ["", "## patch", ""]
    for name, items in result["patch"].items():
        lines.append("### %s (%d)" % (name, len(items)))
        for item in items:
            lines.append("- %s" % item)
        lines.append("")
    if result["stops"]:
        lines.append("## STOP")
        for s in result["stops"]:
            lines.append("- **%s** (exit %d): %s"
                         % (s["name"], s["code"], s["detail"]))
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="cr_delta.py",
        description="What a change request changes, and which finished work it "
                    "kills -- read from the ledger, not from the repository.")
    ap.add_argument("--cr", required=True, help="the CR file raise-issue wrote")
    ap.add_argument("--spec", required=True, help="the current spec.md")
    ap.add_argument("--ledger", required=True,
                    help="the run's resolved.md; task-state.md sits beside it")
    ap.add_argument("--threshold", type=float, default=0.45,
                    help="word overlap above which two statements are the same "
                         "requirement reworded (default: 0.45)")
    ap.add_argument("--json", action="store_true",
                    help="machine-readable output instead of the report")
    a = ap.parse_args(argv)

    for label, path in (("--cr", a.cr), ("--spec", a.spec)):
        if not os.path.isfile(path):
            print("FAIL missing-input: %s %s does not exist" % (label, path))
            return 2

    secs = sections(read(a.cr))
    if OLD_SECTION not in secs or NEW_SECTION not in secs:
        print("FAIL not-a-cr: §%s (old behaviour) and §%s (new behaviour) are "
              "both required -- that is what makes a CR a delta. Found: %s"
              % (OLD_SECTION, NEW_SECTION,
                 ", ".join("§" + k for k in sorted(secs)) or "no sections"))
        return 2

    try:
        tasks, mod = load_tasks(a.ledger)
    except ValueError as exc:
        print("FAIL malformed-task-state: %s" % exc)
        return 2

    delta = build_delta(secs[OLD_SECTION], secs[NEW_SECTION], a.threshold)
    impact = build_impact(delta, requirements(read(a.spec)), tasks, mod)
    result = {"delta": delta, "impact": impact,
              "patch": build_patch(delta, impact)}
    result["stops"] = stops(delta, impact, tasks)

    if a.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        sys.stdout.write(render(result))

    # The first stop's code, so a caller can tell them apart. Reporting all of
    # them and exiting on the first is deliberate: a run that stops for one
    # reason usually has the others waiting behind it, and finding out one at a
    # time costs another pass each time.
    return result["stops"][0]["code"] if result["stops"] else 0


if __name__ == "__main__":
    sys.exit(main())
