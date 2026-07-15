# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Inputs & Assumptions (demo 2A)
# MAGIC
# MAGIC Idempotently creates the three UC tables behind demo 2A and loads the
# MAGIC sample inputs / assumptions JSON into them.
# MAGIC
# MAGIC | Table | Grain | Loaded from |
# MAGIC | --- | --- | --- |
# MAGIC | `scr_inputs` | one row per scenario_id | `sample_data/scr_inputs.json` |
# MAGIC | `scr_assumptions` | one row per assumption_version | `sample_data/scr_assumptions.json` |
# MAGIC | `scr_scenarios` | results — written by `07_scenarios_mlflow` | (empty after setup) |
# MAGIC
# MAGIC Safe to re-run. Existing tables are dropped and rewritten so the demo
# MAGIC starts in a known state.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
fqn = f"{catalog}.{schema}"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Schema (created by demo 1's shared/uc_setup.py — assumed present)

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {fqn}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Locate the sample data JSON files
# MAGIC
# MAGIC The bundle deploys `sample_data/` next to this notebook. Resolve the
# MAGIC path off the notebook's own location so the same code works from any
# MAGIC workspace.

# COMMAND ----------

import json
import os

notebook_path = (
    dbutils.notebook.entry_point.getDbutils().notebook().getContext()
    .notebookPath().getOrElse(None)
)
notebook_dir = os.path.dirname(notebook_path) if notebook_path else "."
# notebook_path is workspace-relative; the bundle puts sample_data/
# at ../sample_data/ from src/.
sample_dir = f"/Workspace{notebook_dir}/../sample_data"
print(f"Loading inputs/assumptions from {sample_dir}")

with open(f"{sample_dir}/scr_inputs.json") as f:
    inputs_doc = json.load(f)
with open(f"{sample_dir}/scr_assumptions.json") as f:
    ass_doc = json.load(f)

print(f"  inputs scenarios: {[s['scenario_id'] for s in inputs_doc['scenarios']]}")
print(f"  assumption versions: {[a['assumption_version'] for a in ass_doc['versions']]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `scr_inputs`

# COMMAND ----------

from pyspark.sql.types import (
    StructType, StructField, StringType, DateType, DoubleType,
    ArrayType, IntegerType,
)

scr_inputs_schema = StructType([
    StructField("scenario_id", StringType(), False),
    StructField("as_of_date", DateType(), False),
    StructField("currency", StringType(), False),
    StructField("rfr_effective_date", DateType(), False),
    StructField("earned_premium", DoubleType(), False),
    StructField("asset_value", DoubleType(), False),
    StructField("asset_modified_duration", DoubleType(), False),
    StructField("lob_volumes", ArrayType(StructType([
        StructField("lob", StringType(), False),
        StructField("v_prem", DoubleType(), False),
        StructField("v_res", DoubleType(), False),
    ])), False),
    StructField("liability_cash_flows", ArrayType(StructType([
        StructField("year", IntegerType(), False),
        StructField("amount", DoubleType(), False),
    ])), False),
])

import datetime as dt
inputs_rows = [
    (
        s["scenario_id"],
        dt.date.fromisoformat(s["as_of_date"]),
        s["currency"],
        dt.date.fromisoformat(s["rfr_effective_date"]),
        float(s["earned_premium"]),
        float(s["asset_value"]),
        float(s["asset_modified_duration"]),
        [(r["lob"], float(r["v_prem"]), float(r["v_res"])) for r in s["lob_volumes"]],
        [(int(r["year"]), float(r["amount"])) for r in s["liability_cash_flows"]],
    )
    for s in inputs_doc["scenarios"]
]
df = spark.createDataFrame(inputs_rows, scr_inputs_schema)
df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{fqn}.scr_inputs")
print(f"✓ {fqn}.scr_inputs — {df.count()} row(s)")

spark.sql(f"""
    COMMENT ON TABLE {fqn}.scr_inputs IS
    'Demo 2A SCR inputs. One row per scenario_id; carries per-LoB volumes,'
    ' asset value/duration, liability cash flows, earned premium. Loaded by'
    ' 01_inputs_assumptions.py from sample_data/scr_inputs.json.'
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `scr_assumptions`

# COMMAND ----------

scr_assumptions_schema = StructType([
    StructField("assumption_version", StringType(), False),
    StructField("effective_date", DateType(), False),
    StructField("is_current", StringType(), False),  # BooleanType but stored as 'true'/'false' for SQL readability
    StructField("comment", StringType(), True),
    StructField("nl_lob_order", ArrayType(StringType()), False),
    StructField("nl_lob_sigmas", ArrayType(StructType([
        StructField("lob", StringType(), False),
        StructField("sigma_prem", DoubleType(), False),
        StructField("sigma_res", DoubleType(), False),
    ])), False),
    StructField("nl_lob_correlation", ArrayType(ArrayType(DoubleType())), False),
    StructField("bscr_rho_market_uw", DoubleType(), False),
    StructField("op_factor", DoubleType(), False),
    StructField("cat_plug", DoubleType(), False),
    StructField("lacdt", DoubleType(), False),
    StructField("ir_shock_up_bps", IntegerType(), False),
    StructField("ir_shock_down_bps", IntegerType(), False),
    StructField("ir_shock_down_floor", DoubleType(), False),
])

ass_rows = [
    (
        a["assumption_version"],
        dt.date.fromisoformat(a["effective_date"]),
        "true" if a["is_current"] else "false",
        a.get("comment"),
        a["nl_lob_order"],
        [(r["lob"], float(r["sigma_prem"]), float(r["sigma_res"]))
         for r in a["nl_lob_sigmas"]],
        [[float(x) for x in row] for row in a["nl_lob_correlation"]],
        float(a["bscr_rho_market_uw"]),
        float(a["op_factor"]),
        float(a["cat_plug"]),
        float(a["lacdt"]),
        int(a["ir_shock_up_bps"]),
        int(a["ir_shock_down_bps"]),
        float(a["ir_shock_down_floor"]),
    )
    for a in ass_doc["versions"]
]
df = spark.createDataFrame(ass_rows, scr_assumptions_schema)
df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{fqn}.scr_assumptions")
print(f"✓ {fqn}.scr_assumptions — {df.count()} row(s)")

spark.sql(f"""
    COMMENT ON TABLE {fqn}.scr_assumptions IS
    'Demo 2A SCR assumptions. Versioned by assumption_version with'
    ' effective_date and is_current flag. Sigma values approximate the'
    ' EIOPA Standard Formula Annex shape for the corresponding LoBs but'
    ' are reduced to a 4-LoB scheme — synthetic, not certified.'
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `scr_scenarios` — empty after setup; populated by 07_scenarios_mlflow

# COMMAND ----------

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {fqn}.scr_scenarios (
        scenario_id         STRING,
        run_id              STRING  COMMENT 'MLflow run_id',
        assumption_version  STRING,
        shock_ir_bps        INT,
        shock_motor_uplift     DOUBLE,
        shock_property_uplift  DOUBLE,
        shock_liability_uplift DOUBLE,
        shock_other_uplift     DOUBLE,
        scr_nl_premres      DOUBLE,
        scr_mkt_ir          DOUBLE,
        scr_cat             DOUBLE,
        bscr                DOUBLE,
        op_risk             DOUBLE,
        lacdt               DOUBLE,
        scr                 DOUBLE,
        run_ts              TIMESTAMP
    )
    COMMENT 'Demo 2A scenario sweep results. One row per (scenario_id, run_id).'
""")

# Truncate on re-run so the demo always starts clean.
spark.sql(f"TRUNCATE TABLE {fqn}.scr_scenarios")
print(f"✓ {fqn}.scr_scenarios (empty)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

display(spark.sql(f"""
    SELECT table_name, comment
    FROM {catalog}.information_schema.tables
    WHERE table_schema = '{schema}' AND table_name LIKE 'scr\\\\_%' ESCAPE '\\\\'
    ORDER BY table_name
"""))
