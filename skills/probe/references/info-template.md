# The skeleton `init` writes

`init` copies the block below into `<repo>/.claude/claude/docs/probe-live/info.md`, replacing a
`<ops điền>` only with a value `init_scan.py` proved from a file in the repository, and adding one
mode per environment the operator names. Never a guessed port, URL or database name.

```markdown
# Probe info — <repository name>

> Holds passwords and connection strings inline. Keep this file out of git (or in .gitignore).
> One `## mode:` per environment. Values in `<...>` are unfilled; the probe stops on the ones it needs.
> Keys: references/info-schema.md of /ktkit:probe.

## mode: local
- kind: <host-local | docker-local>          # how this mode runs
- env_class: dev                              # only `dev` may write
- risk: free                                  # free only with env_class dev
- fe_url: <ops điền>                          # opened in Chrome
- api_urls: <name=url, name=url>              # only when a probe compares an API
- ports: <ops điền>                           # checked before anything starts
- start_cmds: <ops điền>                      # how to start what is not running
- stop_cmds: <optional>                       # the repository's own stop command
- db_type: <postgres | mysql | none | ...>    # only when a probe compares with the DB
- db_connection: <ops điền>                   # inline, never printed
- db_access: read-only
- default_account: <label>

### account: <label>
- role: <business role>
- login_method: <password | sso | none>
- user: <ops điền>
- password: <ops điền>
- can_write: <yes | no>
- login_recipe: <optional: fill X = {user}; fill Y = {password}; click Z>

## mode: <remote environment>
- kind: remote
- env_class: <uat | prod | ...>               # anything but dev is read-only
- risk: read-only
- fe_url: <ops điền>
- default_account: <label>

### account: <label>
- role: viewer
- login_method: <password | sso>
- user: <ops điền>
- password: <ops điền>
- can_write: no                               # mandatory outside dev
```
