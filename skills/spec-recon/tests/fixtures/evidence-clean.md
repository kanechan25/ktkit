# Measurement: report template

Reproduce: `python3 scripts/probe_xlsx.py src/Templates/report.xlsx --sheets --names`

| Property | Value | Label |
| -------- | ----- | ----- |
| md5 | 1c6c405125e9b0e68969b04823b77701 | [measured] |
| sheet count | 5 | [measured] |
| defined names | 178 | [measured] |
| sheet names shared with the published form | 0 of 5 | [derived] |

The published form names 3 defined ranges. [quoted]

Not accessed: the deployed blob — the loader falls back to object storage and this
run has no credentials for it, so only the in-repository copy was measured.

Source of the comparison: `docs/forms/report-form.md:41`
