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


def test_text_documents_shard_by_line_count():
    p = pf.plan(SAMPLE, {"code"}, [], 12, 3)
    t = [x for x in p["waves"][0]["tasks"]
         if x["role"] == "doc-extract" and x["path"] == "a.md"][0]
    check("1400 lines becomes 2 mappers at 700 each", t["count"] == 2, t)


def test_html_is_one_agent_and_carries_the_strip_instruction():
    p = pf.plan(SAMPLE, {"code"}, [], 12, 3)
    t = [x for x in p["waves"][0]["tasks"] if x["path"] == "c.html"][0]
    check("a 9000-line html document is still one agent", t["count"] == 1, t)
    check("html task says to strip tags first",
          t.get("note") and "strip tags" in t["note"], t)


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
