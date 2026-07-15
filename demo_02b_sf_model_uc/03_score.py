# Databricks notebook source
# MAGIC %md
# MAGIC # Use Case 2 · Step 3 — run the model on the whole group
# MAGIC
# MAGIC The workbook computes **one entity per file**. The registered model
# MAGIC scores **all 100 entities in one pass**, straight off the governed
# MAGIC inputs table, and writes `sfm_results` — with the model version and
# MAGIC calibration recorded on every row, so any number can be traced back to
# MAGIC the exact parameters that produced it.
# MAGIC
# MAGIC Ends with the **parity check**: ENT-001's result must equal the legacy
# MAGIC workbook's output (the committed oracle) to a rounding tolerance.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("sfm_volume_name", "sfm_assets")
dbutils.widgets.text("model_alias", "cal_2025")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
volume = dbutils.widgets.get("sfm_volume_name")
alias = dbutils.widgets.get("model_alias")
fqn = f"{catalog}.{schema}"
vol_path = f"/Volumes/{catalog}/{schema}/{volume}"
MODEL_NAME = f"{fqn}.sfm_scr_model"

# COMMAND ----------

import mlflow
from mlflow import MlflowClient

mlflow.set_registry_uri("databricks-uc")
client = MlflowClient()
mv = client.get_model_version_by_alias(MODEL_NAME, alias)
print(f"Scoring with {MODEL_NAME} @{alias} → version {mv.version}")

model = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@{alias}")
inputs_pd = spark.table(f"{fqn}.sfm_inputs").orderBy("entity_id").toPandas()
results_pd = model.predict(inputs_pd)
results_pd["model_version"] = int(mv.version)
print(f"✓ scored {len(results_pd)} entities")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Persist — one results table, every row traceable

# COMMAND ----------

from pyspark.sql import functions as F

results = spark.createDataFrame(results_pd)
cal_year = int(results_pd.calibration_year.iloc[0])

if spark.catalog.tableExists(f"{fqn}.sfm_results"):
    spark.sql(f"DELETE FROM {fqn}.sfm_results WHERE calibration_year = {cal_year}")
    results.write.mode("append").saveAsTable(f"{fqn}.sfm_results")
else:
    results.write.saveAsTable(f"{fqn}.sfm_results")

spark.sql(f"""
COMMENT ON TABLE {fqn}.sfm_results IS
'SCR results per entity and calibration year, produced by the sfm_scr_model '
'registered model (see model_version column — every number traces to the exact '
'model version and therefore the exact calibration that produced it). £m. '
'Synthetic data.'
""")
n = spark.table(f"{fqn}.sfm_results").where(f"calibration_year={cal_year}").count()
print(f"✓ {fqn}.sfm_results — {n} rows for calibration {cal_year}")

display(spark.sql(f"""
    SELECT calibration_year,
           COUNT(*) AS entities,
           ROUND(SUM(scr), 1) AS group_scr,
           ROUND(SUM(scr_nl), 1) AS nl,
           ROUND(SUM(scr_mkt), 1) AS mkt,
           ROUND(SUM(scr_cat), 1) AS cat
    FROM {fqn}.sfm_results GROUP BY calibration_year ORDER BY calibration_year
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parity — the model equals the workbook

# COMMAND ----------

import json

with open(f"{vol_path}/expected_entity_001.json") as f:
    oracle = json.load(f)
expected = oracle[f"cal_{cal_year}"]

got = results_pd[results_pd.entity_id == "ENT-001"].iloc[0]
rows, ok = [], True
for k in ["scr_nl", "scr_mkt", "scr_cat", "bscr", "op_risk", "scr"]:
    delta = abs(float(got[k]) - float(expected[k]))
    passed = delta <= 0.01
    ok = ok and passed
    rows.append((k, float(expected[k]), float(got[k]), float(round(delta, 6)),
                 "✓" if passed else "✗ MISMATCH"))
display(spark.createDataFrame(rows, ["metric", "workbook_oracle", "registered_model",
                                     "abs_delta", "status"]))
assert ok, "Parity FAILED — the registered model does not reproduce the workbook"
print("✓ PARITY PASS — the governed model reproduces the workbook exactly")

# COMMAND ----------

print("Scoring complete. Next: 04_recalibrate_2026.py")
