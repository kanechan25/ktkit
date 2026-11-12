---
name: probe
description: "Use when a live behaviour must be checked in a real browser through the Chrome DevTools MCP -- 'probe live', 'verify this on localhost / dev / UAT', 'check the screen with admin then viewer', 'compare what the page shows with the DB' -- or when the user types /ktkit:probe. Reads where and how to probe from <repo>/.claude/claude/docs/probe-live/info.md and what to probe from the session. Checks the info file against what this probe needs before starting anything, opens a fresh isolated Chrome context per account, keeps every environment but dev read-only, always asks where evidence goes unless --no-evidence turns evidence off, records everything it starts in a ledger, and at the end asks before closing, killing and stopping exactly that -- unless --no-cleanup keeps it running with a hand-over table."
argument-hint: "[--mode <name>] [--cleanup (default) | --no-cleanup] [--no-evidence] [<info-file>] | init | cleanup <ledger>"
user-invocable: true
---

# Probe live — `/ktkit:probe $ARGUMENTS`

Check how a running system behaves, in a real browser, with evidence for every step. The info file
says **where** and **with what** (URLs, accounts, database, how to start things). The session says
**what** to probe. Nothing in this skill is specific to one repository: everything that differs
between repositories lives in that repository's info file.

## Arguments

```
/ktkit:probe [--mode <name>] [--no-cleanup] [--no-evidence] [<info-file>]
/ktkit:probe init
/ktkit:probe cleanup <ledger>
```

| Argument | Meaning |
| -------- | ------- |
| `--mode <name>` | the `# mode:` section to use. Absent ⇒ the mode the session just named; none named ⇒ ask. Never default to any mode. |
| `--cleanup` | the default, never needs typing: at the end, ask once, then close, kill and stop what this run started |
| `--no-cleanup` | for this run only: close, kill and stop **nothing**; print a hand-over table instead (`--cleanup=off` is the same) |
| `--no-evidence` | for this run only: no evidence question, no screenshot, no saved JSON, no report file. Conclusions are given in chat, each marked `(no evidence)`. The ledger is still written — cleanup needs it — at `<repo>/.claude/claude/probe-live/<yyyymmdd>/probe-<slug>/ledger.md`, without asking. Every other rule is unchanged |
| `<info-file>` | another info file, for a draft. Default `<repo>/.claude/claude/docs/probe-live/info.md`, `<repo>` = `git rev-parse --show-toplevel` of the cwd |
| `init` | scaffold the info file for this repository; probes nothing, opens no browser |
| `cleanup <ledger>` | clean up what an earlier `--no-cleanup` run left running |

Cleanup and evidence are decided by their flags, **never inferred from prose**. "Khỏi chụp" without
`--no-evidence` is still a default run. "Để đó tao xem" without the flag is
still a default run; the closing question offers `giữ lại` for that.

## Hard rules

1. **Nothing starts before the three preflight tiers pass.** No process, container, Chrome context,
   evidence folder or start command until tier 1, 2 and 3 are all PASS. Before that, only reads. Tiers
   run cheapest first; a failing tier reports **all** of its own gaps at once and the later tiers do
   not run — a later tier's gap surfacing on the rerun is the price of not paying for it twice.
2. **Every environment but `dev` is read-only. No exception, no unlock, no "but the operator asked".**
   Only the exact label `env_class: dev` may change state. Anything else — `uat`, `prod`, `int`,
   `staging`, a typo — is protected. Asked to "just try Save" there ⇒ do not click; say it is read-only
   and that a write must be done by hand outside this skill.
3. **A fresh isolated context, always, one per account.** `new_page` with
   `isolatedContext: probe-<yyyymmddHHMMSS>-<label>`. Never the default tab, never a reused context,
   never logout/login inside one context. Suspect cache ⇒ new context, not a hard reload.
4. **Only the ledger decides what may be closed, killed or stopped.** What was running before this
   run is `PRE-EXISTING`: reuse it, never kill, restart or rebuild it.
5. **Ask before cleaning; ask where evidence goes** (unless `--no-evidence`). "ok rồi, cảm ơn" is not an answer to the cleanup
   question, and "cứ làm đi" is not an answer to the evidence question.
6. **`docker stop` only, by the exact name the ledger recorded.** Never `rm`, `down`, `down -v`, a
   volume removal, or a compose-wide command.
7. **No secret leaves the info file.** No password, connection string or recipe key value in chat,
   ledger, report, screenshot or saved JSON. A snapshot showing a password value is not evidence.
8. **Every conclusion points at an evidence file.** Input screen, result screen, API JSON — numbered by
   step. No evidence ⇒ the conclusion is worthless. Under `--no-evidence` there is none by choice: every
   conclusion says `(no evidence)`, and nothing claims it was saved.

## Phases

P0 load tools → P1 tier 1 → P2 tier 2 → P3 tier 3 → P4 evidence location → P5 start → P6 contexts and
login → P7 probe → P8 report → P9 cleanup gate. P5 onwards only after P1–P3 pass.

### P0 — Load the MCP tools

`ToolSearch` `select:` the tools under **both** prefixes, `mcp__chrome-devtools__` and
`mcp__plugin_chrome-devtools-mcp_chrome-devtools__`: `new_page, list_pages, select_page,
navigate_page, close_page, take_snapshot, take_screenshot, fill, fill_form, click, type_text,
press_key, wait_for, evaluate_script, list_network_requests, get_network_request,
list_console_messages, get_console_message`. Which prefixes exist is measured in P2.

### P1 — Tier 1, the info file (no network, no MCP call)

1. Requirement: read it from the session — the request, the issue or spec being discussed, the route
   or flow. Nothing concrete ⇒ ask **one** question and stop. This is the only question tier 1 asks.
2. Build the needs map from the requirement and the mode. **In doubt, it is needed** — a gap reported
   before anything runs is cheaper than one found half-way.

   | The probe needs | When | `--needs` item |
   | --------------- | ---- | -------------- |
   | an account | the requirement names a label or role, else `default_account` | `account:<label-or-role>` — a role shared by several accounts is the first in the file; the same role twice is two different accounts |
   | the database | it compares the screen with stored data, checks a record, "is it in the DB" | `db` |
   | an API | it compares JSON from a service | `api:<service>` |
   | swagger | it says so | `swagger` |

3. Run, from the repository:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/probe/scripts/check_info.py" --mode <name> --needs <list>
   ```

   It prints one table of **every** gap, each with why this probe needs it and `file:line` to fix —
   including every `{key}` an account's `login_recipe` uses that the account does not fill.
   FAIL ⇒ print the table as it is, stop. Do not report the first gap only; do not start anything to
   "see what else is missing". Missing file ⇒ say exactly that, suggest `/ktkit:probe init`, stop —
   tier 2 does not run.
   - `--list-accounts --mode <name>` prints `label · role · can_write` when an account named in the
     session matches nothing: show it and ask one question. Never substitute another account, and
     never use a `can_write: yes` account for a read when a `no` account fits.
   - A red "git tracks this file" line is printed as it is.
4. Print the needs map with its reasons, e.g. `DB: needed (requirement: "so số liệu với DB")`, so a
   wrong inference is corrected now.

### P2 — Tier 2, tools

| # | Check | How | FAIL |
| - | ----- | --- | ---- |
| A1 | Node and `npx` | `node -v`, `command -v npx` | report, stop |
| A2 | Chrome installed | look it up for this OS (macOS app bundle; `google-chrome`/`chromium` on PATH on Linux); never assume a path | report, stop |
| A3 | MCP registered | P0 found the tools under at least one prefix | print `claude mcp add ...` for the operator to run; never install or reconfigure |
| A4 | MCP alive | `list_pages` (creates nothing); quote the error on failure | stop |
| A5 | One server chosen | both prefixes present ⇒ pick the one whose server passes A6, name it in the report, use only that one | — |
| A6 | Server isolated | read its launch args: `claude mcp get <server-name>` prints `Args:`; else user `~/.claude.json` `mcpServers`, the repo's `.mcp.json`, or the running process with `ps`. PASS only with `--isolated`. FAIL on `--browserUrl`/`-u`, `--wsEndpoint`/`-w`, `--autoConnect`, `--userDataDir` (any spelling) **and on no flag at all** — without `--isolated` the server uses one fixed profile every session shares. Args not findable ⇒ FAIL, say so | stop |
| A7 | Sandbox | `lsof`, `curl` to localhost and `docker` may need the harness's sandbox bypass; follow the harness, say so in one line, never widen permissions yourself | — |

Isolation is this skill's own job: it passes `isolatedContext` itself and never relies on a hook.

### P3 — Tier 3, live checks that start nothing

- **B3** `kind: remote` ⇒ `curl -sI <fe_url>` returns a status (not DNS failure or timeout).
- **B5** `host-local`/`docker-local` ⇒ `lsof -iTCP:<port> -sTCP:LISTEN` for each port in `ports`. Held ⇒
  record the holder as `PRE-EXISTING`. Held by something unknown that the start command needs ⇒
  report, never kill. Free ⇒ resolve how to start it (below); nothing in the repository starts it ⇒
  ask one question now, not in P5.
- **Start command.** `start_cmds` filled ⇒ use it. Absent or a placeholder ⇒ **work it out from the
  repository, do not stop**: run `python3 "${CLAUDE_PLUGIN_ROOT}/skills/probe/scripts/init_scan.py"`, read the repository's own
  `CLAUDE.md`/`AGENTS.md`/`README`, and match each free port to the script, project or target that
  opens it (a `--port`/`-p` flag, a `launchSettings.json` URL, a config naming the port, a doc saying
  "FE on 3100"). The package manager is the lockfile's (`pnpm-lock.yaml` ⇒ `pnpm`, `yarn.lock` ⇒
  `yarn`, `package-lock.json` ⇒ `npm`), run in the directory that holds that `package.json`. Every
  derived command carries the `file:line` it came from and is shown in the "will probe" table; a port
  no source ties to a command is the only thing asked, in one question for all of them.
- **B8** the database, only when `db` is needed: read-only connection and `select 1`, print the DB name
  and the read-only state, never the connection string. A database that `start_cmds` itself brings up
  is checked statically here and connected to right after it is up (B8b), before anything else starts;
  failure there ⇒ stop and clean up exactly what was started.
- `KEPT` rows from an earlier ledger still alive ⇒ one line "N things KEPT from <ledger>", treat them
  as `PRE-EXISTING`.

Database access is read-only, always. `postgres`: connect with
`PGOPTIONS='-c default_transaction_read_only=on'`. Any other `db_type` has no read-only adapter: say so
in the report, run only `SELECT`/`SHOW`/`DESCRIBE`/`EXPLAIN` checked before execution, and never write
syntax for an engine from memory.

Then print the "will probe" table: mode · URL · accounts · access (free / READ-ONLY) · DB needed
(why) · what will start · what cleanup will do.

### P4 — Ask where evidence goes (always, before anything starts)

`--no-evidence` ⇒ skip this phase: create only the ledger folder named in the arguments table, write
its first line as `evidence: none (--no-evidence)`, and go on to P5.

> Evidence lưu ở đâu? Đề xuất: `<evidence_base>/<yyyymmdd>/probe-<slug>/evidence/` — `yes` để dùng, hoặc
> gửi folder khác.

Which path is proposed, first match wins:

1. a folder the operator already named in this session for this probe;
2. the mode's `evidence_base`: `<evidence_base>/<yyyymmdd>/probe-<slug>/evidence/`;
3. the default: `<repo>/.claude/claude/probe-live/<yyyymmdd>/probe-<slug>/evidence/`.

The default is only a proposal. A folder the operator names — in the session or in reply to this
question — is where evidence goes, used verbatim, with no layer added, even outside the repository.
`<slug>` comes from the requirement (issue number, screen or route name); neither stated ⇒ the
time `HHMMSS`, never an invented name. Existing files are never overwritten, numbering continues.
No answer ⇒ nothing starts. The chosen path is the first line of `ledger.md` in that folder.

### P5 — Start what is missing

Only what B5 found absent, only with the command resolved in P3 — `start_cmds`, or the one derived
from the repository with its source. A container only when
`kind: docker-local`; a `host-local` mode never gets one, not even "just for the database" — report
what is missing instead. Processes started here are not tied to this session: they outlive it unless
P9 stops them.
Before each start, append a ledger row (format in `references/probe-steps.md`): time · kind
(`process`/`container`/`chrome-context`) · id (PID / container name / context name) · port · command ·
`STARTED`. Wait for `healthcheck` when declared.

### P6 — Contexts and login

One `new_page` per account, `isolatedContext: probe-<yyyymmddHHMMSS>-<label>`, each a ledger row.
Log in inside that context with that account's keys: follow `login_recipe`, replacing `{key}` with the
account's values; no recipe ⇒ read the form with `take_snapshot` and use `user` + `password`, asking if
unsure. `sso` ⇒ stop and wait for the human named in `sso_note`. Credentials come from the info file
only — never search elsewhere.

### P7 — Probe, with evidence per step

`--no-evidence` ⇒ no `take_screenshot` and no saved JSON. `take_snapshot` and `get_network_request`
are still read — to act safely and to read the answer — but nothing is written to disk.

For every step that feeds a conclusion: screenshot of the input state, screenshot of the result, and
the API response JSON from `get_network_request` — numbered, named as in `references/probe-steps.md`.

Read-only mode, before every `click`, `fill`, `press_key`, `type_text`: `take_snapshot`, read the
target's label. A write action — the defaults below plus the mode's `write_action_hints` — or anything
ambiguous ⇒ do not act; record "skipped: read-only". Defaults: save, submit, delete, remove, create,
add, update, edit, upload, import, approve, reject, confirm, publish, send, apply, register; 保存,
削除, 登録, 更新, 送信, 承認, 確定, 追加; lưu, xóa, gửi, tạo, cập nhật, duyệt, xác nhận. Never
`evaluate_script` a `fetch` or `XMLHttpRequest` with a write method there.

### P8 — Report

Numbers and evidence paths first (`--no-evidence`: numbers, each conclusion marked `(no evidence)`,
and no `report.md`). In read-only mode, end with `list_network_requests`: any method other
than GET/HEAD/OPTIONS to a URL outside `auth_url_patterns` (default `login, signin, auth, token,
session`) ⇒ a **red first line** in the report. Never hidden.

### P9 — Cleanup gate (the last step, also after a failure or an abort)

**Default (`--cleanup`)** — one question per turn, repeated each turn until it gets a real answer,
listing from the ledger:

> Probe xong, evidence ở `<path>` (`--no-evidence`: ledger ở `<path>`). Tôi sẽ đóng context `<names>`, kill `<PID/port>`, stop container
> `<names>`. Dọn hết chứ? (`giữ lại` để để nguyên và nhận lệnh dọn)

- `confirm`/`xong`/`dọn đi` ⇒ `close_page` every `probe-*` page in the ledger → `stop_cmds` when
  declared, else `SIGTERM` by PID → `docker stop <name>` for ledger containers. The evidence folder
  and the ledger stay.
- `giữ lại` ⇒ the hand-over branch below. `chưa` or anything else ⇒ nothing; ask again next turn.
- Then **measure**, never trust an exit code: `list_pages`, `lsof -iTCP:<port>`, `docker ps`. Print
  cleaned / still running (and why: `PRE-EXISTING`, `KEPT`). Mark rows `CLEANED`.
- No way to ask (non-interactive) ⇒ clean nothing; last line "còn chạy: …".

**`--no-cleanup`** — close, kill, stop nothing and do not ask. Re-measure with `list_pages`, `lsof`,
`docker ps`; rows go `STARTED` → `KEPT`; print the hand-over table (kind · id · port/URL · exact stop
command) with the evidence and ledger paths, and end with one line: "Đã giữ lại theo `--no-cleanup`;
còn chạy: N process, M container, K context Chrome." Chrome belongs to this session's MCP server: when
the session closes the transport, the server shuts down and closes the browser it launched — so a kept
window lasts only while this session is open. Say so; never promise more.

## `init`

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/skills/probe/scripts/init_scan.py"` — suggestions only, each
   with `file:line`; it reads key **names** of env example files, never values of a real `.env`.
2. Write `references/info-template.md`'s skeleton to `<repo>/.claude/claude/docs/probe-live/info.md`,
   creating the folder, filling only what the scan proved; everything else stays `<ops điền>`.
3. The file exists ⇒ never overwrite; ask whether to append a mode or stop.
4. Warn that the file holds inline secrets and must stay out of git; the check script flags it.
5. List the keys still `<ops điền>` and stop.

## `cleanup <ledger>`

Read the ledger, measure which `STARTED`/`KEPT` rows are still alive, list them, ask once, then clean
and measure exactly as P9. `PRE-EXISTING` rows are never touched.

## Excuses that do not hold

| Excuse (heard in baseline runs) | Reality |
| ------------------------------- | ------- |
| "The operator asked for the Save, so I'll do it with the fields unchanged" | Unchanged fields still send a write. Protected env ⇒ no click, no unlock. |
| "A viewer getting 200 would be a finding, so let me try" | Prove permissions by reading; the write itself is out of scope. |
| "They said ok rồi, cảm ơn — that means done, clean up" | That answers nothing. Ask the cleanup question. |
| "`docker stop` then `rm` and drop the volume, to be tidy" | `stop` only, by ledger name. |
| "While they fill in the DB string, I'll start the backend" | Tier 1 failed ⇒ nothing starts. |
| "Two accounts have role `user`, so I can't choose" | Either serves: take the first in the file and say which. |
| "`start_cmds` is blank, so I can't start the FE" | The repository says how it runs: derive it, cite the line, start it. |
| "cứ làm đi covers it; the scratchpad holds nothing important" | Always ask where evidence goes. |
| "They said khỏi chụp, so skip evidence" | Only `--no-evidence` skips it. Without the flag, ask. |
| "`--no-evidence`, so no ledger either" | The ledger is how cleanup knows what is ours. It is always written. |
| "Report the first gap; the next run will show the next" | One table, every gap, once. |
| "This port is probably mine" | Not in the ledger ⇒ not yours. |
| "Small probe, isolation is overkill" | Always a new isolated context. |
| "`--no-cleanup`, so no need to list anything" | Kept ≠ silent: re-measure, hand over, last line. |

## Reference

`references/info-schema.md` — every info-file key, required when, and examples from an invented repo.
`references/info-template.md` — the skeleton `init` writes. `references/probe-steps.md` — evidence
naming, the ledger format and the hand-over table.
