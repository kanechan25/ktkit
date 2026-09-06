<!-- group: Help | order: 90 -->
# ktkit:help — this

```bash
/ktkit:help                  # the index: every skill, one line each
/ktkit:help chain            # one skill's page
/ktkit:help --all            # every page, end to end
/ktkit:chain --help          # the same page, CLI-style
```

`--help`, `-h` and `help` work on **any** ktkit skill, as long as it is the only argument. With other
arguments present the skill runs normally — `/ktkit:chain req.md --help` runs chain.

## Where the content lives

Each page is `skills/<name>/references/help.md`, beside the skill it documents. The index is
assembled by `scripts/help.py` from those files, so a skill added to this plugin appears in the index
without anyone editing a list.

`skills/spec-recon/tests/test_help.py` checks each page against that skill's own `## Arguments`
section, in both directions. A flag documented here that the skill does not accept fails the suite;
so does a flag the skill accepts that no page mentions.

## See also

`/ktkit:help chain` — start here if you are new.
