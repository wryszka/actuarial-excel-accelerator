# Actuarial Excel Accelerator

A public Databricks accelerator showing actuaries how to migrate
Excel + VBA processes to Databricks. One repo, one migration recipe,
a demo for every flavour of the problem — start with demo 0.

## What's in the box

| Demo | What gets migrated | Status |
|---|---|---|
| **0. The VBA nobody understands** | Monthly claims-bordereau macro → Genie Code explains + converts it → file-arrival job runs it unattended | ✅ Built |
| **1. EIOPA Risk-Free Rate ingestion** | Monthly EIOPA term-structure file → VBA reshape → Excel curve history | ✅ Built |
| **2A. Solvency II SCR Standard Formula** | Multi-tab SCR workbook with hardcoded module aggregation + scenario macro | ✅ Built |
| **3. Experience & Loss-Ratio Monitoring** | Monthly PivotTable MI-pack → **Genie + AI/BI dashboard** over an ~800k-row book | ✅ Built |
| **4. Chain-Ladder Reserving** | Run-off triangle workbook with development factors | _Coming soon_ |

All demos share one catalog + one schema, with per-demo asset prefixes
(`rfr_*`, `scr_*`, `exp_*`) so they're easy to tell apart in the workspace.
Demo 2A consumes Demo 1's `rfr_curves` gold table for discounting; Demo 3
stands alone. Demo 3 is the one that shows what **AI/BI Genie and
Dashboards** replace — the giant pivot-table workbook an actuary refreshes
by hand every month.

## The take-away: a migration recipe

The point of this accelerator is not the curves. It is the
**migration recipe**: a repeatable 6-step pattern for moving an
Excel + VBA process to Databricks. See [`MIGRATION_RECIPE.md`](MIGRATION_RECIPE.md).

```
Inventory → Decompose → Land → Rebuild → Validate parity → Operate
```

Each demo applies that recipe end-to-end so you can see the pattern
on a process that resembles yours.

## Deploy demo 1

You'll need:
- Databricks workspace with serverless compute and Unity Catalog
- Databricks CLI v0.200+ (`brew install databricks/tap/databricks`)

```bash
# 1. Clone
git clone https://github.com/wryszka/actuarial-excel-accelerator.git
cd actuarial-excel-accelerator

# 2. Point databricks.yml at your workspace
#    Edit host: and profile: under targets.default
#    Override variables if your catalog/schema/warehouse differs

# 3. Deploy
databricks bundle deploy

# 4. Run UC setup (creates schema + rfr_landing volume — idempotent)
databricks bundle run setup_demo

# 5. Upload the sample EIOPA files to the volume
databricks fs cp demo_01_rfr_etl/sample_data/ \
    dbfs:/Volumes/<catalog>/actuarial_excel_demo/rfr_landing/ \
    --recursive

# 6. Run the end-to-end demo 1 job
databricks bundle run run_rfr_etl

# 7. Validate
databricks bundle run validate_rfr
```

## Deploy demo 2A (after demo 1)

Demo 2A reads `rfr_curves` from demo 1 to discount liability cash
flows in the Market IR sub-module. Make sure demo 1 has been run
end-to-end first.

```bash
# Load inputs + assumptions
databricks bundle run scr_setup --target dev

# The full demo arc — orchestrator → parity test → MLflow sweep →
# UC SQL UDF registration → Lakeview dashboard
databricks bundle run scr_full_run --target dev

# Smoke test
databricks bundle run scr_validate --target dev
```

Demo 2A's round-trip story: open `demo_02a_scr_sf/excel/SCR_StandardFormula.xlsm`,
type shocks into the `Round_Trip` tab, hit Refresh. Power Query calls
the UC `scr_total` UDF; Databricks computes the breakdown; the result
flows back into the workbook.

## Deploy demo 3 — Experience Monitoring (Genie + AI/BI)

Demo 3 stands alone (no dependency on demos 1–2). The notebooks live
**flat** in `demo_03_experience_genie/` — deploy, then open the folder in
the workspace and Run All in order (`00` → `99`):

```bash
databricks bundle deploy -t dev
# open /Workspace/Shared/actuarial-excel-accelerator/demo_03_experience_genie/
```

The whole accelerator deploys to a **shared** folder
(`/Workspace/Shared/actuarial-excel-accelerator/`) so the same path opens for
everyone in the workspace — no per-user home, no `files/` nesting.

`01_generate_data.py` fabricates an ~800k-row book and lands it in the
`exp_landing` Volume; `04_gold.py` builds the Genie-commented tables;
`06`/`07` create the Genie space and AI/BI dashboard. To build the "before"
workbook, copy the slice files `01` emits and run the builder locally — see
[`demo_03_experience_genie/README.md`](demo_03_experience_genie/README.md).

## Overriding catalog / schema / warehouse

Three ways, all equivalent:

```bash
# (a) per-deploy
databricks bundle deploy --var "catalog_name=my_catalog,schema_name=my_schema"

# (b) edit databricks.yml under targets.default.variables (preferred for a fixed setup)

# (c) per-run for a single job
databricks bundle run run_rfr_etl --params catalog_name=my_catalog
```

| Variable | Default | What it controls |
|---|---|---|
| `catalog_name` | `lr_serverless_aws_us_catalog` | UC catalog for all tables |
| `schema_name` | `actuarial_excel_demo` | Schema shared across demos 1-3 |
| `warehouse_id` | _(SP-managed serverless PRO)_ | Warehouse for ad-hoc SQL |
| `rfr_volume_name` | `rfr_landing` | Volume where demo 1 monthly files land |

## Repository layout

```
├── README.md                   # this file
├── MIGRATION_RECIPE.md         # the cross-cutting take-away
├── databricks.yml              # DAB config + variables + target
├── resources/
│   ├── jobs.yml                # setup + monthly orchestration jobs
│   └── pipelines.yml           # DLT silver pipeline
├── shared/
│   └── uc_setup.py             # catalog/schema/volume — one notebook for all demos
├── demo_01_rfr_etl/
│   ├── README.md
│   ├── excel/
│   │   ├── RFR_Master.xlsm     # the "before" — author's Excel + VBA workbook
│   │   ├── VBA_SPEC.md         # spec for the VBA modules inside the .xlsm
│   │   └── build_excel_data.py # generates an .xlsx version of RFR_Master
│   ├── sample_data/            # synthetic EIOPA monthly files (.xlsx)
│   └── src/
│       ├── 01_bronze_autoloader.py  # Volume → bronze (file-as-blob)
│       ├── 02_silver_dlt.sql        # DLT unpivot + DQ expectations + forward rate
│       ├── 03_gold_publish.py       # publish rfr_curves with Genie-ready comments
│       └── 99_validate.py           # smoke test
├── demo_02a_scr_sf/
│   ├── README.md
│   ├── excel/
│   │   ├── SCR_StandardFormula.xlsm  # the "before" — Excel + VBA SCR model
│   │   ├── VBA_SPEC.md               # VBA modules + Power Query round-trip spec
│   │   ├── SCR_StandardFormula.xlsx  # no-VBA fixture + hidden parity oracle
│   │   └── build_excel_data.py       # fixture generator + Python compute oracle
│   ├── sample_data/                  # scr_inputs.json + scr_assumptions.json
│   └── src/
│       ├── 01_inputs_assumptions.py
│       ├── 02_module_nl_premres.py
│       ├── 03_module_market_ir.py
│       ├── 04_module_cat.py
│       ├── 05_aggregation.py
│       ├── 06_orchestrator.py        # compute_scr(scenario_id, shocks)
│       ├── 07_scenarios_mlflow.py    # 30-scenario sweep → MLflow
│       ├── 08_parity_test.py         # Excel oracle ↔ Databricks
│       ├── 09_sql_udfs.py            # UC UDFs for the Excel round-trip
│       ├── 10_dashboard.py           # Lakeview dashboard
│       └── 99_validate.py
└── .gitignore
```

## About this demo

This is a synthetic demonstration. The EIOPA-shaped files in
`sample_data/` are fully synthetic — they reproduce the file layout
of the EIOPA monthly publication but contain made-up rates. The
real published curves are at
[eiopa.europa.eu/tools-and-data/risk-free-interest-rate-term-structures_en](https://www.eiopa.europa.eu/tools-and-data/risk-free-interest-rate-term-structures_en).
No customer data is used.

## Licence

MIT.
