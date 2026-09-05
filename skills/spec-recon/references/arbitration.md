# Arbitration — no absence claim reaches the report unverified

## The failure this exists to stop

In the run this skill was built from, a document-only reviewer reported a whole area of the
specification as an unimplemented gap. It was specific, it was confident, and it was wrong: the code
had implemented it. Nothing in a document-to-document review could have caught that, because the
reviewer searched documents for a concept the code names differently.

The general form: **absence in a derived source is not absence in the artifact.** A document not
mentioning something is a fact about the document.

## What gets routed

Any verdict of this shape, from any reviewer that could not read code:

> *not implemented · missing · not present · no support for · not covered · does not exist · has not
> been built · to be done*

becomes `needs-probe`. **`needs-probe` is not a verdict** and never appears in a report as one. It
is a routing state.

Verdicts that are **not** routed here, because they are claims about documents and a document
reviewer is the right judge:

- two documents asserting different values for one thing
- a requirement with no corresponding section anywhere in the document set
- a citation that does not support what it is cited for
- a conclusion the documents do not license

## The route

```
document reviewer -> verdict "missing"     -> needs-probe
needs-probe       -> spec-recon-arbiter-impl (Read, Grep, Glob)
                     |- REFUTED  path:line          -> verdict is dropped; the citation is kept
                     |- UPHELD   searched + unsearched -> verdict enters the report, with both lists
                     `- UNSAFE   reason              -> routed on, see below
```

`UNSAFE` means the answer lives somewhere the arbiter cannot reach. Route it by kind:

| The answer is in | Goes to |
| ---------------- | ------- |
| a binary artifact | `spec-recon-probe-artifact` |
| an issue, PR or milestone | `spec-recon-probe-vcs` |
| history | the lead, which precomputes `git log` into a file |
| live data | `not-accessed` **plus the exact command to enable `--probe runtime`** — never a guess |

The last row is where the labelling rule is most likely to be quietly broken. When runtime probing
is off, the temptation is to answer "what does the real data look like" from seed files, fixtures or
a migration default and present it as a measurement. Those answer a different question. Report
`needs-runtime-probe`, print the command, and stop.

## What an UPHELD verdict must carry

`REFUTED` is cheap: one line of real code ends the argument.

`UPHELD` is a claim about an entire codebase made from a partial search, so it carries its own
weakness in the report:

```markdown
| V-014 | UPHELD | `retryBudgetMs` is not referenced in the client |
| | searched | retryBudgetMs, retry_budget_ms, RetryBudgetMs, retry-budget-ms, budgetMs, glob **/*retry* |
| | unsearched | generated bundles under dist/, and anything injected at build time |
```

An `UPHELD` with an empty `unsearched` field is only correct when the whole surface was genuinely
searched, which is rare. An empty field with a wide claim is itself a defect.

## The disposition

Lean towards refuting. Not because absence claims are usually wrong, but because the costs are
asymmetric: a wrongly upheld absence sends people to build something that already exists, while a
wrongly refuted one is caught the moment somebody opens the cited line.

## Conflicts between a probe and a document

When a probe contradicts a document, the probe wins on **what is**, the document wins on **what was
intended**, and the disagreement itself is the finding. Do not resolve it by preferring one source.

```markdown
| Finding | The shipped template has no sheet named in the published form (0 of 5 match) |
| Measured | `probe_xlsx.py src/Templates/report.xlsx --sheets` [measured] |
| Stated | `docs/forms/report-form.md:41` names five sheets [quoted] |
| Reading | either the template implements a different form, or the form reference is stale. This run cannot tell which, and the distinction changes who has to act. |
```

Never collapse that into "the template is wrong". Which of the two is wrong is a question for
someone with authority over the form, and stating it as settled removes their chance to answer.
