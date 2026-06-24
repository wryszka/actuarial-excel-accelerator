# VBA spec — `Experience_Monitoring.xlsx` (the "before")

The committed `.xlsx` is a no-macro fixture so it opens anywhere. In the
real world this workbook carries a `RefreshPack` macro — the operational
engine the actuary runs every month. Specifying it here is the
**Inventory** step of the migration recipe; the notebooks then map each
piece onto a Databricks primitive (**Decompose**).

## Tabs

| Tab | Role | Cadence |
|---|---|---|
| `Data_Claims` | pasted claims-transaction export | monthly (replaced wholesale) |
| `Data_Premium` | pasted premium export | monthly |
| `Lookup` | segment → LOB / region / channel (the VLOOKUP source) | rarely |
| `Pivot_Experience` | PivotTable: earned premium / incurred / loss ratio by channel | refreshed monthly |
| `Dashboard` | chart screenshotted into the board pack | view-only |

## The macro (`RefreshPack`)

```vba
Sub RefreshPack()
    ' 1. Import — file picker, open the monthly claims & premium CSVs,
    '    copy their rows into Data_Claims / Data_Premium (clearing the old paste).
    ' 2. Map — fill the VLOOKUP column down Data_Claims:
    '        =VLOOKUP([@policy_segment], Lookup!A:D, 2, FALSE)   ' line_of_business
    '    ...repeated for region and channel.
    ' 3. Refresh — ThisWorkbook.RefreshAll to rebuild every PivotTable.
    ' 4. Re-bind — point Charts("LossRatioByChannel") at the refreshed pivot range.
    ' 5. Pray — no error handling; a renamed column or an extra header row
    '    silently produces #N/A and a wrong loss ratio nobody catches.
End Sub
```

| VBA / Excel idiom | Databricks shape | Notebook |
|---|---|---|
| File picker + paste into Data tabs | UC Volume + CSV read | `02_bronze.py` |
| `VLOOKUP` fill-down | governed join to `exp_dim_segment` | `03_silver.py` |
| Helper columns (accident year, paid vs reserve) | typed, commented silver columns | `03_silver.py` |
| `RefreshAll` PivotTables | gold aggregate tables | `04_gold.py` |
| Chart re-bind | AI/BI dashboard + Genie space | `07_dashboard.py`, `06_genie_space.py` |
| No error handling / `#N/A` | explicit DQ asserts (unmapped segments, bad dates) | `03_silver.py` |
| "Refresh takes half a day" | scheduled / on-demand notebook run | the pipeline itself |

## `build_excel_data.py`

Builds this workbook from the Excel-sized slice the pipeline emits
(**Motor · London · accident year 2024**) and writes `parity_oracle.json`
— the grand totals the pivot displays — which `05_parity.py` ties back to
the Databricks gold table.
