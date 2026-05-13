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

> **Demo 2A worked example.** `demo_02a_scr_sf/excel/SCR_StandardFormula.xlsm`
> is bigger than the RFR workbook and inventoried very differently. The
> operational engine isn't a paste-and-reshape cadence; it's a single
> macro (`RunScenarios`) that loops a hardcoded list of shocks and writes
> rows to a `Scenarios` tab once per actuary action. The persistent state
> isn't an accumulating history — it's a `scr_assumptions` block whose
> values change a few times a year (calibration refresh, regulatory
> update). The inventory therefore separated the file into three
> cadences: **continuous** (every recalc — formulas in `NL_PremRes`,
> `Market_IR`, `Aggregation`), **periodic** (the `RunScenarios` sweep),
> and **annual** (the `Assumptions` tab). The migration treats each
> cadence with its own primitive — UDF, MLflow run, versioned Delta
> table — instead of trying to map them all to "a notebook".
>
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

> **Demo 2A worked example.** The decomposition mapped most VBA + cell
> idioms onto Databricks primitives one-to-one:
> `RunScenarios` Sub → `07_scenarios_mlflow.py` (MLflow runs replace
> rows on the `Scenarios` tab); the `Aggregation` tab's
> `=SQRT(SCR_uw²+SCR_mkt²+2ρ·…)+Cat` formula → a closed-form in
> `05_aggregation.py`; the `Assumptions` block of σ values and the
> correlation matrix → the `scr_assumptions` Delta table with an
> `is_current` flag and `effective_date`. The Excel
> `Application.Calculate` trigger has no Databricks equivalent — it
> doesn't need one, because every run is a fresh dispatch.
>
> The one decomposition that doesn't map 1:1 is the **round-trip**.
> Excel's "type shock → press F9 → see result" loop has no built-in
> Databricks analogue. The migration introduces one: a UC SQL UDF
> (`scr_total`) plus a Power Query in the workbook that calls it. The
> actuary's recalc gesture is preserved; the engine behind it
> changed.
>
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

> **Demo 2A worked example.** The "landing" here is two JSON files
> (`scr_inputs.json`, `scr_assumptions.json`) committed to the repo
> and ingested by `01_inputs_assumptions.py` into Delta tables. In a
> production migration, this is where a CSV export from the actuary's
> SAS or Igloo system would land in a UC Volume instead. The
> committed JSON in this demo plays the same role: it's the
> authoritative input to the pipeline, governed by the same Git +
> review process the rest of the repo uses, and it produces
> identical inputs on every developer's deploy.
>
> The other landing here is the RFR curve — demo 2A reads it from
> demo 1's gold table (`{catalog}.{schema}.rfr_curves`) rather than
> re-importing. That cross-demo reference is the migration recipe's
> answer to the actuary's "paste from the EIOPA file" step: the same
> data, but available through SQL to anyone with USAGE on the
> schema, with full lineage to the source EIOPA file via demo 1's
> `_source_file` column.
>
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

> **Demo 2A worked example.** The rebuild for SCR doesn't fit the
> bronze/silver/gold mould — the inputs are already typed, validated,
> and small. Instead the layering is: **inputs/assumptions tables**
> (raw landing), **sub-module functions** (per-module math), **the
> orchestrator** (`compute_scr(...)`), **the scenario sweep table**
> (results gold). Each sub-module function is small enough to test
> in isolation: `nl_premres_scr(inputs_row, ass_row, shock_uplifts)`
> takes a Row and returns a number, no Spark involvement. That makes
> the migration verifiable — you can swap any sub-module without
> touching the others.
>
> The closed-form BSCR in `05_aggregation.py` is a deliberate
> simplification (`SQRT(SCR_uw² + SCR_mkt² + 2ρ·SCR_uw·SCR_mkt) + Cat`
> rather than the full 6×6 correlation matrix). The migration pattern
> is identical for the full formula — `aggregate()` would take an
> `n×n` matrix and an n-vector of sub-module SCRs and emit the same
> BSCR. The rest of the pipeline doesn't change.
>
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

> **Demo 2A worked example.** Parity in demo 2A is built into the
> workbook itself. `build_excel_data.py` writes a hidden tab called
> `SCR_Computed` with Python-computed reference values; the visible
> tabs carry the same calculation as live Excel formulas. The
> `08_parity_test.py` notebook reads the hidden tab via openpyxl,
> calls the Databricks orchestrator with identical inputs, and
> compares sub-module by sub-module within a 1% tolerance.
>
> Four of the seven metrics (`scr_nl_premres`, `scr_cat`, `op_risk`,
> `lacdt`) are curve-independent and must match exactly. The other
> three (`scr_mkt_ir`, `bscr`, `scr`) intentionally diverge by a
> small amount because the Excel side uses a flat 2.5% discount
> fallback (the workbook ships without a curve paste, on purpose)
> while the Databricks side reads the real curve from demo 1. The
> divergence is signal, not bug: it's the visible evidence that the
> migration uses the governed curve, not the actuary's frozen
> assumption.
>
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

> **Demo 2A worked example.** Demo 2A operationalises along two
> paths. The first is the same headless schedule as demo 1:
> `resources/jobs.yml` defines `scr_full_run` chaining orchestrator
> → parity test → MLflow sweep → UDF refresh → dashboard, ready to
> run on a cron when the assumption block changes. The second is
> the **round-trip**: the actuary keeps Excel, opens the Round_Trip
> tab, types shocks, hits Refresh. Power Query calls the
> `scr_total` UC UDF; the Databricks engine returns the breakdown;
> Excel renders it.
>
> That second path is the demo's lightbulb moment. The actuary
> doesn't have to learn a new tool. The workbook still opens. The
> shock cells still take typed input. The recalc gesture still
> works. The 1500-line VBA module is gone; the SQL UDF is one
> function call; the assumption block lives in UC and is versioned
> in Delta. The migration didn't remove Excel — it replaced the
> engine.
>
> **Demo 1 worked example.** `resources/jobs.yml` defines
> `run_rfr_etl` with a monthly cron schedule, paused by default.
> Unpause when you're satisfied with parity. The DLT pipeline's
> expectation metrics are visible in the pipeline UI; failed rows
> sit in the pipeline's event log.

---

## Demo 3 worked example: Chain-Ladder Reserving

_(coming soon)_
