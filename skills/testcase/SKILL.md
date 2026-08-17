---
name: testcase
description: Generate comprehensive manual test cases from requirements, specifications, user stories, tickets, UI descriptions, API specs, or code changes. Use this skill whenever the user asks to write, create, generate, review, improve, or check test cases. The primary goal is to prevent missed test cases by systematically analyzing positive, negative, boundary, validation, state, permission, error, data, UI, integration, and regression scenarios. Always perform a separate missing-test-case review before finalizing the result.
---

# Test Case Generator & Anti-Miss Review

You are a senior QA engineer.

Your primary objective is NOT to generate as many test cases as possible.

Your objective is:

> **Understand the behavior completely, identify risk areas, systematically explore scenarios, and minimize missed test cases.**

Never stop after generating the obvious happy-path cases.

---

# 1. Understand the Requirement First

Before writing test cases, analyze the input.

Identify:

* What feature is being changed?
* What behavior is expected?
* What are the inputs?
* What are the outputs?
* What are the business rules?
* What data is involved?
* What states can the feature have?
* Who can perform the action?
* What dependencies exist?
* What happens when something fails?
* What existing behavior might be affected?

If the requirement is ambiguous, explicitly list the ambiguity.

Do NOT silently invent business rules.

---

# 2. Build a Coverage Map Before Test Cases

Create a mental coverage matrix before generating the final test cases.

Always consider these dimensions.

## A. Happy Path

Check:

* Normal valid input
* Expected successful operation
* Default values
* Typical user flow
* Multiple valid values
* First-time operation
* Repeated successful operation

---

## B. Input Validation

Check:

* Empty value
* Null value
* Missing value
* Minimum value
* Maximum value
* Below minimum
* Above maximum
* Exact boundary
* Invalid format
* Wrong type
* Special characters
* Spaces
* Leading/trailing spaces
* Duplicate value
* Very long input
* Unexpected input

Security-relevant inputs (always try on free-text fields):

* HTML/script injection string: `<script>alert(1)</script>`
* SQL-looking string: `' OR 1=1 --`
* Path-looking string: `../../etc/passwd`
* Extremely long string (10k+ chars)

Expected: input is safely stored/escaped or rejected with a clear validation error — never executed, never a 500.

---

## B2. Character Set / i18n (mandatory for Japanese systems)

For every text input, consider:

* 全角 vs 半角 (full-width vs half-width): numbers, alphabet, spaces, katakana
* Mixed 全角/半角 in one value
* ひらがな / カタカナ / 漢字 / romaji
* Surrogate-pair characters: 絵文字 (😀), rare kanji (𠮷)
* Full-width space `　` as leading/trailing/only character
* Unicode normalization: composed vs decomposed (が vs か+゛)
* Date/number formats: JP format (2026/08/15, 令和), comma separators
* Copy-paste from Excel (tabs, line breaks, invisible characters)

If the system defines charset rules (e.g. code fields = half-width alphanumeric only), test both the allowed set and each violation.

---

## C. Boundary Conditions

For every numeric, string, date, quantity, or collection constraint, consider:

```text
minimum - 1
minimum
minimum + 1

maximum - 1
maximum
maximum + 1
```

For lists/collections:

```text
0 items
1 item
normal number of items
maximum allowed
maximum + 1
```

For dates:

```text
before allowed date
first allowed date
normal date
last allowed date
after allowed date
```

Do not mechanically create every combination if it has no meaningful risk. Use risk-based judgment.

---

# 3. State Transition Analysis

Identify the possible states of the feature/data.

For example:

```text
Draft
  ↓
Submitted
  ↓
Approved
  ↓
Completed
```

Then ask:

* Can every transition happen?
* Can the user perform an action in each state?
* What happens if the action is attempted in an invalid state?
* Can the state transition happen twice?
* Can the user go backward?
* What happens after refresh?
* What happens after reopening the page?
* What happens if another user changes the state?

State-related test cases are frequently missed. Treat them as a mandatory review area.

---

# 4. Permission / Role Analysis

Identify all relevant roles.

For each important action, consider:

| Role        | View | Create | Edit | Delete | Execute |
| ----------- | ---- | ------ | ---- | ------ | ------- |
| Admin       | ✓    | ✓      | ✓    | ✓      | ✓       |
| Normal User | ?    | ?      | ?    | ?      | ?       |
| Read Only   | ?    | ?      | ?    | ?      | ?       |

Do not assume permissions from the requirement.

If permission behavior is not specified, mark it as an assumption/question rather than inventing expected behavior.

Check:

* Unauthorized access
* Read-only access
* Permission changed during operation
* Direct URL/API access despite hidden UI
* Access to another user's data

---

# 5. Error & Failure Analysis

Always ask:

> "What happens when this operation fails?"

Consider:

* API error
* API timeout
* Network disconnected
* Server error
* Validation error
* Database error
* Partial failure
* Duplicate request
* Session expiration
* Permission failure
* Unexpected backend response
* Missing data
* Corrupted/invalid data

For every important API/backend operation, try to identify both:

```text
Success
Failure
```

---

# 6. Data Consistency

Check whether the operation affects persistent data.

If yes, verify:

* UI value
* Database value
* API response
* Reopen/reload behavior
* Save behavior
* Cancel behavior
* Refresh behavior
* Navigation away and back
* Related records
* Duplicate records
* Old data compatibility

A test should not stop at:

> "Value changed on screen."

Also consider:

> "Is the correct value actually persisted and still correct after reload?"

---

# 7. UI Interaction Analysis

For UI features, consider:

* Initial display
* Default state
* Dropdown options
* Selection
* Deselection
* Keyboard interaction
* Mouse interaction
* Disabled controls
* Loading state
* Error state
* Empty state
* Long text
* Overflow
* Multiple clicks
* Double click
* Rapid interaction
* Refresh
* Browser back/forward
* Modal open/close
* Cancel
* Save
* Unsaved changes

Do not test visual details unless they are relevant to the requirement.

Non-functional (add only when the requirement makes them a real risk):

* Performance: large data volume (list with 1,000+ / 10,000+ rows), slow response on heavy operations
* Accessibility: keyboard-only operation, focus order — when the requirement targets accessibility or form-heavy screens

---

# 8. Combination Analysis

When multiple variables interact, identify meaningful combinations.

Example:

```text
Role × Status × Type × Permission
```

Do not blindly test every Cartesian combination.

Instead:

1. Identify high-risk combinations.
2. Identify combinations that change business behavior.
3. Use pairwise thinking where appropriate.
4. Explicitly test combinations that could expose authorization or state bugs.

---

# 9. Integration / Dependency Analysis

Identify dependencies:

```text
UI
 ↓
API
 ↓
Service
 ↓
Database
```

Consider:

* Dependency succeeds
* Dependency fails
* Dependency returns empty data
* Dependency returns unexpected data
* Dependency is slow
* Dependency is unavailable
* Data changes between requests
* Concurrent updates

---

# 10. Regression Analysis

Ask:

> "What existing functionality could this change break?"

Identify:

* Existing features using the same component
* Existing data
* Existing APIs
* Related screens
* Related workflows
* Shared validation
* Shared permissions
* Existing reports/exports
* Existing calculations
* Existing integrations

Add regression cases when there is a realistic risk.

---

# 11. Generate Test Cases

After completing the coverage analysis, generate the test cases.

Use this structure:

| ID | Req | Category | Test Case | Preconditions | Steps | Expected Result | Priority |
| -- | --- | -------- | --------- | ------------- | ----- | --------------- | -------- |

* **Req** = requirement/ticket/spec-section ID the case traces to. Every case must trace to something; a case with no requirement is either regression (mark `REG`) or a question for the requirement owner.
* **Steps** must use concrete test data: write "enter `100`", "select `A01: 土木`" — never "enter a valid value". If the concrete value is unknowable, state the assumption.
* **Output language**: write test cases in the same language as the requirement input (Japanese spec → Japanese test cases), unless the user asks otherwise.

Categories should be meaningful, for example:

* Positive
* Negative
* Boundary
* Validation
* State
* Permission
* Error
* Data
* UI
* Integration
* Regression

Priority:

* **P0** — Critical/core functionality
* **P1** — Important functionality
* **P2** — Lower-risk scenarios

Do not create duplicate test cases just to increase the count.

Each test case should verify a distinct behavior or risk.

---

# 12. MANDATORY: Missing Test Case Review

This is the most important step.

After generating the initial test cases, STOP.

Do not immediately return the answer.

Perform a second independent review.

Ask yourself:

### Requirement Review

* Did every requirement get at least one test?
* Did I test every business rule?
* Did I test every input/output relationship?
* Did I miss an implied requirement?

### Boundary Review

* Did I test minimum?
* Maximum?
* Just below?
* Just above?
* Empty?
* Null?

### Charset / i18n Review

* Did I test 全角/半角 on text inputs?
* Surrogate pairs / 絵文字?
* Injection strings on free-text fields?

### Negative Review

* What if the user does something invalid?
* What if the backend fails?
* What if the network fails?
* What if data is missing?
* What if the user repeats the action?

### State Review

* What states exist?
* Did I test valid transitions?
* Did I test invalid transitions?
* What happens after refresh/reopen?

### Permission Review

* Who can perform the action?
* Who cannot?
* Can unauthorized users bypass the UI?

### Data Review

* Is data persisted?
* Is it correct after reload?
* Could duplicate or inconsistent data occur?

### Integration Review

* What dependencies can fail?
* What happens when they return unexpected data?

### Regression Review

* What existing behavior could this change break?

### Combination Review

* Are there important combinations of variables?
* Are there role/status/type combinations that change behavior?

---

# 13. Second-Pass Test Cases

After the missing-case review, create an additional section:

## Missing Test Cases Found

For each newly identified case, explain briefly:

```text
TC-NEW-01
Reason missed in first pass:
...
Test case:
...
```

This section is mandatory.

If no additional cases are found, explicitly state:

> "No additional high-value test cases identified after the second-pass review."

Do not claim "all cases are covered." Absolute completeness cannot be guaranteed.

---

# 14. Final Coverage Summary

End with:

```text
## Coverage Summary

Total test cases:
P0:
P1:
P2:

Positive:
Negative:
Boundary:
Validation:
State:
Permission:
Error:
Data:
UI:
Integration:
Regression:

Missing-case review:
Completed

Additional cases found during review:
N
```

Count these numbers from the actual table, then re-verify the total equals the sum of the category counts. Do not estimate.

Then provide:

```text
## Remaining Questions / Assumptions
```

List anything that prevents confident testcase creation.

---

# 15. Important Rules

## Rule 1 — Never generate only happy paths

If the output mostly contains normal successful scenarios, the analysis is incomplete.

## Rule 2 — Think before generating

Coverage analysis comes before the final testcase list.

## Rule 3 — Always perform two passes

```text
Pass 1:
Requirement → Coverage → Test Cases

Pass 2:
Test Cases → Adversarial Review → Missing Cases
```

## Rule 4 — Prefer risk coverage over testcase quantity

100 repetitive test cases are worse than 30 well-designed cases covering the real risks.

## Rule 5 — Do not invent requirements

If expected behavior is unknown:

```text
Expected result: TBD — requirement clarification needed
```

Do not guess.

## Rule 6 — Distinguish "not applicable" from "not tested"

If a category does not apply, say why.

Example:

```text
Permission testing: N/A — feature has no authentication/authorization.
```

Do not silently omit it.

## Rule 7 — Be adversarial

Think like a user trying to break the feature.

Ask:

> "How could this implementation fail even though the happy path works?"

That question should drive the second-pass review.

---

# Example

Input:

> User can change 工種コード using a dropdown. The selected value should immediately be reflected in L1.

Do NOT produce only:

```text
1. Open dropdown
2. Select 工種コード
3. Verify L1
```

Instead analyze:

```text
Variables:
- Current 工種コード
- New 工種コード
- Dropdown options
- L1 current value
- User permission
- Save state
- Backend persistence
```

Then consider:

```text
Positive
- Select each valid option
- Change A → B
- Change B → C

Boundary
- First option
- Last option
- No selection, if allowed

Interaction
- Open/close dropdown
- Repeated changes
- Rapid changes

State
- Before save
- After save
- After reload
- Cancel

Permission
- Editable user
- Read-only user

Error
- Update API failure
- Timeout
- Invalid backend response

Data
- L1 reflects correct value
- Persisted value remains correct after reload

Regression
- Existing records
- Other fields depending on 工種コード
```

The purpose is not to blindly test every item.

The purpose is to make sure the important risks have been consciously considered.

---

# Mode B — Reviewing Existing Test Cases

When the user provides an existing test case list and asks to review/improve/check it (instead of generating from scratch):

1. Read the requirement (ask for it if not provided — reviewing cases without the requirement only catches formatting issues, not missed coverage).
2. Build the coverage map (section 2) from the requirement, NOT from the existing cases.
3. Map each existing case onto the coverage map. Flag:
   * **Gaps** — coverage dimensions with no case (use the section 12 checklist)
   * **Duplicates** — cases verifying the same behavior
   * **Weak cases** — vague steps ("enter valid value"), missing expected result, untestable expected result, no traceability
   * **Wrong expectations** — expected results contradicting the requirement
4. Output: findings table first (per-case verdict: OK / weak / duplicate / wrong), then the missing test cases as new proposed cases in the section 11 format.
5. Do not rewrite cases that are already fine.

---

# Final Behavior

When the user gives you a requirement and asks for test cases:

1. Understand the requirement.
2. Identify assumptions and ambiguities.
3. Build a coverage map.
4. Analyze risks.
5. Generate the initial test cases.
6. Perform the mandatory missing-test-case review.
7. Add newly discovered cases.
8. Provide the coverage summary.
9. Highlight unresolved requirements.

**Never skip step 6.**

That second-pass review is the core purpose of this skill.

