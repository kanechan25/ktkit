<!-- group: Frame | order: 15 -->
# ktkit:raise-issue — a messy complaint becomes an issue another agent can start from

The step before analysis. It takes what someone actually said — a chat message, a screenshot, half a
GitHub issue — and turns it into one Vietnamese file that states the problem, the current state, the
evidence and what is still unknown. **No cause, no fix, no spec.** Naming a cause here anchors every
later phase to one line of enquiry before any evidence exists, so the skill is forbidden from doing
it even when the answer looks obvious.

```
/ktkit:raise-issue "the export button does nothing on the reports screen"
```

## The cases

```bash
# the normal one — describe it, let the skill frame it
/ktkit:raise-issue "share links expire after an hour, they used to last a day"

# a description that already lives in a file
/ktkit:raise-issue --file notes/from-support.md

# pointing at a GitHub issue: exactly one read, body and labels only, never the comments
/ktkit:raise-issue --issue 4821

# you already know it is a change request, not a defect
/ktkit:raise-issue --type cr "deadline should count working days, not calendar days"

# re-raising into a folder that exists, without being asked to approve the slug again
/ktkit:raise-issue --slug 4821-export-button-dead "still broken after the deploy"

# somewhere other than the artifact root
/ktkit:raise-issue --out docs/triage "the totals row disappears above 500 items"

# do not interview me; every gap becomes [MISSING]
/ktkit:raise-issue --no-ask "..."
```

## What you get

```
.claude/claude/prompts/<slug>/<slug>-<YYYYMMDDHHMM>.md
```

Under `prompts/`, which is what makes it an **input** to the rest of the toolkit rather than a note.
Re-raising the same problem writes a new timestamped file in the same folder — nothing is ever
overwritten, so the successive framings of one problem stay readable side by side.

## The two gates

| Gate | What it does |
| ---- | ------------ |
| **Missing data** (soft) | A required field is empty and you do not know it → the file is written anyway, marked `[MISSING]`. Missing data never blocks you. |
| **S5b confirm** (hard) 🔴 | The skill replays the problem in ≤ 10 lines and asks whether that is the problem you are hitting. **No `đúng`, no file.** `--no-ask` does not skip it; nothing does. |

The confirm comes *after* verification on purpose: by then you are looking at the `[UNVERIFIED]` and
`[LOCATED]` lines too, which is where a misremembered screen or function name gets caught — the
single most expensive error this skill can make.

## Every fact carries a label

`[CONFIRMED]` you said it · `[GH #N]` from the issue body · `[SCREENSHOT]` read off an image ·
`[VERIFIED path:line]` you named it and it checks out · `[UNVERIFIED]` you named it and it does not,
with the searches listed · `[LOCATED path:line ← anchor "<s>" trong <area>]` the skill found it and
you have not looked · `[ASSUMED: …]` inferred, and it must say what would make it wrong ·
`[MISSING]` no data. A bare identifier anywhere in the file is a bug.

## Do not

| Anti-pattern | Why |
| ------------ | --- |
| Expect a diagnosis | It stops before one deliberately. `/ktkit:rca` does that, and does it better for having a framed problem to start from. |
| Expect blast radius or options | That is `/ktkit:analyze-feat`. |
| Use it as a search tool | LOCATE is capped at 6 calls and 1 `Read`, and stops at *where the string appears* — never climbing into the hooks above it. Failing is a legitimate, cheap outcome. |
| Point it at GitHub without a number | Without `--issue` it must not touch the forge at all — no listing, no searching, no guessing the number off a branch name. |
| Tidy up §9 | It keeps your words verbatim. Editing it destroys the one section everything else can be checked against. |

## See also

`/ktkit:help chain` — hand the file straight to `/ktkit:chain` and the analysis, spec and plan follow
from it. `/ktkit:help rca` · `/ktkit:help analyze-feat` — the next step if you drive by hand.
