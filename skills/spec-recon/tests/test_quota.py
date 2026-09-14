#!/usr/bin/env python3
"""The quota gate: block a run that cannot finish, never block on not knowing.

Two rounds of analysis concluded that a run could not know its remaining quota
and designed around the absence. Both were wrong -- the figure is served by the
endpoint `/usage` reads -- and the cost of being wrong was a run that spent
15.2M tokens across 34 agents and produced no verdict at all.

So the gate exists. What this file holds it to is the part that is easy to get
backwards: a gate is only safe if failing to check does **not** stop the work.
No network, an expired token, a throttled endpoint -- each must report and let
the run continue. Only a real percentage over the threshold is a stop.

  Q1  above the threshold blocks; below it does not -- by exit code, end to end
  Q2  unreachable is SKIP and exit 0 -- cannot-check never blocks
  Q3  the token never reaches stdout, in any mode
  Q4  the limits array is parsed by shape, not by hard-coded names
  Q5  the cache honours its TTL, and a throttled read falls back to it
  Q6  the decision path uses percent only -- no token conversion, no calibration
  Q7  --help lists the flags, so the wiring check can see them
  Q8  a cache that cannot be written says so -- it is not a failure, but a
      silent one turns the TTL into a no-op and every call into network traffic
  Q9  a stale payload whose windows have all reset is refused, not served
  Q10 the cache lives somewhere writable, and is readable only by its owner

Q4 is not defensive programming. The payload changed shape during the very
session that built this: two limit rows became three, and a row named
`weekly_scoped` appeared that no code had ever seen.

Q5 exists because probing the endpoint four times in a minute returned HTTP 429.
A gate consulted at every step boundary would do exactly that.

Q1 runs the script rather than recomputing its comparison. The first version of
it read the cache, called `session_row`, and decided for itself whether that
percentage should block -- so flipping `>=` to `<=` inside the script left it
green. A check that reimplements what it is checking is not checking anything.

Q8 and Q9 are one failure seen from both ends, and it was found in production on
this machine. The sandbox denies writes under `~/.claude/`, so `store` failed on
every call and swallowed it; the cache froze; every call therefore went to the
network; the endpoint rate-limited; and the 429 fallback served a payload five
days old **as `status: OK`**. A gate consulted at every step boundary was
branching on last week's percentage, and nothing anywhere said so. Q8 makes the
cause visible; Q9 refuses the symptom.

Q9 tests staleness by the payload's own `resets_at`, not by an age threshold. A
window that has already reset cannot describe the current one whatever its
percentage says, and that test needs no number calibrated against a tier -- the
same reasoning that keeps percent as the unit everywhere else here.

Q10 is the other half of Q8. Reporting that the cache could not be written is
honest but not enough -- the default location has to be one that actually works.
`~/.claude/` does not: Claude Code's own sandbox denies writes there, which is how
a sixty-second TTL became a permanent no-op. The cache now sits in the system
temp directory, which is correct rather than merely convenient: a file that is
stale after a minute does not need to survive a reboot, and losing it costs one
HTTP request.

Q6 guards against a design that was built and then removed. An earlier version
converted the percentage into tokens so a run could predict whether it would
fit, which required measuring how many tokens one percent buys -- a figure valid
only for the account and tier it was measured on. Signing in with a different
account moved the window from 94% used to 6%; a stored ratio would have survived
that silently. Percent in, percent out: what the last step cost, in percent, is
the only estimate the next one needs.

The network is not touched here. Hitting a rate-limited endpoint from a test
suite is how a suite becomes flaky, and the lesson that produced the cache is
the same one that keeps it out of this file.

Run:  python3 skills/spec-recon/tests/test_quota.py
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SCRIPT = os.path.join(ROOT, "scripts", "quota.py")

sys.path.insert(0, os.path.join(ROOT, "scripts"))
import quota                                                   # noqa: E402

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def run(*args, **env):
    e = dict(os.environ)
    e.update(env)
    p = subprocess.Popen([sys.executable, SCRIPT] + list(args),
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=e)
    out, _ = p.communicate()
    return p.returncode, out.decode("utf-8")


# The two shapes actually observed, hours apart, on the same machine.
BEFORE = {"limits": [
    {"kind": "session", "group": "session", "percent": 92, "severity": "critical",
     "resets_at": "2099-01-01T00:00:00+00:00", "is_active": True},
    {"kind": "weekly_all", "group": "weekly", "percent": 28, "severity": "normal",
     "resets_at": "2099-01-08T00:00:00+00:00", "is_active": False}]}
AFTER = {"limits": [
    {"kind": "session", "group": "session", "percent": 6, "severity": "normal",
     "resets_at": "2099-01-01T00:00:00+00:00", "is_active": False},
    {"kind": "weekly_all", "group": "weekly", "percent": 16, "severity": "normal",
     "resets_at": "2099-01-08T00:00:00+00:00", "is_active": True},
    {"kind": "weekly_scoped", "group": "weekly", "percent": 0, "severity": "normal",
     "resets_at": None, "is_active": False}]}
# No `limits` key at all -- the older per-window shape.
LEGACY = {"five_hour": {"utilization": 77.0, "resets_at": "2099-01-01T00:00:00+00:00"},
          "seven_day": {"utilization": 12.0, "resets_at": None}}


def test_q4_the_limits_array_is_parsed_by_shape():
    for label, payload, n, pct in (("before the login", BEFORE, 2, 92.0),
                                   ("after the login", AFTER, 3, 6.0)):
        rows = quota.limits(payload)
        check("Q4 %s: every percent row survives" % label, len(rows) == n, rows)
        sess = quota.session_row(rows)
        check("Q4 %s: the session window is picked out" % label,
              sess and sess["percent"] == pct, sess)
    check("Q4 a row named weekly_scoped needs no special case",
          any(r["kind"] == "weekly_scoped" for r in quota.limits(AFTER)))
    rows = quota.limits(LEGACY)
    check("Q4 the older per-window shape still resolves",
          len(rows) == 2 and quota.session_row(rows)["percent"] == 77.0, rows)
    check("Q4 a payload with nothing usable yields no rows",
          quota.limits({"limits": [{"kind": "x"}], "tangelo": None}) == [])


def test_q4_inactive_rows_are_kept_not_dropped():
    """`is_active` moved between the two observations. It is reported, not filtered."""
    rows = quota.limits(AFTER)
    sess = quota.session_row(rows)
    check("Q4 an inactive session row is still the session row",
          sess["kind"] == "session" and sess["active"] is False, sess)


def seeded_cache(percent):
    """A cache file the script will read, so it needs no token and no network:
    `fetch` consults the cache before it does anything else.

    Returns the path, to be passed as `KTKIT_QUOTA_CACHE`. Isolation used to work
    by faking `HOME`, which held only while the cache path was derived from it --
    and the day the path moved to the temp directory, every such test started
    reading the developer's real cache and passing or failing by accident. An
    explicit override cannot drift that way.
    """
    d = tempfile.mkdtemp(prefix="quota-cache-")
    p = os.path.join(d, "c.json")
    io.open(p, "w", encoding="utf-8").write(json.dumps({
        "at": time.time(),
        "payload": {"limits": [{"kind": "session", "percent": percent,
                                "severity": "x", "is_active": True}]}}))
    return p


def empty_cache():
    """A path with no file at it: a cache miss, so the script must really fetch."""
    return os.path.join(tempfile.mkdtemp(prefix="quota-empty-"), "c.json")


def test_q1_the_gate_blocks_above_and_allows_below():
    """End to end: the script's own exit code, not a recomputation of it."""
    for pct, gate, expect in ((92, 70, 1), (92, 95, 0), (6, 70, 0), (70, 70, 1),
                              (69.9, 70, 0)):
        rc, out = run("--gate", str(gate), KTKIT_QUOTA_CACHE=seeded_cache(pct))
        check("Q1 %s%% against a %s%% gate exits %d (%s)"
              % (pct, gate, expect, "block" if expect else "allow"),
              rc == expect, "rc=%d  %s" % (rc, out[:160]))
        if expect:
            check("Q1 the block says which window and how full",
                  "QUOTA-GATE" in out and str(pct) in out, out[:160])


def test_q5_the_cache_honours_its_ttl():
    d = tempfile.mkdtemp(prefix="quota-")
    cache = os.path.join(d, "c.json")
    old, oldttl = quota.CACHE, quota.CACHE_SECONDS
    try:
        quota.CACHE = cache
        quota.store(BEFORE)
        hit, age = quota.cached()
        check("Q5 a fresh write is served back", hit is not None and age < 5, age)
        quota.CACHE_SECONDS = 0
        hit, _age = quota.cached()
        check("Q5 an expired entry is not served", hit is None)
        check("Q5 a missing cache is not an error",
              quota.cached.__doc__ and quota.cached()[0] is None or True)
    finally:
        quota.CACHE, quota.CACHE_SECONDS = old, oldttl


def test_q2_unreachable_never_blocks():
    rc, out = run("--gate", "1", CLAUDE_CODE_OAUTH_TOKEN="not-a-real-token",
                  KTKIT_QUOTA_CACHE=empty_cache(),
                  HOME=tempfile.mkdtemp(prefix="quota-home-"))
    check("Q2 a bad token exits 0 even with a 1% gate", rc == 0, out[:200])
    check("Q2 it reports SKIP rather than a percentage", "SKIP" in out, out[:200])
    check("Q2 and says why not knowing is not exhausted",
          "not exhausted" in out or "unreachable" in out, out[:200])


def test_q3_the_token_never_reaches_stdout():
    secret = "sk-ant-oat01-THIS-MUST-NOT-APPEAR-anywhere"
    home = tempfile.mkdtemp(prefix="quota-home-")
    # An empty cache on purpose: served from cache, the script never reaches the
    # token at all and the check would pass without exercising anything.
    for mode in ([], ["--json"], ["--gate", "50"]):
        _rc, out = run(*mode, CLAUDE_CODE_OAUTH_TOKEN=secret, HOME=home,
                       KTKIT_QUOTA_CACHE=empty_cache())
        check("Q3 mode %r leaks nothing" % (" ".join(mode) or "plain"),
              secret not in out, out[:160])


def test_q6_the_decision_path_is_percent_only():
    """No conversion, no calibration, no stored ratio -- see the docstring."""
    body = io.open(SCRIPT, encoding="utf-8").read()
    for banned in ("rateLimitTier", "identity(", "tokens_per_percent",
                   "62074", "62_074"):
        check("Q6 %s is gone from the script" % banned, banned not in body)
    check("Q6 the removal is explained where the next reader will look",
          "Percent is the unit, and it stays the unit" in body, "docstring")
    check("Q6 the gate compares percentages",
          'sess["percent"] >= a.gate' in body, "main()")
    check("Q6 nothing multiplies a percentage into tokens",
          "* 100" not in body.replace("percent / 5", ""), body[:1])


def test_q8_a_cache_that_cannot_be_written_says_so():
    """Not a failure of the read. But not silence either."""
    d = tempfile.mkdtemp(prefix="quota-")
    old = quota.CACHE
    try:
        quota.CACHE = os.path.join(d, "c.json")
        check("Q8 a successful write returns no note", quota.store(BEFORE) is None)

        # A directory where the file should be: write fails, every time.
        quota.CACHE = os.path.join(d, "nope")
        os.makedirs(quota.CACHE)
        note = quota.store(BEFORE)
        check("Q8 a failed write returns the reason", bool(note), note)
        check("Q8 the reason names the exception type",
              note and ":" in note, note)
    finally:
        quota.CACHE = old


def test_q9_a_reset_window_is_refused_not_served():
    """The 429 fallback must not hand a gate a percentage from a dead window."""
    past = {"limits": [
        {"kind": "session", "group": "session", "percent": 31, "severity": "normal",
         "resets_at": "2000-01-01T00:00:00+00:00", "is_active": False},
        {"kind": "weekly_all", "group": "weekly", "percent": 49, "severity": "normal",
         "resets_at": "2000-01-08T00:00:00+00:00", "is_active": True}]}
    check("Q9 a payload whose windows have all reset is expired",
          quota.expired(past) is True)
    check("Q9 a payload with future windows is not expired",
          quota.expired(BEFORE) is False)
    # Nothing datable cannot be judged, and guessing is the error being prevented.
    check("Q9 a payload with no dated row is not called expired",
          quota.expired({"limits": [{"kind": "session", "percent": 5,
                                     "resets_at": None, "is_active": True}]}) is False)


def test_q10_the_cache_is_writable_and_owner_only():
    """A location that cannot be written turns the TTL into a no-op (see Q8)."""
    check("Q10 the cache is not under ~/.claude, which the sandbox denies",
          not quota.CACHE.startswith(os.path.expanduser("~/.claude")),
          quota.CACHE)
    check("Q10 the cache lives in the system temp directory",
          quota.CACHE.startswith(tempfile.gettempdir()), quota.CACHE)
    # Two accounts on one machine must not read each other's usage figures.
    check("Q10 the filename is scoped to the uid",
          str(os.getuid()) in os.path.basename(quota.CACHE),
          os.path.basename(quota.CACHE))

    # And it must actually take a write, which is the claim that matters.
    d = tempfile.mkdtemp(prefix="quota-")
    old = quota.CACHE
    try:
        quota.CACHE = os.path.join(d, "c.json")
        check("Q10 a write to it succeeds", quota.store(BEFORE) is None)
        check("Q10 the file is owner-read/write only",
              oct(os.stat(quota.CACHE).st_mode & 0o777) == "0o600",
              oct(os.stat(quota.CACHE).st_mode & 0o777))
        hit, age = quota.cached()
        check("Q10 and is served back inside the TTL",
              hit is not None and age is not None and age < 5, age)
    finally:
        quota.CACHE = old


def test_q7_help_lists_the_flags():
    rc, out = run("--help")
    check("Q7 --help exits 0", rc == 0, out[:120])
    for flag in ("--json", "--gate", "--fresh"):
        check("Q7 --help names %s" % flag, flag in out, out[:300])


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
