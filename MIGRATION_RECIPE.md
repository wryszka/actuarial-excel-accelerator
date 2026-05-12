# The Migration Recipe

The same six steps work for any Excel + VBA process. The demos in
this repo show what each step looks like in practice.

---

## 1. Inventory

Before you migrate anything, write down what you have. List every
tab, every named range, every VBA module, every external dependency
(files imported from a vendor, files emailed to an actuary, files
downloaded from a regulator portal). Inventory is half the work — it
tells you what's actually a data flow and what's just decoration.

A good inventory has three columns: **artefact**, **what it does**,
**how often it changes**. Things that change monthly are the
operational engine. Things that change yearly are reference data.
Things that never change are constants you can hard-code.

> **Demo 1 worked example.** The EIOPA RFR workbook
> (`demo_01_rfr_etl/excel/RFR_Master.xlsm`) inventoried as:
>
> | Artefact | What it does | Cadence |
> |---|---|---|
> | `ImportFile` VBA Sub | File picker → opens EIOPA `.xlsx` → copies `RFR_spot_no_VA` to `Raw_Paste` | Monthly |
> | `ReshapeCurve` VBA Sub | Transposes maturity × currency; types cells | Monthly |
> | `AppendHistory` VBA Sub | Finds next free block on `History` tab; writes the new curve below | Monthly |
> | `RefreshChart` VBA Sub | Re-binds `Charts("CurveChart")` to the `History` range | Monthly |
> | `History` tab | Accumulating curve archive | Append-only |
> | `Chart` tab | Curve viz | View-only |
>
> All four VBA Subs are operational. The History tab is the only
> persistent state. The Chart is a derivative.

## 2. Decompose

For each artefact in the inventory, decide which migration "shape"
it maps to:

| Excel shape | Databricks shape |
|---|---|
| File picker + paste-special | UC Volume + Auto Loader |
| Cell formulas, transpose, type-cast | DLT silver SQL (with expectations) |
| `End(xlUp)` append to a History tab | Delta append to a gold table |
| Chart re-binding | AI/BI dashboard or Genie space |
| Named range pointing at a constants block | Reference table or DAB variable |
| `On Error Resume Next` | DQ expectations + a quarantine table |

Don't try to mimic the Excel macros 1:1. The shapes above mean the
output of the new pipeline is the same data — but the failure modes
are observable and the inputs are governed.

> **Demo 1 worked example.** The decomposition gave us four
> notebooks plus one DLT pipeline:
>
> - `ImportFile` → `01_bronze_autoloader.py` (Auto Loader over the
>   `rfr_landing` Volume; binary-file ingest + parse)
> - `ReshapeCurve` → `02_silver_dlt.sql` (UNPIVOT maturity columns
>   into rows + type cast + DQ expectations)
> - `AppendHistory` → `03_gold_publish.py` (Delta MERGE into
>   `rfr_curves` keyed on (effective_date, currency, maturity_months))
> - `RefreshChart` → _deferred to demo 2/3 dashboarding work_
> - "Quirky" VBA workarounds (`On Error Resume Next`, hard-coded cell
>   addresses) become explicit silver expectations — they don't
>   migrate, they get _exposed_.

## 3. Land

Move the raw inputs to a UC Volume before doing anything else. The
Volume is the new "file picker dialog" — it's where the monthly file
lives, governed by UC permissions, observable by lineage, and
discoverable by anyone with USAGE on the catalog.

Don't transform on the way in. The bronze table should preserve the
shape that Excel saw, plus two cheap metadata columns: `_source_file`
and `_ingested_at`. Future-you needs to be able to answer "which
monthly drop did this row come from" without forensics.

> **Demo 1 worked example.** Monthly EIOPA file dropped into
> `/Volumes/<catalog>/actuarial_excel_demo/rfr_landing/`. The bronze
> notebook reads it via `binaryFile` Auto Loader, parses the
> `RFR_spot_no_VA` tab with openpyxl on the driver (small files —
> fine for monthly), and writes one row per (effective_date,
> maturity_year) with one column per currency. Same shape the actuary
> saw on the Excel `Transform` tab.

## 4. Rebuild

Re-express the VBA logic as a transformation pipeline. The pattern is
boring: bronze (raw), silver (cleansed + DQ), gold (published, keyed,
Genie-discoverable). Each layer has one job:

- **Bronze**: keep what came in. No mutation. Idempotent on re-run.
- **Silver**: the transforms the VBA used to do (transpose, cast,
  filter), as DLT SQL with `CONSTRAINT ... EXPECT ... ON VIOLATION
  DROP ROW`. The expectations are the formal version of the
  `IsNumeric()` checks and `If x > 0 Then` guards your VBA contained
  but didn't surface.
- **Gold**: the table downstream people care about. Has a primary
  key. Has column comments suitable for AI/BI Genie. Has table
  properties to mark it as published.

> **Demo 1 worked example.** Silver applies four expectations:
> `spot_rate BETWEEN -0.05 AND 0.20`, `currency IN ('EUR','GBP','USD')`,
> `maturity_months BETWEEN 12 AND 360`, and `effective_date IS NOT
> NULL`. It also computes a derived **1-year forward rate** per
> (effective_date, currency) using a window function over maturity.
> Gold publishes `{catalog}.{schema}.rfr_curves` keyed on
> (effective_date, currency, maturity_months) with column comments
> describing every field — so a Genie space over the schema can
> answer "what was the 10-year EUR spot rate in September?" without
> further metadata work.

## 5. Validate parity

You cannot ship a migration until you can prove the new pipeline
produces the same numbers as the old workbook. The cheap version:
run the new pipeline on three months of historical inputs and
diff its output against the History tab from the workbook.

The right version: encode the parity check as a notebook that runs
every time the pipeline runs, and fails the job if any row drifts
beyond tolerance. Treat parity as a permanent SLA, not a one-off
acceptance test.

> **Demo 1 worked example.** `99_validate.py` runs the full pipeline
> against three months of sample files and prints
> `(effective_date, currency, count, min_rate, max_rate)` per month.
> Sufficient for a demo. A production version would diff against the
> `History` tab exported from the workbook and fail on any row whose
> rate differs by more than 1bp.

## 6. Operate

The last step makes it routine. A scheduled job, a paused-by-default
cron in `resources/jobs.yml`, monitoring on the DLT pipeline, owners
on the catalog. The actuary doesn't open Excel on the first business
day of every month anymore — the file arrives, the job runs, the
chart updates, and a Slack notification fires if any expectation was
violated.

This step is where the work-from-anywhere benefit actually shows up.
The migration isn't "Excel logic in Databricks". It's "the monthly
process no longer needs you to be at your laptop at 9am on the first
of the month".

> **Demo 1 worked example.** `resources/jobs.yml` defines
> `run_rfr_etl` with a monthly cron schedule, paused by default.
> Unpause when you're satisfied with parity. The DLT pipeline's
> expectation metrics are visible in the pipeline UI; failed rows
> sit in the pipeline's event log.

---

## Demo 2 worked example: SCR Standard Formula

_(coming soon)_

## Demo 3 worked example: Chain-Ladder Reserving

_(coming soon)_
