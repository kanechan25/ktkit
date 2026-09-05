---
name: escalation-ladder
description: Use the moment anything in a task is unknown — a term that cannot be found, two sources disagreeing, a sentence with two readings, a fact about a library — to decide whether to search, challenge, look it up, assume with a falsifier, or ask the user. Classifies every unknown into one of five tiers before acting, and forbids asking the user until the tiers below are provably exhausted. Also use when a document or plan already carries a list of open questions and you want them triaged and resolved instead of handed back.
allowed-tools: Read, Grep, Glob, Bash, Agent
---

# Escalation Ladder

Read this whenever the work produces something you do not know.

The failure this file prevents is not guessing. It is **escalating** — turning every unknown into a
question for the person you are working with, when most unknowns are answerable from the repository,
the documents already in scope, or a public source. A question they have to research themselves is
not a finding; it is the work handing itself back.

The opposite failure is real too, and worse: deciding something quietly and presenting it as
established. Tier 3.5 exists so that deciding is possible **and recorded**.

Every unknown gets classified into exactly one tier **before** you do anything with it.

---

## The ladder

| Tier | It belongs here when | Who resolves it | Exit criteria |
|---|---|---|---|
| **T1 · RESOLVABLE** | The answer exists in something that can be opened: the project's documents, the source, a file's own history, an artifact the work is about, a prior run of this same workflow | a resolver subagent | Found, with `file:line` and a verbatim quote |
| **T2 · CONFLICT** | Two sources say different things and **both cite evidence** | one round of cross-examination | One side refuted **with evidence** |
| **T3 · EXTERNAL FACT** | The fact lives outside the project: library or API behaviour, a format, a standard, a service limit | you, via the portable ladder below | An authoritative source **plus its version** |
| **T3.5 · EVIDENCED ASSUMPTION** | Two readings exist, **but one has more evidence** — a convention repeated across the project, a precedent elsewhere, what the code does, what the history shows — **and** being wrong is cheap to correct | you | A reading, its evidence, and a **falsifier** |
| **T4 · TRUE AMBIGUITY** | Two or more readings are equally supported, the consequences differ materially, and being wrong is expensive or hard to reverse. Nobody has made this decision yet | **the user** | The user decides — or the recorded default applies |

**You may only move up a tier by proving the tier below is exhausted. Not by finding it hard.**
Every tier has a written exit criterion precisely so "exhausted" is a claim someone else can check.

Record the tier next to every unknown in whatever artifact the calling workflow writes. That record
is what separates a real gap from a search that stopped early — the two are indistinguishable
without it.

---

## Before anything: the decision log

If the project keeps a decision log for this work — by convention
`.claude/context/decisions/<slug>.md` — **read it first**.

A question already carrying an ID there is **settled**. Do not ask it again, and do not decide it
again either; quote the existing entry and move on. Re-deciding a logged question silently
overwrites a decision somebody made on purpose.

---

## T1 — search before you conclude

Sources, in this order. A "not found anywhere" conclusion, or a T4 escalation, that skipped any of
them is a search failure, not a gap.

1. **The project's own documents, searched with the documents' vocabulary — not the request's.**
   A request saying "second approver" will never match a manual saying "dual sign-off". Build the
   term set from the words the documents themselves use: add synonyms, abbreviations, field names,
   and — for a non-English document set — both the original term and its English gloss. **Record the
   expanded term list** next to the unknown; it is the evidence that the search was real.
2. **The source code**, when the documents describe a system that exists. Code is not the standard
   the work is measured against, but it is evidence about what a term means.
3. **The file's own history** — the last commits that touched it (`git log -5 -- <path>`).
4. **The artifact the work is actually about**, when the question is about its content — a
   spreadsheet, a template, a binary export. Open it **with a real parser for that format**.
   ⛔ Never pattern-match a regex over a container format: it silently returns nothing and the
   nothing looks like an empty file.
5. **A prior run of this same workflow** — an earlier analysis, spec, or note for the same work
   item. A question answered last round is answered.
6. **Live operational data**, *if* this session has a read-only tool for it.
7. **Cross-session memory**, *if* this session has one.

Steps 6 and 7 are conditional on purpose. **Detect the tool at runtime; never hardcode a tool
name.** Tool names are specific to the machine the session runs on, and a workflow that assumes
yours will fail on everyone else's. If no such tool is present, that source simply does not exist
this run — say so, do not invent it.

If a search shows a section whose topic matches but whose wording does not, **read that section**
rather than trusting the search.

### How T1 actually gets done: dispatch, do not read

⛔ **Do not open the files yourself.** In an agentic loop your context is re-sent on every turn, so
a file read at turn 3 with twenty turns to go is paid for twenty more times. Worse, touching a file
can pull in the project's own auto-loaded conventions — tens of thousands of tokens — into the
context you keep.

So: **one unknown, one resolver subagent.** Dispatch `escalation-resolver` (or
`<plugin>:escalation-resolver` when installed as a plugin), giving it exactly one question, the
paths it may read, and nothing else.

⛔ **Never pass it your own reasoning or your candidate answer.** Shared analysis is what makes a
subagent confirm your blind spot instead of testing it.

Several independent unknowns → dispatch them **in one message** so they run concurrently.

**Budget**: at most 5 resolvers per round, at most 2 rounds for the same question. Out of budget is
not a reason to escalate — it moves the unknown to T3.5 if a reading is better evidenced, or leaves
it `Undecided`.

You hold three kinds of thing: the question, the tier, and a one-line conclusion with its citation.
Nothing else enters your context.

---

## T2 — one round of challenge, then move on

Two sources disagreeing is not an ambiguity; it is an unverified claim on at least one side. Put the
claim to the other side **once**. Each answer is `UPHELD` or `REFUTED`, with evidence.

* One side refuted → settled. Record the exchange and the refuting evidence.
* Neither refuted after one exchange → **do not run a second exchange.** Go to T3.5 if one reading
  has more evidence, T4 if neither does.

A disagreement that survives one evidenced challenge is information about the request, not a reason
to keep spending rounds.

If the project declares an arbiter for conflicts — see the adapter below — apply it instead of
guessing which source wins.

---

## T3 — external facts, portably

Take the first step that works:

1. **A documentation lookup tool, if this session has one.** Detect it at runtime — look for a tool
   whose name suggests documentation retrieval — and use it if present. ⛔ Never hardcode the name.
2. **Fetch the official documentation page.** Record the URL and the version.
3. **Read the dependency actually installed in the project** — the manifest or lockfile for the
   version, then the installed package's own source or README. This is often *more* accurate than
   published docs, because it is the version in use.
4. **None of the three worked → stop. Do not escalate to T4.** Record the unknown as `Undecided`
   with the note `external fact unverifiable: <fact>; tried 1,2,3`.

Step 4 is the load-bearing one. A fact the tooling cannot reach is not a product decision, and the
user cannot answer it either — they would have to run the same three steps. Asking them converts a
tooling limit into an interruption.

⛔ **Never answer a T3 question from memory.** A remembered version number is a fabricated citation
with a plausible shape.

---

## T3.5 — decide, and write down what would prove you wrong

This is the tier that keeps T4 small. Most ambiguity is not a live product question; it is a
sentence that could be read two ways where the project already reveals which one was meant.

Pick the reading with more evidence, then record all five: the assumption, the reading, the
evidence, the **falsifier**, and the blast radius if it is wrong.

**The falsifier is mandatory.** If you cannot state what observation would prove the assumption
wrong, you do not have an evidenced assumption — you have a preference. Send it back to T1 for more
searching, or up to T4.

### T3.5 or T4: what does being wrong cost?

| If the assumption is wrong… | Tier |
|---|---|
| One line of a document changes; nobody has acted on it | **T3.5** |
| Where a file goes, what something is named, how something is presented — and a precedent exists | **T3.5** |
| It has been written into documentation of a running system that people follow | **T4** |
| It drags a technical, contractual, or compliance decision that cannot be walked back | **T4** |

**Asymmetry decides, not difficulty.** A hard question with a cheap wrong answer is T3.5.

The project may narrow or widen this table — see the adapter.

---

## Rulings, not stalls

A running task does not wait on a human. Conflicts, ambiguities, defects in the plan, a budget you
would have asked to exceed — **decide them.** Record each as

```
Ruling: <what you decided> — <why> — <what it costs if wrong>
```

and keep going. A wrong ruling costs rework the user can see and undo; a session parked on a
question costs their whole day and buys nothing.

**Four things stop you, and only these:**

1. an irreversible or destructive operation;
2. a security-sensitive action;
3. a side effect outside this workspace that norms say you ask about first — a merge, a push to a
   shared branch, a publish;
4. a plan so broken that every path forward is a guess.

Everything else is a ruling.

---

## T4 — the last resort

An unknown reaches the user only when every box below is ticked. The boxes are not ceremony: each
one names a place where the answer usually turns out to be available.

1. T1 exhausted — the sources that exist this run, with the search terms and files recorded.
2. T2 exhausted — one evidenced challenge has already run, or there is no second source to challenge.
3. T3 exhausted — or the question is provably not an external fact.
4. T3.5 rejected, **saying which half failed**: no reading has more evidence, and/or being wrong is
   expensive.
5. The user has not already answered it — re-read the request **and the decision log** before asking.
6. Options, consequences, a **recommendation**, and a **default** are all written out.

Then four rules on top:

* **Batch at the end.** One gate, once, after the work converges. A later pass routinely deletes an
  earlier pass's question.
* **Cap the count at 3.** Above the cap, do **not** ask seven questions: group them and report one
  finding — `N ambiguities of the same kind` — with three representatives. Seven separate questions
  interrupt seven times and still fail to say that the request is missing a section.
* **Every row carries a default, phrased so silence is a valid answer.** The default is applied and
  recorded as an assumption. No gate blocks indefinitely.
* **Recommend.** A question with no recommendation moves the whole task to the reader.

### Gate format

```markdown
## ⛔ NEEDS A DECISION — silence accepts the default (max 3 rows)
| # | Question | Default applied | Recommendation | Cost if wrong | Where it changes |

## ✅ SETTLED WITHOUT YOU (T1/T2/T3) — read only, no answer needed
| Question | Tier | Conclusion | Evidence (file:line) |

## 🟡 ASSUMPTIONS TAKEN (T3.5)
| ASM | Reading chosen | Evidence | Falsifier | Blast radius |
```

Close the artifact with one metric line:

```
self_resolve_ratio=0.88 · self_resolved=7 · needs_user=1 · assumptions=1 · gates=1
```

`self_resolve_ratio = self_resolved / (self_resolved + needs_user)`, two decimals.

**A ratio below 0.70 means tiers 1–3 were not exhausted.** Go back to T1 — do not ship the artifact.
An assumption with an empty falsifier is the same kind of defect: fix it or escalate it.

⛔ **Print the tables into the artifact file, not into the conversation.** A table printed to chat is
billed as output and then re-billed on every following turn, and the content is already in the file.
The conversation gets the path and the metric line.

---

## Per-project calibration: the adapter

Nothing above names a specific project, tool, or directory, on purpose — the ladder has to work in
any repository.

Where a project needs to be specific, it declares it in `.claude/context/repo-adapter.md`:

| Section | What it declares |
|---|---|
| **1. Doc SOT** | Which directory is authoritative and which is generated |
| **2. Datastore probe** | The read-only tool or command for live data, if any |
| **3. Artifact reader** | How this project's unusual formats must be read, and what is forbidden |
| **4. Arbiter** | When two sources conflict, which one wins, and who decides |
| **5. Cost asymmetry** | The project's own version of the T3.5-versus-T4 table |

**Read it if it exists.** If it does not exist, the ladder still runs — but with no cost table you
must default to the tight side: **treat the unknown as T4.** Not knowing what being wrong costs is
itself a reason not to decide alone.

---

## Rationalizations, and what is actually true

| Excuse | Reality |
|---|---|
| "It's unclear here, so I'll ask" | T1 is not exhausted. The file's history, the code, and the prior run are artifacts. Skipping all three makes this a lazy question, not an ambiguity. |
| "Searching takes longer than asking" | Longer for you, slower for them, and their answer still has to be verified by the search you skipped. |
| "I'm not sure how library X behaves — better confirm" | T3, not T4. The user is not an authoritative source for framework behaviour; the docs are. |
| "The two sources disagree, let the user decide" | T2 has not run. One evidenced challenge first; the user gets only what survives it. |
| "I'll ask each question as it comes up, to be safe" | Drip-feed. Batch every T4 into one gate at the end. |
| "I remember that this caps at 100" | Memory is not a source. T3 needs a fetch and a version. |
| "They probably mentioned it, but I'll confirm" | Re-read the request and the decision log. Asking for something already answered signals you did not read it. |
| "No source could answer, so it's a question for the user" | If the portable steps failed, theirs would fail too. That is `Undecided` with the attempts recorded, not a gate. |
| "Nobody can answer this, so I'll pick one and call it settled" | The reverse failure, and the worse one. Deciding is allowed at T3.5 — **recorded**, with a falsifier. Deciding silently is a fabricated conclusion. |
| "I'll read the files myself, it's faster" | It is faster this turn and costs every later turn. Dispatch a resolver. |
| "The ratio looks fine, so the ladder worked" | A perfect ratio with no assumptions recorded, and conclusions that moved without a reason written down, means decisions were made and not written down. |

---

## Red flags

- About to ask the user something before searching the documents' own vocabulary
- About to ask about library or API behaviour instead of fetching its documentation
- About to escalate a conflict without one evidenced challenge
- About to record an assumption with no falsifier
- About to open a gate with an unticked precondition, or with no default
- About to ask more questions than the cap instead of reporting one finding about the request
- About to present a reading you chose as established fact, with no assumption recorded
- About to open files yourself instead of dispatching a resolver
- About to re-decide a question the decision log already settled
- About to name a tool that this session has not been shown to have
