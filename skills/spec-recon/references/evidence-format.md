# Evidence format

An evidence file is a measurement turned into something a document reviewer can read. That is the
entire trick this skill turns: `docs-review` keeps its invariant that reviewers have no shell, and
still gets to reason about code, artifacts and forge state — because those arrive as documents.

Which means an evidence file is held to a **higher** standard than a normal document, not a lower
one. A reviewer will cite it as a source.

## Shape

One file per probe, at `<base>/evidence/probe-<kind>-<topic>.md` where `<kind>` is `code`,
`artifact`, `vcs` or `runtime`.

```markdown
# Probe: <kind> — <topic>

Produced by: `ktkit:spec-recon-probe-<kind>` on <date>
Reproduce: <the exact command, runnable as written>
Scope given: <the caller's words, verbatim>

## Measurements

| Property | Value | Label |
| -------- | ----- | ----- |
| … | … | [measured] |

## Not accessed

| What | Why | What would settle it |
| ---- | --- | -------------------- |
| the deployed blob | no object-storage credentials in this run | `--probe runtime`, or a copy of the deployed file |

## Reading

At most three sentences of what the measurements do and do not license. No recommendations.
```

## The labelling rule

Every number carries exactly one label:

| Label | Means |
| ----- | ----- |
| `[measured]` | read directly out of the thing itself |
| `[quoted]` | copied from a document, with a citation |
| `[derived]` | computed from other numbers in this file |

Two labels in one unlabelled sentence is a defect `check_evidence.py` fails on. The rule is not
pedantry: a derived figure was once read as an observation, acted on, and had to be retracted
mid-run. The retraction cost more than the labels ever will.

Derived numbers must show their arithmetic:

```markdown
| overflow rows | 300 | [derived] = 1,200 measured rows − 900 quoted limit |
```

A `[derived]` value whose inputs are not visible in the same file is not derived, it is asserted.

## Reproducibility

Every file carries a `Reproduce:` line that runs as written — no placeholders, no "adjust the path".
A measurement nobody can rerun is an assertion in a table's clothing, and the difference only shows
up when someone disagrees with it.

For a forge probe, the endpoint per row is the reproduce line:

```markdown
| milestone `Phase1` | due 2026-09-30, 0 open / 0 closed | [measured] |

Reproduce: `GET /repos/<owner>/<repo>/milestones?state=all` with a token in the Authorization header
```

## Not accessed is mandatory when it applies

Every evidence file that could not reach something says so, with a reason and with what would settle
it. Silence about a gap is read as coverage by everyone downstream, and it is the failure mode that
survives every other check in this skill.

This includes gaps caused by the environment: an SSH remote the sandbox blocked, a binary too large
to open, a rate limit reached. Those are `not-accessed`, never `missing`.

## What an evidence file never contains

- **A recommendation.** Not "this should be fixed", not an effort estimate, not a risk rating. The
  measurements are worth more when they are only measurements, because the next reader is allowed to
  disagree with the conclusion without having to distrust the data.
- **An identifier nobody read.** Every table name, column, function, endpoint, config key and file
  path was read off a line in a real file. Anything expected but unverified is marked `[unverified]`
  inline, and never in an identifier column.
- **A number without a label**, or a label without a number.
- **A credential**, in any form, including inside a quoted error message.

## In the report

Evidence files enter `## Source inventory` as first-class sources, marked as artifacts this run
produced rather than documents that already existed:

```markdown
| Source | Kind | Read |
| ------ | ---- | ---- |
| `docs/design.md` | document | fully |
| `<base>/evidence/probe-artifact-template.md` | **evidence produced by this run** | fully |
```

The distinction matters to a reader deciding how much to trust a row: a pre-existing document was
written by someone with context, an evidence file was written by a probe with none.
