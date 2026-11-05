#!/usr/bin/env python3
"""Tier 1 of the probe preflight: is the info file good enough for THIS probe.

A live probe that starts three services, opens Chrome and only then discovers
that the database connection string was never filled in has wasted the
operator's time and left processes behind. Everything this script checks can be
answered from one file, with no network and no MCP call, so it runs first and
reports every gap at once rather than one per attempt.

The model decides what the probe needs -- it has read the requirement -- and
passes that as --needs. This script decides, mechanically, whether the file
supplies it. Neither half trusts the other's job.

  check_info.py --mode <name> [--needs <list>] [--file <path>]
  check_info.py --list-modes [--file <path>]
  check_info.py --list-accounts --mode <name> [--file <path>]
  check_info.py --default-path

--needs is a comma-separated list of:
  account:<label-or-role>   an account the probe logs in with (repeatable)
  db                        the probe compares against the database
  api:<service>             the probe compares against one API (repeatable)
  swagger                   the probe reads the swagger page

The file lives at <repo>/.claude/claude/docs/probe-live/info.md, where <repo>
is the git top level of the working directory (the directory itself outside a
repository). --file overrides it.

No value of any key is ever printed except the non-secret enums below and the
URL keys. A password or connection string in a report is a leak.

Exit codes: 0 PASS, 1 FAIL (the table says why), 2 usage error.
Stdlib only, Python 3.9.
"""
import argparse
import io
import os
import re
import subprocess
import sys

REL_PATH = os.path.join(".claude", "claude", "docs", "probe-live", "info.md")

MODE_RE = re.compile(r"^##\s+mode:\s*(\S+)")
ACCOUNT_RE = re.compile(r"^###\s+account:\s*(\S+)")
KEY_RE = re.compile(r"^\s*-\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s?(.*)$")
PLACEHOLDER_RE = re.compile(r"<[^>]*>")
RECIPE_KEY_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

KINDS = ("host-local", "docker-local", "remote")
RISKS = ("free", "read-only")
LOGIN_METHODS = ("password", "sso", "none")
YES_NO = ("yes", "no")

# Keys whose value is an enum or a URL. Only these may be echoed, and only these
# may carry a trailing `# comment` -- a password can legitimately contain " #".
ENUM_KEYS = ("kind", "env_class", "risk", "login_method", "can_write",
             "db_type", "db_access")
SHOWABLE = ENUM_KEYS + ("fe_url", "swagger_url", "role", "default_account")

ALWAYS = ("fe_url", "kind", "env_class", "risk")
ACCOUNT_REQUIRED = ("role", "login_method", "can_write")


class Entry(object):
    def __init__(self, value, line):
        self.value = value
        self.line = line


class Section(object):
    def __init__(self, name, line):
        self.name = name
        self.line = line
        self.keys = {}
        self.accounts = []          # only on modes
        self.duplicates = []

    def get(self, key):
        e = self.keys.get(key)
        return e.value if e else None

    def filled(self, key):
        v = self.get(key)
        return bool(v) and not PLACEHOLDER_RE.search(v)


def repo_root(cwd):
    try:
        out = subprocess.check_output(["git", "rev-parse", "--show-toplevel"],
                                      cwd=cwd, stderr=subprocess.DEVNULL)
        return out.decode("utf-8").strip()
    except Exception:                                          # noqa: BLE001
        return cwd


def default_path(cwd=None):
    return os.path.join(repo_root(cwd or os.getcwd()), REL_PATH)


def parse(text):
    """Modes, each with its keys and its accounts. Lines outside a mode are prose."""
    modes = []
    mode = target = None
    fence = False
    for n, raw in enumerate(text.split("\n"), 1):
        if raw.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        m = MODE_RE.match(raw)
        if m:
            mode = target = Section(m.group(1), n)
            modes.append(mode)
            continue
        m = ACCOUNT_RE.match(raw)
        if m and mode is not None:
            target = Section(m.group(1), n)
            mode.accounts.append(target)
            continue
        if raw.startswith("## "):            # any other H2 ends the mode
            mode = target = None
            continue
        m = KEY_RE.match(raw)
        if m and target is not None:
            key, value = m.group(1), m.group(2).strip()
            if key in ENUM_KEYS:
                value = re.sub(r"\s+#.*$", "", value).strip()
            if key in target.keys:
                target.duplicates.append((key, n))
            target.keys[key] = Entry(value, n)
    return modes


def find_account(mode, wanted):
    hits = [a for a in mode.accounts if a.name == wanted]
    if not hits:
        hits = [a for a in mode.accounts if (a.get("role") or "") == wanted]
    return hits


def recipe_keys(account):
    recipe = account.get("login_recipe")
    if recipe and not PLACEHOLDER_RE.search(recipe):
        return sorted(set(RECIPE_KEY_RE.findall(recipe)))
    return ["user", "password"]


def parse_needs(raw):
    needs = {"accounts": [], "db": False, "apis": [], "swagger": False}
    bad = []
    for item in [x.strip() for x in (raw or "").split(",") if x.strip()]:
        if item == "db":
            needs["db"] = True
        elif item == "swagger":
            needs["swagger"] = True
        elif item.startswith("account:") and item[8:]:
            needs["accounts"].append(item[8:])
        elif item.startswith("api:") and item[4:]:
            needs["apis"].append(item[4:])
        else:
            bad.append(item)
    return needs, bad


def where(path, line, note=""):
    loc = "%s:%d" % (os.path.basename(path), line) if line else os.path.basename(path)
    return loc + ((" (%s)" % note) if note else "")


def check(path, mode, needs):
    """(errors, warnings). Each error is (what, why, where)."""
    errors, warnings = [], []

    def need_key(section, key, why, label=None):
        what = ("account[%s].%s" % (label, key)) if label else key
        e = section.keys.get(key)
        if e is None:
            errors.append((what, why, where(path, section.line,
                                            "no such key under this section")))
        elif not e.value or PLACEHOLDER_RE.search(e.value):
            errors.append((what, why, where(path, e.line, "still a placeholder")))

    for key, line in mode.duplicates:
        errors.append((key, "declared twice in one mode", where(path, line)))

    # B2 -- the target, always.
    for key in ALWAYS:
        need_key(mode, key, "every probe needs it")
    kind, env_class, risk = mode.get("kind"), mode.get("env_class"), mode.get("risk")
    if mode.filled("kind") and kind not in KINDS:
        errors.append(("kind", "must be one of %s" % ", ".join(KINDS),
                       where(path, mode.keys["kind"].line)))
    if mode.filled("risk") and risk not in RISKS:
        errors.append(("risk", "must be one of %s" % ", ".join(RISKS),
                       where(path, mode.keys["risk"].line)))

    # B6 -- only the exact label `dev` may write. Anything else, a typo
    # included, is protected: wrong in the safe direction.
    protected = not (mode.filled("env_class") and env_class == "dev")
    if mode.filled("env_class") and protected and risk != "read-only":
        errors.append(("risk", "env_class %r is not `dev`, so risk must be read-only"
                       % env_class, where(path, mode.keys["risk"].line)
                       if "risk" in mode.keys else where(path, mode.line)))
    if protected and mode.filled("env_class"):
        for acc in mode.accounts:
            if acc.get("can_write") != "no":
                e = acc.keys.get("can_write")
                errors.append(("account[%s].can_write" % acc.name,
                               "env_class %r is not `dev`: every account must say no"
                               % env_class,
                               where(path, e.line if e else acc.line)))

    # B4 -- the accounts this probe logs in with.
    wanted = list(needs["accounts"])
    if not wanted and mode.filled("default_account"):
        wanted = [mode.get("default_account")]
    for label in wanted:
        hits = find_account(mode, label)
        if not hits:
            known = ", ".join("%s (%s)" % (a.name, a.get("role") or "?")
                              for a in mode.accounts) or "none"
            errors.append(("account[%s]" % label,
                           "the probe needs it; known: %s" % known,
                           where(path, mode.line, "no matching label or role")))
            continue
        if len(hits) > 1:
            errors.append(("account[%s]" % label,
                           "role matches %d accounts; name one by label"
                           % len(hits), where(path, hits[0].line)))
            continue
        acc = hits[0]
        for key in acc.duplicates:
            errors.append(("account[%s].%s" % (acc.name, key[0]),
                           "declared twice", where(path, key[1])))
        for key in ACCOUNT_REQUIRED:
            need_key(acc, key, "every account needs it", acc.name)
        method = acc.get("login_method")
        if acc.filled("login_method") and method not in LOGIN_METHODS:
            errors.append(("account[%s].login_method" % acc.name,
                           "must be one of %s" % ", ".join(LOGIN_METHODS),
                           where(path, acc.keys["login_method"].line)))
        if acc.filled("can_write") and acc.get("can_write") not in YES_NO:
            errors.append(("account[%s].can_write" % acc.name, "must be yes or no",
                           where(path, acc.keys["can_write"].line)))
        if method == "password":
            for key in recipe_keys(acc):
                why = ("login_recipe uses {%s}" % key if acc.filled("login_recipe")
                       else "password login without a login_recipe")
                need_key(acc, key, why, acc.name)
        elif method == "sso":
            need_key(acc, "sso_note", "sso login waits for a human", acc.name)

    # B9 -- what this particular probe asked for.
    if needs["db"]:
        need_key(mode, "db_type", "the probe compares against the database")
        if mode.filled("db_type") and mode.get("db_type") != "none":
            need_key(mode, "db_connection", "the probe compares against the database")
        elif mode.get("db_type") == "none":
            errors.append(("db_type", "the probe needs the database but this mode "
                           "says none", where(path, mode.keys["db_type"].line)))
    elif "db_connection" in mode.keys and not mode.filled("db_connection"):
        warnings.append("db_connection is still a placeholder (%s); not needed "
                        "for this probe" % where(path, mode.keys["db_connection"].line))
    for svc in needs["apis"]:
        apis = mode.get("api_urls") or ""
        names = [p.split("=", 1)[0].strip() for p in apis.split(",") if "=" in p]
        if svc not in names:
            line = mode.keys["api_urls"].line if "api_urls" in mode.keys else 0
            errors.append(("api_urls.%s" % svc, "the probe compares against this API",
                           where(path, line or mode.line,
                                 "service not listed" if line else "no api_urls key")))
    if needs["swagger"]:
        need_key(mode, "swagger_url", "the probe reads swagger")
    return errors, warnings


def tracked_by_git(path):
    """True when git tracks the file. A file holding inline passwords must not be."""
    d = os.path.dirname(os.path.abspath(path))
    try:
        subprocess.check_output(["git", "ls-files", "--error-unmatch",
                                 os.path.abspath(path)], cwd=d,
                                stderr=subprocess.DEVNULL)
        return True
    except Exception:                                          # noqa: BLE001
        return False


def load(path):
    if not os.path.isfile(path):
        return None
    return parse(io.open(path, encoding="utf-8").read())


def main(argv):
    ap = argparse.ArgumentParser(
        description="Tier 1 preflight for /ktkit:probe: check the info file "
                    "against what this probe needs. Prints no secret.")
    ap.add_argument("--file", help="info file (default: <repo>/%s)" % REL_PATH)
    ap.add_argument("--mode", help="the mode to check")
    ap.add_argument("--needs", default="",
                    help="comma list: account:<label|role>, db, api:<svc>, swagger")
    ap.add_argument("--list-modes", action="store_true",
                    help="print the modes the file declares")
    ap.add_argument("--list-accounts", action="store_true",
                    help="print label, role and can_write of a mode's accounts")
    ap.add_argument("--default-path", action="store_true",
                    help="print where the info file is looked for, and exit")
    args = ap.parse_args(argv[1:])

    path = os.path.abspath(args.file) if args.file else default_path()
    if args.default_path:
        print(path)
        return 0

    modes = load(path)
    if modes is None:
        print("B1 info file ....... FAIL  not found: %s" % path)
        print("Run `/ktkit:probe init` to scaffold it, or pass another file. "
              "Nothing was started.")
        return 1
    if not modes:
        print("B1 info file ....... FAIL  %s declares no `## mode: <name>` section"
              % path)
        return 1
    if args.list_modes:
        for m in modes:
            print("%s  (%s, env_class=%s)" % (m.name, where(path, m.line),
                                              m.get("env_class") or "?"))
        return 0
    if not args.mode:
        print("--mode is required (known: %s)" % ", ".join(m.name for m in modes),
              file=sys.stderr)
        return 2
    hits = [m for m in modes if m.name == args.mode]
    if not hits:
        print("B1 info file ....... FAIL  no mode %r; known: %s"
              % (args.mode, ", ".join(m.name for m in modes)))
        return 1
    if len(hits) > 1:
        print("B1 info file ....... FAIL  mode %r declared %d times (%s)"
              % (args.mode, len(hits), ", ".join(where(path, m.line) for m in hits)))
        return 1
    mode = hits[0]
    if args.list_accounts:
        for a in mode.accounts:
            print("%s · %s · can_write=%s" % (a.name, a.get("role") or "?",
                                             a.get("can_write") or "?"))
        return 0

    needs, bad = parse_needs(args.needs)
    if bad:
        print("unknown --needs item(s): %s" % ", ".join(bad), file=sys.stderr)
        return 2

    errors, warnings = check(path, mode, needs)
    protected = mode.get("env_class") != "dev"
    print("Tier 1 -- info file (mode: %s)   file: %s" % (mode.name, path))
    print("B1 file + mode ....... PASS")
    print("access ............... %s" % ("READ-ONLY (env_class %r)"
                                          % (mode.get("env_class") or "?")
                                          if protected else "free (env_class dev)"))
    if tracked_by_git(path):
        print("!! RED: git tracks this file and it holds inline secrets. "
              "Untrack it or add it to .gitignore.")
    for w in warnings:
        print("warn  %s" % w)
    if errors:
        print("FAIL  %d gap(s):" % len(errors))
        print("  %-30s · %-50s · %s" % ("what", "why this probe needs it", "fix at"))
        for what, why, loc in errors:
            print("  %-30s · %-50s · %s" % (what, why, loc))
        print("=> STOP at tier 1. No MCP call, no Chrome, nothing started.")
        return 1
    print("PASS  every key this probe needs is filled")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
