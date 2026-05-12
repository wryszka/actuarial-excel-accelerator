# Databricks notebook source
# MAGIC %md
# MAGIC # Shared UC Setup — Actuarial Excel Accelerator
# MAGIC
# MAGIC One catalog, one schema, demo-specific volumes. Idempotent — safe
# MAGIC to re-run. The schema is shared across all three demos in this
# MAGIC accelerator (RFR ETL today, SCR + chain-ladder later).
# MAGIC
# MAGIC Wired into `setup_demo` in `resources/jobs.yml`. Also runnable
# MAGIC standalone — open in the workspace and Run All.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_serverless_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("rfr_volume_name", "rfr_landing")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
rfr_volume = dbutils.widgets.get("rfr_volume_name")

fqn = f"{catalog}.{schema}"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Schema

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {fqn}")
spark.sql(f"""
    COMMENT ON SCHEMA {fqn} IS
    'Actuarial Excel Accelerator — shared schema for three Excel-migration demos: '
    '(1) EIOPA RFR ingestion, (2) Solvency II SCR Standard Formula, '
    '(3) chain-ladder reserving. Demo 2 and 3 consume the rfr_curves gold table '
    'from demo 1. Synthetic data throughout.'
""")
print(f"✓ schema {fqn}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Grants — let anyone in the workspace browse the demo

# COMMAND ----------

# USAGE on catalog + schema, plus BROWSE on the catalog so the schema
# shows up in Catalog Explorer. Demo grants — replace with your own
# governance model in production.
try:
    spark.sql(f"GRANT USE CATALOG ON CATALOG {catalog} TO `account users`")
    spark.sql(f"GRANT USE SCHEMA ON SCHEMA {fqn} TO `account users`")
    spark.sql(f"GRANT SELECT ON SCHEMA {fqn} TO `account users`")
    print(f"✓ account users granted USE + SELECT on {fqn}")
except Exception as e:
    print(f"[skip] grants: {str(e)[:120]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Demo 1: rfr_landing Volume
# MAGIC
# MAGIC Where monthly EIOPA `.xlsx` files land before bronze ingestion.

# COMMAND ----------

spark.sql(f"CREATE VOLUME IF NOT EXISTS {fqn}.{rfr_volume}")
spark.sql(f"""
    COMMENT ON VOLUME {fqn}.{rfr_volume} IS
    'Landing zone for monthly EIOPA risk-free-rate term-structure files. '
    'Demo 1 bronze ingestion (01_bronze_autoloader.py) reads from here.'
""")
print(f"✓ volume {fqn}.{rfr_volume}")

# COMMAND ----------

print("Setup complete.")
print(f"  Catalog: {catalog}")
print(f"  Schema:  {schema}")
print(f"  Volume:  /Volumes/{catalog}/{schema}/{rfr_volume}")
