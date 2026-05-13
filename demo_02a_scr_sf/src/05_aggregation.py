# Databricks notebook source
# MAGIC %md
# MAGIC # 05 — Aggregation
# MAGIC
# MAGIC ```
# MAGIC BSCR = sqrt(SCR_uw² + SCR_mkt² + 2 · ρ · SCR_uw · SCR_mkt) + SCR_cat
# MAGIC Op   = op_factor · earned_premium
# MAGIC SCR  = BSCR + Op − LACDT
# MAGIC ```
# MAGIC
# MAGIC The +`SCR_cat` outside the square root is a deliberate simplification
# MAGIC (the real S2 BSCR adds Cat inside a fuller correlation matrix). The
# MAGIC migration pattern is identical to the full formula — see the README.

# COMMAND ----------

import math
from typing import Any


def aggregate(scr_uw: float, scr_mkt: float, scr_cat: float,
              earned_premium: float, ass_row: Any) -> dict:
    rho = float(ass_row["bscr_rho_market_uw"])
    bscr = math.sqrt(scr_uw ** 2 + scr_mkt ** 2 + 2 * rho * scr_uw * scr_mkt) + scr_cat
    op = float(ass_row["op_factor"]) * float(earned_premium)
    lacdt = float(ass_row["lacdt"])
    scr = bscr + op - lacdt
    return {
        "scr_nl_premres": scr_uw,
        "scr_mkt_ir": scr_mkt,
        "scr_cat": scr_cat,
        "bscr": bscr,
        "op_risk": op,
        "lacdt": lacdt,
        "scr": scr,
    }


# COMMAND ----------

# MAGIC %md
# MAGIC ## Smoke test with placeholder sub-module SCRs

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_serverless_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
fqn = f"{catalog}.{schema}"

ass_row = spark.table(f"{fqn}.scr_assumptions").filter("is_current = 'true'").collect()[0]
inputs_row = spark.table(f"{fqn}.scr_inputs").filter("scenario_id = 'base'").collect()[0]

example = aggregate(
    scr_uw=144_000_000,
    scr_mkt=47_000_000,
    scr_cat=float(ass_row["cat_plug"]),
    earned_premium=float(inputs_row["earned_premium"]),
    ass_row=ass_row,
)
for k, v in example.items():
    print(f"  {k:18s} {v:>20,.2f}")
