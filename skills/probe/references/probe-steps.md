# Evidence, ledger, hand-over

## Evidence folder

The folder the operator confirmed in P4. Files are numbered by step and never overwritten; a folder
that already has files continues the numbering.

```
<evidence>/
  ledger.md
  01-<account>-<what>-input.png
  02-<account>-<what>-result.png
  02-<account>-<endpoint>.json        # get_network_request body, the step's number
  ...
  report.md                           # optional: the P8 report, each row pointing at a file above
```

- One screenshot of the state before the action, one after, and the JSON of every API response the
  conclusion relies on.
- Strip `Authorization`, `Cookie`, `Set-Cookie` and token fields from saved JSON.
- After `fill` on a password field, check the snapshot: a visible value is not saved as evidence.
- Every row of the report table names its file. A row without one is not a conclusion.

## Ledger

Under `--no-evidence` there is no evidence folder; the ledger alone goes to
`<repo>/.claude/claude/probe-live/<yyyymmdd>/probe-<slug>/ledger.md`, first line
`evidence: none (--no-evidence)`.

`<evidence>/ledger.md`. The first line is the evidence path. Then one row per thing touched, appended
**before** it is started:

```markdown
evidence: <path>
| time | kind | id | port | command | state |
| ---- | ---- | -- | ---- | ------- | ----- |
| 2026-01-01T10:00:00 | process | 4242 | 5173 | pnpm dev | STARTED |
| 2026-01-01T10:00:05 | process | 3131 | 3000 | (found running) | PRE-EXISTING |
| 2026-01-01T10:00:09 | container | probe-db | 5432 | docker run --name probe-db ... | STARTED |
| 2026-01-01T10:01:00 | chrome-context | probe-20260101100100-member | - | new_page | STARTED |
```

`kind`: `process` · `container` · `chrome-context`. `state`: `STARTED` (this run started it),
`PRE-EXISTING` (was running before; never touched), `CLEANED` (stopped and measured gone), `KEPT`
(started, left running by `--no-cleanup` or `giữ lại`). No secret ever goes in the command column:
write `<redacted>` in its place.

Cleanup reads only this file. A process, container or page that is not a `STARTED`/`KEPT` row here is
not this run's, whatever it looks like.

## Hand-over table (`--no-cleanup` or `giữ lại`)

Measured with `list_pages`, `lsof -iTCP:<port> -sTCP:LISTEN` and `docker ps` at hand-over time, never
copied from memory:

| kind | id | port / URL | how to stop |
| ---- | -- | ---------- | ----------- |
| chrome-context | `probe-<ts>-<label>` | the page open | close the window, or `/ktkit:probe cleanup <ledger>` |
| process | PID | port | `kill <PID>`, or the mode's `stop_cmds` |
| container | name | port | `docker stop <name>` |

Then the evidence path, the ledger path, and the line that the Chrome window lives only while this
session's MCP server does.
