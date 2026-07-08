# Databricks notebook source
# MAGIC %md
# MAGIC # Use Case 2 · Setup — volume + source files
# MAGIC
# MAGIC **From spreadsheet model to governed model.** A simple Standard-Formula
# MAGIC capital model lives in an Excel workbook — one file per entity, a
# MAGIC typed-in calibration block, no version history. This use case
# MAGIC re-implements it as a **versioned model in Unity Catalog** and runs it
# MAGIC across the whole group in one pass.
# MAGIC
# MAGIC All assets are prefixed **`sfm_`** in the shared schema. This notebook
# MAGIC creates the `sfm_assets` volume and copies the source files into it so
# MAGIC everything a user needs — the workbook, the inputs, both calibration
# MAGIC files — is in one clearly-described place:
# MAGIC
# MAGIC | File in `sfm_assets` | What it is |
# MAGIC |---|---|
# MAGIC | `SF_Model.xlsx` | the "before": one-entity Standard Formula workbook (live formulas) |
# MAGIC | `sf_inputs.csv` | balance-sheet inputs for 100 entities (ENT-001 = the workbook's entity) |
# MAGIC | `calibration_2025.json` | the 2025 parameter set |
# MAGIC | `calibration_2026.json` | the 2026 update (sigmas, IR shock, cat factor, one correlation) |
# MAGIC | `expected_entity_001.json` | ENT-001's expected SCR under both calibrations (parity anchor) |
# MAGIC
# MAGIC Idempotent. Set `reset = yes` to drop the `sfm_` tables for a clean re-run
# MAGIC (model versions in Unity Catalog are kept — that history is the point).
# MAGIC
# MAGIC > **About this demo.** All data is synthetic; no customer data is used.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_serverless_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("sfm_volume_name", "sfm_assets")
dbutils.widgets.dropdown("reset", "no", ["no", "yes"])

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
volume = dbutils.widgets.get("sfm_volume_name")
fqn = f"{catalog}.{schema}"
vol_path = f"/Volumes/{catalog}/{schema}/{volume}"

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {fqn}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {fqn}.{volume}")
spark.sql(f"""
    COMMENT ON VOLUME {fqn}.{volume} IS
    'Use Case 2 (Standard Formula model → Unity Catalog) source files: the legacy '
    'Excel workbook SF_Model.xlsx, sf_inputs.csv (100 entities), the 2025/2026 '
    'calibration JSONs, and the ENT-001 parity oracle. Synthetic data.'
""")
print(f"✓ volume {vol_path}")

try:
    spark.sql(f"GRANT READ VOLUME ON VOLUME {fqn}.{volume} TO `account users`")
    print("✓ volume grant applied")
except Exception as e:
    print(f"[skip] grants: {str(e)[:120]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Copy the source files into the volume
# MAGIC
# MAGIC The files ship with this folder (deployed to the shared workspace path);
# MAGIC copying them into the volume makes them downloadable from Catalog
# MAGIC Explorer and readable by any compute.

# COMMAND ----------

import os
import shutil

nb_dir = "/Workspace" + os.path.dirname(
    dbutils.notebook.entry_point.getDbutils().notebook()
    .getContext().notebookPath().get())

FILES = [
    ("excel/SF_Model.xlsx", "SF_Model.xlsx"),
    ("data/sf_inputs.csv", "sf_inputs.csv"),
    ("data/calibration_2025.json", "calibration_2025.json"),
    ("data/calibration_2026.json", "calibration_2026.json"),
    ("data/expected_entity_001.json", "expected_entity_001.json"),
]
for src_rel, dst_name in FILES:
    src = f"{nb_dir}/{src_rel}"
    dst = f"{vol_path}/{dst_name}"
    shutil.copyfile(src, dst)
    print(f"✓ {dst_name:28s} → {dst}")

# COMMAND ----------

if dbutils.widgets.get("reset") == "yes":
    for t in ["sfm_inputs", "sfm_results", "sfm_impact"]:
        spark.sql(f"DROP TABLE IF EXISTS {fqn}.{t}")
        print(f"✓ dropped {fqn}.{t}")
    print("Reset complete (registered model versions kept — that history is the point).")
else:
    print("No reset requested.")

# COMMAND ----------

print("Setup complete. Next: 01_inputs.py")
