#!/usr/bin/env python3
"""Turn recon.json into a fleet plan: which agents to spawn, and how many.

This is a script rather than a paragraph of instructions on purpose. "How many
agents of which role" is the decision that spends the money, and a decision the
model improvises differently each run is not a feature -- it is a defect nobody
can reproduce. Structure is decided here and locked by tests; content (what each
agent is actually asked, in the caller's own words) stays with the lead.

The boundary, stated once so it is not renegotiated:
    planner decides STRUCTURE   -- how many agents, of which roles, in which wave
    lead decides CONTENT        -- the prompt each of them receives

Falsifier for that boundary: if two runs over one recon.json produce different
plans, the boundary is wrong and belongs back with the model.

Sharding rules
    text document      1 agent per <= 700 lines, capped per wave
    html document      1 agent, and the caller must strip tags to a temp file
                       first -- an agent that reads raw markup spends its whole
                       budget on it
    snapshot document  1 agent per document, never split: a change-surface index
                       needs the whole document in one context
    binary artifacts   1 agent for the whole group; measuring in bulk is cheaper
    code questions     1 agent per topic cluster, never one per identifier
    vcs                exactly 1 agent, because the rate limit is shared

Runtime probes are never planned. `probe-runtime` touches a live system, so it
runs only when a human types its name; a planner that could infer it from the
inputs would eventually infer it wrongly.

Usage
    plan_fleet.py <recon.json> [--probe code,artifact,vcs] [--baseline N]
                  [--max-parallel 12] [--rounds 3] [--json]
Exit status
    0  a plan was produced
    2  the arguments or the recon file are unusable
"""
import argparse
import json
import os
import sys

# Tool sets proved on this harness by direct probe. Declaring anything else is
# how an agent silently loses Grep and Glob: granting Bash removes them.
SET_A = "Read, Grep, Glob"
SET_B = "Read, Bash"
SET_C = "Read, Write, Grep, Glob"

LINES_PER_MAPPER = 700
MAX_PARALLEL = 12

# Per-wave ceilings from the design. They cap fan-out, they do not choose roles:
# document count changes how many agents run, never which ones.
CAP = {
    "doc-extract": 12,
    "state-extract": None,      # one per snapshot, never merged
    "probe-artifact": 2,
    "probe-code": 4,
    "probe-vcs": 1,
}

ROLES = {
    "doc-extract":    {"agent": "ktkit:docs-review-mapper",      "tools": SET_C, "kind": "producer"},
    "state-extract":  {"agent": "ktkit:spec-recon-state-extract", "tools": SET_C, "kind": "producer"},
    "probe-code":     {"agent": "ktkit:spec-recon-probe-code",    "tools": SET_A, "kind": "reviewer"},
    "probe-artifact": {"agent": "ktkit:spec-recon-probe-artifact", "tools": SET_B, "kind": "producer"},
    "probe-vcs":      {"agent": "ktkit:spec-recon-probe-vcs",     "tools": SET_B, "kind": "producer"},
    "probe-runtime":  {"agent": "ktkit:spec-recon-probe-runtime", "tools": SET_B, "kind": "producer"},
    "arbiter-impl":   {"agent": "ktkit:spec-recon-arbiter-impl",  "tools": SET_A, "kind": "reviewer"},
}

# Base token cost per spawn, measured on this harness. Bash costs ~4.7k more
# than Grep+Glob because its schema carries the whole sandbox description, so a
# plan that leans on set B is visibly more expensive here rather than at the
# end of the month.
BASE_TOKENS = {SET_A: 6619, SET_B: 11353, SET_C: 6875}


def ceil_div(a, b):
    return -(-a // b)


def plan(recon, probes, baseline_paths, max_parallel, rounds):
    inputs = recon.get("inputs", [])
    baseline = set(baseline_paths or [])

    docs = [r for r in inputs
            if not r["is_binary"] and r["path"] not in baseline]
    snaps = [r for r in inputs if r["path"] in baseline]
    bins = [r for r in inputs if r["is_binary"]]

    tasks = []

    # --- documents -> mappers, sharded by line count ------------------------
    shards = 0
    for r in docs:
        lines = r.get("lines") or 0
        n = max(1, ceil_div(lines, LINES_PER_MAPPER)) if lines else 1
        html = r["ext"] in (".html", ".htm")
        if html:
            n = 1
        shards += n
        tasks.append({"role": "doc-extract", "count": n, "path": r["path"],
                      "lines": lines,
                      "note": ("strip tags to a temp file before reading"
                               if html else None)})
    over = shards - CAP["doc-extract"]
    if over > 0:
        tasks.append({"role": "_note", "count": 0, "path": None,
                      "note": "%d doc shards exceed the per-wave cap of %d; "
                              "run them in batches within the same wave"
                              % (shards, CAP["doc-extract"])})

    # --- snapshots -> one agent each, never split ---------------------------
    for r in snaps:
        tasks.append({"role": "state-extract", "count": 1, "path": r["path"],
                      "lines": r.get("lines")})

    # --- binaries -> one agent for the whole group --------------------------
    if bins and "artifact" in probes:
        ambiguous = [g["basename"] for g in recon.get("duplicates", [])
                     if g["status"] != "resolved"]
        tasks.append({"role": "probe-artifact", "count": 1, "path": None,
                      "targets": [r["path"] for r in bins],
                      "note": ("resolve ambiguous sources first: %s"
                               % ", ".join(ambiguous)) if ambiguous else None})

    # --- code probes: one per topic cluster, not per identifier -------------
    if "code" in probes:
        n_code = min(CAP["probe-code"], max(1, ceil_div(len(docs), 3)))
        tasks.append({"role": "probe-code", "count": n_code, "path": None,
                      "note": "one agent per topic cluster; the lead writes the "
                              "clusters from --scope"})

    # --- vcs: exactly one, the rate limit is shared -------------------------
    if "vcs" in probes:
        tasks.append({"role": "probe-vcs", "count": 1, "path": None,
                      "note": "gh auth token for credentials, urllib for "
                              "transport; never `gh api`"})

    # --- runtime: only when asked by name -----------------------------------
    if "runtime" in probes:
        tasks.append({"role": "probe-runtime", "count": 1, "path": None,
                      "note": "explicitly requested; read-only queries only"})

    wave1 = [t for t in tasks if t["role"] != "_note"]
    n1 = sum(t["count"] for t in wave1)

    waves = [{
        "n": 1,
        "purpose": "extract and probe",
        "tasks": wave1,
        "agents": n1,
        "batches": max(1, ceil_div(n1, max_parallel)),
    }]

    # Review waves reuse the docs-review team unchanged, plus the arbiter that
    # every "not implemented" verdict has to survive.
    review = [
        {"role": "review", "agent": "ktkit:docs-review-requirement", "count": 1},
        {"role": "review", "agent": "ktkit:docs-review-evidence", "count": 1},
        {"role": "review", "agent": "ktkit:docs-review-coverage", "count": 1},
        {"role": "review", "agent": "ktkit:docs-review-failure", "count": 1},
        {"role": "arbiter-impl", "agent": ROLES["arbiter-impl"]["agent"], "count": 1},
    ]
    waves.append({
        "n": 2,
        "purpose": "review to convergence (ceiling %d)" % rounds,
        "tasks": review,
        "agents": sum(t["count"] for t in review),
        "batches": 1,
    })

    est = 0
    for t in wave1:
        tools = ROLES.get(t["role"], {}).get("tools", SET_A)
        est += BASE_TOKENS[tools] * t["count"]
    est += BASE_TOKENS[SET_A] * waves[1]["agents"] * rounds

    return {
        "schema": 1,
        "probes": sorted(probes),
        "max_parallel": max_parallel,
        "rounds_ceiling": rounds,
        "waves": waves,
        "notes": [t["note"] for t in tasks
                  if t.get("note") and t["role"] == "_note"],
        "estimate": {
            "wave1_agents": waves[0]["agents"],
            "review_agents_per_round": waves[1]["agents"],
            "base_tokens_floor": est,
            "caveat": "base tokens only: the prompt body and every tool result "
                      "are on top, and they dominate",
        },
    }


def render(p):
    lines = []
    for w in p["waves"]:
        parts = []
        for t in w["tasks"]:
            label = t.get("agent") or ROLES.get(t["role"], {}).get("agent", t["role"])
            parts.append("%s x%d" % (label.split(":")[-1], t["count"]))
        lines.append("wave%d (%s) = %s = %d agents%s"
                     % (w["n"], w["purpose"], " + ".join(parts), w["agents"],
                        "" if w["batches"] == 1 else " in %d batches" % w["batches"]))
    for n in p["notes"]:
        lines.append("note: %s" % n)
    lines.append("floor ~%dk base tokens (bodies and tool results on top)"
                 % (p["estimate"]["base_tokens_floor"] // 1000))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("recon")
    ap.add_argument("--probe", default="code,artifact,vcs")
    ap.add_argument("--baseline", nargs="*", default=[],
                    help="paths that describe current state, not the spec")
    ap.add_argument("--max-parallel", type=int, default=MAX_PARALLEL)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if not os.path.isfile(a.recon):
        sys.stderr.write("no such recon file: %s\n" % a.recon)
        return 2
    try:
        with open(a.recon) as fh:
            recon = json.load(fh)
    except ValueError as exc:
        sys.stderr.write("recon.json is not valid JSON: %s\n" % exc)
        return 2

    probes = set(x.strip() for x in a.probe.split(",") if x.strip())
    unknown = probes - {"code", "artifact", "vcs", "runtime"}
    if unknown:
        sys.stderr.write("unknown probe layer(s): %s\n" % ", ".join(sorted(unknown)))
        return 2

    p = plan(recon, probes, a.baseline, a.max_parallel, a.rounds)
    if a.json:
        sys.stdout.write(json.dumps(p, indent=1, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write(render(p) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
