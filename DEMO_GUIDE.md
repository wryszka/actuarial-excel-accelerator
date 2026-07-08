# Actuarial Excel Accelerator — Demo Guide

One repo, four self-runnable use cases, each migrating a different
flavour of the Excel estate an insurance company actually runs on. Every
use case is a complete, deployable asset — run them yourself, in order or
independently.

| # | Use case | The Excel pain | What it becomes | Folder |
|---|---|---|---|---|
| 1 | **The VBA nobody understands** | a legacy macro cleans the monthly claims bordereau; nobody remembers how | Genie Code explains it, converts it; a file-arrival job runs it unattended — with a quarantine for the rows the VBA silently dropped | `demo_00_vba_csv_etl/` |
| 2 | **From spreadsheet model to governed model** | a Standard-Formula capital model in a workbook; one file per entity, retyped calibrations | a versioned model in Unity Catalog — a model version *is* a calibration; group-wide scoring; calibration impact in seconds | `demo_02b_sf_model_uc/` |
| 3 | **Ad-hoc analytics: pivots → Genie & AI/BI** | the claims listing lands in Excel and the pivot ritual begins | the same table governed; Genie answers in plain English; a published live dashboard; then more tables for the analysis Excel can't hold | `demo_03_experience_genie/` |
| 4 | **The monthly blend (Lakeflow Designer)** | the join–clean–aggregate canvas living in a desktop ETL tool | the same canvas, no-code, on the platform — backed by real code, lineage, a schedule; provably equal to the coded pipeline | `demo_04_lakeflow_designer/` |

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

## Deploy once

```bash
git clone https://github.com/wryszka/actuarial-excel-accelerator.git
cd actuarial-excel-accelerator
# point databricks.yml targets at your workspace, then:
databricks bundle deploy -t dev
```

Each use-case tab (or each folder's `README.md`) has the step-by-step
from there.
