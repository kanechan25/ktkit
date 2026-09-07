#!/usr/bin/env python3
"""One verdict at every step boundary: keep going, or stop while the work is safe.

A run of `spec-recon` spent 15.2M tokens across 34 agents, hit the session limit
in the middle of its final wave, and produced no verdict at all. Nothing in the
skill could have seen it coming, because nothing measured anything until it was
over.

This is the thing that measures. It is called at every step boundary and answers
`GO` or `STOP`, from three inputs and no predictions:

    tokens spent   sum of `cost.jsonl` -- what each agent reported [measured]
    step cost      the last step's own tokens, and its own percent [measured]
    window         the percentage the usage endpoint reports        [measured]

The decision is arithmetic on those three:

    spent + last_step * SAFETY > budget          -> STOP (the ceiling)
    window_headroom < last_step_pct * SAFETY     -> STOP (the session)

⭐ **Nothing here forecasts.** An earlier design converted quota percent into
tokens so it could predict whether a run would fit, which required a calibration
that is only valid for one account and one tier -- and signing in with a
different account moved the window from 94% used to 6% mid-investigation. What
the last step actually cost is the only estimate the next step needs, and it is
an observation.

    budget.py --base <dir> --budget 4000000 [--step <name>] [--quota-gate 80]

Exit codes are the interface:

    0   GO      there is room for another step of the size of the last one
    1   STOP    there is not; the reason and the resume command are printed
    2   the arguments or the run directory do not make sense

`SAFETY` is the one tunable, and it is a margin rather than a model: a step may
cost more than the one before it, so the check asks for that much again plus
half. Set it lower and a run dies inside a step; set it higher and it stops with
budget unspent.

Stdlib only, Python 3.9.
"""
import argparse
import io
import json
import os
import subprocess
import sys
import time

SAFETY = 1.5
# scripts/ -> spec-recon/ -> skills/ -> the plugin root. `${CLAUDE_PLUGIN_ROOT}`
# when it is set, because a plugin can be installed anywhere.
PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
QUOTA = os.path.join(PLUGIN_ROOT, "scripts", "quota.py")
LEDGER = "budget.jsonl"


def read_cost(base):
    """(total_tokens, agents, reported, missing) from cost.jsonl."""
    p = os.path.join(base, "cost.jsonl")
    total = agents = reported = missing = 0
    if not os.path.isfile(p):
        return 0, 0, 0, 0
    for line in io.open(p, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("kind") != "agent":
            continue
        agents += 1
        tt = d.get("tokens_total")
        if tt is None:
            ti, to = d.get("tokens_in"), d.get("tokens_out")
            tt = (ti or 0) + (to or 0) if (ti is not None or to is not None) else None
        if tt is None:
            missing += 1
        else:
            reported += 1
            total += tt
    return total, agents, reported, missing


def quota_percent(gate=None):
    """(percent, headroom, resets_in_min, note). Unreachable is not exhausted."""
    if not os.path.isfile(QUOTA):
        return None, None, None, "quota.py not found at %s" % QUOTA
    try:
        out = subprocess.check_output([sys.executable, QUOTA, "--json"],
                                      stderr=subprocess.STDOUT, timeout=30)
        d = json.loads(out.decode("utf-8"))
    except Exception as e:                                     # noqa: BLE001
        return None, None, None, "quota unreadable (%s)" % type(e).__name__
    if d.get("status") != "OK":
        return None, None, None, "quota not-checked: %s" % d.get("reason", "?")
    sess = d.get("session") or {}
    pct = sess.get("percent")
    if pct is None:
        return None, None, None, "quota returned no session window"
    return float(pct), 100.0 - float(pct), sess.get("minutes"), None


def ledger(base):
    p = os.path.join(base, LEDGER)
    if not os.path.isfile(p):
        return []
    rows = []
    for line in io.open(p, encoding="utf-8", errors="replace"):
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    return rows


def append(base, row):
    if not os.path.isdir(base):
        os.makedirs(base)
    with io.open(os.path.join(base, LEDGER), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def last_step(rows):
    """What the previous boundary observed, so a delta can be taken."""
    return rows[-1] if rows else None


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="budget.py",
        description="Decide at a step boundary whether another step fits.")
    ap.add_argument("--base", required=True, help="the run directory, <dir>/<base>/")
    ap.add_argument("--budget", type=int, required=True,
                    help="hard ceiling in tokens for this run")
    ap.add_argument("--step", default="?", help="name of the step just finished")
    ap.add_argument("--quota-gate", type=float, default=None, metavar="PCT",
                    help="also stop when the session window is at or above PCT")
    ap.add_argument("--safety", type=float, default=SAFETY,
                    help="margin on the last step's cost (default %.1f)" % SAFETY)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if a.budget <= 0:
        print("BAD-BUDGET  --budget must be positive")
        return 2

    spent, agents, reported, missing = read_cost(a.base)
    pct, headroom, resets, note = quota_percent()
    rows = ledger(a.base)
    prev = last_step(rows)

    step_tokens = spent - (prev.get("spent", 0) if prev else 0)
    step_pct = (pct - prev["percent"]) if (prev and prev.get("percent") is not None
                                          and pct is not None) else None

    append(a.base, {"at": time.time(), "step": a.step, "spent": spent,
                    "agents": agents, "percent": pct,
                    "step_tokens": step_tokens, "step_percent": step_pct})

    need = max(step_tokens, 0) * a.safety
    remaining = a.budget - spent
    reasons = []
    if remaining <= 0:
        reasons.append("the ceiling is spent: %s of %s tokens"
                       % (format(spent, ","), format(a.budget, ",")))
    elif need and remaining < need:
        reasons.append("%s tokens left, and a step like the last one needs %s "
                       "(%s x %.1f)"
                       % (format(int(remaining), ","), format(int(need), ","),
                          format(int(step_tokens), ","), a.safety))
    if a.quota_gate is not None and pct is not None and pct >= a.quota_gate:
        reasons.append("session window at %.0f%% (gate %.0f%%)" % (pct, a.quota_gate))
    if step_pct and headroom is not None and headroom < step_pct * a.safety:
        reasons.append("%.0f%% of the window left, and a step like the last one "
                       "took %.0f%%" % (headroom, step_pct))

    verdict = "STOP" if reasons else "GO"
    out = {"verdict": verdict, "step": a.step, "spent": spent, "budget": a.budget,
           "remaining": max(int(remaining), 0), "agents": agents,
           "agents_missing_usage": missing, "step_tokens": int(step_tokens),
           "window_percent": pct, "window_headroom": headroom,
           "resets_in_minutes": resets, "quota_note": note, "reasons": reasons}

    if a.json:
        print(json.dumps(out, indent=2))
    else:
        n = lambda v: format(int(v), ",")
        bar = ""
        if a.budget:
            f = min(int(20.0 * spent / a.budget), 20)
            bar = "  [%s%s]" % ("#" * f, "." * (20 - f))
        print("%s  after %s" % (verdict, a.step))
        print("  budget   %s / %s tokens%s   [measured: cost.jsonl, %d agents]"
              % (n(spent), n(a.budget), bar, agents))
        if step_tokens:
            print("  last step %s tokens%s"
                  % (n(step_tokens),
                     ("  (%.1f%% of the window)" % step_pct) if step_pct else ""))
        if pct is not None:
            print("  window   %.0f%% used · %.0f%% left%s"
                  % (pct, headroom,
                     (" · resets in %.0f min" % resets) if resets else ""))
        elif note:
            print("  window   %s   <- not a stop; the run continues and says so" % note)
        if missing:
            print("  ⚠️ %d agent(s) reported no usage: the spend above is a floor" % missing)
        for r in reasons:
            print("  ⛔ %s" % r)
        if verdict == "STOP":
            print("")
            print("  Everything finished so far is on disk. Nothing in flight is lost.")
            if resets:
                print("  The window resets in %.0f minutes." % resets)
            print("  Resume:  ktkit:spec-recon --resume %s --budget <new>" % a.base)
    return 1 if verdict == "STOP" else 0


if __name__ == "__main__":
    sys.exit(main())
