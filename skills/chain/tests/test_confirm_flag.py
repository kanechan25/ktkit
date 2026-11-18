#!/usr/bin/env python3
"""A gate waits for the user only when --confirm says so.

Without --confirm the chain is meant to run unattended: every gate still writes
its block -- the defaults it applied and why -- but nothing stops on it. With
--confirm every one of those gates goes through /ktkit:confirm-with-me. The two
ways this breaks are silent: a gate that still waits in the default mode makes
an unattended run hang, and a default nobody saw recorded as a user's answer
reads later as a decision somebody made on purpose.

  F1  --confirm is in the hint and in ## Arguments, and is off by default
  F2  step 00 writes the mode to <chain-dir>/gates for 05 and --resume to read
  F3  The gate has both modes, and auto never posts or waits
  F4  every approval gate -- 03, 05, 06 contract, 07 cap -- names --confirm
  F5  hard stops are named as outside the flag
  F6  feat-req-execute reads the mode, and a direct run still waits
  F7  an auto-accepted row is never recorded as a user's answer

Run:  python3 skills/chain/tests/test_confirm_flag.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

CHAIN = os.path.join(ROOT, "skills", "chain", "SKILL.md")
HELP = os.path.join(ROOT, "skills", "chain", "references", "help.md")
EXEC = os.path.join(ROOT, "skills", "feat-req-execute", "SKILL.md")

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def plain(path):
    text = io.open(path, encoding="utf-8").read()
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", ""))


def section(text, start, end):
    return text[text.index(start):text.index(end)]


def main():
    c = plain(CHAIN)
    hint = re.search(r"^argument-hint: (.*)$", io.open(CHAIN, encoding="utf-8").read(), re.M)
    check("F1 hint names --confirm", hint and "[--confirm]" in hint.group(1), "")
    args = section(c, "## Arguments", "## Layout")
    check("F1 Arguments names --confirm, default off",
          re.search(r"--confirm\] .*Default OFF", args) is not None, "")
    check("F1 help page names --confirm", "--confirm" in plain(HELP), "")

    route = section(c, "### 00 — route", "### 01 — analyse")
    check("F2 step 00 writes the mode", "<chain-dir>/gates" in route
          and "confirm" in route and "auto" in route, "")

    gate = section(c, "## The gate", "## The manifest")
    check("F3 auto mode does not post or wait",
          "auto — the default" in gate and "Do not post it to the user and do not wait" in gate, "")
    check("F3 confirm mode posts through confirm-with-me",
          "confirm — --confirm" in gate and "/ktkit:confirm-with-me" in gate, "")

    for name, start, end in (("03", "### 03 — spec", "### 04 — plan"),
                             ("05", "### 05 — implement", "#### ⛔ Freeze"),
                             ("06", "3. A contract-level row is a gate.", "### 07 — converge"),
                             ("07", "#### ⛔ Two rounds", "### 08 — hand-off")):
        check("F4 step %s names --confirm" % name, "--confirm" in section(c, start, end), "")

    check("F5 hard stops stop either way", "stops either way" in c, "")

    e = plain(EXEC)
    mode = section(e, "## Gate mode", "## ⚠️ FORMAT GATE")
    check("F6 execute reads <run-dir>/gates", "<run-dir>/gates" in mode, "")
    check("F6 a direct run still waits", "a direct run" in mode and "Stop and wait" in mode, "")
    check("F6 hard stops unchanged in execute", "stop in either mode" in mode, "")

    check("F7 auto rows are not user answers",
          "auto-accepted: no --confirm" in c
          and "Record an auto-accepted row as user answered at the gate" in c, "")

    print()
    if failures:
        print("%d failure(s)" % len(failures))
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()
