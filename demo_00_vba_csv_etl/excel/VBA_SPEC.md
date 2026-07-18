# The legacy workbook — `ClaimsBordereauETL.xlsm`

The "before" of Use Case 1. One VBA module (`ClaimsBordereauETL.bas`), one
macro (`CleanBordereau`), run by hand every month.

## What the macro does

1. File picker → the month's claims CSV.
2. Reads it **row by row** (this is why it's slow on a full file).
3. **Dedupe** — keeps the first row per claim (the extract double-fires).
4. **Parse dates** in three formats (dd/mm/yyyy, yyyy-mm-dd, dd-Mon-yy).
   A loss date it can't read → **the row is silently skipped**.
5. **Parse money** — strips `£`, treats `-`/blank as zero, `(x)` as negative.
6. **Map status codes** — `O/RO/C/CWP` + dirty variants → clean labels.
7. Drops the `Handler` column; computes `incurred = paid + outstanding`;
   flags `large_loss_flag = incurred > 100000`.
8. Writes `<input>_CLEAN.csv` — the file that goes to the pricing/reserving
   system.

## One-time setup (to have the .xlsm on camera)

1. Open `ClaimsBordereauETL.xlsx` in Excel.
2. Add a worksheet named **`Clean`** (the macro writes to it).
3. Developer → **Visual Basic** → File → **Import File…** →
   `ClaimsBordereauETL.bas`.
4. Save As → **Excel Macro-Enabled Workbook** → `ClaimsBordereauETL.xlsm`
   (stays local — `.xlsm` is excluded from git and sync).

## The Genie Code prompts (Use Case 1, step 2–3)

Open a notebook, paste the whole VBA module into Genie Code, and ask — in
order:

**Prompt 1 — understand it:**
> This is a VBA macro from an old Excel workbook we run every month and
> nobody here fully understands it anymore. Explain, step by step, what it
> does — and flag anything risky.

Expected reveal: it **silently drops rows** whose loss date won't parse.

**Prompt 2 — rebuild it here:**
> Rewrite this as a Databricks notebook in PySpark that does the same thing
> on a claims CSV read from a Unity Catalog volume: dedupe on claim
> reference, the three date formats, the £/(x) amount parsing, the status
> mapping, incurred = paid + outstanding, and a large-loss flag over £100k.
> One change: instead of silently dropping rows with an unreadable loss
> date, keep them in a separate quarantine table.

The validated result is `../01_clean_claims.py` — compare against it.
