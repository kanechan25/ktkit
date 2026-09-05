---
name: translate-file
description: Use when the user wants to translate a file's textual content from English or Japanese into Vietnamese while preserving structure/formatting. Triggers "/ktkit:translate-file <path>", "dịch file này sang tiếng Việt". Translates ONLY prose/presentation; keeps every vie-non-trans token unchanged (technical terms, identifiers, proper nouns, module/function/component names, code, file paths, CLI commands, URLs, JSON keys, brand names) in its original language. Japanese proper nouns that stay untranslated get an English gloss in parentheses, e.g. 編集中 (Editing). ALWAYS confirms the exact source file first and BLOCKS until the user confirms before translating; if the source file cannot be determined it STOPS and asks for it. Writes <stem>_vi.<ext> next to the source; never edits the original.
disable-model-invocation: true
argument-hint: "<path/to/source-file> — English/Japanese file; output written as <stem>_vi.<ext> beside it"
user-invocable: true
---

# Translate file (EN/JP → VI) — `/ktkit:translate-file $ARGUMENTS`

Translate the **textual content** of one source file from **English or Japanese** into
**Vietnamese**, translating **only the prose and presentation** while keeping every
**vie-non-trans** token (technical terms, identifiers, proper nouns, module/function/
component names, code, file paths, CLI commands, URLs, JSON keys, brand names) exactly
as written. Write the result to `<stem>_vi.<ext>` beside the source. **Never edit the original.**

## ⛔ Hard guardrails (NEVER break)

- **ALWAYS confirm the source file FIRST** (Step 2) and BLOCK until the user replies `confirm`. No translation before explicit confirm.
- **If the source file cannot be determined** (missing arg, empty/unclear path) → **STOP and ask the user to supply it**. NEVER guess which file.
- Only mutation allowed: write the single output file `<stem>_vi.<ext>` (Step 6). NEVER modify the original.
- NEVER translate/alter identifiers, code symbols, file paths, CLI commands, URLs, JSON keys, proper nouns.
- NEVER change anything inside code blocks / inline code — copy verbatim.
- Do NOT translate source-code files into Vietnamese (violates the repo "code/comments English-only" rule) — see Step 3 scope.
- This skill lives in global `~/.claude/skills/` — invoked manually only.

## Translation principles (CORE)

### Principle #1 — translate prose only; keep vie-non-trans verbatim

**TRANSLATE into natural Vietnamese**: sentences / narrative / descriptions / explanations, the
prose part of headings, prose inside table cells & list items, prose annotations.

**KEEP VERBATIM (vie-non-trans — do NOT translate, do NOT romanize, do NOT change)**:
- Technical terms / domain-spec terminology.
- Identifiers: variable / function / method / class / type / interface / enum / component / module / package names.
- API endpoint / route / HTTP verb / DTO / field / entity / column / schema / table names.
- File paths, filenames, config keys, env vars, constants.
- Code symbols, inline code `...`, and the **entire content of code blocks** (copy verbatim).
- CLI commands, flags, scripts.
- URLs / link targets (keep the URL; if the link's display text is prose, translate the display text only).
- Numbers, codes, IDs, versions, uppercase acronyms (MCD, JV, API, CI…), symbols.
- Proper nouns: person names (keep as-is, do NOT romanize unless necessary), company/product/brand names, app/feature/screen/module names when treated as proper nouns.

### Principle #2 — Japanese proper noun → keep + English gloss

- When a **Japanese** token is treated as a **proper noun in that context** (a module / state / feature /
  screen / status name, an enum value, a fixed identifier/label) → **KEEP the Japanese** and add an
  **English gloss** in parentheses immediately after.
- Format: `<日本語> (English gloss)`. Example: a module named `編集中` → write `編集中 (Editing)`.
- The gloss is **English**, not Vietnamese (it annotates the Japanese name).
- **Only when it is a proper noun.** If the same Japanese token appears as ordinary prose (not a proper
  noun), translate it straight into Vietnamese per Principle #1 — no parentheses.
- Judgment cues for "is it a proper noun?": it's a UI label / status / enum value, it's emphasized or
  backticked/quoted as a name, or it appears as a fixed identifier. When unsure and it's a business noun,
  prefer keep + gloss.

### Preserve structure & presentation
- Markdown: heading levels, bullet/number lists, table pipes, blockquotes, bold/italic, link syntax,
  frontmatter `key:` (translate a prose value, keep the key).
- Code blocks ```` ``` ````: copy verbatim, do not touch.
- Keep the same section order and paragraph correspondence as the original (do not add/remove sections).
- Preserve whitespace / indentation reasonably per the source format.

## Step 1 — Resolve the source file (fail-fast)

```
$ARGUMENTS = "<path/to/source-file>"
```

- Resolve to an absolute path. If **missing / empty / cannot determine** → **STOP**, ask the user to
  supply the exact path. Do NOT guess.
- If the path does **not exist** → STOP, report the wrong path.

## Step 2 — CONFIRM gate (MANDATORY, before any translation)

Post this and BLOCK until the user confirms:

```
File gốc cần dịch là: `<resolved-path>` — đúng không?
(→ dịch sang tiếng Việt, ghi ra `<stem>_vi.<ext>` cạnh file gốc)
Reply `confirm` để dịch · `abort` để hủy · `modify: <path>` để đổi file.
```

- Translate ONLY on an explicit `confirm`. Silence / tangential reply → do NOT translate.
- `abort` → cancel + report. `modify: <path>` → switch to the new path and repost this gate for it.

## Step 3 — Detect type & language + scope check

| Type | Handling |
|---|---|
| Text/doc (`.md`, `.txt`, `.mdx`, `.rst`, `.adoc`, plain text) | ✅ Primary. Translate prose, keep structure. |
| Data with prose (`.csv`, `.json`, `.yaml` with prose values) | ⚠️ Translate only prose values; keep keys/schema/numbers/enums. Ask if it risks breaking format. |
| Source code (`.cs`, `.ts`, `.tsx`, `.py`…) | ❌ Do NOT translate to Vietnamese (repo "code/comments English-only" rule). Explain and decline. |
| Binary (`.docx`, `.xlsx`, `.pdf`, images…) | ❌ STOP. Cannot read/write text directly. For images → suggest the `translate-image` skill. |

Detect source language (EN / JP / mixed) from the content.

## Step 4 — Translate

Read the source, then produce the Vietnamese version applying Principle #1 + #2 and preserving structure.

## Step 5 — (reserved) — verify nothing structural was dropped

Sanity-check: same headings/sections/code blocks present; identifiers untouched.

## Step 6 — Write the output file (the only mutation)

- Filename: insert `_vi` **before the last extension**: `<stem>_vi.<ext>`, in the **same directory** as the source.
  - `readme.md` → `readme_vi.md`
  - `spec.txt` → `spec_vi.txt`
  - `a.design.md` → `a.design_vi.md`
  - no extension (`NOTES`) → `NOTES_vi`
- If `<stem>_vi.<ext>` already exists → ask to overwrite, or write `<stem>_vi.<n>.<ext>`.
- Never edit the original file.

## Step 7 — Chat summary (4–6 lines)

```
Nguồn:  <resolved-path>  (ngôn ngữ: EN | JP | mixed)
Đích:   <stem>_vi.<ext>
Giữ nguyên (vie-non-trans): {vài ví dụ đáng chú ý}
JP giữ + gloss: {số lượng / vài ví dụ 編集中 (Editing)}
```

## Edge cases

| Case | Handling |
|---|---|
| Missing arg / source not determinable | STOP, ask user to supply path. Do NOT guess, do NOT confirm. |
| Path does not exist | STOP, report wrong path. |
| User doesn't reply `confirm` (silent/off-topic) | Do NOT translate — wait / re-post the gate. |
| `modify: <path>` | Switch to new path → repost the confirm gate for it. |
| Binary file (docx/xlsx/pdf) | STOP; for images suggest `translate-image`. |
| Source code file | Decline VI translation (repo rule); explain. |
| Pure-English file (no JP) | Still translate EN prose → VI, keep identifiers. |
| Output `_vi` already exists | Ask to overwrite or write `<stem>_vi.<n>.<ext>`. |
| Very large file | Translate fully, no truncation; batch internally if needed, drop nothing. |
| Ambiguous JP "is it a proper noun?" | Fixed label/status/enum/identifier → keep + gloss; prose → translate straight. When unsure on a business noun, prefer keep + gloss. |

## Reference

This skill writes its output **beside the source file**, so it is the one skill in this plugin that
needs no artifact directory: there is nothing to create under `<repo-root>/.claude/claude/` and no
preflight to run. Every other skill here follows that layout rule instead.
