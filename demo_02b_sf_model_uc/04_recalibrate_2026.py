# Databricks notebook source
# MAGIC %md
# MAGIC # Use Case 2 · Step 4 — the 2026 calibration arrives
# MAGIC
# MAGIC In the workbook world this is the painful week: retype the parameter
# MAGIC block in every entity's file, hope no formula broke, and try to explain
# MAGIC what changed and why the number moved.
# MAGIC
# MAGIC Here it is three moves:
# MAGIC
# MAGIC 1. **Register version 2** of `sfm_scr_model` from `calibration_2026.json`
# MAGIC    (alias `@cal_2026`; `@champion` moves with it).
# MAGIC 2. **Score the same inputs** with the new version.
# MAGIC 3. **`sfm_impact`** — version 2 vs version 1 on identical data: the
# MAGIC    capital impact of the calibration update, per entity, per module.
# MAGIC    The impact assessment that takes weeks of workbook churn, in seconds —
# MAGIC    and both sides of the comparison are permanently reproducible, because
# MAGIC    each is a registered model version.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("sfm_volume_name", "sfm_assets")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
volume = dbutils.widgets.get("sfm_volume_name")
fqn = f"{catalog}.{schema}"
MODEL_NAME = f"{fqn}.sfm_scr_model"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Register version 2 — same code, new calibration

# COMMAND ----------

result = dbutils.notebook.run("02_register_model", 600, {
    "catalog_name": catalog,
    "schema_name": schema,
    "sfm_volume_name": volume,
    "calibration_file": "calibration_2026.json",
})
print("✓ 02_register_model re-run with calibration_2026.json")

from mlflow import MlflowClient
import mlflow
mlflow.set_registry_uri("databricks-uc")
client = MlflowClient()
v25 = client.get_model_version_by_alias(MODEL_NAME, "cal_2025").version
v26 = client.get_model_version_by_alias(MODEL_NAME, "cal_2026").version
print(f"Model versions: @cal_2025 → v{v25}   @cal_2026 → v{v26} (also @champion)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Score the same inputs with the new version

# COMMAND ----------

result = dbutils.notebook.run("03_score", 600, {
    "catalog_name": catalog,
    "schema_name": schema,
    "sfm_volume_name": volume,
    "model_alias": "cal_2026",
})
print("✓ scored all entities with @cal_2026 (parity vs the oracle re-checked inside)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. The impact table — what did the calibration update cost?

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TABLE {fqn}.sfm_impact AS
SELECT
    a.entity_id,
    i.entity_name,
    i.line_of_business,
    a.scr  AS scr_2025,
    b.scr  AS scr_2026,
    ROUND(b.scr - a.scr, 4)                    AS scr_delta,
    ROUND((b.scr - a.scr) / a.scr, 4)          AS scr_delta_pct,
    ROUND(b.scr_nl  - a.scr_nl, 4)             AS delta_nl,
    ROUND(b.scr_mkt - a.scr_mkt, 4)            AS delta_mkt,
    ROUND(b.scr_cat - a.scr_cat, 4)            AS delta_cat,
    ROUND(b.op_risk - a.op_risk, 4)            AS delta_op,
    a.model_version AS model_version_2025,
    b.model_version AS model_version_2026
FROM      {fqn}.sfm_results a
JOIN      {fqn}.sfm_results b USING (entity_id)
JOIN      {fqn}.sfm_inputs  i USING (entity_id)
WHERE a.calibration_year = 2025 AND b.calibration_year = 2026
""")
spark.sql(f"""
COMMENT ON TABLE {fqn}.sfm_impact IS
'Capital impact of the 2026 calibration update: sfm_scr_model @cal_2026 vs '
'@cal_2025 on identical inputs, per entity and per risk module (£m). Both sides '
'are registered model versions, so the comparison is permanently reproducible. '
'Synthetic data.'
""")
print(f"✓ {fqn}.sfm_impact")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The headline — group impact and the biggest movers

# COMMAND ----------

display(spark.sql(f"""
    SELECT ROUND(SUM(scr_2025), 1) AS group_scr_2025,
           ROUND(SUM(scr_2026), 1) AS group_scr_2026,
           ROUND(SUM(scr_delta), 1) AS group_delta,
           ROUND(SUM(scr_delta) / SUM(scr_2025), 4) AS group_delta_pct,
           ROUND(SUM(delta_nl), 1)  AS from_nl,
           ROUND(SUM(delta_mkt), 1) AS from_mkt,
           ROUND(SUM(delta_cat), 1) AS from_cat,
           ROUND(SUM(delta_op), 1)  AS from_op
    FROM {fqn}.sfm_impact
"""))

display(spark.sql(f"""
    SELECT entity_id, line_of_business,
           ROUND(scr_2025, 1) AS scr_2025, ROUND(scr_2026, 1) AS scr_2026,
           ROUND(scr_delta, 1) AS delta, scr_delta_pct
    FROM {fqn}.sfm_impact ORDER BY scr_delta DESC LIMIT 10
"""))

# COMMAND ----------

print("Recalibration complete. Model versions v1/@cal_2025 and v2/@cal_2026 both live —")
print("any past result is reproducible by loading its version. Next: 99_validate.py")
