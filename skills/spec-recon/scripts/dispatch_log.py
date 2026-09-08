#!/usr/bin/env python3
"""Record what an agent was *sent*, because that is the one term nobody measured.

A run of 24 agents cost 5,345,133 tokens. Wave 1 handed its agents 852,260 bytes
of document -- about 213,000 tokens of content, **9.7%** of what the wave spent.
The other 90% went somewhere, and three candidate explanations were fitted
against the 24 agents and all three failed:

    output tokens written   R2 = 0.145   (and the slope came out negative)
    tool calls made         R2 = 0.421
    output x calls          R2 = 0.025

Every model left a fixed 166,000-262,000 per agent unexplained. The clearest case
is `arbiter-B-bugs-accept`: 398,092 tokens spent, 2,286 tokens written back --
a ratio of 174 to 1. Whatever it paid for, it was not reading and it was not
writing.

One term was never measured, and it is the only one left: **the prompt the lead
sends**. It is composed in the dispatch call and never written anywhere, so its
size is invisible -- and a subagent's prompt is re-sent on every internal turn it
takes, which makes an invisible term the one most likely to dominate.

So this script makes it visible. The lead writes each agent's payload here
*before* dispatching, and the file is both the measurement and the artifact:

    dispatch_log.py --base <dir> --agent <name> --wave N --payload-file <path>
    dispatch_log.py --base <dir> --agent <name> --wave N --payload-stdin
    dispatch_log.py --base <dir> --report          -> rewrite dispatch.md

⭐ **This does not optimise anything.** It measures. The next run's `dispatch.md`
answers whether the payload is the missing term, and only then is there a
defensible way to cut it -- a cut aimed at a term nobody has sized is how the
tool-call cap got proposed on the strength of a quadratic the data later refused.

Stdlib only, Python 3.9.
"""
import argparse
import io
import json
import os
import sys
import time

LEDGER = "dispatch.jsonl"
RENDER = "dispatch.md"
CHARS_PER_TOKEN = 4.0


def append(base, row):
    if not os.path.isdir(base):
        os.makedirs(base)
    with io.open(os.path.join(base, LEDGER), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def rows(base):
    p = os.path.join(base, LEDGER)
    if not os.path.isfile(p):
        return []
    out = []
    for line in io.open(p, encoding="utf-8", errors="replace"):
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def costs(base):
    """What each agent actually spent, from cost.jsonl, so the two can be paired."""
    p = os.path.join(base, "cost.jsonl")
    if not os.path.isfile(p):
        return {}
    out = {}
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
        tt = d.get("tokens_total")
        if tt is None:
            ti, to = d.get("tokens_in"), d.get("tokens_out")
            tt = (ti or 0) + (to or 0) if (ti is not None or to is not None) else None
        out[d.get("agent")] = {"tokens": tt, "calls": d.get("tool_calls")}
    return out


def render(base):
    rs = rows(base)
    cs = costs(base)
    n = lambda v: format(int(v), ",")
    out = ["# What each agent was sent", "",
           "Payload sizes are `[measured]` in characters; the token column is `[derived]`",
           "at %g characters per token. Recorded by `scripts/dispatch_log.py` before each",
           "dispatch, because the prompt a subagent receives is composed in the call and",
           "written nowhere -- and it is re-sent on every internal turn the agent takes.",
           "", "This page measures. It concludes nothing.", ""]
    out[3] = out[3] % CHARS_PER_TOKEN
    if not rs:
        out.append("Nothing recorded yet.")
        io.open(os.path.join(base, RENDER), "w", encoding="utf-8").write("\n".join(out))
        return "\n".join(out)

    tot_chars = sum(r.get("chars") or 0 for r in rs)
    out += ["## Total", "",
            "| | Value | Label |", "| - | ----: | ----- |",
            "| Payloads recorded | %d | [measured] |" % len(rs),
            "| Payload characters | %s | [measured] |" % n(tot_chars),
            "| Payload tokens | %s | [derived] |" % n(tot_chars / CHARS_PER_TOKEN),
            ""]

    paired = [r for r in rs if cs.get(r["agent"], {}).get("calls")]
    if paired:
        out += ["## Payload against spend", "",
                "⭐ The column that matters is the last one: a subagent's prompt is re-sent on",
                "every internal turn, so `payload x calls` is the shape to compare against what",
                "the agent actually spent. If that column tracks the spend, the payload is the",
                "term that was missing.", "",
                "| Agent | Payload tok | Calls | Spent | payload x calls | share |",
                "| ----- | ----------: | ----: | ----: | --------------: | ----: |"]
        for r in sorted(paired, key=lambda x: -(x.get("chars") or 0)):
            pt = (r.get("chars") or 0) / CHARS_PER_TOKEN
            c = cs[r["agent"]]["calls"]
            spent = cs[r["agent"]]["tokens"]
            prod = pt * c
            share = ("%.0f%%" % (100.0 * prod / spent)) if spent else "-"
            out.append("| `%s` | %s | %d | %s | %s | %s |"
                       % (r["agent"], n(pt), c,
                          n(spent) if spent else "not reported", n(prod), share))
        out.append("")

    out += ["## Per payload", "",
            "| Wave | Agent | Characters | Tokens | Recorded |",
            "| ---- | ----- | ---------: | -----: | -------- |"]
    for r in rs:
        out.append("| %s | `%s` | %s | %s | %s |"
                   % (r.get("wave", "-"), r.get("agent", "?"),
                      n(r.get("chars") or 0),
                      n((r.get("chars") or 0) / CHARS_PER_TOKEN),
                      r.get("at_iso", "")))
    out.append("")
    text = "\n".join(out)
    io.open(os.path.join(base, RENDER), "w", encoding="utf-8").write(text)
    return text


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="dispatch_log.py",
        description="Measure the prompt each agent is sent, before it is sent.")
    ap.add_argument("--base", required=True, help="the run directory")
    ap.add_argument("--agent", default=None, help="the agent about to be dispatched")
    ap.add_argument("--wave", default=None, help="wave label")
    ap.add_argument("--payload-file", default=None,
                    help="a file holding the payload as it will be sent")
    ap.add_argument("--payload-stdin", action="store_true",
                    help="read the payload from stdin")
    ap.add_argument("--payload-chars", type=int, default=None,
                    help="the length, when the payload itself is not available")
    ap.add_argument("--keep", action="store_true",
                    help="store the payload text alongside its size")
    ap.add_argument("--report", action="store_true", help="rewrite dispatch.md")
    a = ap.parse_args(argv)

    if a.report and not a.agent:
        print(render(a.base))
        return 0
    if not a.agent:
        print("NO-AGENT  --agent is required unless --report is given alone")
        return 2

    text = None
    if a.payload_stdin:
        text = sys.stdin.read()
    elif a.payload_file:
        if not os.path.isfile(a.payload_file):
            print("NO-PAYLOAD  %s" % a.payload_file)
            return 2
        text = io.open(a.payload_file, encoding="utf-8", errors="replace").read()

    if text is None and a.payload_chars is None:
        print("NO-SIZE  give --payload-file, --payload-stdin, or --payload-chars")
        return 2

    chars = len(text) if text is not None else a.payload_chars
    row = {"at": time.time(),
           "at_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "wave": a.wave, "agent": a.agent, "chars": chars}
    if a.keep and text is not None:
        row["payload"] = text
    append(a.base, row)
    render(a.base)
    print("DISPATCH  %s · wave %s · %s chars (~%s tokens [derived])"
          % (a.agent, a.wave, format(chars, ","),
             format(int(chars / CHARS_PER_TOKEN), ",")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
