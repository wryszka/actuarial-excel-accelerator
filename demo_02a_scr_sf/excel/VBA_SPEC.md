# VBA_SPEC — SCR_StandardFormula.xlsm

Spec for the hand-built `SCR_StandardFormula.xlsm`. This is the
**"before and after"** of demo 2A:

- **Before** (Tabs `Inputs`, `Assumptions`, `NL_PremRes`, `Market_IR`,
  `Cat`, `Aggregation`, `Output`): a recognisably-real SCR Standard
  Formula model in Excel + VBA. Cells contain formulas; VBA macros
  run scenario sweeps and format the output tab.

- **After** (Tab `Round_Trip`, Power Query + a small VBA helper): the
  same workbook with the calculation engine replaced by a UC Python
  SQL UDF. Actuary types shocks into the Round_Trip tab, hits
  refresh, sees Databricks-computed SCR.

Author the .xlsm by hand from this spec and commit it. The companion
`build_excel_data.py` produces a no-VBA `.xlsx` with the same
formulas plus a hidden `SCR_Computed` tab — that's what the parity
test reads.

---

## Tabs

| Tab | Purpose |
|---|---|
| `Instructions` | One-page README. |
| `Inputs` | Per-LoB volumes (Motor, Property, Liability, Other), asset value + duration, liability cash flows by year, earned premium. |
| `RFR_Curves` | Pasted from `{catalog}.{schema}.rfr_curves` (demo 1 gold). One row per (effective_date, currency, maturity_months, spot_rate). |
| `Assumptions` | σ_prem / σ_res per LoB, 4×4 LoB correlation matrix, BSCR ρ(Mkt, UW), Op factor, Cat plug, LACDT, IR shock bps. |
| `NL_PremRes` | Per-LoB combined σ → NL σ via the correlation matrix → SCR_uw = 3·σ_NL·V_NL. |
| `Market_IR` | NAV under IR up/down. PV-of-liabilities via discount factor; assets via modified duration. SCR_mkt_ir = max NAV impact. |
| `Cat` | Plug pass-through from Assumptions. |
| `Aggregation` | BSCR = √(SCR_uw² + SCR_mkt² + 2ρ·SCR_uw·SCR_mkt) + Cat. SCR = BSCR + Op − LACDT. |
| `Scenarios` | Results table populated by `RunScenarios()`. One row per shock combo. |
| `Output` | Formatted SCR breakdown for printing. Built by `GenerateSummary()`. |
| `Round_Trip` | Power Query-driven tab — actuary types shocks here, Excel calls the UC SQL UDF, results appear. |

## Named ranges

| Name | Refers to | Used by |
|---|---|---|
| `rng_AssumptionsBlock` | `Assumptions!$A$3:$C$7` | `RunScenarios` |
| `rng_IRShockUp` | `Assumptions!$B$14` | `RunScenarios` |
| `rng_IRShockDown` | `Assumptions!$B$15` | `RunScenarios` |
| `rng_LobUpliftMotor` | _missing — should be `Inputs!$B$12`, but the VBA uses the raw cell address instead. Leave it broken on purpose._ | `RunScenarios` |
| `rng_ScenariosOut` | `Scenarios!$A$4` | `RunScenarios` |
| `rng_RoundTripParams` | `Round_Trip!$B$3:$B$8` | Power Query (`PQ_ShockParams`) |
| `rng_RoundTripResult` | `Round_Trip!$B$12:$B$18` | Power Query refresh target |

---

## VBA modules

All Subs live in one module called `SCR_Pipeline`.

### `Sub RunScenarios()`

The macro that the actuary clicks at month-end to refresh the scenario
sweep.

Pseudocode:

```
1. Application.ScreenUpdating = False   ' (deliberately placed wrong — should
                                        ' be inside the loop body, but actuary
                                        ' placed it at the top of Sub once and
                                        ' never noticed. Symptom: chart flicker
                                        ' on first run after Excel restart.)
2. shocks = Array(
       Array(0,   0.0, 0.0, 0.0, 0.0),
       Array(200, 0.0, 0.0, 0.0, 0.0),
       Array(-200,0.0, 0.0, 0.0, 0.0),
       Array(0,   0.10, 0.0, 0.0, 0.0),
       Array(0,   0.0, 0.10, 0.0, 0.0),
       ' ... 30 rows total — combinations of IR bps + LoB uplifts
   )
3. nextRow = 4
4. For each shock In shocks
   - Write shock[0] (IR bps) into IRShockUp/IRShockDown
   - Write shock[1..4] into Inputs!B12..B15 (BAD — should use named
     range, but does not. Known quirk.)
   - Application.Calculate
   - Read SCR breakdown cells from Aggregation tab
   - Write (scenarioId, ir_shock_bps, motor_uplift, ..., scr) into
     Scenarios!A{nextRow}:M{nextRow}
   - nextRow = nextRow + 1
5. On Error Resume Next            ' (eats any single-iteration error so
                                   ' a bad config doesn't break the sweep —
                                   ' wrong: silently produces NULL rows)
6. Application.ScreenUpdating = True
```

Key constructs:
- `Application.Calculate` to force a full recalc after each shock
- `Cells(row, col).Value = ...` to write each scenario result row
- Stored shock combos as a hardcoded array (no input data source for
  the scenarios — known maintenance pain point)

### `Sub GenerateSummary()`

Formats the Output tab from the current calc state.

Pseudocode:

```
1. Clear Output!A4:B20
2. Write (label, =Aggregation!B<n>) for each of:
     - SCR_uw, SCR_mkt, SCR_cat, BSCR, Op, LACDT, SCR
3. Apply bold + accounting format to value column
4. Insert a horizontal rule between BSCR and SCR
```

### `Sub LegacyExportSCR()` — DEAD CODE

Same realism device as demo 1's `LegacyExportCSV`. Half-finished CSV
writer; nobody calls it. Comment inside: `' DO NOT REMOVE — kept for
2019 SCR refresh process`.

### `Sub RoundTrip_Refresh()` — the migration target

A small VBA helper that pokes shock parameters into the Power Query
parameter cells, then triggers `ActiveWorkbook.RefreshAll`. Together
with the Power Query (below), this is the **post-migration**
calculation path.

Pseudocode:

```
1. ThisWorkbook.Connections("DBX_SCR_UDF").Refresh
2. If Application.WorksheetFunction.IsError(Range("Round_Trip!B12")) Then
     MsgBox "Refresh failed — check the SQL warehouse connection."
3. Range("Round_Trip!C2").Value = "Last refreshed: " & Now()
```

---

## Power Query — `PQ_ShockParams` and `PQ_SCR_UDF`

The **post-migration** path. No VBA does the SCR math anymore; the UC
Python UDF does. The Power Query reads shock parameter cells, calls
the UDF, returns a result table.

### Connection setup (one-time)

Data → Get Data → From Database → From Databricks. Supply:

- Server hostname: `<workspace-host>` (e.g. `fevm-lr-serverless-aws-us.cloud.databricks.com`)
- HTTP path: the SQL warehouse HTTP path (Settings → SQL Warehouses)
- Catalog: `${var.catalog_name}`
- Database/schema: `${var.schema_name}`
- Authentication: Azure AD / OAuth user-to-machine

Authenticate when prompted. The connection is saved as `DBX_SCR_UDF`
and re-used by the queries below.

### `PQ_ShockParams` — pulls Excel parameters

```m
let
    p = Excel.CurrentWorkbook(){[Name="rng_RoundTripParams"]}[Content],
    ir = p{0}[Value],
    motor = p{1}[Value],
    prop = p{2}[Value],
    liab = p{3}[Value],
    other = p{4}[Value],
    asof = p{5}[Value]
in
    [ir_shock_bps=ir, motor_uplift=motor, property_uplift=prop,
     liability_uplift=liab, other_uplift=other, as_of=asof]
```

### `PQ_SCR_UDF` — calls the UC function and returns the result

```m
let
    params = PQ_ShockParams,
    Source = DatabricksMultiCloud.Catalogs(
        "{workspace-host}",
        "{http-path}",
        [Catalog="${var.catalog_name}", Database="${var.schema_name}"]
    ),
    Schema = Source{[Name="${var.schema_name}"]}[Data],
    -- Note: SQL UDF calls in Power Query use `Sql.Database` / native
    -- query passthrough rather than the navigator. The actuary
    -- typically pastes this:
    Query = Value.NativeQuery(
        Source{[Name="${var.catalog_name}"]}[Data],
        "SELECT " &
        "  result.scr_uw    AS scr_uw," &
        "  result.scr_mkt   AS scr_mkt," &
        "  result.scr_cat   AS scr_cat," &
        "  result.bscr      AS bscr," &
        "  result.op_risk   AS op_risk," &
        "  result.lacdt     AS lacdt," &
        "  result.scr       AS scr " &
        "FROM (SELECT ${var.schema_name}.scr_total(" &
        "  Number.ToText(params[motor_uplift]) & ", " &
        "  Number.ToText(params[property_uplift]) & ", " &
        "  Number.ToText(params[liability_uplift]) & ", " &
        "  Number.ToText(params[other_uplift]) & ", " &
        "  Number.ToText(params[ir_shock_bps]) &
        ") AS result)"
    )
in
    Query
```

The result table is loaded into `Round_Trip!B12:B18` as a vertical
slice (one row per metric).

> **Note for the demo author.** Power Query's M function for the
> Databricks connector is `DatabricksMultiCloud.Catalogs`. Exact M
> syntax differs slightly across versions of the connector; the
> intent above is the pattern, not a literal copy-paste. The simplest
> path is to set up the connection visually first, then edit the
> generated M to parameterise.

---

## Round_Trip tab layout

```
A1: "Round-Trip — Databricks SCR engine"   (bold)
A3: "Shock parameters"                     (header)
A4: "IR shock (bps)"      B4: <user input — int>
A5: "Motor uplift"        B5: <user input — fraction, e.g. 0.10>
A6: "Property uplift"     B6: <user input>
A7: "Liability uplift"    B7: <user input>
A8: "Other uplift"        B8: <user input>
A9: "As-of date"          B9: <user input — text 'YYYY-MM-DD'>

A11: "SCR breakdown (from Databricks)"     (header)
A12: "SCR_uw"             B12: <Power Query result>
A13: "SCR_mkt"            B13:   "
A14: "SCR_cat"            B14:   "
A15: "BSCR"               B15:   "
A16: "Op risk"            B16:   "
A17: "LACDT"              B17:   "
A18: "SCR"                B18:   "   (bold, accounting format)

A20: <button — caption "Refresh from Databricks", OnClick=RoundTrip_Refresh>
```

---

## Things this workbook does badly (which is the point)

Demo 2A's migration sells itself if the destination clearly fixes:

1. **Scenarios hardcoded inside the macro.** Adding a new shock combo
   requires editing VBA.
2. **`On Error Resume Next`** in `RunScenarios` — bad config silently
   produces NULL rows.
3. **`Application.ScreenUpdating = False` placed at top of Sub** and
   then `= True` at end — wrong scope; an early Exit Sub leaves Excel
   in mute mode and the actuary has to Alt-F8 to fix.
4. **One hardcoded cell address** in `RunScenarios` where a named
   range exists for the same target.
5. **No version control** on assumptions. New σ values overwrite old.
6. **No audit trail** — who ran the sweep, when, with what inputs.
7. **Scenario sweep recalculates the same engine 30 times** — slow.

The Databricks rebuild fixes 1-7 by construction: scenarios live in a
table, errors raise expectations, headless Spark jobs replace
`Application.ScreenUpdating`, named UC paths replace cell addresses,
`scr_assumptions` is versioned with `effective_date`, MLflow captures
every scenario run, and one query against the SQL UDF returns the
breakdown.
