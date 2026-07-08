# Use Case 2 — From spreadsheet model to governed model

**What gets migrated:** a Standard-Formula capital model that lives in an
Excel workbook — one file per entity, a typed-in calibration block, no
version history, shared by email. **What it becomes:** a **versioned
model registered in Unity Catalog** (`sfm_scr_model`), scored against a
governed inputs table across the whole group in one pass, with every
result traceable to the exact model version — and therefore the exact
calibration — that produced it.

The centre of this use case is the conceptual jump:
**the model stops being a file and becomes a governed asset.**

## The "before"

`SF_Model.xlsx` (in the `sfm_assets` volume and in `excel/`) is a
deliberately simple three-module Standard Formula for one entity:

- non-life premium & reserve risk, market interest-rate risk, catastrophe
- correlation-matrix aggregation → BSCR, operational-risk add-on → SCR
- an `Inputs` tab, a `Calibration` tab (the parameter block the actuary
  retypes when the regulator updates it), a `Model` tab with live formulas

Real-life pain this file carries: a group of 100 entities means 100
workbooks; a calibration update means retyping the block in each one;
"which parameters produced the Q3 number?" has no answer; sharing means
emailing the file.

## The "after" — assets in Databricks (all prefixed `sfm_`)

| Asset | What it is |
|---|---|
| Volume `sfm_assets` | all source files, clearly described: workbook, inputs CSV, both calibration JSONs, parity oracle |
| `sfm_inputs` | inputs table, one row per entity (ENT-001 = the workbook's entity, exactly) |
| **Model `sfm_scr_model`** | the workbook's formulas as an MLflow pyfunc, **registered in Unity Catalog**; the calibration is logged with the model, so *a model version is a calibration*. Version 1 = `@cal_2025`, version 2 = `@cal_2026`, `@champion` on the latest |
| `sfm_results` | SCR per entity per calibration year, with `model_version` on every row |
| `sfm_impact` | v2 vs v1 on identical inputs: the capital impact of the calibration update, per entity, per module |

## The notebooks (flat — open and Run All, in order)

| Notebook | Does |
|---|---|
| `00_setup.py` | `sfm_assets` volume + copies the source files into it (+ `reset=yes` switch) |
| `01_inputs.py` | inputs CSV → `sfm_inputs`, fully commented |
| `02_register_model.py` | the model class → log → **register in UC** → aliases (defaults to the 2025 calibration) |
| `03_score.py` | batch-score all 100 entities with `@cal_2025` → `sfm_results`; **parity check**: ENT-001 equals the workbook |
| `04_recalibrate_2026.py` | registers **version 2** from the 2026 calibration, re-scores, builds `sfm_impact` — the group-wide capital impact in seconds |
| `99_validate.py` | smoke test |

## Run it

```bash
databricks bundle deploy -t dev
# open /Workspace/Shared/actuarial-excel-accelerator/demo_02b_sf_model_uc/
# Run All: 00 → 01 → 02 → 03 → 04 → 99
```

Widgets on every notebook default to the values in `databricks.yml`
(`catalog_name`, `schema_name`, `sfm_volume_name`).

## Suggested walkthrough

1. **Open `SF_Model.xlsx`** (download it from the `sfm_assets` volume in
   Catalog Explorer). Change an input, watch SCR recalc. Point at the
   `Calibration` tab: "when this changes, someone retypes it in every
   entity's file."
2. **Open `02_register_model`.** The same formulas as a readable class;
   the calibration logged with the model. Show the registered model in
   Catalog Explorer (→ Models → `sfm_scr_model`): version, aliases,
   description, lineage — *control and audit for a capital model*.
3. **Run `03_score`.** One hundred entities in one pass, results
   traceable via `model_version`. The parity cell: the model equals the
   workbook to the fourth decimal.
4. **Run `04_recalibrate_2026`.** The 2026 parameters arrive → version 2
   → `sfm_impact`: the group SCR moves ~+9%, decomposed by module and by
   entity. In the workbook world this comparison is weeks of churn; both
   sides here are registered versions, reproducible forever.
5. **Mention where this goes next**: scheduled runs, results feeding
   dashboards and regulatory reporting — see the
   [Solvency II QRT demo](https://github.com/wryszka/solvency-ii-qrt-demo-pnc)
   for a fully-implemented pipeline of that shape.

## About this demo

All data is synthetic. The model is a deliberately simplified,
Solvency-II-*style* standard formula for illustration — it is not the
EIOPA specification. No customer data is used.
