# Use Case 1 — Move an Excel macro to Databricks

Every month an actuary receives a claims listing as a CSV, opens Excel, and
runs an old macro that cleans it up — parses the dates, tidies the numbers,
works out incurred, flags the big losses — and saves a clean file for the
pricing or reserving system. Nobody wrote it recently. Nobody's quite sure
what's inside. And on a full month's file it takes a couple of minutes to
grind through, row by row.

This use case moves that macro to Databricks. You'll paste the old code into
an assistant that explains it and rewrites it, run the new version over the
same file — **done in seconds, not minutes** — schedule it to run every
morning by itself, and prove the numbers match Excel to the penny.

If you've never opened Databricks, that's the point — this is written for
you. Follow the steps in order.

## The picture

```
   claims_raw.csv                 ClaimsBordereauETL.xlsm (the old macro)
   (200k messy rows)   ──────────▶  clean + enrich, row by row  ──▶  *_CLEAN.csv
        │                                                              │
        │  upload to Databricks                                        │ load back to compare
        ▼                                                              ▼
   brd_claims_raw  ──▶  01_clean_claims (the same rules, in seconds)  ──▶  brd_claims_clean
                                                                    reconcile: same to the penny
```

Everything in Databricks is named with a **`brd_`** prefix so it's easy to
find; all data is synthetic.

## Before you start (once)

- **Build the Excel workbook** so you have the "before" to show: open
  `excel/ClaimsBordereauETL.xlsx`, add a sheet named `Clean`, import
  `excel/ClaimsBordereauETL.bas` in the VBA editor, and save as
  `ClaimsBordereauETL.xlsm`. Full steps in `excel/VBA_SPEC.md`.
- **Find the notebooks** in Databricks: left sidebar → **Workspace** →
  `Shared` → `actuarial-excel-accelerator` → `demo_00_vba_csv_etl`. You'll
  see `00_setup`, `01_clean_claims`, `02_reconciliation`, `99_validate`.
- **Run `00_setup` once.** Open it and click **Run all** at the top. It
  creates the folder and loads the raw CSV into a table. (~1 minute.)

---

## The walkthrough

### Step 1 — The monthly job, in Excel (the "before")

1. You have `data/claims_raw.csv` — a month of claims from the administrator.
   Open it if you like: mixed date formats, `£` signs, duplicate rows. Real.
2. Open `ClaimsBordereauETL.xlsm`, and run the macro: **Developer → Macros →
   `CleanBordereau` → Run**. Pick `claims_raw.csv`.
3. Watch it. It processes **row by row and takes a couple of minutes** — the
   everyday reality of a big spreadsheet job. When it finishes it saves
   `claims_raw_CLEAN.csv` next to the input. *That* clean file is what
   normally gets uploaded onwards.

**Say this:** *"This runs every month. It's slow, it's on my laptop, and honestly I'm not 100% sure what it does inside."*

### Step 2 — Ask what the code actually does

1. In Excel, open the code: **Developer → Visual Basic** (or Alt/Option +
   F11). Select all the code in `ClaimsBordereauETL` and copy it.
2. In Databricks, open a notebook cell and open **Genie Code** (the
   assistant). Paste the code and ask (copy this line):

   *This is a VBA macro we run every month and nobody fully understands it. Explain step by step what it does, and flag anything risky.*

3. Read the answer. It explains the dedupe, the date parsing, the money
   tidy-up — and flags the thing nobody knew: **rows with an unreadable
   loss date are silently dropped.** You've been losing claims for years.

### Step 3 — Turn it into a Databricks notebook

1. Ask Genie Code the follow-up (copy this line):

   *Rewrite this as a Databricks notebook in PySpark that does the same thing on a claims CSV, and instead of silently dropping the bad-date rows, keep them in a separate quarantine table.*

2. It writes the code. We've saved the finished, checked version as
   **`01_clean_claims`** — open it. Each section is one rule from the macro,
   labelled, so you can see the old logic mapped across.

### Step 4 — Point it at your data

Two options — pick one:

- **Just use the ready table.** `00_setup` already loaded the CSV into
  `brd_claims_raw`. In `01_clean_claims`, leave the `source` widget (top of
  the notebook) on **`table`**. Nothing to upload.
- **Upload your own CSV** (the "bring your own data" moment). Left sidebar →
  **Catalog** → `lr_dev_aws_us_catalog` → `actuarial_excel_demo` → Volumes →
  `brd_landing` → **Upload to this volume** → choose your CSV. Then in
  `01_clean_claims` set `source` to **`file`** and `upload_file_name` to
  your file's name.

### Step 5 — Run it, and watch the clock

Open `01_clean_claims` and click **Run all**. It cleans all 200k rows and
writes `brd_claims_clean` (and `brd_quarantine`) **in a few seconds** — the
identical work the macro spent minutes on. That contrast is the whole point.

### Step 6 — Schedule it to run itself

No more "remember to run the macro". Schedule the notebook:

1. In `01_clean_claims`, top-right, click **Schedule** → **Add schedule**.
2. Set it to **Every day** at, say, 07:00. Leave compute on Serverless.
3. **Create.** That's it — each morning Databricks runs the clean for you
   and updates the table. Nobody opens Excel.

### Step 7 — Prove it's the same

Open `02_reconciliation` and click **Run all**. It loads the Excel macro's
output back into Databricks as a table and compares it to the notebook's
output — row count and every total. **They match to the penny.** Then it
shows the one difference: the claims Excel had been silently dropping, now
safely kept in `brd_quarantine`.

Run `99_validate` for an automated all-green check.

---

## What you end up with

| Table (`brd_` prefix) | What it is |
|---|---|
| `brd_claims_raw` | the raw monthly CSV, as received |
| `brd_claims_clean` | cleaned + enriched claims — the macro's job, done in seconds |
| `brd_quarantine` | the bad-date rows the macro silently dropped |
| `brd_excel_output` | the Excel result, loaded back for the reconciliation |

Plus a scheduled job that refreshes it every morning, and lineage you can
click through in Catalog Explorer — none of which a spreadsheet on a laptop
can give you.

## About this demo

All data is synthetic — the claims listing resembles a UK motor/property
bordereau but every value is fabricated. No customer data is used.
