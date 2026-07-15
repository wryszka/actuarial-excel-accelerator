# Databricks notebook source
# MAGIC %md
# MAGIC # Demo 3 · Step 0 — Setup
# MAGIC
# MAGIC **Experience & Loss-Ratio Monitoring** — the third demo in the Actuarial
# MAGIC Excel Accelerator, and the one that shows what **AI/BI Dashboards + Genie**
# MAGIC replace: the monthly *management-information pack* an actuary maintains as
# MAGIC a stack of Excel PivotTables.
# MAGIC
# MAGIC This notebook is idempotent. It ensures the shared schema exists and
# MAGIC creates the `exp_landing` Volume where this demo's source CSVs land.
# MAGIC Everything in this track is prefixed **`exp_`** so it's instantly
# MAGIC identifiable next to the `rfr_*` (demo 1) and `scr_*` (demo 2A) assets in
# MAGIC the same schema.
# MAGIC
# MAGIC > **About this demo.** All data is synthetic. The book of business, claims
# MAGIC > and premium are fabricated to resemble a UK general-insurance portfolio;
# MAGIC > no customer data is used. See `README.md`.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("exp_volume_name", "exp_landing")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
volume = dbutils.widgets.get("exp_volume_name")
fqn = f"{catalog}.{schema}"

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {fqn}")
print(f"✓ schema {fqn}")

spark.sql(f"CREATE VOLUME IF NOT EXISTS {fqn}.{volume}")
spark.sql(f"""
    COMMENT ON VOLUME {fqn}.{volume} IS
    'Demo 3 (Experience Monitoring) landing zone. The monthly claims-transaction '
    'and premium CSV extracts an actuary would export from policy/claims systems '
    'land here; 02_bronze.py ingests from this Volume.'
""")
print(f"✓ volume /Volumes/{catalog}/{schema}/{volume}")

# COMMAND ----------

# Demo grants so anyone in the workspace can browse the result. Replace with
# your own governance model in production.
try:
    spark.sql(f"GRANT USE CATALOG ON CATALOG {catalog} TO `account users`")
    spark.sql(f"GRANT USE SCHEMA ON SCHEMA {fqn} TO `account users`")
    spark.sql(f"GRANT SELECT ON SCHEMA {fqn} TO `account users`")
    spark.sql(f"GRANT READ VOLUME ON VOLUME {fqn}.{volume} TO `account users`")
    print("✓ grants applied to `account users`")
except Exception as e:
    print(f"[skip] grants: {str(e)[:140]}")

# COMMAND ----------

print("Setup complete.")
print(f"  Catalog: {catalog}")
print(f"  Schema:  {schema}")
print(f"  Volume:  /Volumes/{catalog}/{schema}/{volume}")
print("Next: 01_generate_data.py")
