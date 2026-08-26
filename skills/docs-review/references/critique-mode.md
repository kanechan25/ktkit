# Mode C — Critiquing a single document

Read this when the user hands you **one document and no standard**:

```text
docs-review 3 .claude/claude/specs/billing/retry/abc.md
```

The document is the subject, not something being measured against a spec. It is the kind of file
someone writes while thinking: claims, findings, assertions, open questions, conclusions. Some of it
is right, some is wrong, some was true last month, and some is a question the repository already
answers.

`3` is the number of **self-review rounds**. Round 1 reviews the document. Round 2 reviews *round 1's
own output*. Round 3 reviews round 2's. That recursion is the point of the mode — see §4.

## The trap

With no spec to compare against, the natural move is to read the document and say what it says back,
with a few observations. That produces a review shaped by whatever the document already thought of,
and the author learns nothing they did not write themselves.

There is no external standard here, but there are four standards **inside** the situation, and every
one of them is checkable.

## 1. The four axes

Every statement in the document lands on one of these. Nothing is reviewed on impression.

| Axis | The question | Checked against |
| ---- | ------------ | --------------- |
| **Truth** | Is this claim about the code, a file, an identifier, a value, or a behaviour actually true? | The repository — source, config, docs, `git log` / `git blame` |
| **Internal consistency** | Do two statements in this same document disagree? | The document itself |
| **Open questions** | The author marked this unresolved. Is it *actually* unresolved, or does the repository already answer it? | The repository first, then `references/self-clarify.md` |
| **Reasoning** | Does the conclusion follow from the evidence the document itself supplies? | The document's own stated evidence |

Then two things the axes above do not reach, and which the author asked for by name:

* **Knock-on analysis** — statement X is true, something follows from X, and the document never says
  it. A design decision with an unstated consequence is the most expensive kind of gap here, because
  the author will act on the decision without the consequence.
* **Widening** — the document addresses A, and A belongs to a class that also contains B and C which
  it never mentions. Say what the class is, so the omission is arguable rather than a matter of taste.

## 2. Verdicts

Mode C has its own verdict set. `Covered` / `Missing` mean nothing here — there is no requirement to
cover. Column order and section names are in `report-schema.md`.

| Verdict | Means | Evidence required |
| ------- | ----- | ----------------- |
| `Verified` | Checked against the repository and it holds | path:line + quote |
| `Refuted` | Checked and it does not hold | path:line + quote of what is actually there |
| `Unverifiable` | No artifact can settle it — a tooling limit or a genuinely external fact | the searches and sources tried |
| `Contradict` | Conflicts with another statement in the same document | both statements, both line numbers |
| `Unsupported` | An assertion or conclusion the document's own evidence does not carry | the evidence it offers, and what it is short of |
| `Answerable` | An open question the repository already answers | **the answer**, with its citation |
| `Open` | Genuinely open: a decision nobody has made yet | what was searched to establish that |
| `Implication` | Follows from a statement in the document, and the document does not say it | the statement it follows from |

`Refuted` and `Answerable` are the rows that earn the run. A `Refuted` row means the author is about
to act on something false. An `Answerable` row means the author was about to go and find out
something the repository would have told them.

## 3. The team

| Role | Does | Given |
| ---- | ---- | ----- |
| `claims` (producer) | Inventories every checkable statement, mints `CLM` IDs, classifies each by axis | the document only |
| `verify` (reviewer) | Opens the repository and settles each claim: `Verified`, `Refuted`, `Unverifiable` | the claim list, the repo root — **not** the document |
| `implication` (reviewer) | Knock-on analysis and widening; also internal contradictions | the document, the claim list |
| `failure` (reviewer) | Attacks the review, not the document | the review, the claim list, the document |
| `adjudicator` | Upholds or refutes each finding against the files | the finding lists only |

`verify` deliberately does not get the document. It gets the claim, and goes looking. Handing it the
document's own argument for a claim is how a wrong claim gets confirmed by its own reasoning.

### Route by `Kind`, not by section

Split `claims.md` by what each row **is**, then slice by claim count — fifteen or so per agent. Never
by heading: the number of claims decides the number of tool calls, and a long section may hold two.

| `Kind` | Goes to | Because |
| ------ | ------- | ------- |
| `fact` | `verify` | the repository settles it |
| `question` | `verify` | the repository often already answers it |
| `assertion` | `implication` | `claims` itself defines these as checkable against the document's own evidence, **not** the repo |
| `conclusion` | `implication` | same — it is the `Reasoning` axis, not `Truth` |

Sending an `assertion` to `verify` costs three to five searches and returns `Unverifiable`, because
`verify` is required to search hard before it may say that. The repository has no opinion on whether
a recommendation is wise. One measured run spent a large part of 455 tool calls on exactly this.

**The way back matters as much as the routing.** If `claims` mislabels a `fact` as an `assertion`,
routing alone would mean it is never checked against the repository at all — silently. So:

* `implication` may emit `VERIFY-NEEDED: CLM-nnn — <identifier>` for any row it was given that turns
  out to make a claim about the repository. The lead collects them and runs one final small `verify`.
* `claims` **leans towards `fact` when unsure**. Mislabelling that way costs tool calls; mislabelling
  the other way loses a finding.
* `failure` checks the `assertion` and `conclusion` rows for anything that is really a `fact` dodging
  verification.
* `verify` may emit `HISTORY-NEEDED: <path or string> — <what to look for>` for a claim about
  **change**, and writes no row for it. You run the git command, append the output to
  `docs-history.md`, and dispatch one final small `verify` with those claim IDs and that path — the
  slice writes their rows. Never write the row yourself: a row the lead composed is a row nobody
  verified, and rule 3b exists for it.

Three independent guards. `VERIFY-NEEDED:` is the same routing mechanism as `UNMAPPED:`,
`HISTORY-NEEDED:` and `EXTERNAL-FACT:` — reviewer emits, lead executes.

`claims` is the only role that mints `CLM` IDs, for the reason `report-schema.md` §1 gives.

## 3b. The wave protocol for this mode

`review-team.md` §6 is written for Mode A and names `requirement · evidence · coverage · failure`.
**Those are not the roles here.** This is the sequence for Mode C, and it replaces §6 entirely:

```text
WAVE n
 1. Lead dispatches every `claims` slice in ONE message      → they run concurrently
      each: lines <a>-<b>, writes claims.md, returns COVERED_LINES + LAST_LINE_PROCESSED
 2. Lead compares those two numbers against the range it handed out (section 5).
    Short → dispatch ONLY the remaining lines. Equal → done, do not dispatch again
 3. Lead splits claims.md by `Kind` (section 3), then by claim count, and dispatches
    ALL of these in ONE message:
      verify      × slices of  fact | question      (never given the document)
      implication × slices of  assertion | conclusion
      failure     × 1                                (attacks the review, not the document)
 4. Lead runs verify_citations.py over the rows written so far, before step 5
 5. Lead collects the markers and executes them: VERIFY-NEEDED and HISTORY-NEEDED each
    get one final small `verify`; EXTERNAL-FACT is the lead's own lookup
 6. Lead concatenates the shards into the report (rule 3b — cat, never assemble)
 7. Lead dispatches `adjudicator` × 1 with the finding lists ONLY — and the finding
    lists include `implication`'s. Its Implication, Unsupported and Contradict rows are
    findings like any other and are adjudicated as reasoning findings, not by opening files
 8. Only UPHELD material findings are merged. REFUTED ones stay in `## Round findings`
    with the refuting evidence
 9. Lead appends one `## Round log` row per role plus a TOTAL row, BEFORE deciding
10. TOTAL all zeros on the material columns → converged. Otherwise next wave, up to the
    ceiling
```

Step 7 is the one that goes missing. `verify` verdicts arrive already double-guarded — the role
searched for them, `verify_citations.py` checked the quotes, and `failure` sweeps the rows. Nothing
guards `implication` except the adjudicator, so skipping it leaves the whole `Reasoning` axis
unchecked for a wave, and unchecked in the direction that produces confident-sounding rows.

From wave 2 on, the subject is the previous wave's output (section 4) and `claims` does not run
again: there are no new claims to mint, only verdicts and findings to attack. Re-dispatching `claims`
on wave 2 re-reads the document and re-mints IDs, which is the one thing `report-schema.md` §1
forbids.

## 4. What the rounds actually review

This is the part that differs from Mode A, and the reason a round count is worth passing.

**Round 1** — the document. Claims inventoried, verified against the repository, implications and
contradictions raised, findings adjudicated.

**Round 2 and after** — *the previous round's output*, with the document and the repository still
available. The subject is now the review itself:

1. Which verdicts cite evidence that does not say what the verdict claims?
2. Which `Refuted` rows are wrong — the claim was right and the reviewer searched badly?
3. Where did the reviewer **misread what the author meant**, and refute a claim the author never made?
4. Which `Unverifiable` rows are actually verifiable, with a search nobody tried?
5. Which `Implication` rows do not follow, or are the reviewer's opinion dressed as a consequence?
6. What did every previous round miss, in the document, that all of them assumed away?

Item 3 is the one to take seriously. A review that argues with a strawman of the author is worse than
no review, because it is confidently specific.

Stop when a round produces no material finding — no verdict changed, no citation rejected, no row
added. A round that only rewords is not a round. The `--rounds` value is the ceiling, and reaching it
with findings outstanding is reported on line 1, exactly as in Mode A.

## 5. Reading the document is a mapper's job, not the lead's

Same rule as Mode A, same reason: what the lead reads is re-sent on every later turn. The lead holds
the claim IDs and the finding lists. `claims` reads the document; `verify` reads the repository.

For a document under a few thousand words, `claims` reads it in one pass. Above that, slice it and
dispatch one `claims` agent per slice — the ID registry stays one file with one writer.

**Slice by line range, never by heading.** Get the line count with `wc -l`, divide it, and hand each
agent `lines <a>-<b>`. A heading name is not a boundary either of you can check: the agent cannot
prove it reached the end of "§5-7a", and neither can you, so the only move left is to dispatch it
again and hope. That is exactly how one run turned three slices into nine dispatches —
`slice 3` → `supplement` → `residue` → `final residue` — each one re-reading the document from the top.

Every `claims` agent closes with `COVERED_LINES` and `LAST_LINE_PROCESSED`. Compare them with the
range you handed out. Equal → the slice is done, do not dispatch it again. Short → dispatch **only
the remaining lines**. This is arithmetic, not judgement; do not re-read the document to decide.

## 6. What the report says

Sections and their exact columns are in `report-schema.md`: `## Claims` carries the verdict table,
`## Knock-on and widening` the `Implication` rows, and the self-clarify sections behave as they do in
Mode A — an `Answerable` row is a tier-1 resolution and belongs in `## Self-resolved` too.

The document's **own content is never edited**. A file full of someone's reasoning is the last place
to apply automated edits, and a reviewer that misread the author would write that misreading into
their file.

But a review sitting beside a document nobody reopens changes nothing. So one thing goes back: a
single delimited block, appended at the **end** of the document, listing what the run found and
linking to where it is settled. Nothing above the marker is touched — byte for byte.

## 7. The status block written back into the document

Write it with the script, after the loop has ended and the lint is clean:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/docs-review/scripts/upsert_block.py" <document> --block <file>
python3 "${CLAUDE_PLUGIN_ROOT}/skills/docs-review/scripts/upsert_block.py" <document> --verify --report <report>
```

It replaces the block on every later run instead of stacking copies, and it never reads the document
into your context. Never assemble the block by reading the document and writing it back.

Two tables, and the split is the point:

```markdown
<!-- docs-review:begin -->
## Review status

`spec.docs-review.md` · round 2 · 118 claims · 76 Verified

### Settled — safe to apply

| CLM | Where, in this file | Says now | Should say | Source |
| --- | ------------------- | -------- | ---------- | ------ |
| [CLM-031](spec.docs-review.md#clm-031) | §8, line 210 | *open question:* does OnlyOffice support named ranges? | Yes | `docs/onlyoffice.md:88` |
| [CLM-014](spec.docs-review.md#clm-014) | §3.2, line 88 | `retryLimit` defaults to 5 | `retryLimit` defaults to 3 | `src/config/retry.ts:22` |

### Yours to decide — nobody can apply these for you

| CLM | Verdict | The problem |
| --- | ------- | ----------- |
| [CLM-047](spec.docs-review.md#clm-047) | Contradict | §5 and §9 disagree on when the cache is written; which one you meant is not recoverable from the file |
| [CLM-052](spec.docs-review.md#clm-052) | Unsupported | "cuts latency 40%" — the evidence in this document does not carry the number |
| [CLM-061](spec.docs-review.md#clm-061) | Implication | §4 commits to idempotent retries, which requires a dedup key; the document never mentions one |

Full citations: `spec.docs-review.md`.
<!-- docs-review:end -->
```

Rules for the first table, each for a reason:

1. **`Where` carries the section *and* the line** — section first. Hunting for the sentence is the
   slowest part of applying a finding, and the section survives edits while the line number does not.
2. **Sort it by line number, descending.** Then applying the rows from the top down never invalidates
   the line numbers below, and the numbers stay usable to the last row.
3. **`Says now` and `Should say` sit side by side.** Enough to act without opening the report.
4. **`Source` is a repository citation.** It is what makes a row believable without re-verifying it.
5. **Only `Answerable` and `Refuted` rows that carry a real value belong here.** A `Refuted` whose
   quote only shows absence goes in the second table: knowing a statement is wrong is not knowing
   what is right.

`Contradict`, `Unsupported`, `Implication`, `Open`, `Unverifiable` and value-less `Refuted` go in the
second table — every one of them needs a decision the repository cannot supply.

Between them the two tables account for **every material row**. That is the property to check: a
finding that reaches neither table has been dropped, and the block is the only part of this run the
author is guaranteed to read.
