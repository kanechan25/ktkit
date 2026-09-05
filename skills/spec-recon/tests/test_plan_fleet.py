#!/usr/bin/env python3
"""Tests for the dispatch planner.

The planner exists so that "how many agents of which role" is reproducible. The
first test below is therefore the important one: the same recon file must always
produce the same plan. If it ever does not, the structure/content boundary is
wrong and the decision belongs back with the model rather than in this script.

The rest lock the rules that were bought with a real run: runtime probes are
never inferred, vcs is exactly one agent because the rate limit is shared,
snapshots are never split, and no agent is ever handed a tool set that this
harness silently rewrites.

Run:  python3 skills/spec-recon/tests/test_plan_fleet.py
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(SKILL, "scripts"))

import plan_fleet as pf                                        # noqa: E402

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def rec(path, lines=100, binary=False, ext=".md"):
    return {"path": path, "bytes": lines * 40, "mtime": 0, "ext": ext,
            "is_binary": binary, "md5": "x" * 32, "lines": lines,
            "lang": "en", "revision_markers": {}, "git_tracked": True,
            "last_commit": None}


def recon(inputs, duplicates=None):
    return {"schema": 1, "repo": "/r", "prior_report": None,
            "prior_report_mtime": None, "stale_risk": [], "patterns": [],
            "inputs": inputs, "duplicates": duplicates or [],
            "totals": {}}


SAMPLE = recon([
    rec("a.md", 1400),                 # 2 shards
    rec("b.md", 300),                  # 1 shard
    rec("c.html", 9000, ext=".html"),  # 1 shard regardless of size
    rec("t.xlsx", 0, binary=True, ext=".xlsx"),
    rec("state.md", 500),
])


def test_plan_is_deterministic():
    """The falsifier for the whole design: same input, same plan. Always."""
    a = pf.plan(SAMPLE, {"code", "artifact", "vcs"}, ["state.md"], 12, 3)
    b = pf.plan(SAMPLE, {"code", "artifact", "vcs"}, ["state.md"], 12, 3)
    check("two runs over one recon produce an identical plan",
          json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))


def test_documents_shard_by_bytes_not_lines():
    """A line is not a unit of cost, and treating it as one produced shards that
    differed by three orders of magnitude."""
    p = pf.plan(SAMPLE, {"code"}, [], 12, 3)
    t = [x for x in p["waves"][0]["tasks"]
         if x["role"] == "doc-extract" and x["path"] == "a.md"][0]
    expect = pf.ceil_div(1400 * 40, pf.BYTES_PER_MAPPER)
    check("shard count follows byte size", t["count"] == max(1, expect), t)


def test_one_huge_line_is_sharded_like_any_other_bulk():
    """The case the line rule got wrong: one line of minified markup, 800 KB."""
    r = recon([{"path": "min.html", "bytes": 800 * 1024, "mtime": 0,
                "ext": ".html", "is_binary": False, "md5": "x" * 32,
                "lines": 1, "lang": "en", "revision_markers": {},
                "git_tracked": True, "last_commit": None}])
    p = pf.plan(r, {"code"}, [], 12, 3)
    t = [x for x in p["waves"][0]["tasks"] if x["role"] == "doc-extract"][0]
    expect = pf.ceil_div(int(800 * 1024 * 0.71), pf.BYTES_PER_MAPPER)
    check("a single 800 KB line is sharded by size, not left as one",
          t["count"] == expect and t["count"] > 1, (t["count"], expect))
    check("html still carries the strip-first instruction",
          t.get("note") and "strip tags" in t["note"], t)


def test_ten_thousand_short_lines_are_not_over_sharded():
    """The mirror case: many lines, little content. The line rule over-split it."""
    r = recon([{"path": "many.md", "bytes": 30 * 1024, "mtime": 0, "ext": ".md",
                "is_binary": False, "md5": "x" * 32, "lines": 10000,
                "lang": "en", "revision_markers": {}, "git_tracked": True,
                "last_commit": None}])
    p = pf.plan(r, {"code"}, [], 12, 3)
    t = [x for x in p["waves"][0]["tasks"] if x["role"] == "doc-extract"][0]
    check("10,000 short lines stay one agent (30 KB < one shard)",
          t["count"] == 1, t["count"])


BIG = recon([{"path": "big.md", "bytes": 500 * 1024, "mtime": 0, "ext": ".md",
              "is_binary": False, "md5": "x" * 32, "lines": 12000, "lang": "en",
              "revision_markers": {}, "git_tracked": True, "last_commit": None}])


def test_a_split_file_gets_contiguous_ranges_covering_it_exactly():
    """C1: the agent Reads once at a given offset instead of grepping around."""
    t = [x for x in pf.plan(BIG, {"code"}, [], 12, 3)["waves"][0]["tasks"]
         if x["role"] == "doc-extract"][0]
    rs = t["ranges"]
    check("a split file has one range per shard", len(rs) == t["count"], t)
    check("ranges start at 0", rs[0]["offset"] == 0, rs[0])
    check("ranges are contiguous",
          all(rs[i]["offset"] + rs[i]["limit"] == rs[i + 1]["offset"]
              for i in range(len(rs) - 1)), rs)
    check("ranges cover the file exactly",
          rs[-1]["offset"] + rs[-1]["limit"] == t["bytes"], (rs[-1], t["bytes"]))
    check("no zero-length range", all(r["limit"] > 0 for r in rs), rs)


def test_small_documents_are_packed_instead_of_one_agent_each():
    """Sizing cuts both ways: 40 tiny files must not become 40 agents."""
    r = recon([{"path": "t%02d.csv" % i, "bytes": 2500, "mtime": 0,
                "ext": ".csv", "is_binary": False, "md5": "x" * 32,
                "lines": 40, "lang": "en", "revision_markers": {},
                "git_tracked": True, "last_commit": None} for i in range(40)])
    de = [x for x in pf.plan(r, {"code"}, [], 12, 3)["waves"][0]["tasks"]
          if x["role"] == "doc-extract"]
    agents = sum(x["count"] for x in de)
    check("40 files of 2.5 KB do not become 40 agents", agents <= 4, agents)
    carried = sum(len(x.get("paths", [])) for x in de)
    check("every small file is still carried by some agent", carried == 40, carried)
    for x in de:
        check("a packed batch names the files it carries",
              x.get("paths") and len(x["ranges"]) == len(x["paths"]), x)
        check("a packed batch stays within one shard",
              x["bytes"] <= pf.BYTES_PER_MAPPER, x["bytes"])


def test_a_packed_batch_reads_each_file_whole():
    """Grouped files are read entire, so their ranges start at 0 each."""
    r = recon([{"path": "s%d.md" % i, "bytes": 5000, "mtime": 0, "ext": ".md",
                "is_binary": False, "md5": "x" * 32, "lines": 80, "lang": "en",
                "revision_markers": {}, "git_tracked": True,
                "last_commit": None} for i in range(3)])
    t = [x for x in pf.plan(r, {"code"}, [], 12, 3)["waves"][0]["tasks"]
         if x["role"] == "doc-extract"][0]
    check("a packed batch is one agent", t["count"] == 1, t)
    check("each carried file is read from its start",
          all(rg["offset"] == 0 for rg in t["ranges"]), t["ranges"])
    check("each carried file is read whole",
          all(rg["limit"] == 5000 for rg in t["ranges"]), t["ranges"])


def test_snapshots_are_never_split():
    p = pf.plan(SAMPLE, {"code"}, ["state.md"], 12, 3)
    st = [x for x in p["waves"][0]["tasks"] if x["role"] == "state-extract"]
    check("one state-extract per baseline document", len(st) == 1, st)
    check("a snapshot is never sharded", st[0]["count"] == 1, st)
    docs = [x["path"] for x in p["waves"][0]["tasks"] if x["role"] == "doc-extract"]
    check("a baseline document is not also mapped as a spec document",
          "state.md" not in docs, docs)


def test_binaries_get_one_agent_for_the_whole_group():
    p = pf.plan(SAMPLE, {"artifact"}, [], 12, 3)
    art = [x for x in p["waves"][0]["tasks"] if x["role"] == "probe-artifact"]
    check("binary probing is one agent for the group", len(art) == 1 and
          art[0]["count"] == 1, art)


def test_ambiguous_source_reaches_the_artifact_task():
    r = recon([rec("t.xlsx", 0, binary=True, ext=".xlsx")],
              duplicates=[{"basename": "t.xlsx", "members": [],
                           "source": None, "status": "ambiguous",
                           "copies_differ": True}])
    p = pf.plan(r, {"artifact"}, [], 12, 3)
    art = [x for x in p["waves"][0]["tasks"] if x["role"] == "probe-artifact"][0]
    check("an ambiguous artifact source is passed to the prober",
          art.get("note") and "ambiguous" in art["note"], art)


def test_vcs_is_exactly_one_agent():
    p = pf.plan(SAMPLE, {"vcs"}, [], 12, 3)
    v = [x for x in p["waves"][0]["tasks"] if x["role"] == "probe-vcs"]
    check("vcs is one agent, because the rate limit is shared",
          len(v) == 1 and v[0]["count"] == 1, v)


def test_vcs_task_forbids_gh_api():
    p = pf.plan(SAMPLE, {"vcs"}, [], 12, 3)
    v = [x for x in p["waves"][0]["tasks"] if x["role"] == "probe-vcs"][0]
    check("the vcs task carries the transport rule",
          v["note"] and "never `gh api`" in v["note"], v)


def test_runtime_is_never_planned_unless_named():
    p = pf.plan(SAMPLE, {"code", "artifact", "vcs"}, [], 12, 3)
    roles = [x["role"] for x in p["waves"][0]["tasks"]]
    check("runtime never appears without being asked for",
          "probe-runtime" not in roles, roles)
    p2 = pf.plan(SAMPLE, {"runtime"}, [], 12, 3)
    check("runtime appears when named explicitly",
          "probe-runtime" in [x["role"] for x in p2["waves"][0]["tasks"]])


def test_offline_probe_set_drops_vcs():
    p = pf.plan(SAMPLE, {"code", "artifact"}, [], 12, 3)
    roles = [x["role"] for x in p["waves"][0]["tasks"]]
    check("--probe code,artifact runs fully offline", "probe-vcs" not in roles, roles)


def test_every_role_uses_a_probed_tool_set():
    """Granting Bash removes Grep and Glob on this harness, silently.

    Only three sets were ever probed. Anything else is a defect even when it
    looks like a harmless superset.
    """
    probed = {pf.SET_A, pf.SET_B, pf.SET_C}
    bad = {k: v["tools"] for k, v in pf.ROLES.items() if v["tools"] not in probed}
    check("no role declares an unprobed tool set", not bad, bad)
    for k, v in pf.ROLES.items():
        if "Bash" in v["tools"]:
            check("%s does not ask for Grep/Glob alongside Bash" % k,
                  "Grep" not in v["tools"] and "Glob" not in v["tools"], v["tools"])


def test_arbiter_can_still_search():
    """The agent that refutes 'not implemented' lives by grep. It must keep it."""
    tools = pf.ROLES["arbiter-impl"]["tools"]
    check("arbiter-impl keeps Grep and Glob",
          "Grep" in tools and "Glob" in tools, tools)
    check("arbiter-impl has no Bash, which would remove them",
          "Bash" not in tools, tools)


def test_fan_out_is_batched_not_exceeded():
    big = recon([rec("d%d.md" % i, 700) for i in range(20)])
    p = pf.plan(big, {"code"}, [], 12, 3)
    w1 = p["waves"][0]
    check("more agents than the cap are split into batches",
          w1["batches"] >= 2, w1)
    check("the plan says the cap was exceeded",
          any("exceed" in n for n in p["notes"]), p["notes"])


def test_cli_rejects_an_unknown_probe_layer():
    d = tempfile.mkdtemp()
    path = os.path.join(d, "recon.json")
    with open(path, "w") as fh:
        json.dump(SAMPLE, fh)
    rc = pf.main([path, "--probe", "code,telepathy"])
    check("an unknown probe layer exits 2", rc == 2, "rc=%s" % rc)


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
