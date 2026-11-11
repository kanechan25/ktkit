#!/usr/bin/env python3
"""A chain run stops on a window it measured, never on a cost it forecast.

The gate this replaces refused to start phase D because the window left,
converted into tokens at the run's own rate, was smaller than what phases A-C
had cost -- with 44% of the session unspent. Now a background watch reads every
session and weekly window, trips a wind-down at `--wind-down` percent, and the
run finishes what is in flight, records it in one checkpoint file, and pauses.

  W1  six agents marking five sub-steps each write ONE file: six sections,
      thirty lines, every line stamped YYYY-MM-DD HH:MM
  W2  status exits 0 running, 3 wind-down, 4 paused/complete; resume returns to 0
  W3  every window under the threshold: the watch trips nothing
  W4  a weekly window at the threshold trips it, and the reason names that window
  W5  the session window at the threshold trips it
  W6  an unreadable quota is not exhausted: nothing trips
  W7  a paused run is not watched: the watch exits without tripping
  W8  latest gives each task's last milestone with its next sub-step
  W9  budget.py --window-advisory stops on spent >= budget only; the forecast
      that used to stop the run is a note
  W10 without the flag budget.py still stops on the forecast (spec-recon unchanged)
  W11 chain no longer carries the A-C rule or --budget-execute, and documents
      --wind-down and the checkpoint
  W12 --await-reset on a paused run whose windows refilled resumes it, and says why
  W13 a window still full is waited for: the run stays paused
  W14 an unreadable quota never resumes a paused run blind
  W15 the resume command kept at pause comes back from latest, and the docs say
      the lead continues without asking

The window is seeded through `KTKIT_QUOTA_CACHE`, never read live: a verdict
that depends on how much quota the machine has spent today is not a test.

Run:  python3 skills/chain/tests/test_wind_down.py
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(SKILL))
CHECKPOINT = os.path.join(SKILL, "scripts", "checkpoint.py")
WATCH = os.path.join(SKILL, "scripts", "window_watch.py")
BUDGET = os.path.join(ROOT, "scripts", "budget.py")

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def seed(cache, session=None, weekly=None, rows=True):
    """Write a fresh quota cache with the given percentages."""
    later = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    limits = []
    if rows:
        limits = [{"kind": "session", "percent": session, "resets_at": later},
                  {"kind": "weekly_all", "percent": weekly, "resets_at": later}]
    with io.open(cache, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.time(), "payload": {"limits": limits}}))


def env(cache):
    e = dict(os.environ, KTKIT_QUOTA_CACHE=cache)
    e.pop("CLAUDE_PLUGIN_ROOT", None)
    return e


def run(script, *args, **kw):
    p = subprocess.run([sys.executable, script] + list(args), capture_output=True,
                       text=True, env=kw.get("env"))
    return p.returncode, p.stdout + p.stderr


def status(base):
    return run(CHECKPOINT, "status", "--base", base)[0]


def test_one_file_for_every_agent():
    base = tempfile.mkdtemp()
    procs = []
    for agent in range(6):
        for step in range(1, 6):
            procs.append(subprocess.Popen(
                [sys.executable, CHECKPOINT, "mark", "--base", base,
                 "--agent", "worker-T%02d" % agent, "--task", "T%02d" % agent,
                 "--step", "%d/5 sub-step" % step, "--state", "done",
                 "--next", "step %d" % (step + 1), "--files", "a.py,b.py"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    for p in procs:
        p.wait()
    files = sorted(os.listdir(base))
    text = io.open(os.path.join(base, "checkpoint.md"), encoding="utf-8").read()
    rows = [l for l in text.splitlines() if l.startswith("- ")]
    stamped = [l for l in rows if re.match(r"- \d{4}-\d{2}-\d{2} \d{2}:\d{2} \| ", l)]
    check("W1 one file, no lock or temp file left", files == ["checkpoint.md"], files)
    check("W1 six sections", text.count("\n## worker-T") == 6, text)
    check("W1 thirty milestones, all stamped to the minute",
          len(rows) == 30 and len(stamped) == 30, "%d rows, %d stamped" % (len(rows), len(stamped)))
    check("W1 header carries created, updated and status",
          re.search(r"Created: \d{4}-\d{2}-\d{2} \d{2}:\d{2} · Updated: ", text)
          and "Status: running" in text, text[:200])
    shutil.rmtree(base)


def test_status_codes():
    base = tempfile.mkdtemp()
    check("W2 a fresh run is running", status(base) == 0)
    run(CHECKPOINT, "trip", "--base", base, "--reason", "session at 96.0%")
    check("W2 tripped is 3", status(base) == 3)
    run(CHECKPOINT, "pause", "--base", base, "--reason", "session at 97.1%")
    check("W2 paused is 4", status(base) == 4)
    run(CHECKPOINT, "resume", "--base", base)
    check("W2 resumed is 0", status(base) == 0)
    run(CHECKPOINT, "finish", "--base", base)
    check("W2 complete is 4", status(base) == 4)
    text = io.open(os.path.join(base, "checkpoint.md"), encoding="utf-8").read()
    check("W2 the trip and the pause record their percentage",
          "wind-down | session at 96.0%" in text and "paused | session at 97.1%" in text, text)
    shutil.rmtree(base)


def watch_once(session, weekly, rows=True, before=None):
    base, cache = tempfile.mkdtemp(), tempfile.mktemp()
    seed(cache, session, weekly, rows)
    if before:
        run(CHECKPOINT, before, "--base", base, "--reason", "x")
    rc, out = run(WATCH, "--base", base, "--once", env=env(cache))
    st = status(base)
    text = ""
    if os.path.isfile(os.path.join(base, "checkpoint.md")):
        text = io.open(os.path.join(base, "checkpoint.md"), encoding="utf-8").read()
    shutil.rmtree(base)
    os.remove(cache)
    return rc, out, st, text


def test_watch():
    rc, out, st, _ = watch_once(44.0, 60.0)
    check("W3 under the threshold trips nothing", rc == 0 and st == 0, out)
    rc, out, st, text = watch_once(50.0, 96.0)
    check("W4 weekly at 96% trips", st == 3, out)
    check("W4 the reason names the weekly window", "weekly_all at 96.0%" in text, text)
    rc, out, st, text = watch_once(96.5, 10.0)
    check("W5 session at 96% trips", st == 3 and "session at 96.5%" in text, out + text)
    rc, out, st, _ = watch_once(None, None, rows=False)
    check("W6 unreadable quota trips nothing", rc == 0 and st == 0 and "SKIP" in out, out)
    rc, out, st, text = watch_once(99.0, 99.0, before="pause")
    check("W7 a paused run is not tripped", st == 4 and "wind-down" not in text, out + text)


def test_latest():
    base = tempfile.mkdtemp()
    for step, nxt in (("1/3 write test", "implement"), ("2/3 implement", "run gate")):
        run(CHECKPOINT, "mark", "--base", base, "--agent", "worker-T03", "--task", "T03",
            "--step", step, "--state", "done", "--next", nxt, "--files", "src/a.py")
    rc, out = run(CHECKPOINT, "latest", "--base", base)
    lines = [l for l in out.splitlines() if "T03" in l]
    check("W8 one line per task, the last milestone",
          len(lines) == 1 and "2/3 implement" in lines[0] and "next: run gate" in lines[0], out)
    shutil.rmtree(base)


def budget_case(advisory):
    base, cache = tempfile.mkdtemp(), tempfile.mktemp()
    seed(cache, 50.0, 10.0)
    with io.open(os.path.join(base, "cost.jsonl"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": "agent", "tokens_total": 600000}) + "\n")
    args = ["--base", base, "--budget", "1000000", "--step", "a"]
    run(BUDGET, *args, env=env(cache))
    with io.open(os.path.join(base, "cost.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": "agent", "tokens_total": 300000}) + "\n")
    extra = ["--window-advisory"] if advisory else []
    rc, out = run(BUDGET, *(["--base", base, "--budget", "1000000", "--step", "b"] + extra),
                  env=env(cache))
    with io.open(os.path.join(base, "cost.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": "agent", "tokens_total": 200000}) + "\n")
    rc2, out2 = run(BUDGET, *(["--base", base, "--budget", "1000000", "--step", "c"] + extra),
                    env=env(cache))
    shutil.rmtree(base)
    os.remove(cache)
    return rc, out, rc2, out2


def test_budget_modes():
    rc, out, rc2, out2 = budget_case(advisory=True)
    check("W9 a forecast past the ceiling is a note, not a stop",
          rc == 0 and "a note, not a stop" in out, out)
    check("W9 spent reaching the ceiling stops", rc2 == 1 and "ceiling is spent" in out2, out2)
    rc, out, _, _ = budget_case(advisory=False)
    check("W10 without the flag the forecast still stops", rc == 1, out)


def test_docs():
    skill = io.open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8").read()
    helpp = io.open(os.path.join(SKILL, "references", "help.md"), encoding="utf-8").read()
    for name, text in (("SKILL.md", skill), ("help.md", helpp)):
        check("W11 %s has no --budget-execute" % name, "--budget-execute" not in text)
        check("W11 %s documents --wind-down and checkpoint.md" % name,
              "--wind-down" in text and "checkpoint.md" in text)
    check("W11 no rule refuses phase D on what A-C cost",
          "do not start it" not in skill and "Before phase D" not in skill)


def await_once(session, weekly, rows=True):
    base, cache = tempfile.mkdtemp(), tempfile.mktemp()
    seed(cache, session, weekly, rows)
    run(CHECKPOINT, "pause", "--base", base, "--reason", "session at 96.4%",
        "--command", "/ktkit:chain req.md --resume --execute")
    rc, out = run(WATCH, "--base", base, "--await-reset", "--once", env=env(cache))
    st = status(base)
    _, latest = run(CHECKPOINT, "latest", "--base", base)
    text = io.open(os.path.join(base, "checkpoint.md"), encoding="utf-8").read()
    shutil.rmtree(base)
    os.remove(cache)
    return rc, out, st, latest, text


def test_await_reset():
    rc, out, st, latest, text = await_once(3.0, 40.0)
    check("W12 refilled windows resume the run", rc == 0 and st == 0, out)
    check("W12 the resume records the readings", "resumed | every window under 96%" in text, text)
    rc, out, st, _, _ = await_once(10.0, 97.0)
    check("W13 a full weekly window keeps it paused", st == 4 and "next reading" not in out, out)
    rc, out, st, _, _ = await_once(None, None, rows=False)
    check("W14 unreadable never resumes blind", st == 4 and "SKIP" in out, out)
    rc, out, st, latest, _ = await_once(97.0, 10.0)
    check("W15 latest prints the kept resume command",
          "Resume: /ktkit:chain req.md --resume --execute" in latest, latest)
    skill = io.open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8").read()
    check("W15 the skill starts --await-reset and continues without asking",
          "--await-reset" in skill and "without asking" in skill)


if __name__ == "__main__":
    for fn in (test_one_file_for_every_agent, test_status_codes, test_watch,
               test_latest, test_budget_modes, test_docs, test_await_reset):
        fn()
    print()
    if failures:
        print("%d failure(s)" % len(failures))
        sys.exit(1)
    print("all checks passed")
