# Handoff to docs-review

## Why a handoff and not a second engine

`docs-review` already owns the expensive parts: independence between derivation and challenge, waves
that run to convergence, the report schema, the citation checker, the lint that recomputes
convergence instead of trusting the report. Rebuilding any of that here would produce two things to
keep in sync, and they would drift.

So this skill produces **evidence documents** and hands them over. The invariant that reviewers have
no shell is untouched; they are simply given more to read.

## The call

```bash
ktkit:docs-review <spec> <docs>... --evidence <base>/evidence/ --rounds N --out <report>
```

`--evidence <dir>` loads every `.md` under the directory into the document set, marked as artifacts
this run produced.

## Before handing over

1. `check_evidence.py <base>/evidence/` exits 0. An evidence file with an unlabelled number or no
   reproduce line must not become a source a reviewer cites.
2. Every evidence file has a `Not accessed` section, or genuinely reached everything. Silence about
   a gap is read as coverage.
3. `steps/06-handoff.md` records exactly what was passed: which evidence files, which documents,
   which arguments. That file is the handoff.

## What docs-review does differently with evidence present

Two changes, and no others:

- Evidence files enter `## Source inventory` marked as **evidence produced by this run**, not as
  pre-existing documents. A reader weighing a row needs to know which it is.
- The self-clarify ladder gains a fifth tier-1 source: **this run's probe results**. An unknown that
  a probe already answered is resolved from the evidence file rather than escalated.

Everything else — verdict vocabulary, ID allocation, wave structure, the lint — is unchanged. If
something here seems to need a third change to `docs-review`, that is a sign the evidence file is
doing work it should not: fix the file, not the reviewer.

## Running without the handoff

`--handoff off` stops after `check_evidence.py` passes and reports the evidence directory. This is
supported, and it is how the skill is tested: bringing up the probe layer never required
`docs-review` to change first.

Use it when the question is "what is actually true here" rather than "do these documents cover this
spec" — reconnaissance whose output a person reads directly.

## Two skills, two entry points

`docs-review` keeps working exactly as before. Without `--evidence` its behaviour does not change by
a single byte, and there is a test that says so. It is both a skill you run on its own and a
component this one calls; those roles do not conflict, because the flag is optional and inert when
absent.
