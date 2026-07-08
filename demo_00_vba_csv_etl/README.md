# Demo 0 — The VBA nobody understands

**What gets migrated:** the monthly claims-bordereau macro — a legacy
Excel workbook that imports the TPA's CSV, "cleans it up" (nobody is
quite sure how), and exports a standardised CSV for the pricing system.
**How:** paste the VBA into **Genie Code** and ask *what does this do?*
— then ask it to do the same thing on Databricks. **Then:** automate it
with a file-arrival job, so next month nobody runs anything.

This is the simplest demo in the accelerator and the recommended place
to start: one macro, one notebook, one job.

## The assets

| Where | What |
|---|---|
| `data/bordereau_2025_11.csv`, `_12.csv` | two monthly vendor files, ~45k rows each, deliberately messy (three date formats, `£`/`(x)` amounts, dirty status codes, 600 duplicate rows, ~200 unusable dates) |
| `excel/ClaimsBordereauETL.bas` | the legacy VBA (real, working — import into Excel once, see `excel/VBA_SPEC.md`) |
| `excel/Bordereau_ETL.xlsx` | workbook shell for the `.bas` (save as `.xlsm` locally) |
| `data/expected_output_*.csv` | what the VBA produces (Python oracle mirroring it rule-for-rule) — the reconciliation anchor |
| `00_setup.py` | `brd_landing` volume (`incoming/`, `reference/`) + a `reset=yes` switch for retakes |
| `01_bordereau_etl.py` | the converted notebook: bronze → silver + **quarantine** (the rows the VBA silently dropped) |
| `02_reconciliation.py` | VBA output ⇄ silver, counts and £ to the penny — then the quarantine reveal |
| `03_create_job.py` | Lakeflow job + **file-arrival trigger** on `incoming/` |
| `99_validate.py` | smoke test |

All tables are prefixed `brd_` in the shared `actuarial_excel_demo` schema.

## Run it

```bash
databricks bundle deploy -t dev
# open /Workspace/Shared/actuarial-excel-accelerator/demo_00_vba_csv_etl/
```

1. Run `00_setup`.
2. Upload `data/bordereau_2025_11.csv` to the volume's `incoming/` folder
   (Catalog Explorer → volume → Upload, or
   `databricks fs cp data/bordereau_2025_11.csv dbfs:/Volumes/<cat>/actuarial_excel_demo/brd_landing/incoming/`).
3. Run `01_bordereau_etl`, then `02_reconciliation` → tie-out to the penny.
4. Run `03_create_job`, then drop `bordereau_2025_12.csv` into `incoming/` —
   the job fires by itself. Re-run `02` with
   `source_file = bordereau_2025_12.csv`.
5. `99_validate` for the smoke test.

The full recording script (scene by scene, with the Genie Code prompts)
is in [`DEMO_GUIDE.md`](DEMO_GUIDE.md).

## Bring your own data (the on-ramp, shown in every use case)

The vendor CSV gets into Databricks in one gesture — no pipeline needed:
Catalog Explorer → your schema → **Create → Table** → drop the CSV → the
UI infers the schema → Create. In this use case the same gesture targets
the volume instead (upload into `incoming/`) because a *recurring* feed
deserves a pipeline — that's the point of stage 2.

## About this demo

All data is synthetic — the bordereau resembles a UK motor/property TPA
extract but every value is fabricated. No customer data is used.
