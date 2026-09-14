#!/usr/bin/env python3
"""How much of the subscription window is left, from the source `/usage` reads.

An earlier round of this work concluded that a run cannot know its remaining
quota, and designed around that: the user would supply a ceiling and the run
would meter itself against the session transcript. That conclusion was wrong,
and the cost of being wrong was a run that spent 15.2M tokens and returned no
verdict at all.

The number is served by the same authenticated endpoint the `/usage` command
reads:

    GET https://api.anthropic.com/api/oauth/usage

It answers with a `limits` array -- one row per active window, each carrying a
`kind`, a `percent`, a `severity` and a `resets_at`. That is the whole gate: a
run about to spend an hour of agents can ask whether the window it would spend
into has room, and when it would refill if not.

    quota.py                 human-readable, one line per window
    quota.py --json          the parsed limits, for a gate to branch on
    quota.py --gate <pct>    exit 1 when the session window is at or above <pct>

Credentials, in order: `CLAUDE_CODE_OAUTH_TOKEN`, then the macOS keychain entry
`Claude Code-credentials`, then `~/.claude/.credentials.json`. The token is read,
used as a bearer header, and never printed -- not in output, not in an error, not
in a debug line.

Unreachable is **not** the same as exhausted. No network, an expired token, an
endpoint that moved: each reports `SKIP` with the reason and exits 0, because a
gate that blocks a run on its own inability to check is worse than no gate. Only
a real percentage at or above the threshold is a stop.

**Percent is the unit, and it stays the unit.** An earlier draft converted the
percentage into tokens so a run could predict whether it would fit -- which meant
measuring how many tokens one percent buys, and that figure is only valid for the
account and tier it was measured on. Signing in with a different account moved
this machine from 94% used to 6% mid-investigation; a stored conversion would
have survived that and been wrong. So there is no conversion, no calibration and
no stored ratio. A run reads the percentage when it needs it, and reads it again
at the next boundary. What the last step actually cost, in percent, is the only
estimate needed for the next one.

The answer is cached for `CACHE_SECONDS`, and that is not an optimisation. The
endpoint rate-limits: probing it four times inside a minute while testing this
script returned `HTTP 429`. A gate consulted at every step boundary would do
exactly that, so a fresh read happens at most once a minute and every check in
between is served from `~/.claude/ktkit-quota-cache.json`. `--fresh` forces a
read; a cached row is labelled with its age so nothing reports a stale figure as
current.

Stdlib only, Python 3.9.
"""
import argparse
import json
import os
import io
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

ENDPOINT = "https://api.anthropic.com/api/oauth/usage"
CACHE = os.path.expanduser("~/.claude/ktkit-quota-cache.json")
CACHE_SECONDS = 60
KEYCHAIN_SERVICE = "Claude Code-credentials"
UA = "claude-cli/2.1.236"
TIMEOUT = 20


def _from_env():
    for var in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_OAUTH_TOKEN"):
        v = os.environ.get(var, "").strip()
        if v:
            return v, var
    return None, None


def _from_keychain():
    if sys.platform != "darwin":
        return None, None
    try:
        out = subprocess.check_output(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            stderr=subprocess.DEVNULL, timeout=15)
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired):
        return None, None
    try:
        d = json.loads(out.decode("utf-8"))
    except ValueError:
        return None, None
    tok = (d.get("claudeAiOauth") or {}).get("accessToken")
    return (tok, "keychain") if tok else (None, None)


def _from_file():
    p = os.path.expanduser("~/.claude/.credentials.json")
    if not os.path.isfile(p):
        return None, None
    try:
        d = json.load(open(p))
    except (ValueError, IOError):
        return None, None
    tok = (d.get("claudeAiOauth") or {}).get("accessToken")
    return (tok, "~/.claude/.credentials.json") if tok else (None, None)


def token():
    for fn in (_from_env, _from_keychain, _from_file):
        tok, src = fn()
        if tok:
            return tok, src
    return None, None


def cached():
    """(payload, age_seconds) or (None, None). A cache miss is not an error."""
    try:
        with io.open(CACHE, encoding="utf-8") as fh:
            d = json.load(fh)
        age = time.time() - float(d["at"])
        if age <= CACHE_SECONDS:
            return d["payload"], age
    except Exception:                                          # noqa: BLE001
        pass
    return None, None


def store(payload):
    """Write the cache. Returns None on success, or why it could not be written.

    A cache that cannot be written is not a failure of the read -- but it is not
    nothing either, and the first version swallowed it. On a machine whose
    sandbox denies writes under `~/.claude/`, every `store` fails, the cache
    stays frozen at whatever it held, and so **every** call goes to the network.
    That is precisely the traffic the cache exists to prevent, and it ends in the
    429 whose fallback is the frozen cache. Silent, self-reinforcing, and
    invisible until somebody reads a percentage from last week.

    So the reason is returned and surfaced as a note. It never blocks.
    """
    try:
        tmp = CACHE + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": time.time(), "payload": payload}))
        os.replace(tmp, CACHE)
        return None
    except Exception as e:                                     # noqa: BLE001
        return "%s: %s" % (type(e).__name__, e)


def expired(payload):
    """True when every dated row in the payload has already reset.

    The principled staleness test, and the only one that survives moving between
    accounts: a window whose `resets_at` has passed describes a window that no
    longer exists, whatever its percentage says. No fixed age threshold is used,
    for the same reason no token conversion is stored -- a number calibrated here
    is wrong on the next tier.

    A payload with no dated row at all is not judged expired; there is nothing to
    judge it by, and guessing would be the error this function prevents.
    """
    dated = [r for r in limits(payload) if r.get("minutes") is not None]
    return bool(dated) and all(r["minutes"] < 0 for r in dated)


def fetch(fresh=False):
    """(payload, source, error, age, cache_note).

    Exactly one of payload/error is set. `cache_note` is why the cache could not
    be written, when it could not; it never makes the read a failure.
    """
    if not fresh:
        hit, age = cached()
        if hit is not None:
            return hit, "cache", None, age, None
    tok, src = token()
    if not tok:
        return None, None, ("no OAuth token found: set CLAUDE_CODE_OAUTH_TOKEN, "
                            "or sign in so the keychain entry exists"), None, None
    req = urllib.request.Request(ENDPOINT, headers={
        "Authorization": "Bearer %s" % tok,
        "anthropic-beta": "oauth-2025-04-20",
        "User-Agent": UA,
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            payload = json.loads(r.read().decode("utf-8"))
        note = store(payload)
        return payload, src, None, 0.0, note
    except urllib.error.HTTPError as e:
        hint = {401: " (token expired? run /login)",
                403: " (token expired? run /login)",
                429: " (the endpoint rate-limits; this is why the answer is "
                     "cached for %ds)" % CACHE_SECONDS}.get(e.code, "")
        # A stale cache beats no answer when the reason is throttling -- but only
        # while it still describes a window that exists. Serving a payload whose
        # windows have all reset is worse than SKIP: SKIP is visibly a non-answer
        # and every caller here is built to continue past one, whereas a stale
        # percentage is indistinguishable from a current one and a gate will
        # branch on it.
        try:
            with io.open(CACHE, encoding="utf-8") as fh:
                d = json.load(fh)
            age = time.time() - float(d["at"])
            if expired(d["payload"]):
                return (None, src,
                        "HTTP %d from the usage endpoint%s, and the cached answer "
                        "is %.0fs old with every window already reset -- refusing "
                        "to report last window's percentage as this one's"
                        % (e.code, hint, age), None, None)
            return d["payload"], "stale cache", None, age, None
        except Exception:                                      # noqa: BLE001
            pass
        return None, src, "HTTP %d from the usage endpoint%s" % (e.code, hint), None, None
    except Exception as e:                                     # noqa: BLE001
        return None, src, "%s: %s" % (type(e).__name__, e), None, None


def minutes_until(iso):
    if not iso:
        return None
    try:
        return (datetime.fromisoformat(iso)
                - datetime.now(timezone.utc)).total_seconds() / 60.0
    except (ValueError, TypeError):
        return None


def limits(payload):
    """Normalise the `limits` array; fall back to the per-window objects."""
    rows = []
    for row in payload.get("limits") or []:
        if not isinstance(row, dict) or row.get("percent") is None:
            continue
        rows.append({"kind": row.get("kind") or row.get("group") or "?",
                     "percent": float(row["percent"]),
                     "severity": row.get("severity") or "unknown",
                     "resets_at": row.get("resets_at"),
                     "minutes": minutes_until(row.get("resets_at")),
                     "active": bool(row.get("is_active"))})
    if rows:
        return rows
    for key in ("five_hour", "seven_day"):
        w = payload.get(key)
        if isinstance(w, dict) and w.get("utilization") is not None:
            rows.append({"kind": key, "percent": float(w["utilization"]),
                         "severity": "unknown", "resets_at": w.get("resets_at"),
                         "minutes": minutes_until(w.get("resets_at")),
                         "active": True})
    return rows


def session_row(rows):
    """The window a run about to start would actually spend into."""
    for r in rows:
        if r["kind"] in ("session", "five_hour"):
            return r
    return rows[0] if rows else None


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="quota.py",
        description="Report subscription window utilisation from the usage endpoint.")
    ap.add_argument("--json", action="store_true",
                    help="machine-readable, for a gate to branch on")
    ap.add_argument("--gate", type=float, default=None, metavar="PCT",
                    help="exit 1 when the session window is at or above PCT")
    ap.add_argument("--fresh", action="store_true",
                    help="bypass the cache; the endpoint rate-limits, so use sparingly")
    a = ap.parse_args(argv)

    payload, src, err, age, cache_note = fetch(fresh=a.fresh)
    if err:
        out = {"status": "SKIP", "reason": err, "credential_source": src}
        print(json.dumps(out, indent=2) if a.json
              else "SKIP quota  %s\n     -> unreachable is not exhausted; "
                   "the run continues and says so" % err)
        return 0

    rows = limits(payload)
    if not rows:
        print(json.dumps({"status": "SKIP", "reason": "no limit rows"}, indent=2)
              if a.json else "SKIP quota  the endpoint returned no limit rows")
        return 0

    sess = session_row(rows)
    stale = src == "stale cache"
    if a.json:
        out = {"status": "STALE" if stale else "OK", "credential_source": src,
               "age_seconds": round(age or 0.0, 1),
               "limits": rows, "session": sess}
        if cache_note:
            out["cache_note"] = cache_note
        print(json.dumps(out, indent=2))
    else:
        stamp = "" if not age else "  · %.0fs old" % age
        print("quota (source: the endpoint /usage reads · %s%s)" % (src, stamp))
        for r in rows:
            when = ("resets in %.0f min" % r["minutes"]) if r["minutes"] is not None \
                else "no reset time"
            bar = "#" * int(r["percent"] / 5) + "." * (20 - int(r["percent"] / 5))
            print("  %-12s %5.1f%%  [%s]  %-18s %s%s"
                  % (r["kind"], r["percent"], bar, when, r["severity"],
                     "" if r["active"] else "  (inactive)"))
        if sess:
            print("  headroom in the window a run spends into: %.1f%%"
                  % (100.0 - sess["percent"]))
        if stale:
            print("  ⚠ STALE — the endpoint refused and this is the last answer it "
                  "gave. Treat every figure above as a lower bound.")
        if cache_note:
            print("  ⚠ the cache could not be written (%s); every call will go to "
                  "the network, which is what the endpoint rate-limits" % cache_note)

    if a.gate is not None and sess and sess["percent"] >= a.gate:
        msg = ("QUOTA-GATE  session window at %.1f%% (>= %.1f%%)"
               % (sess["percent"], a.gate))
        if sess["minutes"] is not None:
            msg += " · resets in %.0f min" % sess["minutes"]
        print(msg)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
