# Self-Clarify — resolving unknowns without handing them to the user

Read this whenever the audit produces something you do not know: a term you cannot find, two
documents that disagree, a spec sentence with two readings, a fact about a library.

The failure this file prevents is not "guessing". It is **escalating** — turning every unknown
into a question for the user, when most of them are answerable from the repository, the documents,
or a public source. A question the reader has to research themselves is not a finding; it is the
audit handing back its own work.

The opposite failure is real too, and worse: deciding a product question quietly and stamping the
row `Covered`. Tier 3.5 exists so that deciding is possible **and recorded**.

Every unknown gets classified into exactly one tier **before** you do anything with it. Section
names, table columns and field labels for everything below come from `report-schema.md` — this
file owns the decisions, that file owns the strings.

---

## The ladder

| Tier | It belongs here when | Who resolves it | Exit criteria |
| ---- | -------------------- | --------------- | ------------- |
| **T1 · RESOLVABLE** | The answer exists in something you can open: the documents, the spec, the source code, the document's own history, a previous report | self / coverage reviewer | Found, with `file:line` and a verbatim quote |
| **T2 · REVIEWER DISAGREEMENT** | Two reviewers, or two documents, say different things and **both cite evidence** | one round of cross-examination | One side refuted **with evidence** |
| **T3 · UNKNOWN EXTERNAL FACT** | The fact lives outside the document set: library or API behaviour, a format, a standard, a service limit | lead, via the portable ladder below | An authoritative source **plus its version** |
| **T3.5 · EVIDENCED ASSUMPTION** | The spec is ambiguous, **but one reading has more evidence** — a convention repeated across the documents, a precedent elsewhere in the set, what the code does, what the history shows — **and** being wrong is cheap to correct | self | A reading, its evidence, and a **falsifier** |
| **T4 · TRUE PRODUCT AMBIGUITY** | Two or more readings are equally supported, the consequences differ materially, and being wrong is expensive or irreversible. Nobody has made this decision yet | **the user** | The user decides — or the recorded default applies |

**You may only move up a tier by proving the tier below is exhausted.** Not by finding it hard.
Every tier has a written exit criterion precisely so "exhausted" is a claim someone else can check.

Record the tier in the `Tier` column of the requirement row. That column is what separates a real
documentation gap from a search that stopped early — the two are indistinguishable without it.

---

## T1 — search before you conclude

Four sources, in this order. A `Missing` verdict or a T4 escalation that skipped any of them is a
search failure reported as a finding.

1. **The documents, using the documents' vocabulary.** Not the spec's. A spec saying "second
   approver" will never match a manual saying "dual sign-off". Build the term set from
   `docs-index.md` (its Key terms column exists for this), add synonyms, abbreviations, field
   names, and — for Japanese sets — both the Japanese term and its English gloss. Record the full
   expanded list in the row's Note.
2. **The source code**, when the documents describe a system that exists. Code is not the standard
   the audit checks against, but it is evidence about what a term means.
3. **The document's own history**, from `docs-history.md`. Reviewers have no shell: the lead writes
   that file during inventory (the last commits touching each document) precisely so history is
   available as a readable artifact. When it does not answer the question, the reviewer asks for
   more with `HISTORY-NEEDED: <path> — <what to look for>`, and the lead runs it.
4. **The previous report**, if one exists. A question answered in the last run is answered.

If the index shows a section whose topic matches but whose wording does not, **read that section**
rather than trusting the grep.

## T2 — one round of challenge, then move on

Two reviewers disagreeing is not an ambiguity; it is an unverified claim on at least one side.
Put the finding to the other side once. Each answers `UPHELD` or `REFUTED`, with evidence.

* One side refuted → the row is settled. Record the exchange in `## Round findings`.
* Neither side refuted after one exchange → **do not run a second exchange**. Go to T3.5 if one
  reading has more evidence, T4 if neither does.

A disagreement that survives one evidenced challenge is information about the spec, not a reason
to keep spending rounds.

## T3 — external facts, portably

Reviewers have no MCP tools, no web access, and no shell. **T3 is the lead's job.** A reviewer that
needs an external fact returns `EXTERNAL-FACT: <the fact needed> — <why the verdict depends on it>`
and continues with the rest of its slice.

The lead then takes the first step that works:

1. **A documentation MCP tool, if this machine has one.** Detect it at runtime — look for a tool
   whose name contains `context7` — and use it if present. **Never hardcode a tool name**: MCP tool
   names are specific to the machine the skill is running on, and a plugin that assumes yours will
   fail on everyone else's.
2. **Fetch the official documentation page.** Web fetch is a core capability, so this step works
   everywhere. Record the URL and the version.
3. **Read the dependency actually installed in the repository** — the manifest or lockfile for the
   version, then the installed package's own source or README. This is often *more* accurate than
   published docs, because it is the version in use.
4. **None of the three worked → stop. Do not escalate to T4.** Record the row as `Undecided` with
   the note `external fact unverifiable: <fact>; tried 1,2,3`.

Step 4 is the load-bearing one. A fact the tooling cannot reach is not a product decision, and the
user cannot answer it either — they would have to run the same three steps. Asking them converts a
tooling limit into an interruption.

Never answer a T3 question from memory. A remembered version number is a fabricated citation with
a plausible shape.

## T3.5 — decide, and write down what would prove you wrong

This is the tier that keeps T4 small. Most spec ambiguity is not a live product question; it is a
sentence that could be read two ways where the document set already reveals which one was meant.

Pick the reading with more evidence, then record all five things: the assumption, the reading, the
evidence, the **falsifier**, and the blast radius if it is wrong.

**The falsifier is mandatory.** If you cannot state what observation would prove the assumption
wrong, you do not have an evidenced assumption — you have a preference. Send it back to T1 for more
searching, or up to T4.

### Choosing between T3.5 and T4: what does being wrong cost?

| If the assumption is wrong… | Tier |
| --------------------------- | ---- |
| One row of a report changes; nobody has acted on it | **T3.5** |
| One sentence of a document changes, traceable through the fix table | **T3.5** |
| It has been written into documentation of a running system that people follow | **T4** |
| It drags a technical, contractual, or compliance decision that cannot be walked back | **T4** |

Asymmetry decides, not difficulty. A hard question with a cheap wrong answer is T3.5.

## T4 — the last resort

A row reaches the user only when every box below is ticked. The boxes are not ceremony: each one
names a place where the answer usually turns out to be available.

1. T1 exhausted — all four sources, with the terms and files recorded.
2. T2 exhausted — at least two reviewers agreed it is **undecidable**, not merely disagreed.
3. T3 exhausted — or the question is provably not an external fact.
4. T3.5 rejected, saying which half failed: no reading has more evidence, and/or being wrong is
   expensive.
5. The user has not already answered it. Re-read the request before asking.
6. Options, consequences, a recommendation, and a default are written out.

Then five rules on top:

* **Every T4 candidate is challenged before it reaches the user.** The lead sends the candidate
  list to the requirement and coverage reviewers with one instruction: *prove this is resolvable at
  T1–T3.* Only what survives goes to the gate. In practice most candidates die here, to one search
  in the documents' own vocabulary — which is exactly why the lead cannot be the one to judge its
  own questions.
* **Batch at the end.** One gate, after the review loop converges. A reviewer in a later wave
  routinely deletes an earlier wave's question.
* **Cap the count.** Default three, or `--max-questions`. Above the cap, do **not** ask seven
  questions: group them and report one finding about the spec — `spec quality: N ambiguities of the
  same kind` — with three representatives. Seven separate questions interrupt seven times and still
  fail to say that the spec is missing a section.
* **Every row carries a default**, phrased so silence is a valid answer. The default is applied and
  recorded as an assumption. No gate blocks indefinitely.
* **Recommend.** A question with no recommendation moves the whole task to the reader.

### The gate is self-contained

This skill runs on machines whose setup you know nothing about.

1. **Never invoke another skill to run the gate.** It must work on a bare install with no other
   plugins. (Reviewers cannot invoke skills at all — they are not granted the capability.)
2. **Never emit another skill's trigger phrase** in the skill body, the output, or the report. Some
   setups run approval protocols keyed to a literal phrase; printing one would trip a mechanism
   belonging to someone else's machine. Use the label `DECISION GATE`, which is ours.
3. **Print the gate in the format `report-schema.md` defines**, and nothing more.

If the user's own environment has an approval mechanism, that is theirs to invoke — not ours to
detect, call, or assume.

---

## Rationalizations, and what is actually true

| Excuse | Reality |
| ------ | ------- |
| "The spec is unclear here, so I'll ask" | T1 is not exhausted. `docs-history.md`, the code, and the previous report are artifacts. Skipping all three makes this a lazy question, not an ambiguity. |
| "Searching takes longer than asking" | Longer for you, slower for them, and their answer still has to be verified by the search you skipped. |
| "I'm not sure how library X behaves — better confirm" | T3, not T4. The user is not an authoritative source for framework behaviour; the docs are. |
| "The reviewers disagree, let the user decide" | T2 has not run. One evidenced challenge first; the user gets only what survives it. |
| "I'll ask each question as it comes up, to be safe" | Drip-feed. Batch every T4 into one gate at the end. |
| "I remember that this library caps at 100" | Memory is not a source. T3 needs a fetch and a version. |
| "The user probably mentioned it, but I'll confirm" | Re-read the request. Asking for something already answered signals you did not read it. |
| "No source could answer, so it's a question for the user" | If three portable steps failed, the user's steps would fail too. That is `Undecided` with the attempts recorded, not a gate. |
| "Nobody can answer this, so I'll pick one and mark it Covered" | The reverse failure, and the worse one. Deciding is allowed at T3.5 — **recorded**, with a falsifier. Deciding silently is a fabricated verdict. |
| "The ratio looks good, so the ladder is working" | A perfect ratio with no assumptions recorded and verdicts that moved during the loop means decisions were made and not written down. |

## Who enforces this

The lead cannot audit its own escalations — its own questions always look reasonable from inside.
So:

* **The failure reviewer** rejects any row heading for the user that has not proved T1–T3
  exhausted, and any assumption without a falsifier.
* **The lint** enforces what is mechanically checkable: gate completeness, the falsifier column,
  the question cap, and the two ratio warnings at both ends. Check ids are in `report-schema.md`.
* **`--ask-only`** skips tiers 1–3 and surfaces everything. It is a diagnostic for inspecting what
  the ladder is absorbing. It is never the default, and a report produced that way says so.

## Red flags

- About to ask the user something before searching the documents' own vocabulary
- About to ask about library or API behaviour instead of fetching its documentation
- About to escalate a reviewer disagreement without one evidenced challenge
- About to record an assumption with no falsifier
- About to open a decision gate with an unticked precondition, or with no default
- About to ask more questions than the cap instead of reporting a spec-quality finding
- About to mark a row `Covered` on a reading you chose, with no assumption recorded
- About to name another skill, or print another skill's trigger phrase, to run the gate
