# Databricks notebook source
# MAGIC %md
# MAGIC # Reset dispatcher — bring any use case back to its original state
# MAGIC
# MAGIC Backs the **Reset** buttons in the Excel Accelerator app (and works
# MAGIC standalone). Pick a scenario and this notebook re-runs the right chain:
# MAGIC
# MAGIC | scenario | what happens | takes |
# MAGIC |---|---|---|
# MAGIC | `uc1` | demo 0: drop `brd_` tables, clear `incoming/` — clean slate for the bordereau demo | ~1 min |
# MAGIC | `uc2` | use case 2: drop `sfm_` tables, re-copy volume files (model versions kept by design) | ~1 min |
# MAGIC | `uc3` | use case 3: full world regen (data → bronze → silver → gold → listing), Genie space back to the single-table starter, dashboards re-published | ~15 min |
# MAGIC | `uc4` | use case 4: rebuild the Designer source tables, drop the canvas output | ~2 min |
# MAGIC | `all` | all four, in order | ~20 min |
# MAGIC
# MAGIC Everything it calls is idempotent.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_serverless_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("warehouse_id", "a3b61648ea4809e3")
dbutils.widgets.dropdown("scenario", "all", ["uc1", "uc2", "uc3", "uc4", "all"])

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
warehouse_id = dbutils.widgets.get("warehouse_id")
scenario = dbutils.widgets.get("scenario")

BASE = {"catalog_name": catalog, "schema_name": schema}
TIMEOUT = 3600


def run(path, extra=None):
    params = {**BASE, **(extra or {})}
    print(f"→ {path} {params}")
    dbutils.notebook.run(path, TIMEOUT, params)
    print(f"✓ {path}")

# COMMAND ----------


def reset_uc1():
    run("../demo_00_vba_csv_etl/00_setup",
        {"brd_volume_name": "brd_landing", "reset": "yes"})


def reset_uc2():
    run("../demo_02b_sf_model_uc/00_setup",
        {"sfm_volume_name": "sfm_assets", "reset": "yes"})


def reset_uc3():
    v = {"exp_volume_name": "exp_landing"}
    run("../demo_03_experience_genie/01_generate_data", v)
    run("../demo_03_experience_genie/02_bronze", v)
    run("../demo_03_experience_genie/03_silver")
    run("../demo_03_experience_genie/04_gold")
    run("../demo_03_experience_genie/08_claims_listing", v)
    run("../demo_03_experience_genie/09_genie_starter", {"mode": "reset_starter"})
    run("../demo_03_experience_genie/06_genie_space")
    run("../demo_03_experience_genie/07_dashboard", {"warehouse_id": warehouse_id})
    run("../demo_03_experience_genie/10_dashboard_starter", {"warehouse_id": warehouse_id})


def reset_uc4():
    run("../demo_04_lakeflow_designer/01_sources_check",
        {"exp_volume_name": "exp_landing", "drop_output": "yes"})


ACTIONS = {"uc1": [reset_uc1], "uc2": [reset_uc2], "uc3": [reset_uc3],
           "uc4": [reset_uc4],
           "all": [reset_uc1, reset_uc2, reset_uc3, reset_uc4]}

for fn in ACTIONS[scenario]:
    fn()

print(f"\n✓ RESET COMPLETE — scenario: {scenario}")
