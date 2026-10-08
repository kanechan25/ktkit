# PR write-up style guide — the nine rules (S1–S9)

These rules are **the skill's**, not any one repository's. The section headings come from whatever
PR template the repository has; what goes *inside* them is governed here.

⚠️ Every example below is **invented**. It is modelled on a fictional parcel-logistics system —
depots, delivery slips, a master table — chosen because it needs both English and a non-Latin script
to show the language rule. Copy the **shape**, never the content: in a repository with no Japanese,
every term here would simply be English. See `references/exemplar.md` for the same invented system
written out end to end.

---

## S1 — Every claim carries a measurement

If there is no number, do not write the sentence in a way that implies one.

| ✅ | ⛔ |
|---|---|
| "0 of 7 depots matched the spec" | "the depot code was wrong" |
| "wrong in 14 of 31 cases, one off by more than 2× (18,204 claimed against 44,930 actual)" | "several counts were inaccurate" |
| "1,204 files / 18,330 tests, 0 fail" | "all tests pass" |
| "the remaining 6 rows differ by 1.46bn, and two of them would compute to zero" | "some rows were wrong" |

**Where the number comes from**: a commit body, or context the user pasted. Never from the diff stat
(line counts are not record counts), never from an estimate, never from the model.

No number available → write the claim at the level the source supports, and mark it
`<!-- TBD: measurement -->`. An honest unmeasured sentence beats an invented measured one.

## S2 — Each change item is Impact → Cause → Fix

`## Changes` is a numbered list of **work items**, not commits. Each item:

```markdown
### 3. Seed row counts were recorded in two places, one of them unchecked

**Impact:** anyone reading `DepotSeedContext.cs` was reading numbers that were wrong in 14 of
31 cases, one of them off by more than a factor of two.

**Cause:** the count lived both in a comment and in a test; only the test was ever run.

**Fix —** the numbers were removed, not corrected. Tests one directory away already own them.
```

- The **heading states the symptom**, not the task ("Seed row counts were recorded in two places",
  not "Refactor seed comments").
- **Fix** may state what was deliberately *not* done, and why the obvious alternative is worse.
- Group related commits into one item. 11 commits becoming 7 items is normal and good.

## S3 — Name the alternative you rejected — marker ⛔

A reviewer's first reaction to any fix is "why not do it the other way?". Answer it before they ask.

> ⛔ Renumbering `display_order` to match was considered and rejected: it would undo a decision from
> 2026-02-11, reorder three pickers that all sort by that column, and — because the seeder only ever
> inserts — a JSON edit would never reach an environment that has already been seeded.

Only write this when a commit body actually records the rejected option. Do not invent trade-offs.

## S4 — State what this PR does NOT fix — marker ⚠️

The most valuable paragraph in any PR body, and the one most often missing.

> ⚠️ 9 existing records on `staging` still hold the wrong code. They **do not heal by themselves** —
> reallocation only runs when the depot changes, so Recalculate and Confirm will not clear them.
> Environment work is out of scope here, but nobody should assume this PR fixed them.

Covers: data already written wrong, environments not covered, follow-up work, known limitations.

## S5 — Evidence of a real run — marker 🎯

Not "tested", but *what was run* and *what came out*, reproducibly.

> 🎯 Verified by running it: renaming `北部拠点` → `北部拠点ZZ` halts with 0 bytes written; on the
> real CSV only the intended file changes and its sibling is byte-identical.

> 🎯 Seed mutation: **0 tests red before, 1 red after.**

⛔ This skill never runs anything. Every 🎯 line must be quoted from a commit body or the user's
context. No source → no 🎯.

## S6 — Point at the right source when history misleads — marker 🔴

When the branch's own history contradicts the tree that will be merged:

> 🔴 Read the current behaviour in #412, not in this branch's history. Two PRs fixed this defect
> independently and the merge settled on #412; the commit here that carried an earlier version of
> the fix is superseded.

## S7 — A section for what was deliberately not built

Scope decisions are content, not omissions.

> ### 6. Two items were deliberately **not** built
>
> **A date-range option on the picker.** The spec allows it and it is genuinely missing, but shipping
> it now would be worse than leaving it out: the back end no longer validates this field, so a
> malformed value saves successfully and only fails later. Today the option cannot be selected, so
> the bad value cannot be created. It needs its own PR.

## S8 — Warn when the diff size lies

A `+19,741 / −188` headline makes reviewers assume a monster. Separate generated from authored:

> ⚠️ **The diff size is misleading.** `64 files, +19,741 / −188`:
>
> | | |
> |---|---|
> | `20260315090412_RenumberDepots.Designer.cs` | **+18,306 — 92.7 % of all insertions, in one file** |
> | 28 × `seed/depots/*.json` | **one byte each** — a trailing newline |
> | actually authored | **≈35 files, ≈+1,407** |

Percentages come from the stat, which the skill *is* allowed to read. Include this block only when
generated or noise files actually distort the picture.

## S9 — Notes for Reviewers says what to SKIP

Save the reviewer's time by pointing away from files, not only towards them.

> 1. **Skip `20260315090412_RenumberDepots.Designer.cs`** — generated, 92.7 % of the diff. Review
>    the 96-line `20260315090412_RenumberDepots.cs` instead.
> 2. **The 28 JSON files changed by exactly one byte** — a trailing newline. Git renders that as
>    `-1/+1` on an identical line; the content is untouched.
> 3. Each fix is a separate commit, so any one of them can be reverted on its own.

---

## The marker set

| Marker | Meaning | Use when |
|---|---|---|
| ⛔ | rejected alternative, or a thing that must not be done next | a commit records the option that was turned down |
| ⚠️ | a caveat that survives the merge | data, environments or scope left unfixed |
| 🎯 | verified by an actual run | a commit records the run and its result |
| 🔴 | read this source, not that one | branch history contradicts the merged tree |

Keep the markers in every repository — they are this skill's voice, not the template's. A repository
whose template or recent PRs forbid emoji gets `NOTE:` / `WARNING:` / `VERIFIED:` / `IMPORTANT:`
prefixes instead.

## Two small conventions

- A meta line under the description:
  `**Ticket:** ABC-123 | **Type:** 🐛 Bug fix + 🧹 Cleanup | **Review Time:** ~35 min`
  Type may combine several kinds. Leave `—` where the source gives nothing.
- `Testing` is checkboxes **plus numbered scenarios with real results** — "the depot verify target —
  PASS on every step", not "tested locally". Tick a checkbox only when a source states it.

## Title

`<type>(<scope>): <symptom>`

- scope lowercase, comma-separated across the parts actually touched: `fix(core,api,web):`
- the subject is the **measured symptom**: what was wrong, where, how much
- domain nouns stay in their original script; the sentence around them is in the PR's language
- include a ticket or API code only when the repository's own commits use that convention

| ✅ | ⛔ |
|---|---|
| `fix(core,api,web): 配送伝票 printed the wrong 拠点コード for all 7 depots` | `fix(core): fix depot code bug` |
| `fix(api): token refresh dropped every request queued during the refresh window` | `fix: bug fixes and improvements` |
| `feat(billing): invoices can be re-issued after a partial refund` | `feat: update billing` |

## Japanese (`--lang ja`)

The same nine rules, the same markers, the same section frame. What changes is the prose only:

- Sentences are Japanese, in the plain `です・ます` register a reviewer reads in a PR.
- Identifiers, paths, commands, numbers and the title's `<type>(<scope>):` prefix stay exactly as
  they are; the subject after the colon is Japanese.
- A commit body written in English is summarised into Japanese — never quoted untranslated at
  length.
- Section headings come from the repository's template as written. With no template, the fallback
  headings are translated.

⛔ Vietnamese is never a PR language, whatever the sources or the session are written in.

## The failure mode to avoid above all

A body that reads like a changelog:

```markdown
## Changes
- Updated DepotService
- Fixed seeder
- Added tests
- Refactored mapper
```

Every line is true and none of them tells a reviewer what broke, why, or what to look at. If the
commit bodies only support this much, say so with the thin-source warning — do not dress it up.
