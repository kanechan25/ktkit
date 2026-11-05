<!-- group: Verify | order: 75 -->
# ktkit:probe — check live behaviour in an isolated Chrome, with evidence, then clean up

Opens the running system through the Chrome DevTools MCP and checks what the session asked about,
saving a screenshot and the API JSON for every step. **Where** and **with what** come from one file per
repository, `<repo>/.claude/claude/docs/probe-live/info.md`; **what** comes from the conversation.

```
/ktkit:probe [--mode <name>] [--no-cleanup] [<info-file>]
/ktkit:probe init
/ktkit:probe cleanup <ledger>
```

| Argument | Meaning |
| -------- | ------- |
| `--mode <name>` | the `# mode:` to use; never defaulted — named in the session, or asked |
| `--cleanup` | the default: ask once at the end, then close, kill and stop what this run started |
| `--no-cleanup` | leave everything running; print a hand-over table with the stop commands |
| `init` | scaffold the info file for this repository |
| `cleanup <ledger>` | clean up what an earlier `--no-cleanup` run kept |

## The cases

```bash
# localhost, one account, compare the screen with the database
/ktkit:probe --mode local

# UAT with two accounts — read-only, whatever the request says
/ktkit:probe --mode uat

# keep Chrome and the services up to look at by hand afterwards
/ktkit:probe --mode local --no-cleanup
```

## What it guarantees

- **Nothing starts until the info file covers this probe.** Every gap — a database string the
  comparison needs, a key the login recipe uses — is reported in one table with `file:line`.
- **Only `env_class: dev` may change state.** Every other environment is read-only; a write button is
  not clicked even when asked.
- **A new isolated Chrome context per account**, and a server that must run with `--isolated`.
- **It asks where evidence goes** before anything starts.
- **It only stops what its ledger says it started.** What was already running is reused, never killed.

## Do not

| Anti-pattern | Why |
| ------------ | --- |
| Put the requirement in the info file | The file says where and with what; the session says what. |
| Commit the info file | It holds passwords inline. |
| Expect a kept Chrome to outlive the session | The MCP server closes the browser it launched when the session ends. |

## See also

`/ktkit:confirm-with-me` gates one irreversible step; this skill has no unlock for writes outside dev.
