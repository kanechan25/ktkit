#!/usr/bin/env python3
"""Suggestions for `/ktkit:probe init`, each with the file and line it came from.

The info file is filled by the operator. This script only finds facts a
repository already states -- a published port, a dev script, an env key name --
so the skeleton does not start empty where it does not have to. Anything it
cannot point at a line for, it does not suggest: a guessed port is worse than a
blank one, because it looks filled.

It reads key NAMES of env example files and never opens a real `.env`: values
there are secrets, and a suggestion list is printed to a chat.

  init_scan.py [--root <dir>]

Stdlib only, Python 3.9. Prints suggestions; writes nothing.
"""
import argparse
import glob
import io
import json
import os
import re
import subprocess
import sys

SKIP_DIRS = {".git", "node_modules", "bin", "obj", "dist", "build", ".next",
             "vendor", "__pycache__", ".venv", "venv"}
MAX_DEPTH = 4

PORT_RE = re.compile(r"""^\s*-\s*["']?(?:[\d.]+:)?(\d{2,5}):(\d{2,5})""")
SCRIPT_KEYS = ("dev", "start", "serve", "preview")
URL_RE = re.compile(r"https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0|\*|\+):(\d{2,5})")
ENV_KEY_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")
MAKE_RE = re.compile(r"^([A-Za-z][\w.-]*)\s*:(?!=)")
SECRETISH = re.compile(r"(DB|DATABASE|CONN|URL|HOST|PORT|AUTH|LOGIN|USER)", re.I)


def repo_root(cwd):
    try:
        out = subprocess.check_output(["git", "rev-parse", "--show-toplevel"],
                                      cwd=cwd, stderr=subprocess.DEVNULL)
        return out.decode("utf-8").strip()
    except Exception:                                          # noqa: BLE001
        return cwd


def walk(root):
    root_depth = root.rstrip(os.sep).count(os.sep)
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS
                         and not x.startswith("."))
        if d.count(os.sep) - root_depth >= MAX_DEPTH:
            dirs[:] = []
        for f in sorted(files):
            yield os.path.join(d, f)


def lines(path):
    try:
        return io.open(path, encoding="utf-8", errors="replace").read().split("\n")
    except IOError:
        return []


def rel(root, path):
    return os.path.relpath(path, root)


def scan_compose(root, path, out):
    for n, line in enumerate(lines(path), 1):
        m = PORT_RE.match(line)
        if m:
            out.append(("ports", "host port %s (container %s)" % (m.group(1), m.group(2)),
                        "%s:%d" % (rel(root, path), n)))


def scan_package(root, path, out):
    text = lines(path)
    try:
        scripts = json.loads("\n".join(text)).get("scripts") or {}
    except ValueError:
        return
    for key in SCRIPT_KEYS:
        if key not in scripts:
            continue
        n = next((i for i, l in enumerate(text, 1) if '"%s"' % key in l), 0)
        out.append(("start_cmds", "%s script: %s" % (key, scripts[key]),
                    "%s:%d" % (rel(root, path), n)))
        for port in re.findall(r"(?:-p|--port)[ =](\d{2,5})", scripts[key]):
            out.append(("ports", "port %s in the %s script" % (port, key),
                        "%s:%d" % (rel(root, path), n)))


def scan_urls(root, path, out, key):
    for n, line in enumerate(lines(path), 1):
        for port in URL_RE.findall(line):
            out.append((key, "local URL on port %s" % port,
                        "%s:%d" % (rel(root, path), n)))


def scan_env_example(root, path, out):
    for n, line in enumerate(lines(path), 1):
        m = ENV_KEY_RE.match(line)
        if m and SECRETISH.search(m.group(1)):
            out.append(("env key", "%s (name only)" % m.group(1),
                        "%s:%d" % (rel(root, path), n)))


def scan_makefile(root, path, out):
    for n, line in enumerate(lines(path), 1):
        m = MAKE_RE.match(line)
        if not m:
            continue
        target = m.group(1)
        # A cleanup target removes things; suggesting it as a start or stop
        # command would hand the operator a destructive line that looks safe.
        if re.search(r"(clean|prune|remove|rm|reset|purge|nuke)", target):
            continue
        if re.search(r"(^|[-_.])(stop|down)($|[-_.])", target):
            key = "stop_cmds"
        elif re.search(r"(^|[-_.])(dev|start|up|run|serve)($|[-_.])", target):
            key = "start_cmds"
        else:
            continue
        out.append((key, "make %s" % target, "%s:%d" % (rel(root, path), n)))


def scan(root):
    out = []
    for path in walk(root):
        name = os.path.basename(path)
        if re.match(r"^(docker-)?compose[\w.-]*\.ya?ml$", name):
            scan_compose(root, path, out)
        elif name == "package.json":
            scan_package(root, path, out)
        elif name == "launchSettings.json":
            scan_urls(root, path, out, "ports")
        elif re.match(r"^\.env[\w.-]*\.(example|sample|template)$", name) or \
                name in ("env.example", "example.env"):
            scan_env_example(root, path, out)
        elif name in ("Makefile", "makefile"):
            scan_makefile(root, path, out)
        elif re.match(r"^README(\.\w+)?$", name, re.I):
            scan_urls(root, path, out, "fe_url?")
    return out


def main(argv):
    ap = argparse.ArgumentParser(
        description="Suggest info-file values for /ktkit:probe init, each with "
                    "file:line. Reads env key names only; writes nothing.")
    ap.add_argument("--root", help="repository root (default: git top level of cwd)")
    args = ap.parse_args(argv[1:])
    root = os.path.abspath(args.root) if args.root else repo_root(os.getcwd())
    found = scan(root)
    print("init suggestions for %s" % root)
    if not found:
        print("  none found -- every key stays <ops điền>")
        return 0
    seen = set()
    for key, what, where in found:
        if (key, what, where) in seen:
            continue
        seen.add((key, what, where))
        print("  %-12s %-50s %s" % (key, what, where))
    print("Suggestions only. Values not listed here stay <ops điền>.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
