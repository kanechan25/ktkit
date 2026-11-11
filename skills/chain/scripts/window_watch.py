#!/usr/bin/env python3
"""Watch the subscription windows for a chain run, and call the wind-down at the threshold.

The gate this replaces stopped on a forecast. It took what phases A-C had cost,
assumed phase D would cost as much, converted the window's remaining percentage
into tokens at the run's own rate, and refused to start phase D -- with 44% of
the session still unspent. The window was never close to empty; the arithmetic
only said it might become so.

This measures instead. Run in the background for the life of a chain run, it
reads `quota.py` every `--interval` seconds and looks at every session and
weekly window the endpoint reports. While all of them are under `--wind-down`
percent it does nothing. The first time any one reaches it, it trips the run's
checkpoint into `wind-down` and exits -- and the exit is the signal: a
background command that ends wakes the lead.

    window_watch.py --base <chain-dir> [--wind-down 96] [--interval 100] [--once]
    window_watch.py --base <chain-dir> --await-reset [--wind-down 96] [--interval 100]

`--await-reset` is the other half, and it is what makes a pause automatic rather
than a hand-over. Started in the background once the run has paused, it sleeps
until the window that tripped it resets, then reads again: once every session
and weekly window is back under the threshold it sets the checkpoint to
`running` and exits -- and that exit wakes the lead, which continues the run as
`--resume`. A window still over the threshold after its reset time (a weekly
one, say, while the session refilled) is simply waited for in turn. Nothing is
forecast here either: it resumes on a reading, never on the clock alone.

The last few percent are the room the run uses to finish what is in flight and
write its checkpoint. That margin is a setting, not a measurement, so the
percentage at the trip and at the pause are both recorded in the checkpoint: if
a wind-down ever needs more than it was given, the file says by how much.

`--interval` defaults to 100 seconds. `quota.py` caches its answer for 60, and
the endpoint returned HTTP 429 when it was asked four times inside a minute, so
anything much faster than the cache only reads the cache.

Unreadable is not exhausted: a `SKIP` from `quota.py` is printed and the watch
goes on. The watcher also exits, without tripping anything, once the checkpoint
says the run is `paused` or `complete` -- nobody is left to wake.

Exit status
    0  tripped, resumed, or the run is no longer in a state to watch
    2  unusable arguments

Stdlib only, Python 3.9.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import checkpoint                                              # noqa: E402

PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(
    os.path.dirname(os.path.dirname(HERE)))
QUOTA = os.path.join(PLUGIN_ROOT, "scripts", "quota.py")
WIND_DOWN = 96.0
INTERVAL = 100


def watched(rows):
    """The windows a run can run out of: the session and every weekly one."""
    return [r for r in rows
            if r.get("kind") in ("session", "five_hour", "seven_day")
            or str(r.get("kind", "")).startswith("weekly")]


def read_windows():
    """([rows], note). An empty list with a note is a SKIP, never a stop."""
    try:
        out = subprocess.check_output([sys.executable, QUOTA, "--json"],
                                      stderr=subprocess.STDOUT, timeout=60)
        d = json.loads(out.decode("utf-8"))
    except Exception as e:                                     # noqa: BLE001
        return [], "quota unreadable (%s)" % type(e).__name__
    if d.get("status") not in ("OK", "STALE"):
        return [], "quota not-checked: %s" % d.get("reason", "?")
    return watched(d.get("limits") or []), None


def local_reset(iso):
    if not iso:
        return "no reset time"
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return iso


def poll(base, threshold):
    """'tripped', 'gone' or 'watching', after one reading."""
    head, _ = checkpoint.load(base)
    if head["status"] in ("paused", "complete"):
        print("%s  run is %s; nothing to watch" % (checkpoint.stamp(), head["status"]), flush=True)
        return "gone"
    rows, note = read_windows()
    if note:
        print("%s  SKIP %s -- unreadable is not exhausted" % (checkpoint.stamp(), note), flush=True)
        return "watching"
    print("%s  %s" % (checkpoint.stamp(), "  ".join(
        "%s %.1f%%" % (r["kind"], r["percent"]) for r in rows)), flush=True)
    over = [r for r in rows if r["percent"] >= threshold]
    if not over:
        return "watching"
    r = max(over, key=lambda x: x["percent"])
    reason = "%s at %.1f%% (gate %.0f%%, resets %s)" % (
        r["kind"], r["percent"], threshold, local_reset(r.get("resets_at")))
    checkpoint.main(["trip", "--base", base, "--reason", reason])
    return "tripped"


def seconds_until(iso):
    try:
        return (datetime.fromisoformat(iso)
                - datetime.now(timezone.utc)).total_seconds()
    except (ValueError, TypeError):
        return None


def poll_reset(base, threshold, interval):
    """('resumed' | 'gone' | 'waiting', seconds to sleep), after one reading."""
    head, _ = checkpoint.load(base)
    if head["status"] != "paused":
        print("%s  run is %s; nothing to await" % (checkpoint.stamp(), head["status"]),
              flush=True)
        return "gone", 0
    rows, note = read_windows()
    if note:
        # Unreadable is not refilled either: resuming blind could trip again at once.
        print("%s  SKIP %s -- still waiting" % (checkpoint.stamp(), note), flush=True)
        return "waiting", interval
    print("%s  %s" % (checkpoint.stamp(), "  ".join(
        "%s %.1f%%" % (r["kind"], r["percent"]) for r in rows)), flush=True)
    over = [r for r in rows if r["percent"] >= threshold]
    if not over:
        reason = "every window under %.0f%%: %s" % (threshold, ", ".join(
            "%s %.1f%%" % (r["kind"], r["percent"]) for r in rows))
        checkpoint.main(["resume", "--base", base, "--reason", reason])
        return "resumed", 0
    waits = [seconds_until(r.get("resets_at")) for r in over]
    waits = [w for w in waits if w is not None]
    # Sleep to the latest reset among the full windows, plus a minute for the
    # endpoint to catch up -- but never less than one interval.
    return "waiting", max(interval, (max(waits) + 60) if waits else interval)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="window_watch.py",
                                 description="Trip a chain run's wind-down at a window threshold.")
    ap.add_argument("--base", required=True, help="the chain run directory")
    ap.add_argument("--wind-down", type=float, default=WIND_DOWN, metavar="PCT",
                    help="trip when any session or weekly window reaches PCT (default 96)")
    ap.add_argument("--interval", type=int, default=INTERVAL,
                    help="seconds between readings (default 100)")
    ap.add_argument("--once", action="store_true", help="one reading, then exit")
    ap.add_argument("--await-reset", action="store_true",
                    help="on a paused run: wait for the windows to refill, then resume it")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.base):
        print("BAD-BASE  %s is not a directory" % a.base)
        return 2
    if not 0 < a.wind_down <= 100 or a.interval <= 0:
        print("BAD-ARGS  --wind-down must be in (0, 100] and --interval positive")
        return 2
    while a.await_reset:
        state, wait = poll_reset(a.base, a.wind_down, a.interval)
        if state != "waiting" or a.once:
            return 0
        print("%s  next reading in %.0f min" % (checkpoint.stamp(), wait / 60.0), flush=True)
        time.sleep(wait)
    while True:
        state = poll(a.base, a.wind_down)
        if state != "watching" or a.once:
            return 0
        time.sleep(a.interval)


if __name__ == "__main__":
    sys.exit(main())
