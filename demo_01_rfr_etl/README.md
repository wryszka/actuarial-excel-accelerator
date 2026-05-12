# Demo 1 — EIOPA Risk-Free Rate ETL

The "before" is `excel/RFR_Master.xlsm`: an Excel workbook with four
VBA Subs that import the monthly EIOPA RFR file, reshape the curve,
append it to a History tab, and refresh a chart.

The "after" is a four-notebook pipeline in `src/` that lands the same
file in a UC Volume, expresses the VBA logic as DLT silver, and
publishes a Genie-ready gold table called `rfr_curves`.

## What it does

```
sample_data/EIOPA_RFR_2025_*.xlsx   ← synthetic EIOPA-shaped inputs
              ↓ upload
/Volumes/<catalog>/actuarial_excel_demo/rfr_landing/
              ↓ 01_bronze_autoloader.py
bronze_rfr_curves       (wide — like Raw_Paste in Excel)
              ↓ 02_silver_dlt.sql      (DLT, with expectations)
silver_rfr_curves       (long — like Transform)
              ↓ 03_gold_publish.py
rfr_curves              (the published reference — like History)
              ↓ 99_validate.py
✅ row count + per-month sanity checks
```

## Files

| Path | Purpose |
|---|---|
| `excel/RFR_Master.xlsm` | The "before" — author hand-builds this from `VBA_SPEC.md`. |
| `excel/VBA_SPEC.md` | Spec for the VBA modules inside the .xlsm. |
| `excel/build_excel_data.py` | Generates an .xlsx fixture + the four sample inputs. Re-run any time. |
| `sample_data/` | Four synthetic monthly EIOPA files. Committed binaries. |
| `src/01_bronze_autoloader.py` | Volume → `bronze_rfr_curves`. Parses each file with openpyxl. |
| `src/02_silver_dlt.sql` | DLT MV — unpivot, type, validate, derive 1-year forward. |
| `src/03_gold_publish.py` | Build `rfr_curves` + table/column comments. |
| `src/99_validate.py` | Smoke test. Notebook exits OK / FAIL. |

## Run it

After the repo's top-level `databricks bundle run setup_demo`:

```bash
# Upload the four sample files to the Volume
databricks fs cp demo_01_rfr_etl/sample_data/ \
    dbfs:/Volumes/<catalog>/actuarial_excel_demo/rfr_landing/ \
    --recursive

# Run the end-to-end demo 1 pipeline
databricks bundle run run_rfr_etl

# Smoke test
databricks bundle run validate_rfr
```

## What's interesting in the migration

The bronze notebook reads `.xlsx` files via `cloudFiles.format =
binaryFile` plus a `mapInPandas` parse — a real Auto Loader pattern,
not a `pandas.read_excel()` hack. The silver layer is **declarative
DLT SQL with expectations**, which is the formal version of the
`IsNumeric` and `If x > 0` checks the VBA was already doing
implicitly. The forward-rate derivation uses a `LAG` window function,
which has no clean Excel equivalent — try writing it in VBA without
hard-coding the maturity ladder.

See [`../MIGRATION_RECIPE.md`](../MIGRATION_RECIPE.md) for the
worked-example callouts step by step.

## About this demo

Synthetic data only. The four files in `sample_data/` reproduce the
EIOPA monthly file layout but contain made-up rates from a
Nelson-Siegel-ish generator. Real EIOPA publications:
[eiopa.europa.eu/tools-and-data/risk-free-interest-rate-term-structures_en](https://www.eiopa.europa.eu/tools-and-data/risk-free-interest-rate-term-structures_en).
