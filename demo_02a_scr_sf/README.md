# Demo 2A — Solvency II SCR Standard Formula

## What this demo shows

The "before" is `excel/SCR_StandardFormula.xlsm`: a recognisably-real
SCR Standard Formula model in Excel + VBA. Per-LoB calcs, named
ranges, scenario sweep macro, on-error-resume-next, output-tab
formatter. The kind of file actuaries actually maintain.

The "after" is the same model rebuilt in Databricks:

- **Parameterised, versioned assumptions** in `scr_assumptions`
  (with `effective_date` and `is_current`)
- **Per-LoB and per-shock-scenario inputs** in `scr_inputs`
- **An orchestrator** (`06_orchestrator.py`) that returns the full
  SCR breakdown for any scenario
- **A 30-scenario sweep** logged to MLflow + persisted to
  `scr_scenarios` — replaces the VBA `RunScenarios()` macro
- **Three UC Python SQL UDFs** (`scr_total`, `scr_nl_premres`,
  `scr_mkt_ir`) so the actuary can keep using Excel: shocks typed
  into a `Round_Trip` tab, Power Query refresh, Databricks math
  streamed back
- **A Lakeview dashboard** with the SCR waterfall + breakdown + top-5
  worst scenarios
- **A parity test** that confirms the Databricks orchestrator
  matches Python-computed reference values stored in the Excel
  workbook's hidden `SCR_Computed` tab

Demo 2A consumes `{catalog}.{schema}.rfr_curves` from demo 1 to
discount liability cash flows in the Market IR sub-module. Run demo
1 first.

## Scope — a deliberate simplification

This is a **simplified** Standard Formula structure suitable for a
migration demo, not for production capital calculation:

| Aspect | What this demo does | Real Standard Formula |
|---|---|---|
| Risk modules | 2: NL Premium & Reserve + Market IR | 6 (Market, Default, Life, Health, NL, Intangible) plus sub-modules |
| NL Cat | Single plug from `cat_plug` assumption | Modelled per peril with reinsurance recoveries |
| Market | IR only (up/down 200bps parallel) | IR + Equity + Property + Spread + Currency + Concentration |
| BSCR aggregation | 2×2 closed form + Cat added outside | Full 6×6 correlation; Cat aggregated inside the matrix |
| LACDT | Single constant from `lacdt` assumption | Modelled from deferred tax positions |
| Op risk | 3% × earned premium (one factor) | Premium or technical-provision-driven, capped |
| Sigma calibration | EIOPA-shape values for 4 LoBs | Full LoB list, per-jurisdiction overrides |

**The migration pattern shown here applies identically to the full
Standard Formula.** Adding a sub-module means another notebook
that takes inputs + assumptions and returns a number; adding rows
to the correlation matrix means widening the assumption struct. The
ingestion, parametrisation, MLflow tracking, parity test, UDF
round-trip, and dashboard scaffolding are unchanged.

## The four-step demo arc

| Step | Talk-track moment |
|---|---|
| **1. Ugly Excel** | Open `excel/SCR_StandardFormula.xlsm`. Show the named ranges, the `RunScenarios` macro with its `On Error Resume Next`, the hardcoded shock array, the misplaced `ScreenUpdating`. |
| **2. Migrate** | Open `src/01_inputs_assumptions.py` → `06_orchestrator.py`. The whole SCR calc is six notebooks of explicit Python. Each sub-module is a function that takes a row and returns a number. |
| **3. Parity** | Run `08_parity_test.py`. Databricks SCR matches the Excel's Python oracle to within €1k on the four curve-independent metrics. (The Market IR line uses the live RFR curve from demo 1, so it differs from Excel's flat-rate fallback — that's the point.) |
| **4. Round-trip** | Open `excel/SCR_StandardFormula.xlsm` Round_Trip tab. Type a new shock. Hit Refresh. Databricks SCR flows back through the UC `scr_total(...)` UDF + Power Query. The actuary keeps Excel; the model is no longer in Excel. |

## Deploy

Demo 1 must be deployed first (demo 2A reads `rfr_curves`):

```bash
# Demo 1 — see ../demo_01_rfr_etl/README.md
databricks bundle deploy --target dev
databricks bundle run setup_demo --target dev
databricks bundle run run_rfr_etl --target dev

# Demo 2A
databricks bundle run scr_setup --target dev      # load inputs + assumptions
databricks bundle run scr_full_run --target dev   # orchestrator → parity → sweep → UDFs → dashboard
databricks bundle run scr_validate --target dev   # smoke test
```

All notebooks deploy under
`/Workspace/Users/<me>/actuarial-excel-accelerator/files/demo_02a_scr_sf/`.

## Files

| Path | Purpose |
|---|---|
| `excel/SCR_StandardFormula.xlsm` | The "before" — author hand-builds from `VBA_SPEC.md`. |
| `excel/SCR_StandardFormula.xlsx` | No-VBA fixture with formulas + hidden `SCR_Computed` parity oracle. Built by `build_excel_data.py`. |
| `excel/build_excel_data.py` | Generates the .xlsx fixture + Python compute oracle. |
| `excel/VBA_SPEC.md` | Spec for the .xlsm VBA + Power Query round-trip wiring. |
| `sample_data/scr_inputs.json` | Per-LoB volumes, asset value, cash flows. Loaded by 01. |
| `sample_data/scr_assumptions.json` | Sigmas, correlations, Op factor, Cat plug, LACDT. Loaded by 01. |
| `src/01_inputs_assumptions.py` | UC table create + load. |
| `src/02_module_nl_premres.py` | NL Premium & Reserve sub-module (function + standalone run). |
| `src/03_module_market_ir.py` | Market IR sub-module — uses `rfr_curves`. |
| `src/04_module_cat.py` | Cat plug pass-through. |
| `src/05_aggregation.py` | BSCR + Op − LACDT = SCR. |
| `src/06_orchestrator.py` | `compute_scr(scenario_id, shocks)` — used everywhere. |
| `src/07_scenarios_mlflow.py` | 30-scenario sweep → MLflow + `scr_scenarios` table. |
| `src/08_parity_test.py` | Reads hidden `SCR_Computed` from .xlsx and compares to Databricks. |
| `src/09_sql_udfs.py` | Registers `scr_total`, `scr_nl_premres`, `scr_mkt_ir` UC UDFs. |
| `src/10_dashboard.py` | Lakeview dashboard. |
| `src/99_validate.py` | Smoke test. |

## About this demo

Synthetic data only. Sigma values for the four NL LoBs (Motor,
Property, Liability, Other) approximate the EIOPA Standard Formula
Annex shape for the corresponding lines of business but are reduced
to a 4-LoB scheme and are **not certified** for production capital
calculation.

See [`../MIGRATION_RECIPE.md`](../MIGRATION_RECIPE.md) for the
cross-cutting recipe and its demo 2A worked examples.
