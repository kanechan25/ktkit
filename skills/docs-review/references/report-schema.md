# Report Schema — the literal contract

This file owns **every string** the report is checked against: section headings, table header
rows, field labels, ID formats, and enum values. `scripts/check_report.py` matches these
literally.

Two rules make the contract work:

1. **This file is the only source.** The lint script, `SKILL.md`, the role prompts, and
   `references/*` all read from here. None of them invents a heading, a column, or a field label.
   A section that is not in this file does not go in the report.
2. **Strings are exact.** Same wording, same capitalisation, same order of columns. A heading
   spelled `## Source Inventory` fails the check for `## Source inventory` — that is the point.
   Renaming anything means editing this file and the lint script in the same change.

---

## 1. ID authority — who is allowed to mint which ID

Parallel agents write into separate files. If two of them mint IDs, the IDs collide, the lint
reports `duplicate ID`, and nothing in the report says which agent invented which row. So minting
is a privilege held by exactly one writer per ID type.

| ID | Format | Regex | Minted by | Everyone else |
| -- | ------ | ----- | --------- | ------------- |
| `Doc ID` | `DOC-<2 digits>` | `^DOC-\d{2}$` | **lead**, at inventory | consume only |
| `Req ID` | `REQ-<AREA>-<3 digits>` | `^REQ-[A-Z0-9]{2,8}-\d{3}$` | **checklist builder**, only | consume only |
| `ASM ID` | `ASM-<3 digits>` | `^ASM-\d{3}$` | **lead**, when recording a T3.5 assumption | consume only |
| `D ID` | `D<1–2 digits>` | `^D\d{1,2}$` | **lead**, when opening a decision gate | consume only |
| `Q ID` (Mode B) | `Q-<3 digits>` | `^Q-\d{3}$` | **lead**, at sub-question decomposition | consume only |
| `CLM ID` (Mode C) | `CLM-<3 digits>` | `^CLM-\d{3}$` | **claims agent**, only | consume only |

`CLM ID` follows the same rule as `Req ID` and for the same reason: `claims.md` is the registry, one
file with one writer, so the agents that verify and challenge in parallel cannot mint colliding ids.
A `CLM ID` in the report that is absent from `claims.md` fails `I3 unregistered-id`.

### 1.1 The checklist builder owns `Req ID`

`checklist.md` is the ID registry: one writer, one file, so uniqueness needs no coordination.

The builder must:

* **Read the previous report first** (`docs-review.md` or the file named by `--out`) and reuse
  every `Req ID` it finds for a requirement that still exists. IDs are permanent.
* **Append** new requirements after the highest existing number in that area. Never renumber.
* Mark a requirement the spec no longer contains as `[OBSOLETE]` in the Requirement column, and
  keep its ID and its row.
* Never reuse a retired number for a different requirement.

This duty used to sit with the lead (`SKILL.md` step 1 "load its Req IDs — they are permanent and
this is the only moment you can preserve them"). It now sits with the builder. If the builder
prompt omits it, ID preservation is silently lost between runs and every requirement looks new.

### 1.2 Mappers and reviewers may not mint `Req ID`

A mapper receives a slice of `checklist.md` and maps documents onto the IDs it was given. When it
finds a requirement in the spec that has no row, it does **not** invent an ID. It writes a line
under this heading in its own shard file:

```markdown
## Unmapped candidates

UNMAPPED: <one-line requirement, verbatim from the spec> — <spec section>
```

The lead collects `UNMAPPED:` lines from every shard and passes them to the builder, which mints
the IDs. Same rule for reviewers: a missing requirement is reported as `UNMAPPED:`, never as a new
row with an ID the reviewer chose.

**Lint:** a `Req ID` present in the report but absent from `checklist.md` fails as
`unregistered ID`. This is what catches an agent that minted quietly.

---

## 2. First line of the report

Exactly one of these, and only when it applies:

| First line | When |
| ---------- | ---- |
| `BUDGET-CAPPED — stopped at round N of N (user cap), M findings outstanding` | the round ceiling was reached with material findings left |
| `INCOMPLETE — review loop stopped after round N with findings outstanding` | the user ordered an early stop |
| `DEGRADED — ran without the agent team: <reason>` | the reviewer team was unavailable |
| (no status line) | the loop converged normally |

More than one condition → one line each, in the order above. If any status line is present, the
outstanding findings are listed immediately under it, unmerged.

---

## 3. Sections — exact headings and header rows

Order below is the order in the file. A section that does not apply carries one line stating why,
never silence.

### `## Source inventory`

```markdown
| Doc ID | Path | What it is | Version | Read |
```

`Read` is one of `full`, `searched`, `not-accessed`. Required in **every** mode, not only sharded
runs. `searched` means grep hits plus surrounding sections. A verdict that depends on a document
marked `searched` cannot be reported as a clean pass.

### `## Requirements`

```markdown
| Req ID | Requirement | Tier | Verdict | Evidence | Quote | Note |
```

* `Tier` — one of `T1`, `T2`, `T3`, `T3.5`, `T4`, or `-` when no unknown arose. It records how the
  row was settled, which is what separates a real gap from a search failure.
* `Verdict` — Mode A: `Covered` `Partial` `Missing` `Contradict` `Conflict` `Stale` `Undecided`.
  Mode B uses `## Findings` instead, with `Stated` `Inferred` `Conflicting` `Absent`.
* `Evidence` — `<Doc ID> <path>:<line or section>`. Mandatory for every verdict except `Missing`
  and `Undecided`.
* `Quote` — verbatim, mandatory wherever Evidence is.
* `Note` — for `Missing`: the full expanded search term list and the files searched. For
  `Undecided`: the `D ID` it escalated to. For a row settled by an assumption: the `ASM ID`.

### `## Findings` (Mode B only)

```markdown
| Q ID | Sub-question | Answer | Confidence | Evidence | Quote |
```

### `## Claims` (Mode C only)

```markdown
| CLM ID | Statement | Kind | Verdict | Evidence | Quote | Note |
```

* `Statement` — the author's own wording, quoted, not paraphrased. A paraphrase is where a claim
  becomes the claim the reviewer expected, and every verdict after that argues with something the
  author never wrote.
* `Kind` — one of `fact`, `assertion`, `question`, `conclusion`.
* `Verdict` — one of `Verified` `Refuted` `Unverifiable` `Contradict` `Unsupported` `Answerable`
  `Open` `Implication`.
* `Evidence` + `Quote` — mandatory for every verdict except `Unverifiable` and `Open`, which instead
  record in `Note` every search that was run: terms, files, git commands.
* `Note` — for `Answerable`, **the answer itself** with its citation. For `Contradict`, the other
  statement's `CLM ID`. For `Refuted`, nothing extra: the quote already carries what is actually
  there.

### `## Knock-on and widening` (Mode C only)

```markdown
| CLM ID | Kind | What follows, or what the class is missing | Evidence | Severity |
```

`Kind` is `knock-on` or `widening`. `Severity` is `material` when it would change a decision the
document makes, `nit` otherwise. Every row names the `CLM ID` it derives from — a consequence that
traces to no statement is the reviewer's own opinion, and belongs to the author's judgement, not the
report's table.

### `## Resolutions` (Mode C only)

One subsection per **material** row of `## Claims` — that is, every `Refuted`, `Answerable`,
`Contradict` and `Unsupported`, plus every `material` row of `## Knock-on and widening`. Never for
`Verified`: eighty confirmations turn the section into a second copy of the table.

The heading is the bare ID and nothing else:

```markdown
### CLM-014
**Verdict** Refuted · **Kind** fact · **Severity** material

> §3.2: "retryLimit defaults to 5"

`src/config/retry.ts:22` — `const DEFAULT_RETRY_LIMIT = 3`

Change §3.2 to 3, or change the code if 5 was the intent.
```

The bare ID matters: it is what makes the anchor `#clm-014` stable. A heading that also carries a
description produces an anchor that breaks the next time anyone edits the wording, and the links
written into the reviewed document point at it.

`## Claims` stays exactly as it is — the full table, machine-readable, linted. This section is the
human layer above it, and the anchor target for `## Review status`.

### `## Review team`

```markdown
| Wave | Role | Agent | Model | Mode |
```

`Mode` is `agents` or `degraded`. One row per role per wave. A wave that ran fewer roles than the
design specifies says so here — this table is how a reader sees that only two roles ran.

### `## Round log`

```markdown
| Round | Reviewer | Raised | Upheld | Refuted | New rows | Verdict changes | Citations rejected | Nits |
```

One row per reviewer per round, plus one `TOTAL` row per round with `Reviewer` = `TOTAL`.

**Convergence is read from this table, not asserted in prose.** A report claiming convergence
whose last `TOTAL` row has a non-zero `New rows`, `Verdict changes`, or `Citations rejected` fails
the lint. `Nits` never count toward material.

### `## Round findings`

Free text. Every entry starts with a `Req ID` or `ASM ID` on its own line, then:

```text
REQ-AMT-003
Round 2 finding: ...
Why missed: ...
Challenge: UPHELD | REFUTED | OUT-OF-SCOPE — <evidence>
```

Refuted findings stay in this section. The record of what was challenged and dropped is output,
not waste.

### `## Self-resolved`

```markdown
| Question | Tier | How resolved | Evidence |
```

Every unknown settled at T1, T2 or T3 without reaching the user. This section is the evidence that
work was not pushed onto the reader; an empty one next to a long `## Needs user decision` is a
finding about the audit, not about the documents.

### `## Assumptions taken`

```markdown
| ASM ID | Assumption | Reading chosen | Evidence | Falsifier | Blast radius |
```

`Falsifier` is mandatory: what observation would prove the assumption wrong. An assumption with no
falsifier is a guess wearing a table row — send it back to T1 or escalate it to T4.

### `## Needs user decision`

One block per decision. Field labels are exact, in this order:

```markdown
### D1 · REQ-AMT-003 — <the question in one line>

- [ ] T1 exhausted: expanded-term search across all documents using the DOCUMENTS' vocabulary, the source code, `git log` / `git blame` on the document, and any previous report. Terms and files recorded below.
- [ ] T2 exhausted: put to at least two reviewers, which agreed it is undecidable — not merely disagreed.
- [ ] T3 exhausted: all portable steps tried, or the question is provably not an external fact.
- [ ] T3.5 rejected, with which half failed: no reading has more evidence, and/or being wrong is expensive or irreversible.
- [ ] The user has not already answered it — the request was re-read.
- [ ] Options, consequences, a recommendation and a default are written below.

**Searched:** <terms> across <files>; external: <source> v<version>
**Why no artifact can answer it:** <...>
**Why not an evidenced assumption:** <...>
**Options:** (a) <...> → <consequence>; (b) <...> → <consequence>
**Recommendation:** (a), because <...>
**Default if you do not answer:** (a), recorded in `## Assumptions taken`.
```

Every box must be ticked and every field present. A block short of that is a question that has not
earned the reader's attention yet.

### `## Fixes applied` (only with `--fix`)

```markdown
| Req ID | ASM ID | Document | Old verdict | Change made | New verdict |
```

`ASM ID` is `-` unless the fix rests on an assumption, in which case it names it. A fix that
traces to an assumption and hides it is the failure mode this column exists for.

### `## Proposed, not applied` (only with `--fix`)

```markdown
| Req ID | Verdict | Proposed edit | Decision needed |
```

---

## 4. Metrics line

One line, immediately after the last table:

```text
self_resolve_ratio=0.92 · self_resolved=11 · needs_user=1 · assumptions=2 · max_questions=3
```

`self_resolve_ratio = self_resolved / (self_resolved + needs_user)`, to two decimals.

---

## 5. Lint contract

`scripts/check_report.py` implements exactly these checks and reports them with these ids.
It adds none of its own, and it never renames a section to make a check pass.

| Check | Fails when | Severity |
| ----- | ---------- | -------- |
| `S1 missing-section` | a required section for the mode is absent | fail |
| `S2 header-mismatch` | a table header row differs from this file, in wording or column order | fail |
| `I1 duplicate-id` | the same ID appears on two rows | fail |
| `I2 bad-id-format` | an ID does not match its regex | fail |
| `I3 unregistered-id` | a `Req ID` in the report is not in `checklist.md` | fail |
| `V1 bad-verdict` | a verdict is outside the enum for the mode | fail |
| `V2 missing-evidence` | a verdict needing evidence has no Evidence or no Quote | fail |
| `V3 missing-search-terms` | `Missing` without the expanded term list in Note | fail |
| `C1 false-convergence` | convergence claimed while the last `TOTAL` round row has material counts | fail |
| `C2 missing-round-log` | `## Round log` absent, or no `TOTAL` row | fail |
| `C3 cap-without-status` | ceiling reached with material findings and no status line 1 | fail |
| `R1 coverage-missing` | a `Source inventory` row has no `Read` value | fail |
| `R2 coverage-too-weak` | a verdict cites a document marked `not-accessed` | fail |
| `D1 gate-incomplete` | a decision block misses a checkbox or a field | fail |
| `D2 too-many-questions` | `needs_user` exceeds `--max-questions` | fail |
| `A1 assumption-no-falsifier` | an `## Assumptions taken` row has an empty Falsifier | fail |
| `A2 fix-untraced` | a `## Fixes applied` row has neither a `Req ID` nor an `ASM ID` | fail |
| `M1 escalation-heavy` | `self_resolve_ratio < 0.7` | warn |
| `M2 zero-escalation-unstable` | ratio `1.00`, `assumptions=0`, and the Round log shows verdict changes | warn |
| `M3 degraded-unreported` | `## Review team` has `Mode=degraded` rows and line 1 has no `DEGRADED` status | fail |
| `R3 resolution-missing` | a material row of `## Claims` has no `### <CLM ID>` in `## Resolutions` | fail |

Warnings do not fail the run. They exist because both ends of the ladder are suspicious: too many
questions means the search stopped early, and no questions at all — with no assumptions recorded —
means somebody decided quietly.

---

## 6. What the lint cannot see

The rule that the audit prints no findings into the conversation is not checkable from the report
file. Nothing in the artifact records what was said in chat. It is enforced by the rule in
`SKILL.md` and its red flag, and verified by reading the transcript during the dry run.
