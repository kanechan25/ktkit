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

`claims` is the only role that mints `CLM` IDs, for the reason `report-schema.md` §1 gives.

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

For a document under a few thousand words, `claims` reads it in one pass. Above that, slice it by
heading and dispatch one `claims` agent per slice — the ID registry stays one file with one writer.

## 6. What the report says

Sections and their exact columns are in `report-schema.md`: `## Claims` carries the verdict table,
`## Knock-on and widening` the `Implication` rows, and the self-clarify sections behave as they do in
Mode A — an `Answerable` row is a tier-1 resolution and belongs in `## Self-resolved` too.

The document is **not edited**. Mode C produces a review beside it; what to change is the author's
call, and a file full of someone's own reasoning is the last place to apply automated edits.
