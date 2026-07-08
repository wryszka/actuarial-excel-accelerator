# The legacy workbook — `Bordereau_ETL.xlsm`

The "before" artefact for demo 0. One VBA module (`ClaimsBordereauETL.bas`),
one macro (`RunMonthlyETL`), run by hand every month:

1. File picker → the month's TPA bordereau CSV.
2. Reads the file, dumps it to a `Raw` tab.
3. **Dedupes** — the vendor extract double-fires; keeps the first row per claim ref.
4. **Parses dates** in three formats (dd/mm/yyyy, yyyy-mm-dd, dd-Mon-yy).
   A loss date it can't parse → **the row is silently skipped**. No log, no count.
5. **Parses money** — strips `£`, treats `-`/blank as zero, `(x)` as negative.
6. **Maps status codes** — `O/RO/C/CWP` + dirty variants → clean labels.
7. Derives `incurred = paid + outstanding`.
8. **Drops the Handler column** (nobody remembers why).
9. Writes a `Standardised` tab and exports `<input>_STANDARDISED.csv` —
   which is then uploaded into "the pricing system".

The inventory (recipe step 1) in one table:

| Artefact | What it does | Risk |
|---|---|---|
| `RunMonthlyETL` | the whole pipeline, one keyboard shortcut | key-person dependency |
| `ParseDateISO` | three date formats accumulated over years | **silent row drops** |
| `ParseAmount` | vendor money formats | `Val()` quietly returns 0 on garbage |
| `MapStatus` | hardcoded `Select Case` | unknown codes → "UNKNOWN", nobody reviews |
| dedupe `Collection` | vendor double-extract workaround | drops legit rows if refs ever repeat across months |

## One-time setup (to have the .xlsm on camera)

1. Open `Bordereau_ETL.xlsx` in Excel.
2. ⌥F11 (VBA editor) → File → **Import File…** → `ClaimsBordereauETL.bas`.
3. Save As → **Excel Macro-Enabled Workbook** → `Bordereau_ETL.xlsm`
   (stays local — `*.xlsm` is excluded from git and bundle sync).

## The Genie Code prompts (recording, scene 3)

Open a new notebook, paste the whole VBA module into Genie Code
(the assistant), and ask — in this order:

**Prompt 1 — understand before you migrate:**
> Here is a VBA macro from an old Excel workbook we run every month and
> nobody fully understands anymore. Explain step by step what it does,
> and call out anything surprising or risky.

The expected reveal: it *silently drops rows* whose loss date won't parse,
and quietly zeroes unparseable amounts. That's the reason-to-migrate in
one sentence.

**Prompt 2 — the conversion:**
> Now write PySpark for a Databricks notebook that does the same thing:
> read the bordereau CSV files from a Unity Catalog volume, apply the same
> cleaning rules (dedupe on claim ref, the three date formats, £/(x) amount
> parsing, the status-code mapping, incurred = paid + outstanding), and save
> the result as a governed Delta table. One improvement: instead of silently
> dropping rows with unparseable loss dates, keep them in a separate
> quarantine table.

The validated reference for what comes out is `../01_bordereau_etl.py` —
compare the generated code against it on camera.
