<!-- group: Translate | order: 80 -->
# ktkit:translate-file — a file into Vietnamese, without touching one identifier

Translates **prose and presentation only**. Every technical token stays exactly as written:
identifiers, function and component names, code, file paths, CLI commands, URLs, JSON keys, brand
names. Japanese proper nouns that stay untranslated get an English gloss in parentheses.

```
/ktkit:translate-file <path/to/source-file>
```

Source may be English or Japanese. It **confirms the exact source file and blocks** before translating
anything, and it never edits the original.

## The cases

```bash
# an English design document
/ktkit:translate-file docs/design/export-pipeline.md

# a Japanese specification
/ktkit:translate-file docs/spec/form-layout.md

# a file whose path you are not sure of — it stops and asks rather than guessing
/ktkit:translate-file export-pipeline.md
```

## What you get

```
<stem>_vi.<ext>        written beside the source; the original is untouched
```

## Do not

| Anti-pattern | Why |
| ------------ | --- |
| Ask it to translate code or identifiers | It refuses by design. A translated identifier is a broken reference. |
| Expect it to overwrite the source | Writing `<stem>_vi.<ext>` is the only mutation it makes. |
| Skip the confirm gate | Translating the wrong file quietly produces a plausible, useless output. |

## See also

Nothing else in this toolkit writes prose in another language. `--lang` on `/ktkit:spec-recon`
selects the report language instead.
