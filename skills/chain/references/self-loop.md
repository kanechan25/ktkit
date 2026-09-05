# Step 02 — the self-clarify loop

The analysis skills deliberately do not ask. `/ktkit:analyze-feat` says so in as many words at its
Phase 1: *"⛔ This phase asks the user nothing."* What survives its ladder lands in a table instead
of in a question.

That table is this step's input. Nothing here re-analyses; it resolves.

## What the loop is not

- Not a second ladder. The tiers, the 5-per-round budget and the 2-round cap all come from
  `/ktkit:escalation-ladder`. This file says *when* the loop runs and *what it reads*, nothing more.
- Not a rewrite of the artifact. It replaces one delimited block and touches nothing else.
- Not a place to ask the user. The only gate is at step 03.

## The loop

```
INPUT : path to A (.analyze.md) · path to resolved.md · --rounds N
OUTPUT: A's gate block replaced · resolved.md longer · steps/02-clarify.md

1. Read ONLY A's gate block.
       sed -n '/^## 10\./,$p' <A>          (feature arm)
       sed -n '/^### Unknowns and how each was settled/,$p' <A>   (bug arm)

2. Split it into the three tables: settled · assumptions · T4 pool.

3. For each row that is not already settled:
       ledger.py <ledger> --lookup "<question>"
         HIT  ⇒ cite that row, do not spawn                     [saving 2]
         MISS ⇒ queue it

4. round = 1
   while queue and round <= N:
       take at most 5 questions                                 [ladder budget]
       dispatch Agent(subagent_type: "ktkit:escalation-resolver")
           one question per agent
           ALL of them in ONE message                           [saving 3]
           pass the question, the paths it may read, nothing else
       each agent returns exactly one line
       ledger.py --next-id, then --add, per returned line
       drop from the queue whatever reached T1 / T2 / T3 / T3.5
       round += 1

5. What is left is T4. Cap at 3 rows; more than that becomes one row
   "N ambiguities of the same kind" plus three representatives, and the
   requirement is missing a section.

6. ledger.py <ledger> --metric
       exit 0                       ⇒ go on
       BELOW-FLOOR, rounds left     ⇒ back to 4
       BELOW-FLOOR, out of rounds   ⇒ write it plainly into 02-clarify.md.
                                      ⛔ Do not open the gate. ⛔ Do not
                                      describe the artifact as clean.

7. upsert_block.py <A> --block - --marker chain
8. Write steps/02-clarify.md, append a manifest row.
```

## Where the tokens are saved

Each of these is a mechanism, not an intention.

| # | Mechanism | Why it is cheap |
| - | --------- | --------------- |
| 1 | **Read the gate block, not the report.** | An analysis report has ten-plus sections. In an agentic loop the lead's context is re-sent every turn, so a report opened here is paid for on every turn that follows — `/ktkit:escalation-ladder` makes the same point about opening files at all. The gate block is a fraction of the file and is the only part that contains an unresolved thing. |
| 2 | **Ledger lookup before the spawn.** | The cheapest agent tool set measured on this harness is 6,619 tokens **before it reads anything**. A lookup is a grep. Across A → B → C the same unknown surfaces repeatedly. |
| 3 | **Five resolvers in one message.** | Sequential rounds force the lead to hold round N's results while round N+1 runs. One message, one collection. |
| 4 | **The resolver returns one line.** | Its contract: a verdict with a `file:line`, never the evidence it sifted. ⛔ Never pass it the lead's reasoning either — a subagent shown a hypothesis confirms it instead of testing it. |
| 5 | **Hard ceiling 5 × N.** | Out of budget is not a reason to escalate: the unknown drops to T3.5 if one reading is better evidenced, or is recorded `Undecided`. A loop with no ceiling spends the whole run's budget on the hardest question. |

The expensive part of a chain run is step 01, which walks the codebase. This step reads one block and
spawns bounded agents, so its cost is capped by construction: `5 × N` spawns per phase plus what
those agents read.

## What the resolver may be told

Exactly three things: the question, the paths it may read, and the format of its answer.

⛔ Not the other questions in the queue. ⛔ Not what the analysis concluded. ⛔ Not a candidate
answer. Each of those turns an independent check into a confirmation of the lead's own reading,
which is the failure the whole arrangement exists to avoid.

The resolver holds `Read, Bash` and has **no** `Grep`/`Glob` — declaring `Bash` removes them on this
harness — so it searches through the shell. That is its problem, not the caller's.

## When step 02 does not run

- The gate block has no unsettled rows. Say so in the step file; do not spawn to prove it.
- `--rounds 0`. The T4 pool passes through untouched to step 03, which will gate on it.

Neither case is a failure, and neither is a reason to skip writing `steps/02-clarify.md`. A missing
step file makes the manifest unresumable.
