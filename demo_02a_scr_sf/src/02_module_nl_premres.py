# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — NL Premium & Reserve sub-module
# MAGIC
# MAGIC Compute `SCR_nl_premres` for one scenario.
# MAGIC
# MAGIC Formula:
# MAGIC ```
# MAGIC σ_lob   = sqrt((σ_prem · V_prem)² + 2α · σ_prem · σ_res · V_prem · V_res
# MAGIC               + (σ_res · V_res)²) / V_lob       with α = 0.5
# MAGIC σ_NL    = sqrt(Σ_ij ρ_ij · σ_i · V_i · σ_j · V_j) / V_NL
# MAGIC SCR_uw  = 3 · σ_NL · V_NL
# MAGIC ```
# MAGIC
# MAGIC The notebook is also importable as a function — `06_orchestrator.py`
# MAGIC uses `nl_premres_scr(inputs_row, ass_row, shock_uplifts)` directly.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_serverless_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("scenario_id", "base")
dbutils.widgets.text("motor_uplift", "0.0")
dbutils.widgets.text("property_uplift", "0.0")
dbutils.widgets.text("liability_uplift", "0.0")
dbutils.widgets.text("other_uplift", "0.0")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
fqn = f"{catalog}.{schema}"
scenario_id = dbutils.widgets.get("scenario_id")
shock_uplifts = {
    "Motor":     float(dbutils.widgets.get("motor_uplift")),
    "Property":  float(dbutils.widgets.get("property_uplift")),
    "Liability": float(dbutils.widgets.get("liability_uplift")),
    "Other":     float(dbutils.widgets.get("other_uplift")),
}

# COMMAND ----------

import math
from typing import Any


def combined_sigma(sigma_prem: float, sigma_res: float,
                   v_prem: float, v_res: float, alpha: float = 0.5) -> float:
    """EIOPA-style combined σ over (premium, reserve) with α=0.5."""
    v = v_prem + v_res
    if v == 0:
        return 0.0
    num = (
        (sigma_prem * v_prem) ** 2
        + 2 * alpha * sigma_prem * sigma_res * v_prem * v_res
        + (sigma_res * v_res) ** 2
    )
    return math.sqrt(num) / v


def nl_premres_scr(inputs_row: Any, ass_row: Any,
                   shock_uplifts: dict[str, float] | None = None) -> float:
    """Aggregate NL Premium & Reserve SCR across the LoBs."""
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
            float(sigmas[lob]["sigma_prem"]),
            float(sigmas[lob]["sigma_res"]),
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


# COMMAND ----------

# MAGIC %md
# MAGIC ## Inputs + assumptions for this scenario

# COMMAND ----------

inputs_row = spark.table(f"{fqn}.scr_inputs") \
    .filter(f"scenario_id = '{scenario_id}'") \
    .collect()[0]
ass_row = spark.table(f"{fqn}.scr_assumptions") \
    .filter("is_current = 'true'") \
    .collect()[0]

print(f"Scenario   : {scenario_id}")
print(f"Assumption : {ass_row['assumption_version']}")
print(f"Shocks     : {shock_uplifts}")

# COMMAND ----------

scr = nl_premres_scr(inputs_row, ass_row, shock_uplifts)
print(f"\nSCR_nl_premres = {scr:,.2f}")

dbutils.notebook.exit(str(scr))
