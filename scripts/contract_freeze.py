#!/usr/bin/env python3
"""Freeze what a run is building against, so a change request cannot land silently.

A change request that arrives while `05 implement` is running is the one case
where two people are editing the same contract at once. The worker is building
against `spec.md`, `plan.md` and `tasks.md` as they were when the phase started;
the change request rewrites them. Nothing crashes. The worker finishes something
that satisfies a spec nobody has approved any more, and the run reports success.

This records the hashes of those three files at the moment the phase starts, and
compares them later:

    freeze   `<chain-dir>/contract.json`, one SHA-256 per artifact
    check    exit 0 unchanged, exit 3 drifted -- with which files and when
    block    the run is BLOCKED, with a reason, and nothing may resume past it
    resume   BLOCKED -> EXECUTING, and only the affected part is re-run

The idea of snapshotting the artifacts is taken from `speckit-superpowers-bridge`
and the implementation is not: that repository is one author, tens of stars, and
weeks between pushes against a spec-kit that releases roughly weekly. An idea
costs nothing to borrow. A dependency has to be maintained by whoever is on call.

`check` reports drift. It never merges, never picks a side, and never decides
whether the drift matters -- `/ktkit:cr-delta` answers that, and a person reads
the answer.

Stdlib only, Python 3.9.
"""
import argparse
import hashlib
import io
import json
import os
import sys
import time

FREEZE_FILE = "contract.json"

# The three artifacts a worker builds against. `tasks.md` is included even though
# `speckit-converge` appends to it on purpose: an append during implement is
# exactly the drift worth seeing, because the worker's task list grew under it.
ARTIFACTS = ("spec.md", "plan.md", "tasks.md")

# The states a run can be in. BLOCKED exists so that a run interrupted by a
# change request is distinguishable from one that failed, and from one that
# finished -- three situations with three different next steps.
STATES = ("EXECUTING", "BLOCKED", "DONE")


def digest(path):
    """SHA-256 of a file, or None when it does not exist.

    Absence is recorded rather than treated as an error: a run frozen before
    `tasks.md` existed and checked after it appeared has drifted, and saying so
    is the point.
    """
    if not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def freeze_path(base):
    return os.path.join(base, FREEZE_FILE)


def load(base):
    path = freeze_path(base)
    if not os.path.isfile(path):
        return None
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save(base, data):
    parent = os.path.dirname(os.path.abspath(freeze_path(base)))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    tmp = freeze_path(base) + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, freeze_path(base))


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def do_freeze(base, feature_dir):
    data = load(base) or {}
    if data.get("state") == "BLOCKED":
        print("FAIL blocked: this run is BLOCKED (%s). Resolve it before "
              "freezing again -- re-freezing would adopt the new contract "
              "without anybody deciding to."
              % data.get("reason", "no reason recorded"))
        return 2
    data.update({
        "feature_dir": feature_dir,
        "state": "EXECUTING",
        "frozen_at": now(),
        "artifacts": dict((name, digest(os.path.join(feature_dir, name)))
                          for name in ARTIFACTS),
    })
    data.setdefault("history", []).append(
        {"at": data["frozen_at"], "event": "freeze", "state": "EXECUTING"})
    save(base, data)
    for name in ARTIFACTS:
        d = data["artifacts"][name]
        print("%-10s %s" % (name, (d[:12] if d else "(absent)")))
    print("EXECUTING, frozen at %s" % data["frozen_at"])
    return 0


def drifted(data):
    """[(name, was, now)] for every artifact whose hash moved."""
    out = []
    for name in ARTIFACTS:
        was = (data.get("artifacts") or {}).get(name)
        is_now = digest(os.path.join(data["feature_dir"], name))
        if was != is_now:
            out.append((name, was, is_now))
    return out


def do_check(base):
    data = load(base)
    if data is None:
        print("FAIL not-frozen: no %s -- freeze before the phase starts, or "
              "there is nothing to compare against" % FREEZE_FILE)
        return 2
    moved = drifted(data)
    if not moved:
        print("unchanged since %s (%s)" % (data["frozen_at"], data["state"]))
        return 0
    for name, was, is_now in moved:
        print("drifted  %-10s %s -> %s"
              % (name, (was[:12] if was else "(absent)"),
                 (is_now[:12] if is_now else "(deleted)")))
    print("\nThe run is building against a contract that has changed. ⛔ Do not "
          "merge and do not choose a side here -- block the run, then ask "
          "/ktkit:cr-delta what the change reaches.")
    return 3


def do_block(base, reason):
    data = load(base)
    if data is None:
        print("FAIL not-frozen: nothing to block")
        return 2
    if not reason:
        print("FAIL missing-reason: a block with no reason is indistinguishable "
              "from a crash, and the next reader cannot tell whether to resume")
        return 2
    data["state"] = "BLOCKED"
    data["reason"] = reason
    data["blocked_at"] = now()
    data.setdefault("history", []).append(
        {"at": data["blocked_at"], "event": "block", "state": "BLOCKED",
         "reason": reason})
    save(base, data)
    print("BLOCKED: %s" % reason)
    return 0


def do_resume(base, affected):
    """BLOCKED -> EXECUTING, re-freezing against the amended artifacts.

    `--affected` is required and is the whole point: a resume that re-runs
    everything has thrown away the progress the block was protecting, which is
    the outcome blocking existed to prevent.
    """
    data = load(base)
    if data is None:
        print("FAIL not-frozen: nothing to resume")
        return 2
    if data.get("state") != "BLOCKED":
        print("FAIL not-blocked: state is %s, so there is nothing to resume from"
              % data.get("state"))
        return 2
    if not affected:
        print("FAIL missing-affected: name the tasks to re-run. A resume with "
              "no list re-runs everything, which discards exactly the progress "
              "the block was protecting.")
        return 2
    ids = [t.strip() for t in affected.split(",") if t.strip()]
    data["state"] = "EXECUTING"
    data["resumed_at"] = now()
    data["affected"] = ids
    data["frozen_at"] = data["resumed_at"]
    data["artifacts"] = dict((name, digest(os.path.join(data["feature_dir"], name)))
                             for name in ARTIFACTS)
    data.setdefault("history", []).append(
        {"at": data["resumed_at"], "event": "resume", "state": "EXECUTING",
         "affected": ids, "was_blocked_for": data.get("reason")})
    save(base, data)
    print("EXECUTING, re-frozen at %s" % data["resumed_at"])
    print("re-running only: %s" % ", ".join(ids))
    return 0


def do_status(base, as_json):
    data = load(base)
    if data is None:
        print("FAIL not-frozen: no %s" % FREEZE_FILE)
        return 2
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
    print("state      %s" % data.get("state"))
    print("feature    %s" % data.get("feature_dir"))
    print("frozen at  %s" % data.get("frozen_at"))
    if data.get("state") == "BLOCKED":
        print("reason     %s" % data.get("reason"))
    if data.get("affected"):
        print("affected   %s" % ", ".join(data["affected"]))
    print("history    %d event(s)" % len(data.get("history") or []))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="contract_freeze.py",
        description="Record what a run is building against, and notice when it "
                    "changes underneath.")
    ap.add_argument("--base", required=True, help="the chain run directory")
    ap.add_argument("--dir", dest="feature_dir",
                    help="the feature directory holding spec.md / plan.md / "
                         "tasks.md (required with --freeze)")
    ap.add_argument("--freeze", action="store_true",
                    help="record the current hashes and mark the run EXECUTING")
    ap.add_argument("--check", action="store_true",
                    help="exit 3 if any artifact moved since the freeze")
    ap.add_argument("--block", action="store_true",
                    help="mark the run BLOCKED (needs --reason)")
    ap.add_argument("--resume", action="store_true",
                    help="BLOCKED -> EXECUTING (needs --affected)")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--reason", help="why the run is blocked")
    ap.add_argument("--affected",
                    help="comma-separated task ids to re-run on resume")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if a.freeze:
        if not a.feature_dir:
            ap.error("--freeze needs --dir")
        return do_freeze(a.base, a.feature_dir)
    if a.check:
        return do_check(a.base)
    if a.block:
        return do_block(a.base, a.reason)
    if a.resume:
        return do_resume(a.base, a.affected)
    if a.status:
        return do_status(a.base, a.json)
    ap.error("give one of --freeze, --check, --block, --resume, --status")


if __name__ == "__main__":
    sys.exit(main())
