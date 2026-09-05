#!/usr/bin/env python3
"""Probe every capability a run will need, before it spends a single token.

A run that discovers halfway through that `gh` cannot reach the network, or that
the output directory is not writable, has already paid for the agents it
dispatched and still cannot finish. This gate is cheap and idempotent: it asks
every question up front, prints one line per capability, and exits non-zero if
any of them failed, so the caller stops before spawning anything.

Shared by every skill in this plugin. `docs-review` needs the runtime, write and
read groups; `spec-recon` needs those plus vcs and forge.

Two lessons are wired into this file and must not be undone:

  * `gh auth status` is NOT a usable gate. Inside the Claude Code sandbox it
    prints "The token in keyring is invalid" for a token that is perfectly
    valid, because `gh` is a Go binary that verifies certificates through the
    macOS Security framework and the sandbox denies it. The real check is to
    take a token and make one request with a client that does not use that
    framework. A tool's error message is not evidence about its own cause.

  * The same sandbox denies the SSH agent socket, so `git ls-remote` against an
    SSH remote fails with a broken pipe. That is NOT proof the remote is
    unreachable, and a caller must never turn it into "the branch does not
    exist". It is reported as SKIP, never as FAIL.

Usage
    preflight.py --groups runtime,write,read,vcs,forge,artifacts,speckit,mcp [options]

    --out <dir>        directory the run will write to (group: write)
    --inputs <p> [..]  paths the run will read (group: read)
    --repo <dir>       repository root (groups: vcs, forge, artifacts, speckit)
    --report <path>    also write the table here, e.g. <base>/steps/00-preflight.md
    --json             emit machine-readable results instead of the table

Output, one line per capability:
    PASS  python3 stdlib      zipfile, xml.etree.ElementTree, hashlib, json
    FAIL  forge token         -> gh auth login -h github.com --scopes repo
    SKIP  git remote (ssh)    ssh agent denied by sandbox; forge API used instead

Exit status
    0  no FAIL rows
    1  at least one FAIL row
    2  the arguments themselves are unusable

A SKIP is a capability that is unavailable for a reason the run can work around.
It never blocks. Whoever consumes a SKIP must degrade honestly: the questions it
would have answered become `not-accessed`, never `missing` and never guessed.
"""
import argparse
import json as jsonlib
import os
import subprocess
import sys

GROUPS = ("runtime", "write", "read", "vcs", "forge",
          "artifacts", "speckit", "mcp")

# Every skill in this plugin writes its artifacts here, and nowhere else. The
# path is a rule, not a discovery: a repository that does not have the directory
# gets one, and no skill ever probes for an alternative layout. Creating a
# missing directory is the only filesystem change this gate is allowed to make.
ARTIFACT_ROOT = os.path.join(".claude", "claude")
ARTIFACT_DIRS = ("prompts", "analyze", "specs", "pipeline", "implemented",
                 "compacts")

# speckit is a separate toolkit with its own lifecycle. This plugin never ships
# it and never vendors it: `.specify/` is scaffolding that lives inside the
# repository being worked on, so no plugin can supply it on the user's behalf.
SPECKIT_SCAFFOLD = ".specify"
SPECKIT_SKILL = os.path.join("~", ".claude", "skills", "speckit.specify")

# The transport used for every forge request. Deliberately not `gh api`: see the
# module docstring. urllib goes through OpenSSL and works where `gh` does not.
API_ROOT = "https://api.github.com"
UA = "ktkit-preflight"

# Scopes that let a token read issues, pull requests and milestones. Nothing
# here asks for write access -- these skills only read the forge, and demanding
# a broader scope would widen the blast radius of a token for no benefit.
READ_SCOPES = ("repo", "public_repo")


class Result(object):
    def __init__(self, status, name, detail):
        self.status = status          # PASS | FAIL | SKIP
        self.name = name
        self.detail = detail          # a fix command when FAIL, a reason when SKIP

    def line(self):
        return "%-4s  %-22s %s" % (self.status, self.name, self.detail)

    def as_dict(self):
        return {"status": self.status, "name": self.name, "detail": self.detail}


def run(cmd, timeout=20):
    """Run a command, returning (rc, stdout, stderr). Never raises.

    `timeout` is passed to subprocess rather than the `timeout` binary, which
    does not exist on macOS.
    """
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (OSError, ValueError) as exc:
        return 127, "", str(exc)
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        out, err = p.communicate()
        return 124, _dec(out), "timed out after %ss" % timeout
    return p.returncode, _dec(out), _dec(err)


def _dec(b):
    if isinstance(b, bytes):
        return b.decode("utf-8", "replace").strip()
    return (b or "").strip()


def have(binary):
    rc, _, _ = run(["/usr/bin/env", "which", binary], timeout=10)
    return rc == 0


# --------------------------------------------------------------------------
# groups
# --------------------------------------------------------------------------

def check_runtime():
    out = []
    if sys.version_info < (3, 6):
        out.append(Result("FAIL", "python3", "need >= 3.6, have %s" %
                          ".".join(str(x) for x in sys.version_info[:3])))
        return out
    missing = []
    for mod in ("zipfile", "xml.etree.ElementTree", "hashlib", "json",
                "urllib.request", "ssl"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        out.append(Result("FAIL", "python3 stdlib",
                          "missing: %s -> reinstall python3" % ", ".join(missing)))
    else:
        out.append(Result("PASS", "python3 stdlib",
                          "%s, zipfile, ElementTree, hashlib, json, urllib, ssl"
                          % ".".join(str(x) for x in sys.version_info[:3])))
    return out


def check_write(out_dir):
    res = []
    if not out_dir:
        return [Result("FAIL", "write target", "--out is required for group 'write'")]
    target = os.path.abspath(out_dir)
    try:
        for sub in ("", "steps", "evidence"):
            d = os.path.join(target, sub) if sub else target
            if not os.path.isdir(d):
                os.makedirs(d)
        probe = os.path.join(target, ".preflight-probe")
        with open(probe, "w") as fh:
            fh.write("ok\n")
        os.remove(probe)
        res.append(Result("PASS", "write --out", target))
    except (OSError, IOError) as exc:
        res.append(Result("FAIL", "write --out",
                          "%s -> the sandbox may deny writes outside the repo; "
                          "run /sandbox or point --out inside it (%s)"
                          % (target, exc)))
    return res


def check_read(inputs):
    res = []
    if not inputs:
        return [Result("SKIP", "read inputs", "no --inputs given")]
    bad = []
    for p in inputs:
        if not os.path.exists(p):
            bad.append("%s (does not exist)" % p)
        elif not os.access(p, os.R_OK):
            bad.append("%s (not readable)" % p)
    if bad:
        res.append(Result("FAIL", "read inputs", "; ".join(bad)))
    else:
        res.append(Result("PASS", "read inputs", "%d path(s) readable" % len(inputs)))
    return res


def check_vcs(repo):
    """git itself, plus whether the remote is reachable.

    An SSH remote that fails inside the sandbox is a SKIP, not a FAIL: the forge
    API reaches the same data over HTTPS, and treating it as a hard failure
    would stop runs that can complete.
    """
    res = []
    if not have("git"):
        return [Result("FAIL", "git", "not installed -> install git")]
    rc, out, _ = run(["git", "-C", repo or ".", "rev-parse", "--show-toplevel"])
    if rc != 0:
        return [Result("SKIP", "git repo", "%s is not a git work tree" % (repo or "."))]
    res.append(Result("PASS", "git repo", out))

    rc, url, _ = run(["git", "-C", repo or ".", "remote", "get-url", "origin"])
    if rc != 0:
        res.append(Result("SKIP", "git remote", "no 'origin' remote"))
        return res
    is_ssh = url.startswith("git@") or url.startswith("ssh://")
    rc, _, err = run(["git", "-C", repo or ".", "ls-remote", "--heads", "origin"],
                     timeout=25)
    if rc == 0:
        res.append(Result("PASS", "git ls-remote", url))
    elif is_ssh:
        res.append(Result("SKIP", "git remote (ssh)",
                          "%s unreachable here (%s); the sandbox denies the ssh "
                          "agent -- use the forge API, and report anything it "
                          "cannot answer as not-accessed"
                          % (url, err.splitlines()[0] if err else "no detail")))
    else:
        res.append(Result("FAIL", "git ls-remote",
                          "%s -> %s" % (url, err.splitlines()[0] if err else "failed")))
    return res


def forge_token():
    """Find a token without ever asking `gh` to touch the network.

    Order matters: an explicit environment variable beats the keyring, because
    that is how CI and a deliberate override both work.
    """
    for var in ("GH_TOKEN", "GITHUB_TOKEN"):
        val = os.environ.get(var, "").strip()
        if val:
            return val, var
    if have("gh"):
        rc, out, _ = run(["gh", "auth", "token"], timeout=15)
        if rc == 0 and out:
            return out, "gh auth token"
    return None, None


def check_forge(repo):
    """Prove the forge is reachable by making one real request.

    Never `gh auth status`, never "is the binary installed". Both answer a
    different question than the one that matters.
    """
    res = []
    token, source = forge_token()
    if not token:
        return [Result("FAIL", "forge token",
                       "no GH_TOKEN, no GITHUB_TOKEN, no gh keyring token -> "
                       "gh auth login -h github.com --scopes repo,read:org")]
    res.append(Result("PASS", "forge token", "from %s" % source))

    try:
        import urllib.request
    except ImportError:
        return res + [Result("FAIL", "forge api", "urllib unavailable")]

    req = urllib.request.Request(
        API_ROOT + "/rate_limit",
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": UA})
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        body = jsonlib.loads(resp.read().decode("utf-8"))
        scopes = resp.headers.get("X-OAuth-Scopes") or ""
    except Exception as exc:                                  # noqa: BLE001
        return res + [Result("FAIL", "forge api",
                             "GET /rate_limit failed (%s: %s) -> check network, "
                             "then the token" % (type(exc).__name__, exc))]

    core = body.get("resources", {}).get("core", {})
    res.append(Result("PASS", "forge api",
                      "rate limit %s/%s remaining"
                      % (core.get("remaining", "?"), core.get("limit", "?"))))

    have_scopes = set(s.strip() for s in scopes.split(",") if s.strip())
    if have_scopes & set(READ_SCOPES):
        res.append(Result("PASS", "forge scopes", scopes))
    elif not scopes:
        # Fine-grained tokens send no X-OAuth-Scopes header at all. Absence is
        # not proof of insufficiency, so this cannot be a FAIL.
        res.append(Result("SKIP", "forge scopes",
                          "no X-OAuth-Scopes header (fine-grained token); "
                          "permissions will show up as 403 on first use"))
    else:
        res.append(Result("FAIL", "forge scopes",
                          "have '%s', need one of %s -> gh auth login -h "
                          "github.com --scopes repo,read:org"
                          % (scopes, " or ".join(READ_SCOPES))))
    return res


def check_artifacts(repo):
    """Make the plugin's artifact root exist, and prove it can be written to.

    This is the one place the layout rule is enforced. A skill that asks for
    this group may then write under `<repo>/.claude/claude/<area>/` without
    checking anything, and must never write outside `<repo>/.claude/`.
    """
    root = os.path.abspath(os.path.join(repo or ".", ARTIFACT_ROOT))
    made = []
    try:
        for sub in ARTIFACT_DIRS:
            d = os.path.join(root, sub)
            if not os.path.isdir(d):
                os.makedirs(d)
                made.append(sub)
        probe = os.path.join(root, ".preflight-probe")
        with open(probe, "w") as fh:
            fh.write("ok\n")
        os.remove(probe)
    except (OSError, IOError) as exc:
        return [Result("FAIL", "artifact root",
                       "%s not writable (%s) -> run from the repository root, "
                       "or /sandbox to allow writes there" % (root, exc))]
    detail = root if not made else "%s (created %s)" % (root, ", ".join(made))
    return [Result("PASS", "artifact root", detail)]


def check_speckit(repo):
    """Both halves of speckit, reported separately because they fail apart.

    The scaffolding is per-repository and the skills are per-machine, so a user
    can easily have one and not the other. Each missing half gets its own fix,
    and either one is a FAIL: a run that calls `/speckit.plan` without them
    burns tokens up to the point of the call and then cannot continue.

    A FAIL here stops the run. It never degrades to the internalised path on its
    own -- silently delivering a different thing under the same name is how a
    workflow loses the user's trust. The internalised path is reached only when
    the caller passes `--no-speckit`, which skips this group entirely. That flag
    means "take the internalised path", not "check less": it holds even on a
    machine where both halves are present.
    """
    res = []
    scaffold = os.path.abspath(os.path.join(repo or ".", SPECKIT_SCAFFOLD))
    if os.path.isdir(scaffold):
        res.append(Result("PASS", "speckit scaffolding", scaffold))
    else:
        res.append(Result("FAIL", "speckit scaffolding",
                          "no %s in this repository -> run `specify init` at the "
                          "repository root, or re-run the skill with --no-speckit"
                          % SPECKIT_SCAFFOLD))
    skill = os.path.expanduser(SPECKIT_SKILL)
    if os.path.isdir(skill):
        res.append(Result("PASS", "speckit skills", skill))
    else:
        res.append(Result("FAIL", "speckit skills",
                          "%s not installed -> install the speckit skills, or "
                          "re-run the skill with --no-speckit" % SPECKIT_SKILL))
    return res


def check_mcp():
    """The transport for the MCP server this plugin ships in `.mcp.json`.

    The server itself is the plugin's responsibility, not the user's, so a
    failure here is never "go and install it" -- installing a second copy by
    hand produces a differently-named tool that the skills do not call. What can
    actually break is the runner: `npx` fetches the package on first use, so no
    `npx` and no network means no server. Say that, and say it as an environment
    fault.
    """
    if have("npx"):
        return [Result("PASS", "npx (mcp runner)",
                       "ktkit ships sequential-thinking via .mcp.json")]
    return [Result("FAIL", "npx (mcp runner)",
                   "npx not found -> install Node.js. The plugin ships the "
                   "sequential-thinking server itself; do not add a second copy "
                   "by hand, its tool would have a different name")]


CHECKS = {
    "runtime": lambda a: check_runtime(),
    "write": lambda a: check_write(a.out),
    "read": lambda a: check_read(a.inputs),
    "vcs": lambda a: check_vcs(a.repo),
    "forge": lambda a: check_forge(a.repo),
    "artifacts": lambda a: check_artifacts(a.repo),
    "speckit": lambda a: check_speckit(a.repo),
    "mcp": lambda a: check_mcp(),
}


def render(results, groups):
    lines = ["# Preflight", "",
             "Groups probed: %s" % ", ".join(groups), "",
             "```text"]
    lines += [r.line() for r in results]
    lines += ["```", ""]
    fails = [r for r in results if r.status == "FAIL"]
    skips = [r for r in results if r.status == "SKIP"]
    if fails:
        lines.append("**%d FAIL - do not spawn any agent.** Fix these, then run "
                     "again; this gate is cheap and idempotent." % len(fails))
    else:
        lines.append("**No FAIL.** The run may proceed.")
    if skips:
        lines.append("")
        lines.append("%d SKIP - available capability is narrower than the full set. "
                     "Every question these would have answered must be reported as "
                     "`not-accessed` with the reason, never as a finding and never "
                     "guessed." % len(skips))
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--groups", default="runtime,write,read")
    ap.add_argument("--out")
    ap.add_argument("--inputs", nargs="*", default=[])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--report")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    groups = [g.strip() for g in a.groups.split(",") if g.strip()]
    unknown = [g for g in groups if g not in CHECKS]
    if unknown:
        sys.stderr.write("unknown group(s): %s; known: %s\n"
                         % (", ".join(unknown), ", ".join(GROUPS)))
        return 2

    results = []
    for g in groups:
        results.extend(CHECKS[g](a))

    if a.json:
        sys.stdout.write(jsonlib.dumps([r.as_dict() for r in results], indent=1) + "\n")
    else:
        for r in results:
            sys.stdout.write(r.line() + "\n")

    if a.report:
        d = os.path.dirname(os.path.abspath(a.report))
        if d and not os.path.isdir(d):
            try:
                os.makedirs(d)
            except OSError:
                pass
        try:
            with open(a.report, "w") as fh:
                fh.write(render(results, groups))
        except (OSError, IOError) as exc:
            sys.stderr.write("could not write --report %s: %s\n" % (a.report, exc))

    return 1 if any(r.status == "FAIL" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
