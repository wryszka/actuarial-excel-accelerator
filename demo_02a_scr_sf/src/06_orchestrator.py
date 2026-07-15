# Databricks notebook source
# MAGIC %md
# MAGIC # 06 — Orchestrator
# MAGIC
# MAGIC `compute_scr(scenario_id, shocks)` chains the four sub-modules and
# MAGIC returns a full SCR breakdown dict. Used by:
# MAGIC
# MAGIC - `07_scenarios_mlflow` — drives the scenario sweep
# MAGIC - `08_parity_test` — compares against the Excel hidden-tab oracle
# MAGIC - `09_sql_udfs` — wraps it as `scr_total(...)` for the Excel round-trip
# MAGIC - `99_validate` — runs one base scenario as the smoke test
# MAGIC
# MAGIC The orchestrator is **idempotent and pure** w.r.t. its arguments: same
# MAGIC inputs/assumptions/RFR snapshot → same SCR. That's what makes the
# MAGIC scenario sweep meaningful — every difference between runs is explained
# MAGIC by a shock parameter.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("scenario_id", "base")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
fqn = f"{catalog}.{schema}"
scenario_id = dbutils.widgets.get("scenario_id")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Inline the sub-module compute functions
# MAGIC
# MAGIC The sub-module notebooks (`02_*`, `03_*`, `04_*`, `05_*`) each expose a
# MAGIC function with the same body as below. They're inlined here so the
# MAGIC orchestrator has no `%run` dependencies — one notebook, one import.

# COMMAND ----------

import math
from typing import Any


def combined_sigma(sigma_prem, sigma_res, v_prem, v_res, alpha=0.5):
    v = v_prem + v_res
    if v == 0:
        return 0.0
    num = ((sigma_prem * v_prem) ** 2
           + 2 * alpha * sigma_prem * sigma_res * v_prem * v_res
           + (sigma_res * v_res) ** 2)
    return math.sqrt(num) / v


def nl_premres_scr(inputs_row, ass_row, shock_uplifts=None):
    shock_uplifts = shock_uplifts or {}
    lob_order = list(ass_row["nl_lob_order"])
    sigmas = {r["lob"]: r for r in ass_row["nl_lob_sigmas"]}
    vols = {r["lob"]: r for r in inputs_row["lob_volumes"]}
    rho = [list(row) for row in ass_row["nl_lob_correlation"]]
    sigma_lob, v_lob = [], []
    for lob in lob_order:
        uplift = 1.0 + shock_uplifts.get(lob, 0.0)
        v_prem = float(vols[lob]["v_prem"]) * uplift
        v_res = float(vols[lob]["v_res"]) * uplift
        sigma_lob.append(combined_sigma(
            float(sigmas[lob]["sigma_prem"]), float(sigmas[lob]["sigma_res"]),
            v_prem, v_res,
        ))
        v_lob.append(v_prem + v_res)
    v_nl = sum(v_lob)
    if v_nl == 0:
        return 0.0
    inner = 0.0
    for i in range(len(lob_order)):
        for j in range(len(lob_order)):
            inner += rho[i][j] * sigma_lob[i] * v_lob[i] * sigma_lob[j] * v_lob[j]
    sigma_nl = math.sqrt(max(inner, 0.0)) / v_nl
    return 3.0 * sigma_nl * v_nl


def market_ir_scr(inputs_row, ass_row, rfr_rows, ir_shock_bps_override=None):
    curve = {int(r["maturity_months"]): float(r["spot_rate"]) for r in rfr_rows}
    shock_up = (ir_shock_bps_override or ass_row["ir_shock_up_bps"]) / 10_000
    shock_dn = float(ass_row["ir_shock_down_bps"]) / 10_000
    floor = float(ass_row["ir_shock_down_floor"])

    def pv(crv):
        out = 0.0
        for cf in inputs_row["liability_cash_flows"]:
            yr = int(cf["year"])
            mo = yr * 12
            r = crv.get(mo) or crv[min(crv.keys(), key=lambda m: abs(m - mo))]
            out += float(cf["amount"]) / (1.0 + r) ** yr
        return out

    def shocked(s, with_floor=False):
        return {mo: (max(r + s, floor) if with_floor else r + s)
                for mo, r in curve.items()}

    asset_mv = float(inputs_row["asset_value"])
    duration = float(inputs_row["asset_modified_duration"])

    pv_base = pv(curve)
    pv_up = pv(shocked(shock_up))
    pv_dn = pv(shocked(shock_dn, with_floor=True))
    nav_base = asset_mv - pv_base
    nav_up = asset_mv * (1 - duration * shock_up) - pv_up
    nav_dn = asset_mv * (1 - duration * shock_dn) - pv_dn
    return max(nav_base - min(nav_up, nav_dn), 0.0)


def aggregate(scr_uw, scr_mkt, scr_cat, earned_premium, ass_row):
    rho = float(ass_row["bscr_rho_market_uw"])
    bscr = math.sqrt(scr_uw ** 2 + scr_mkt ** 2 + 2 * rho * scr_uw * scr_mkt) + scr_cat
    op = float(ass_row["op_factor"]) * float(earned_premium)
    lacdt = float(ass_row["lacdt"])
    scr = bscr + op - lacdt
    return {
        "scr_nl_premres": scr_uw, "scr_mkt_ir": scr_mkt, "scr_cat": scr_cat,
        "bscr": bscr, "op_risk": op, "lacdt": lacdt, "scr": scr,
    }


# COMMAND ----------

# MAGIC %md
# MAGIC ## `compute_scr(scenario_id, shocks)`

# COMMAND ----------

def compute_scr(scenario_id: str = "base", shocks: dict | None = None,
                catalog: str = catalog, schema: str = schema) -> dict:
    shocks = shocks or {}
    fqn = f"{catalog}.{schema}"

    inputs_row = spark.table(f"{fqn}.scr_inputs") \
        .filter(f"scenario_id = '{scenario_id}'") \
        .collect()[0]
    ass_row = spark.table(f"{fqn}.scr_assumptions") \
        .filter("is_current = 'true'") \
        .collect()[0]
    rfr_rows = (spark.table(f"{fqn}.rfr_curves")
                .filter(f"effective_date = '{inputs_row['rfr_effective_date']}'"
                        f" AND currency = '{inputs_row['currency']}'")
                .select("maturity_months", "spot_rate")
                .collect())
    if not rfr_rows:
        raise RuntimeError(
            f"No rfr_curves rows for effective_date={inputs_row['rfr_effective_date']}, "
            f"currency={inputs_row['currency']}. Run demo 1 first."
        )

    scr_uw = nl_premres_scr(inputs_row, ass_row, shocks.get("lob_uplifts", {}))
    scr_mkt = market_ir_scr(inputs_row, ass_row, rfr_rows, shocks.get("ir_shock_bps"))
    scr_cat = float(ass_row["cat_plug"])

    out = aggregate(scr_uw, scr_mkt, scr_cat,
                    float(inputs_row["earned_premium"]), ass_row)
    out["scenario_id"] = scenario_id
    out["assumption_version"] = ass_row["assumption_version"]
    return out


# COMMAND ----------

# MAGIC %md
# MAGIC ## Smoke run

# COMMAND ----------

result = compute_scr(scenario_id=scenario_id)
print(f"compute_scr(scenario_id='{scenario_id}'):")
for k, v in result.items():
    if isinstance(v, (int, float)):
        print(f"  {k:20s} {v:>20,.2f}")
    else:
        print(f"  {k:20s} {v}")
