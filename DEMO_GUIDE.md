# Actuarial Excel Accelerator — Demo Guide

One repo, one story: **everything an actuary does in Excel, end to end,
moved to one governed platform** — get the data in and clean it, run the
model on it, report on it, and automate the whole chain. It's told in five
chapters. Read them in order for the full journey, or open any one on its
own — each is a complete, self-contained use case.

## The whole journey

```
  UC1 clean the data  →  UC2 run the model  →  UC3 report on it
                                                     │
             UC4 build a step with no code (Designer)│
                                                     ▼
             UC5 connect it all into one scheduled pipeline (Job)
```

- **UC1–UC3** are the spine: input → model → report.
- **UC4** shows how an analyst builds one step *without code* (a Lakeflow
  Designer canvas).
- **UC5** connects the steps into *one scheduled job* — the month-end,
  automated.

| # | Use case | The Excel pain | What it becomes | Folder |
|---|---|---|---|---|
| 1 | **Move the Excel macro** | a slow monthly macro cleans the claims CSV; nobody remembers how | Genie Code explains + rewrites it; 200k rows cleaned in seconds, on a schedule, matched to the penny | `demo_00_vba_csv_etl/` |
| 2 | **Move the capital model** | a Standard-Formula model in a workbook; one file per entity, retyped calibrations | a versioned model in Unity Catalog — a version *is* a calibration; group-wide scoring; calibration impact in seconds | `demo_02b_sf_model_uc/` |
| 3 | **From Excel BI to Genie & dashboards** | pull a CSV from the DWH, build pivots by hand, email the workbook | the same data governed; ask in plain English with Genie; a published live dashboard on the full book | `demo_03_experience_genie/` |
| 4 | **Build a step with no code (Designer)** | the join–clean–aggregate canvas living in a desktop ETL tool | the same canvas in Lakeflow Designer — real code, lineage and a schedule behind it | `demo_04_lakeflow_designer/` |
| 5 | **Connect it all (scheduled Job)** | the month-end checklist run by hand, in someone's head | one Lakeflow Job chaining clean → model → report, on a schedule, unattended | `demo_05_orchestration/` |

## Shared conventions

- **One schema** for everything: `actuarial_excel_demo` (name it per
  `databricks.yml`). Every asset is **prefixed** by its use case —
  `brd_*`, `sfm_*`, `exp_*` (+ `exp_designer_*`) — so nothing gets lost
  in the workspace.
- **Shared workspace path**: the whole accelerator deploys to
  `/Workspace/Shared/actuarial-excel-accelerator/` — the same path opens
  for everyone; notebooks sit flat in each folder, no `src/` nesting.
- **Volumes carry the files**: Excel workbooks, CSVs, calibrations and
  parity oracles live in clearly-commented volumes (`brd_landing`,
  `sfm_assets`, `exp_landing`) — downloadable from Catalog Explorer.
- **Bring your own data**: every use-case doc includes the one-gesture
  on-ramp (Catalog Explorer → Create → Table → drop the CSV). The demo
  tables ship pre-built; the gesture is there to show live.
- **Parity everywhere**: each use case proves the migrated result equals
  the Excel original — to the penny — before asking anyone to trust it.
- **Synthetic data throughout**; no customer names or data anywhere.

## Start here — the setup every use case shares

Read this once; the individual use cases don't repeat it.

**Where the notebooks live.** They're already in the workspace at
`/Workspace/Shared/actuarial-excel-accelerator/` — one flat folder per use
case (`demo_00_vba_csv_etl`, `demo_02b_sf_model_uc`, `demo_03_experience_genie`,
`demo_04_lakeflow_designer`, `demo_05_orchestration`). Find them: left
sidebar → **Workspace** → `Shared` → `actuarial-excel-accelerator`. Each use
case is independent — run just the one you want.

**How to run a notebook.** Open it and click **Run all** at the top. That's
the only "running" you need to do — no command line anywhere.

**Where the data and files live.** Each use case keeps its source files
(Excel workbooks, CSVs) in a **volume** — a folder in Databricks. Find them:
left sidebar → **Catalog** → the catalog → the schema → **Volumes**. Click a
file to download it.

## Running in your own workspace (or Free Edition)

The demo is pre-installed in the workspace above and points at catalog
**`lr_dev_aws_us_catalog`**, schema **`actuarial_excel_demo`**. If you are
running it **somewhere else** — your own workspace, a customer's, or
Databricks Free Edition — do this one thing:

> **Every notebook has `catalog_name` and `schema_name` boxes (widgets) at
> the top. Set them to your own catalog and schema before you click Run
> all.** Nothing else changes. (On Free Edition use catalog `workspace` or
> your default; everything else works the same.)

The docs below show the built-in `lr_dev_aws_us_catalog` path in click-paths
so they read concretely — substitute your own wherever you see it.

Setting up in a brand-new workspace from the source repo (one-time, needs
the Databricks CLI):

```bash
git clone https://github.com/wryszka/actuarial-excel-accelerator.git
cd actuarial-excel-accelerator
# point databricks.yml targets at your workspace, then:
databricks bundle deploy -t dev
```

## Bring your own data (once, applies everywhere)

To run any use case on your own file instead of the built-in data: left
sidebar → **Catalog** → your schema → **Create → Table** → drop your CSV →
the UI reads the columns → **Create**. It's now a governed table you can
point the notebooks at. The built-in demo tables already exist, so this is
optional.

## Presenter pre-flight — before you show this live

Most of the demo is "open notebook → Run all". Two use cases have a little
manual prep that is **not** in Run all — do it *before* your session:

1. **UC1 — the Excel workbook.** The macro-enabled workbook
   `ClaimsBordereauETL.xlsm` is presenter-built (Excel won't let macros ship
   in a downloaded file). Build it once following
   `demo_00_vba_csv_etl/excel/VBA_SPEC.md` (~5 min), or skip the Excel scene
   and start the story at "here's the macro's code" — the Databricks half
   runs entirely on its own.
2. **UC4 — the Designer canvas.** Building the visual canvas is a live
   click-through (there's no "Run all" for it). Do a dry run once so the
   steps are muscle memory; `01_generate_sources` + `02_parity` around it are
   normal notebooks.
3. **Check the workspace supports what each use case needs** — see the
   *Needs* line at the top of each use-case tab. In short: serverless compute
   everywhere; UC2 needs Unity Catalog model registry; UC4 needs Lakeflow
   Designer (GA); UC3/UC4/UC5 use Genie / dashboards / schedules.
4. **Warm it up.** Run each use case end to end once on the target workspace
   the day before, and open the Genie space / dashboards so first load is
   instant on the day.

## Glossary (for non-actuaries and non-Databricks readers)

- **Bordereau** — a claims (or premium) listing sent by an administrator;
  one row per claim.
- **Incurred** — the total cost of a claim = paid so far + still outstanding.
- **Loss ratio** — incurred ÷ earned premium; the headline profitability
  measure (0.85 = 85%).
- **SCR / Standard Formula** — Solvency Capital Requirement; the EU-prescribed
  ("Standard Formula") capital an insurer must hold.
- **Volume** — a folder for files inside Databricks (holds the CSVs/workbooks).
- **Unity Catalog** — Databricks' governance layer: catalogs → schemas →
  tables/models, with permissions and lineage.
- **Genie** — ask questions of your data in plain English; it writes the SQL.
- **Notebook / Run all** — a page of steps you run by clicking one button.

Each use-case tab (or each folder's `README.md`) has the step-by-step.
