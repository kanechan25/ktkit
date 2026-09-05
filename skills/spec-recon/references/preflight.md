# Preflight — the hard gate

Nothing is spawned until this passes. The gate is cheap and idempotent, so running it twice costs
nothing and running it late costs a whole run: a run that discovers halfway through that it cannot
reach the forge has already paid for every agent it dispatched and still cannot finish.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py" \
    --groups runtime,write,read,vcs,forge \
    --out <base> --inputs <paths> --repo <repo> \
    --report <base>/steps/00-preflight.md
```

Exit `1` means at least one `FAIL`. Print the table, print the fix commands, spawn nothing.

## What each group asks

| Group | Asks | Needed by |
| ----- | ---- | --------- |
| `runtime` | python3, and each stdlib module actually used: `zipfile`, `xml.etree.ElementTree`, `hashlib`, `json`, `urllib.request`, `ssl` | every run |
| `write` | can `<base>/`, `<base>/steps/` and `<base>/evidence/` be created and written | every run |
| `read` | is each input path present and readable | every run |
| `vcs` | git present, is this a work tree, is the remote reachable | `--probe …,vcs` |
| `forge` | a token exists, **one real request succeeds**, the scopes allow reading | `--probe …,vcs` |

`--probe code,artifact` needs neither `vcs` nor `forge`, which is what makes a fully offline run
possible with one flag.

## PASS / FAIL / SKIP

**FAIL** blocks. The row carries the command that fixes it, not a description of the problem.

**SKIP** does not block. It means a capability is unavailable for a reason the run can work around.
Whoever consumes a SKIP must degrade honestly: every question it would have answered becomes
`not-accessed` **with the reason attached**, never a finding, never a guess, never silence.

If a capability is needed by only part of the run, its FAIL blocks only that part — and you must
**ask** whether to continue with the rest. Quietly narrowing the scope and then reporting as though
the whole job was done is worse than stopping.

## The forge check, and why it is shaped this way

Three plausible checks are all wrong here:

| Check | Why it fails |
| ----- | ------------ |
| `which gh` | Answers whether a binary exists, which was never the question. |
| `gh auth status` | Inside this sandbox it reports `The token in keyring is invalid` for a token that is completely valid. `gh` is a Go binary that verifies certificates through the macOS Security framework; the sandbox denies it, `gh` fails at the TLS step and attributes it to the keyring. |
| `gh api /rate_limit` | Same TLS failure. Every networked `gh` subcommand dies here. |

The check that works: read the credential with `gh auth token` — which touches the keyring, not the
network — and make **one real request** with `urllib`, which uses OpenSSL and is unaffected.

```text
PASS  forge token            from gh auth token
PASS  forge api              rate limit 5000/5000 remaining
PASS  forge scopes           gist, read:org, repo, workflow
```

A tool's error message is not evidence about its own cause. That is the general form of the lesson,
and it is the same rule the arbitration step applies to absence claims.

**Scopes.** Only `repo` (private) or `public_repo` (public) is required. These skills read the forge
and never write to it; asking for more would widen the blast radius of the token for no benefit.
A fine-grained token sends no `X-OAuth-Scopes` header at all, so an empty header is `SKIP`, not
`FAIL` — absence of the header is not evidence of insufficient permission.

## The vcs check

`git ls-remote` against an **SSH** remote fails in this sandbox: the SSH agent socket is denied.
That is `SKIP`, never `FAIL`, and never evidence about the remote. The forge API reaches the same
facts over HTTPS.

## Fix commands

```text
FAIL  forge token   -> gh auth login -h github.com --scopes repo,read:org
FAIL  write --out   -> sandbox denies writes there; run /sandbox, or move --out inside the repo
FAIL  read inputs   -> the path is missing or unreadable; check it, or drop it from the argument list
FAIL  git           -> install git
FAIL  forge scopes  -> gh auth login -h github.com --scopes repo,read:org
```

## Things that do not exist here

- **`timeout`** is not on macOS. Use `subprocess(timeout=…)` and `urllib(timeout=…)`.
- **`openpyxl`** is not installed and must not be assumed on any machine. Standard library only.
- **`Grep` and `Glob` inside a `Bash` agent.** Granting `Bash` removes them, silently. Set B roles
  search through the shell, where `grep` is a `ugrep` shim honouring `.gitignore`, and the shell is
  zsh, where an unmatched glob aborts the whole command line unless quoted.
