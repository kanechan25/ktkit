#!/usr/bin/env python3
"""check_info.py must stop a probe before it starts, for the right reasons only.

  C1  a missing file fails, names the path, and suggests init
  C2  every gap of one probe is reported in one run, each with file:line
  C3  a key the probe does not need never blocks it
  C4  only the exact `dev` may write; any other label forces read-only
  C5  a protected mode with a can_write account fails
  C6  login_recipe placeholders decide which account keys are required
  C7  no secret value is ever printed
  C8  an account named in the session that matches nothing lists the known ones
  C9  --default-path is <repo>/.claude/claude/docs/probe-live/info.md
  C10 a mode or account heading at the wrong level fails, never folds in

Run:  python3 skills/probe/tests/test_check_info.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "scripts", "check_info.py")

SECRET = "s3cr3t-Pa55 #word"
CONN = "Host=db.example.test;Password=conn-secret"

GOOD = """# notes before any mode are prose
# mode: local
- kind: host-local
- env_class: dev
- risk: free
- fe_url: http://localhost:5173
- api_urls: core=http://localhost:7000
- db_type: postgres
- db_connection: %s
- default_account: owner

#### account: owner
- role: admin          # a note after a non-secret key
- login_method: password
- user: 100
- password: %s
- can_write: yes

#### account: member
- role: member
- login_method: password
- email: m@example.test
- tenant: acme
- password: %s
- can_write: no
- login_recipe: fill Email = {email}; fill Org = {tenant}; fill Password = {password}

# mode: uat
- kind: remote
- env_class: uat
- risk: read-only
- fe_url: https://uat.example.test

#### account: viewer
- role: viewer
- login_method: sso
- sso_note: operator logs in
- can_write: no
""" % (CONN, SECRET, SECRET)

failures = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        failures.append(name)


def run(text, *args):
    d = tempfile.mkdtemp()
    try:
        path = os.path.join(d, "info.md")
        if text is not None:
            with open(path, "w") as fh:
                fh.write(text)
        p = subprocess.Popen([sys.executable, SCRIPT, "--file", path] + list(args),
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=d)
        out, _ = p.communicate()
        return p.returncode, out.decode("utf-8")
    finally:
        shutil.rmtree(d)


def test_c1_missing_file():
    rc, out = run(None, "--mode", "local")
    check("C1 missing file fails", rc == 1, out)
    check("C1 names the path and init", "info.md" in out and "init" in out, out)


def test_c2_all_gaps_at_once():
    text = (GOOD.replace("- db_connection: %s" % CONN, "- db_connection: <ops điền>")
                .replace("- tenant: acme\n", ""))
    rc, out = run(text, "--mode", "local",
                  "--needs", "db,account:member,api:billing")
    check("C2 fails", rc == 1, out)
    for what in ("db_connection", "account[member].tenant", "api_urls.billing"):
        check("C2 reports %s" % what, what in out, out)
    check("C2 gives file:line", "info.md:" in out, out)
    check("C2 says nothing started", "nothing started" in out, out)


def test_c3_unneeded_key_never_blocks():
    text = GOOD.replace("- db_connection: %s" % CONN, "- db_connection: <ops điền>")
    rc, out = run(text, "--mode", "local", "--needs", "account:owner")
    check("C3 passes without db", rc == 0, out)
    check("C3 warns about the placeholder", "warn" in out, out)


def test_c4_only_dev_writes():
    for label in ("staging", "Dev", "prd"):
        text = GOOD.replace("- env_class: dev", "- env_class: %s" % label)
        rc, out = run(text, "--mode", "local", "--needs", "account:owner")
        check("C4 env_class %s with risk free fails" % label,
              rc == 1 and "read-only" in out, out)
    rc, out = run(GOOD, "--mode", "uat", "--needs", "account:viewer")
    check("C4 uat read-only with sso viewer passes", rc == 0, out)
    check("C4 reports READ-ONLY", "READ-ONLY" in out, out)


def test_c5_protected_can_write():
    text = GOOD.replace("- sso_note: operator logs in\n- can_write: no",
                        "- sso_note: operator logs in\n- can_write: yes")
    rc, out = run(text, "--mode", "uat", "--needs", "account:viewer")
    check("C5 can_write yes outside dev fails",
          rc == 1 and "account[viewer].can_write" in out, out)


def test_c6_recipe_keys():
    rc, out = run(GOOD, "--mode", "local", "--needs", "account:member")
    check("C6 recipe account with all keys passes", rc == 0, out)
    text = GOOD.replace("- user: 100\n", "")
    rc, out = run(text, "--mode", "local", "--needs", "account:owner")
    check("C6 no recipe needs user", rc == 1 and "account[owner].user" in out, out)
    rc, out = run(GOOD, "--mode", "local", "--needs", "account:member")
    check("C6 recipe account does not need user", "account[member].user" not in out, out)


def test_c7_no_secret_printed():
    for args in (("--mode", "local", "--needs", "db,account:owner,account:member"),
                 ("--list-accounts", "--mode", "local"),
                 ("--list-modes",)):
        rc, out = run(GOOD, *args)
        check("C7 %s prints no secret" % args[0],
              SECRET not in out and "s3cr3t" not in out and "conn-secret" not in out,
              out)


def test_c8_unknown_account():
    rc, out = run(GOOD, "--mode", "local", "--needs", "account:auditor")
    check("C8 unknown account fails", rc == 1, out)
    check("C8 lists the known accounts", "owner (admin)" in out and "member" in out, out)
    rc, out = run(GOOD, "--mode", "local", "--needs", "account:admin")
    check("C8 a role resolves to its account", rc == 0, out)


def test_c9_default_path():
    d = tempfile.mkdtemp()
    try:
        subprocess.check_call(["git", "init", "-q", d])
        sub = os.path.join(d, "a", "b")
        os.makedirs(sub)
        out = subprocess.check_output([sys.executable, SCRIPT, "--default-path"],
                                      cwd=sub).decode("utf-8").strip()
        want = os.path.join(".claude", "claude", "docs", "probe-live", "info.md")
        check("C9 default path is under the repo root",
              out.endswith(want) and os.path.realpath(os.path.dirname(
                  os.path.dirname(os.path.dirname(os.path.dirname(
                      os.path.dirname(out)))))) == os.path.realpath(d), out)
    finally:
        shutil.rmtree(d)


def test_c10_wrong_heading_level():
    old = GOOD.replace("#### account:", "### account:")
    rc, out = run(old, "--mode", "local", "--needs", "account:owner")
    check("C10 an H3 account fails", rc == 1 and "wrong level" in out, out)
    check("C10 the failure prints no secret", "s3cr3t" not in out, out)
    old = GOOD.replace("# mode:", "## mode:")
    rc, out = run(old, "--mode", "local")
    check("C10 an H2 mode fails", rc == 1 and "wrong level" in out, out)
    rc, out = run("# Title\n\n" + GOOD, "--mode", "local", "--needs", "account:owner")
    check("C10 an H1 title before the modes is prose", rc == 0, out)


def main():
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
