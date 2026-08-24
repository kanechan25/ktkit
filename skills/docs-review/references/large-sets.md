# Large Document Sets — what changes when the set is big

Read this when the measurement in `SKILL.md` step 1 says the set is large: more than 15 documents,
more than ~100,000 words, a document no single agent can read in full, or formats you can only
search.

**This file no longer replaces the workflow.** Index-then-shard used to be the large-set exception;
it is now the standard pipeline at every size, because the lead does not read documents at all and
mappers work on slices regardless. A set of eight documents already runs one checklist builder and
several mappers. Document count changes **how many agents** run, not **which** ones.

What genuinely changes above the threshold is the four things below. Everything else in `SKILL.md`
stays as written.

## 1. The document map becomes mandatory

Below the threshold a mapper rebuilds a document's vocabulary as it reads — with a handful of small
documents that is cheap and accurate. Above it, no single agent sees enough of the set for that to
work, so the vocabulary has to exist as an artifact first.

Split the set across agents (roughly ten documents each) and have each return one row per document:

| Doc ID | Path | Sections (headings) | Key terms used | Values asserted | Version / date |

* **Key terms used** — the vocabulary *the document* uses, not the spec's. This column is the whole
  point of the pass.
* **Values asserted** — every number, limit, threshold, state name, role name, time, format, and ID
  pattern the document states. Copy them verbatim with their section.

Write it to `docs-index.md`. It is an input to every mapper, to the `coverage` reviewer, and to the
conflict sweep.

**Why it comes first:** a requirement written as "second approver" in the spec and "dual sign-off" in
the manual is invisible to a spec-term grep. Without the index, that becomes a confident `Missing`.

## 2. Shard by spec chapter instead of by dimension

Below the threshold, slicing the checklist by dimension keeps related requirements together. Above
it, slice by **spec chapter** instead: a chapter's requirements tend to land in the same documents,
so each mapper reads a smaller part of the set.

Each mapper gets its chapter's slice, `docs-index.md` in full — cross-references live outside the
shard — the documents its rows point at, and permission to open any other document the index
suggests. It writes `shard-<chapter>.md` and ends with the coverage declaration `report-schema.md`
requires.

The lead concatenates the shards. Concatenation, not hand-editing: a 200-row table edited by hand
loses rows, and pulling it through the lead's context costs it on every later turn.

## 3. The conflict sweep becomes a separate pass

With two or three documents, the `coverage` reviewer finds doc-versus-doc disagreement while it works
— it holds the whole set. At forty documents it cannot, because the two documents that disagree
rarely land under the same requirement row.

So run one dedicated pass over the **Values asserted** column of `docs-index.md`: group every
asserted value by what it describes (batch limit, retry count, state name, role, cutoff time,
format), then flag every group whose members disagree.

Each disagreement becomes a `Conflict` row citing both documents — including the ones the spec says
nothing about, which are exactly the ones no requirement row would ever have caught.

## 4. Review waves run per shard, then once across them

Run the `SKILL.md` step 4 wave **per shard**, on that shard's rows and chapter. The rules do not
change: reviewers get no lead reasoning and no prior wave's notes.

Shard waves cap at **2 per shard** — sharding already buys independent eyes, and a third wave inside
one chapter costs more than the cross-shard wave that follows. **Shard waves do not count toward the
`--rounds` ceiling; the cross-shard waves do.** A shard whose second wave still returns material
findings is named in the report as unconverged rather than merged silently.

Then run **one cross-shard wave** over the merged report, looking only for what shard boundaries
hide:

1. Requirements that fall between chapters and landed in no shard
2. The same requirement audited twice with different verdicts
3. `Conflict` rows the sweep found that no shard reflected
4. Shards whose coverage declaration is weaker than their verdicts imply

**An empty wave only counts as clean if the shard's coverage declaration is `full` for the documents
its verdicts depend on.** An empty wave over a `searched`-only shard means the reviewer searched the
same way the mapper did and missed the same things. Say that in the report rather than calling the
shard clean — the lint's `R2 coverage-too-weak` catches the strongest version of this, a verdict
citing a document nobody opened, but not the weaker one.

## When the budget runs out

Deliver fewer shards audited completely. Never audit every shard partially — a report where each
chapter is half-checked cannot be distinguished from a finished one by the person reading it.
Unaudited shards are listed in `## Source inventory` as `not-accessed`, by name, with the chapters
they cover, and the report's first line says the run was capped.
