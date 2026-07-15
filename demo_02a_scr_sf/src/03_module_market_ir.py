# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Market Interest Rate sub-module
# MAGIC
# MAGIC Revalue assets and liabilities under parallel up/down shocks to the
# MAGIC risk-free-rate curve (sourced from demo 1's `rfr_curves` gold table)
# MAGIC and take the worse-case NAV impact.
# MAGIC
# MAGIC ```
# MAGIC NAV_base = asset_MV         − Σ CF_y / (1 + r_y)^y
# MAGIC NAV_up   = asset_up         − Σ CF_y / (1 + r_y + Δ_up)^y
# MAGIC NAV_dn   = asset_dn         − Σ CF_y / (1 + max(r_y + Δ_dn, floor))^y
# MAGIC where asset_X = asset_MV · (1 − D · Δ_X)         (modified duration)
# MAGIC SCR_mkt_ir = max(NAV_base − min(NAV_up, NAV_dn), 0)
# MAGIC ```

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("scenario_id", "base")
dbutils.widgets.text("ir_shock_bps_override", "")  # blank = use the assumption default

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
fqn = f"{catalog}.{schema}"
scenario_id = dbutils.widgets.get("scenario_id")
override = dbutils.widgets.get("ir_shock_bps_override").strip()
ir_shock_bps_override = int(override) if override else None

# COMMAND ----------

from typing import Any


def _build_curve(rfr_rows) -> dict[int, float]:
    """maturity_months → spot_rate"""
    return {int(r["maturity_months"]): float(r["spot_rate"]) for r in rfr_rows}


def _pv_liabilities(cash_flows, curve: dict[int, float]) -> float:
    pv = 0.0
    for cf in cash_flows:
        year = int(cf["year"])
        mo = year * 12
        # nearest-maturity lookup for sparse curves (e.g. 30 maturities, 1y..30y)
        r = curve.get(mo) or curve[min(curve.keys(), key=lambda m: abs(m - mo))]
        pv += float(cf["amount"]) / (1.0 + r) ** year
    return pv


def market_ir_scr(inputs_row: Any, ass_row: Any, rfr_rows,
                  ir_shock_bps_override: int | None = None) -> float:
    base_curve = _build_curve(rfr_rows)
    shock_up = (ir_shock_bps_override or ass_row["ir_shock_up_bps"]) / 10_000
    shock_dn = float(ass_row["ir_shock_down_bps"]) / 10_000
    floor = float(ass_row["ir_shock_down_floor"])

    def shocked(shock: float, with_floor: bool = False) -> dict[int, float]:
        return {
            mo: (max(r + shock, floor) if with_floor else r + shock)
            for mo, r in base_curve.items()
        }

    asset_mv = float(inputs_row["asset_value"])
    duration = float(inputs_row["asset_modified_duration"])

    pv_base = _pv_liabilities(inputs_row["liability_cash_flows"], base_curve)
    pv_up = _pv_liabilities(inputs_row["liability_cash_flows"], shocked(shock_up))
    pv_dn = _pv_liabilities(inputs_row["liability_cash_flows"], shocked(shock_dn, with_floor=True))

    asset_up = asset_mv * (1 - duration * shock_up)
    asset_dn = asset_mv * (1 - duration * shock_dn)

    nav_base, nav_up, nav_dn = asset_mv - pv_base, asset_up - pv_up, asset_dn - pv_dn
    return max(nav_base - min(nav_up, nav_dn), 0.0)


# COMMAND ----------

# MAGIC %md
# MAGIC ## Pull the inputs + assumptions + RFR curve

# COMMAND ----------

inputs_row = spark.table(f"{fqn}.scr_inputs") \
    .filter(f"scenario_id = '{scenario_id}'") \
    .collect()[0]
ass_row = spark.table(f"{fqn}.scr_assumptions") \
    .filter("is_current = 'true'") \
    .collect()[0]

eff_date = inputs_row["rfr_effective_date"]
currency = inputs_row["currency"]
rfr_rows = (spark.table(f"{fqn}.rfr_curves")
            .filter(f"effective_date = '{eff_date}' AND currency = '{currency}'")
            .select("maturity_months", "spot_rate")
            .collect())

if not rfr_rows:
    raise RuntimeError(
        f"No rfr_curves rows for effective_date={eff_date}, currency={currency}. "
        "Run demo 1 first."
    )
print(f"Scenario   : {scenario_id}")
print(f"RFR curve  : {eff_date} {currency} ({len(rfr_rows)} maturities)")
print(f"IR override: {ir_shock_bps_override}")

# COMMAND ----------

scr = market_ir_scr(inputs_row, ass_row, rfr_rows, ir_shock_bps_override)
print(f"\nSCR_mkt_ir = {scr:,.2f}")

dbutils.notebook.exit(str(scr))
