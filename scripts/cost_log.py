#!/usr/bin/env python3
"""Persist what a run cost, per agent, in the run's own directory.

The spend was visible and then gone. `cost-model.md` requires one line of chat
after every wave -- `Wave 2: 5 agents · ~340k tokens · 11m · running ~1.2M` --
and that was the whole record. Scroll past it, or compact the conversation, and
the only numbers describing a multi-million-token run are the ones somebody
happened to remember. The report says what was found; nothing said what it cost.

So cost becomes an artifact like every other measurement here, and it obeys the
same rules the evidence files do:

  * append-only. `cost.jsonl` gains a line per agent and no line is ever
    rewritten -- a correction is a new row carrying its reason, because what a
    wave cost before it was re-run is part of the record;
  * a number is `[measured]` or it is absent. An agent that reported no usage is
    written down as having reported none. It is never filled in from an average,
    and the totals say how many agents are missing from them;
  * the lead's own turns are not measurable from inside the run, and the
    rendered file says so rather than implying the total is complete.

    cost_log.py wave   --base <dir> --wave N --row <csv> [--row <csv>]...
    cost_log.py append --base <dir> --wave N --agent <name> [numbers]
    cost_log.py render --base <dir>          -> rewrites <dir>/cost.md
    cost_log.py total  --base <dir>          -> one line, for the chat

**One call per wave, not per agent.** `wave` is the one the skill uses. A wave can
be forty-nine agents, and forty-nine shell calls to write down what a run cost is
itself a cost worth avoiding: measured against a per-agent call it is roughly a
quarter of the tokens and a fiftieth of the round trips. Tracking that eats a
noticeable fraction of what it tracks is not worth having.

Each `--row` is compact CSV, empty field meaning *not reported*:

    agent,toolset,tokens_in,tokens_out,tool_calls,seconds[,note]
    probe-code,A,148200,3100,14,96
    probe-vcs,B,,,,,returned no usage field

`append` takes one agent with named flags and accepts `--usage-json`, which
stores the harness usage object verbatim so a field this script does not know
about is still on disk. It is for a single late-returning agent or for debugging,
not for the hot path.

Every flag, so that `--help` names them all and a wiring check can see them:
`--base` `--wave` `--row` `--agent` `--toolset` `--tokens-in` `--tokens-out`
`--tokens-total` `--tool-calls` `--seconds` `--usage-json` `--note` `--reason`.

Stdlib only, Python 3.9.
"""
import argparse
import datetime
import io
import json
import os
import sys

LOG = "cost.jsonl"
RENDER = "cost.md"
KNOWN_SETS = {"A": 6619, "B": 11353, "C": 6875}


def now():
    return datetime.datetime.now().replace(microsecond=0).isoformat()


def log_path(base):
    return os.path.join(base, LOG)


def read_rows(base):
    p = log_path(base)
    if not os.path.isfile(p):
        return []
    rows = []
    for line in io.open(p, encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except ValueError:
                rows.append({"kind": "unparseable", "raw": line[:200]})
    return rows


def append_row(base, row):
    if not os.path.isdir(base):
        os.makedirs(base)
    with io.open(log_path(base), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def num(v):
    return v if isinstance(v, int) else None


def totals(rows):
    """Sum only what was reported, and count what was not."""
    agents = [r for r in rows if r.get("kind") == "agent"]
    t = {"agents": len(agents), "reported": 0, "missing": 0,
         "tokens_in": 0, "tokens_out": 0, "tokens_total": 0,
         "tool_calls": 0, "seconds": 0, "base_floor": 0}
    for r in agents:
        ti, to = num(r.get("tokens_in")), num(r.get("tokens_out"))
        tt = num(r.get("tokens_total"))
        if tt is None and (ti is not None or to is not None):
            tt = (ti or 0) + (to or 0)
        if tt is None:
            t["missing"] += 1
        else:
            t["reported"] += 1
            t["tokens_total"] += tt
            t["tokens_in"] += ti or 0
            t["tokens_out"] += to or 0
        t["tool_calls"] += num(r.get("tool_calls")) or 0
        t["seconds"] += num(r.get("seconds")) or 0
        t["base_floor"] += KNOWN_SETS.get(r.get("toolset") or "", 0)
    return t


def thousands(n):
    return "{:,}".format(n)


def render(base):
    rows = read_rows(base)
    agents = [r for r in rows if r.get("kind") == "agent"]
    t = totals(rows)
    waves = sorted(set(r.get("wave") for r in agents if r.get("wave") is not None))

    out = ["# Cost of this run", "",
           "Appended by `scripts/cost_log.py` as each wave returns. Source of every",
           "number: `cost.jsonl`, beside this file. A number here was reported by the",
           "agent that spent it, or it is absent -- nothing on this page is an average.",
           ""]

    if not agents:
        out += ["No agent has reported yet.", ""]
        io.open(os.path.join(base, RENDER), "w", encoding="utf-8").write("\n".join(out))
        return "\n".join(out)

    out += ["## Total", "",
            "| | Value | Label |",
            "| - | ----: | ----- |",
            "| Agents spawned | %d | [measured] |" % t["agents"],
            "| Agents that reported usage | %d of %d | [measured] |"
            % (t["reported"], t["agents"]),
            "| Tokens (in) | %s | [measured] |" % thousands(t["tokens_in"]),
            "| Tokens (out) | %s | [measured] |" % thousands(t["tokens_out"]),
            "| **Tokens (total)** | **%s** | [measured] |" % thousands(t["tokens_total"]),
            "| Tool calls | %s | [measured] |" % thousands(t["tool_calls"]),
            "| Agent wall time | %d s (%.1f min) | [measured] |"
            % (t["seconds"], t["seconds"] / 60.0),
            "| Base floor from tool sets | %s | [derived] |" % thousands(t["base_floor"]),
            ""]

    if t["missing"]:
        out += ["⛔ **%d of %d agents reported no usage.** The total above excludes them "
                "and is therefore a floor, not the bill." % (t["missing"], t["agents"]), ""]

    out += ["⛔ **The lead's own turns are not in this file.** An agent cannot measure the "
            "session that dispatched it, so the true cost of the run is this total plus the "
            "lead's context on every turn. Read the harness's own accounting for that.", "",
            "## Per wave", "",
            "| Wave | Agents | Tokens | Tool calls | Wall time | Running total |",
            "| ---- | -----: | -----: | ---------: | --------: | ------------: |"]
    running = 0
    for w in waves:
        sub = [r for r in agents if r.get("wave") == w]
        st = totals([dict(r, kind="agent") for r in sub])
        running += st["tokens_total"]
        out.append("| %s | %d | %s | %s | %d s | %s |"
                   % (w, st["agents"], thousands(st["tokens_total"]),
                      thousands(st["tool_calls"]), st["seconds"], thousands(running)))

    out += ["", "## Per agent", "",
            "| # | Wave | Agent | Set | Tokens in | out | total | Calls | s | Note |",
            "| -: | ---- | ----- | --- | --------: | --: | ----: | ----: | -: | ---- |"]
    for i, r in enumerate(agents, 1):
        ti, to = num(r.get("tokens_in")), num(r.get("tokens_out"))
        tt = num(r.get("tokens_total"))
        if tt is None and (ti is not None or to is not None):
            tt = (ti or 0) + (to or 0)
        cell = lambda v: thousands(v) if v is not None else "**not reported**"
        out.append("| %d | %s | `%s` | %s | %s | %s | %s | %s | %s | %s |"
                   % (i, r.get("wave", "-"), r.get("agent", "?"),
                      r.get("toolset") or "-", cell(ti), cell(to), cell(tt),
                      cell(num(r.get("tool_calls"))), cell(num(r.get("seconds"))),
                      (r.get("note") or "").replace("|", "/")))

    corrections = [r for r in rows if r.get("kind") == "correction"]
    if corrections:
        out += ["", "## Corrections", "",
                "| When | Why |", "| ---- | --- |"]
        for c in corrections:
            out.append("| %s | %s |" % (c.get("at", "?"),
                                        (c.get("reason") or "").replace("|", "/")))

    out.append("")
    text = "\n".join(out)
    io.open(os.path.join(base, RENDER), "w", encoding="utf-8").write(text)
    return text


def one_line(base):
    rows = read_rows(base)
    t = totals(rows)
    agents = [r for r in rows if r.get("kind") == "agent"]
    waves = sorted(set(r.get("wave") for r in agents if r.get("wave") is not None))
    last = waves[-1] if waves else "-"
    sub = totals([r for r in agents if r.get("wave") == last])
    miss = "" if not t["missing"] else " · %d agents reported nothing" % t["missing"]
    return ("Wave %s: %d agents · %s tokens · %.0fm · running %s%s"
            % (last, sub["agents"], thousands(sub["tokens_total"]),
               sub["seconds"] / 60.0, thousands(t["tokens_total"]), miss))


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="cost_log.py",
        description="Record and render what a run cost.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""subcommands and their flags
  wave    --base --wave --row            one call per wave; this is the hot path
  append  --base --wave --agent --toolset --tokens-in --tokens-out
          --tokens-total --tool-calls --seconds --usage-json --note
  correct --base --reason                append a correction, never edit a row
  render  --base                         rewrite cost.md from cost.jsonl
  total   --base                         print the one-line running total

--row is agent,toolset,tokens_in,tokens_out,tool_calls,seconds[,note]
with an empty field meaning the agent did not report that number.""")
    sub = ap.add_subparsers(dest="cmd")

    a = sub.add_parser("append", help="record one agent's usage")
    a.add_argument("--base", required=True, help="the run directory, <dir>/<base>/")
    a.add_argument("--wave", required=True, help="wave label, e.g. 1")
    a.add_argument("--agent", required=True, help="the agent name that was dispatched")
    a.add_argument("--toolset", choices=sorted(KNOWN_SETS), default=None,
                   help="A, B or C -- only for the derived base floor")
    a.add_argument("--tokens-in", type=int, default=None)
    a.add_argument("--tokens-out", type=int, default=None)
    a.add_argument("--tokens-total", type=int, default=None)
    a.add_argument("--tool-calls", type=int, default=None)
    a.add_argument("--seconds", type=int, default=None)
    a.add_argument("--usage-json", default=None,
                   help="the harness usage object, stored verbatim")
    a.add_argument("--note", default=None)

    w = sub.add_parser("wave", help="record a whole wave in one call (the hot path)")
    w.add_argument("--base", required=True, help="the run directory, <dir>/<base>/")
    w.add_argument("--wave", required=True, help="wave label, e.g. 1")
    w.add_argument("--row", action="append", default=[], required=True,
                   help="agent,toolset,tokens_in,tokens_out,tool_calls,seconds[,note]"
                        " -- empty field means not reported")

    c = sub.add_parser("correct", help="append a correction, never edit a row")
    c.add_argument("--base", required=True)
    c.add_argument("--reason", required=True)

    for name in ("render", "total"):
        s = sub.add_parser(name, help="rewrite cost.md" if name == "render"
                           else "print the one-line running total")
        s.add_argument("--base", required=True)

    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_help()
        return 1

    if args.cmd == "wave":
        stamp = now()
        for raw in args.row:
            parts = [f.strip() for f in raw.split(",")]
            parts += [""] * (7 - len(parts))
            agent, toolset = parts[0], (parts[1] or None)
            if not agent:
                print("ROW-REJECTED  no agent name: %r" % raw)
                return 2
            if toolset and toolset not in KNOWN_SETS:
                print("ROW-REJECTED  unknown tool set %r in %r" % (toolset, raw))
                return 2
            def maybe(v):
                if v == "":
                    return None
                try:
                    return int(v)
                except ValueError:
                    return None
            append_row(args.base, {
                "kind": "agent", "at": stamp, "wave": args.wave, "agent": agent,
                "toolset": toolset, "tokens_in": maybe(parts[2]),
                "tokens_out": maybe(parts[3]), "tokens_total": None,
                "tool_calls": maybe(parts[4]), "seconds": maybe(parts[5]),
                "usage": None, "note": parts[6] or None})
        render(args.base)
        print(one_line(args.base))
        return 0

    if args.cmd == "append":
        usage = None
        if args.usage_json:
            try:
                usage = json.loads(args.usage_json)
            except ValueError:
                usage = {"unparsed": args.usage_json[:500]}
        append_row(args.base, {
            "kind": "agent", "at": now(), "wave": args.wave, "agent": args.agent,
            "toolset": args.toolset, "tokens_in": args.tokens_in,
            "tokens_out": args.tokens_out, "tokens_total": args.tokens_total,
            "tool_calls": args.tool_calls, "seconds": args.seconds,
            "usage": usage, "note": args.note})
        render(args.base)
        print(one_line(args.base))
        return 0

    if args.cmd == "correct":
        append_row(args.base, {"kind": "correction", "at": now(),
                               "reason": args.reason})
        render(args.base)
        return 0

    if args.cmd == "render":
        print(render(args.base))
        return 0

    print(one_line(args.base))
    return 0


if __name__ == "__main__":
    sys.exit(main())
