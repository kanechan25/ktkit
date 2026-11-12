# The probe info file

One file per repository, at `<repo>/.claude/claude/docs/probe-live/info.md`. Every environment is an H1
`# mode: <name>` section in that one file; every account of a mode is an H4 `#### account: <label>`
section under it. Each setting is one `- key: value` line. Any other H1 ends the mode, and fenced
code blocks are ignored, so the file can carry its own notes. A `mode:` or `account:` heading at any
other level (the old `## mode:` / `### account:` layout) fails the check rather than being skipped.

A value containing `<...>` is a placeholder: unfilled. `check_info.py` treats it as missing.

The file holds passwords and connection strings inline, by design: it stays on the operator's machine.
It must be outside git or in `.gitignore`; `check_info.py` prints a red line when git tracks it. A file
behind a symlink that points outside the repository is not tracked, and that is fine.

## Mode keys

| Key | Required | Meaning |
| --- | -------- | ------- |
| `fe_url` | always | the URL opened in Chrome |
| `kind` | always | `host-local` · `docker-local` · `remote`. Docker is used only for `docker-local` |
| `env_class` | always | `dev` or any other label. **Only the exact `dev` may write**; everything else, typos included, is read-only. Declared, never inferred from the mode name or host |
| `risk` | always | `free` (only with `env_class: dev`) · `read-only` (mandatory otherwise) |
| `api_urls` | when the probe compares an API | `name=url, name=url` |
| `swagger_url` | when the probe reads it | |
| `start_cmds` | optional | each command and the port it opens. Absent ⇒ the probe derives it from the repository (scripts, docs, lockfile) and cites the line |
| `ports` | local kinds | the ports to check before starting; used to find what is already running |
| `stop_cmds` | optional | the repository's own stop command for what `start_cmds` started; cleanup prefers it |
| `docker_compose` | optional | the repository's start wrapper; never a volume-removing command |
| `healthcheck` | optional | URL and expected status |
| `default_account` | optional | the account label used when the requirement names none |
| `db_type` | when the probe needs the DB | free text: `postgres`, `mysql`, `sqlite`, `none`... Only `postgres` has a read-only adapter |
| `db_connection` | when the probe needs the DB and `db_type` is not `none` | inline connection string; never printed |
| `db_access` | optional | always `read-only` |
| `viewport` | optional | otherwise Chrome's default |
| `write_action_hints` | optional | extra write-button words for this repository's UI language |
| `auth_url_patterns` | optional | login endpoints exempt from the write-request check; default `login, signin, auth, token, session` |
| `evidence_base` | optional | the root the evidence question proposes under (absent ⇒ `<repo>/.claude/claude/probe-live/`); still always asked, and a folder the operator names always wins |

Database needed or not is decided per probe. Not needed and still a placeholder ⇒ a yellow warning,
never a stop.

## Account keys

| Key | Required | Meaning |
| --- | -------- | ------- |
| `role` | always | business role; the session may name an account by label or by role. A role several accounts share resolves to the first in the file |
| `login_method` | always | `password` · `sso` · `none` |
| `can_write` | always | `yes` · `no`. Every account of a non-`dev` mode must say `no` |
| `login_url` | optional | otherwise found from `fe_url` with `take_snapshot` |
| `login_recipe` | optional | the login in words, with `{key}` placeholders taken from this account |
| `user`, `password`, any key | with `password` login | every key the recipe names; no recipe ⇒ `user` + `password` |
| `sso_note` | with `sso` login | who logs in by hand |
| `note` | optional | free text |

## An example from an invented repository

Values are made up to show the shape, not facts about any system.

```markdown
# mode: local
- kind: host-local
- env_class: dev
- risk: free
- fe_url: http://localhost:5173
- start_cmds: pnpm dev (opens 5173)
- ports: 5173
- db_type: none
- default_account: member

#### account: member
- role: member
- login_method: password
- email: member@example.test
- tenant: acme
- password: <ops điền>
- can_write: yes
- login_recipe: open /signin; fill Email = {email}; fill Workspace = {tenant}; fill Password = {password}; click Sign in

# mode: staging
- kind: remote
- env_class: staging
- risk: read-only
- fe_url: https://staging.example.test
- default_account: auditor

#### account: auditor
- role: viewer
- login_method: sso
- sso_note: the operator logs in by hand
- can_write: no
```

The skill does not know what `email` or `tenant` mean; it substitutes them into the recipe and carries
it out with `take_snapshot`, `fill` and `click`.
