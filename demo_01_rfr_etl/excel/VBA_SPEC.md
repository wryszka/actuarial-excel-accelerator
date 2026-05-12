# VBA_SPEC — RFR_Master.xlsm

Spec for the hand-built `RFR_Master.xlsm`. This is the **"before"** —
the workbook an actuary maintains today, with macros that import each
month's EIOPA file, reshape the curve, and append it to a running
history. The accelerator's job is to migrate everything below to
Databricks.

Author the .xlsm by hand from this spec and commit it as a binary
fixture. Do not generate it programmatically — half the point of the
demo is that this file looks like the workbooks actuaries actually
keep.

The companion script `build_excel_data.py` produces a no-VBA
`.xlsx` version of the same workbook for testing the ingestion logic
without trusting macro execution.

---

## Tabs

| Tab | Purpose |
|---|---|
| `Instructions` | One-page README for the next person who inherits this file. |
| `Raw_Paste` | Where `ImportFile` pastes the contents of the EIOPA `RFR_spot_no_VA` sheet. Wide shape: maturity in column A, currencies in columns B onwards. |
| `Transform` | Long-form view of the latest month — one row per (currency, maturity). Output of `ReshapeCurve`. |
| `History` | The accumulating curve archive. New months stacked below previous months. Output of `AppendHistory`. |
| `Chart` | `CurveChart` — a line chart bound to a `History` range. |

## Named ranges

| Name | Refers to | Used by |
|---|---|---|
| `rng_RawHeader` | `Raw_Paste!$A$5:$D$5` | `ReshapeCurve` |
| `rng_RawData` | `Raw_Paste!$A$6:$D$35` (30 maturities × 4 cols) | `ReshapeCurve` |
| `rng_TransformOut` | `Transform!$A$4:$D$93` (90 rows × 4 cols) | `AppendHistory` |
| `rng_HistoryAnchor` | `History!$A$4` | `AppendHistory` — starting point of `End(xlUp)` walk |
| `LastEffectiveDate` | `Instructions!$B$8` | display only; updated by `AppendHistory` |

## VBA modules

All four Subs live in a single module called `RFR_Pipeline`.

### `Sub ImportFile()`

Pseudocode:

```
1. dlg = Application.FileDialog(msoFileDialogFilePicker)
   - .Title = "Pick the EIOPA monthly RFR file"
   - .Filters: Excel Files *.xlsx;*.xlsm
2. If dlg.Show <> -1: Exit Sub
3. path = dlg.SelectedItems(1)
4. srcWb = Workbooks.Open(path, ReadOnly:=True)
5. srcWs = srcWb.Sheets("RFR_spot_no_VA")
6. Clear Raw_Paste contents (rows 5 onwards)
7. Copy srcWs.Range("A5:D35") into ThisWorkbook.Sheets("Raw_Paste").Range("A5")
8. srcWb.Close SaveChanges:=False
9. MsgBox "Imported. Now run ReshapeCurve."
```

Key VBA constructs:
- `Application.FileDialog(msoFileDialogFilePicker)`
- `.Filters.Add "Excel files", "*.xlsx;*.xlsm"`
- `Workbooks.Open path, ReadOnly:=True`
- `.Range("A5:D35").Copy Destination:=...`

### `Sub ReshapeCurve()`

Pseudocode:

```
1. effDate = Sheets("Raw_Paste").Range("A2").Value
   ' parsed by hand from "...reference date: 2025-09-30"
   ' HARDCODED: assumes the date is the last 10 characters of the string
2. For each currency col in rng_RawHeader (cols B, C, D):
     For each maturity row in rng_RawData (rows 6..35):
        - read rate cell
        - if IsNumeric and rate > -1 then
            write (effDate, currency, maturity, rate) to next row of Transform
3. Drop trailing blank rows
4. Type-cast: maturity → Long, rate → Double
```

Key constructs:
- `Mid$(s, Len(s) - 9, 10)` to peel the date out of the header string
  (hardcoded position — a known quirk)
- `IsNumeric(cell.Value)`
- Nested `For` loops over `Range.Cells`
- `On Error Resume Next` wrapped around the date parse, to swallow
  cases where the header text changed (it gets stripped by the macro
  even though that's never the right thing to do — flag this in the
  decompose step)

### `Sub AppendHistory()`

Pseudocode:

```
1. anchor = Range("rng_HistoryAnchor")  ' History!A4
2. lastRow = History.Cells(History.Rows.Count, 1).End(xlUp).Row
3. If lastRow < 4 Then lastRow = 3
4. newStartRow = lastRow + 1
5. Copy rng_TransformOut into History.Range("A" & newStartRow)
6. Update Instructions!B8 ("LastEffectiveDate") with the effDate
7. MsgBox "Appended " & 90 & " rows. Now run RefreshChart."
```

Key constructs:
- `Cells(Rows.Count, 1).End(xlUp).Row` — the canonical "find last
  filled row" idiom
- `.PasteSpecial xlPasteValues`

### `Sub RefreshChart()`

Pseudocode:

```
1. lastRow = History.Cells(History.Rows.Count, 1).End(xlUp).Row
2. ch = Sheets("Chart").ChartObjects("CurveChart").Chart
3. ch.SetSourceData Source:=History.Range("A3:D" & lastRow)
4. ch.HasTitle = True
5. ch.ChartTitle.Text = "RFR spot curve history"
```

### `Sub LegacyExportCSV()` — DEAD CODE

Included intentionally to make the migration realistic. Comments
inside say `' DO NOT REMOVE — kept for 2019 SCR refresh process`.
Body should be a half-finished CSV writer that doesn't quite work.
Nobody calls it. The migration inventory step (see
`MIGRATION_RECIPE.md`) should explicitly identify it as decoration.

Pseudocode (deliberately ugly):

```
Sub LegacyExportCSV()
    ' DO NOT REMOVE — kept for 2019 SCR refresh process
    Dim fso As Object, fh As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    Set fh = fso.CreateTextFile("C:\Users\jsmith\Documents\rfr_curves.csv", True)
    ' TODO: fix the loop — currently writes header only
    fh.WriteLine "date,ccy,m,r"
    fh.Close
End Sub
```

---

## Things this workbook does badly (which is the point)

The migration sells itself if the destination clearly fixes these:

1. **One hardcoded user path** in `LegacyExportCSV` — breaks for any
   other user.
2. **`On Error Resume Next`** in `ReshapeCurve` — silently eats bad
   reference dates and produces wrong rows.
3. **No DQ checks** beyond `IsNumeric`. A negative 95% rate would
   pass.
4. **No version control.** Successive versions live as
   `RFR_Master_v3.xlsm`, `RFR_Master_FINAL_v3.xlsm`, etc.
5. **Chart bound to a hardcoded range.** Forget to run
   `RefreshChart` and the chart silently shows last month.
6. **Single-user.** Only one actuary can run the macro at a time —
   the file is locked while open.
7. **No lineage.** When the chart looks wrong, no one knows which
   EIOPA file produced which row.

The Databricks rebuild fixes 1-7 by construction: Volume governs the
input (no user paths), DLT expectations replace `IsNumeric`, Delta
Time Travel replaces `_v3_FINAL`, AI/BI Genie replaces the chart,
multiple readers can hit the table at once, and `_source_file`
captures lineage.
