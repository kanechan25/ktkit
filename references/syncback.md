# Sync-back — a specification that still matches the code

A specification that disagrees with the code is worse than no specification. It reads as
authoritative and is quietly wrong: somebody opens it three months later, believes it, and builds on
a shape that was never shipped. Closing that gap is the whole of this file.

`chain` had a sync-back step and it could not close it. Step 06 syncs "every conflict found in 04 or
05" — but 05 hands the work to an execute skill, nothing extracted that skill's divergences, and the
`.implt.md` template had nowhere to put them: `Acceptance Criteria`, `Blast Radius`,
`What Was Built`, `Files Changed`, and no row anywhere saying *the spec said X, I did Y, because Z*.

## 1. Two designs, both half right

**A — write the spec at the moment of divergence.** The reason is captured while it is still in
context, which is the half that matters. But the spec stops being a stable reference during the very
phase that reads it; a change to what the spec promises lands before anyone approves it; and an
aborted run leaves a specification describing code that was rolled back. ⛔ That last one is worse
than the original problem — before, the spec was stale but true of its own moment.

**B — record in `.implt.md`, sync afterwards.** The spec stays stable and an abort is safe. But
nothing says *when* the reason is captured, so it gets written at the end of the phase, by which
point the reason has left context. And a table hand-written into `.implt.md` and then hand-synced
into `spec.md` is **two independent authorings**, which can disagree.

⭐ **What ships is neither: capture at the moment, write at the boundary, render once into both.**

| | Reason survives | Spec stable while implementing | Abort-safe | Has a gate | One file is enough | Tokens |
| - | :-: | :-: | :-: | :-: | :-: | -: |
| A | ✅ | ⛔ | ⛔ | ⛔ | ✅ | ~5–10k |
| B | ⛔ | ✅ | ✅ | ✅ | ⛔ | ~2–3k |
| **C** | ✅ | ✅ | ✅ | ✅ | ✅ | **~2–3k** |

C is cheaper than A because the spec is written **once**, not once per divergence.

## 2. Capture — at the moment, by whoever diverged

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/deviation.py" add \
    --base <chain-dir> --repo <root> --source "spec §4.2" \
    --said "POST /exports returns 202" --did "returns 201" \
    --why "202 needs a job queue the spec does not describe" \
    --evidence src/api/ExportController.cs:88 [--contract]
```

⛔ **`--why` is mandatory.** A diff shows that the code differs; it never shows why somebody chose
that, and nobody can reconstruct it afterwards. The lint refuses a row whose reason is empty, `n/a`
or `tbd` — those are the shapes an unwilling answer takes.

⭐ **`--said` quotes the specification, it does not paraphrase it.** A paraphrase makes the divergence
disappear: "the spec said roughly that" is agreement with anything.

**Nothing diverged is a statement, not a silence:**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/deviation.py" none --base <chain-dir> --repo <root>
```

⛔ An empty record and "the code matches the spec" are different facts, and only one of them is a
finding. `lint` reports `NOT-ANSWERED` for the first and `DECLARED-NONE` for the second.

## 3. Write — at the boundary, and only there

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/deviation.py" lint --base <chain-dir> --repo <root>
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/deviation.py" render --base <chain-dir> --repo <root> \
  | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/upsert_block.py" <spec.md> --block - --marker chain
```

The same rendered table goes into `.implt.md`.

```
deviations.jsonl  ──render──┬──→ spec.md   block
                            └──→ .implt.md table
```

⭐ **Neither is authored separately, so they cannot drift** — and reading `spec.md` alone is enough,
which is the point. Two hand-written tables are two chances to disagree, and the reader who finds
them disagreeing has no way to tell which is true.

The block sits at the **end** of the file and every character above it is copied through untouched,
so citations into the spec keep their line numbers — including any a `docs-review` audit left behind.
The marker is `chain`, so a `docs-review` block in the same file is neither read nor overwritten.

⛔ **Never edit the middle of a specification to record a divergence.** Every citation below the edit
shifts, silently.

## 4. Anchors drift, and an anchor that only *was* true is worse than none

A `path:line` captured mid-phase moves as the implementation continues. `lint` re-checks each one:

| State at the boundary | What happens |
| --------------------- | ------------ |
| the line is still there | kept |
| the file is there, the line moved | ⭐ **re-resolved** — the recorded text is found again, the number updated, and the row marked `line moved` |
| the line is gone and is nowhere in the file | ⛔ **stop** |

The recorded row keeps the line's own text for exactly this: it is what makes re-resolution possible
instead of a choice between trusting a stale number and throwing the row away.

⛔ **A stop is a stop, not a warning.** A divergence anchored to a line that is not there reads as
verified and is not — the same failure `R4` was written for in `gap-design`.

## 5. A contract-level change is a gate

Implementation detail syncs on its own — a variable renamed, a file added, two steps reordered.
A change to what the specification **promises** does not:

| Kind | Route |
| ---- | ----- |
| implementation detail | ✅ synced |
| ⛔ an acceptance criterion changed | 🔴 **gate** |
| ⛔ an API shape or schema changed | 🔴 **gate** |
| ⛔ a requirement dropped | 🔴 **gate** |

Somebody is integrating against those. Mark the row `--contract` and step 06 stops and goes through
**`/ktkit:confirm-with-me`** before writing.

⛔ **"It could not be done" is not "it did not need doing."** That substitution, made silently, is
how a requirement disappears without anyone deciding to drop it.

⚠️ This is a **third** stop in a run and does not count against the gate budget of two: it is not a
question, it is confirmation of a change that has already happened.

## 6. Abort

`deviations.jsonl` lives in the run directory, so it survives an abort and a compaction, and
`spec.md` has not been touched. `--resume` reaches step 06 and picks the record up.

⭐ That is the concrete reason A was rejected: an abort under A leaves a specification describing code
that no longer exists.

## 7. What this never does

| ⛔ Never | Why |
| -------- | --- |
| Re-read the spec and the diff to *find* divergences | ~40–80k tokens for a worse answer: it can see that the code differs and can **never** see why |
| Decide what counts as a divergence | That is judgement. This collects rows and refuses uncheckable ones — the boundary `probe_index.py` keeps between a count and a verdict |
| Accept a row with no `path:line` | "I changed X" that cannot be opened is not a record |
| Let an empty record read as clean | Silence is not "nothing diverged" |
| Sync a contract-level change on its own | §5 |
| Write into `plan.md` | Out of scope. A divergence is about **intent**, and intent lives in the spec; the steps that were carried out are what `.implt.md` is for |
