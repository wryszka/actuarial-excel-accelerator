# Databricks notebook source
# MAGIC %md
# MAGIC # Demo 0 · Setup — volume + reset switch
# MAGIC
# MAGIC **The VBA nobody understands** — demo 0 of the Actuarial Excel
# MAGIC Accelerator: a monthly TPA claims bordereau processed by a legacy Excel
# MAGIC macro, migrated to Databricks by asking Genie Code to *explain* the VBA
# MAGIC and then *convert* it. All assets are prefixed **`brd_`** in the shared
# MAGIC schema.
# MAGIC
# MAGIC Idempotent. Creates the `brd_landing` volume with an `incoming/` folder
# MAGIC (watched by the stage-2 file-arrival job) and a `reference/` folder (for
# MAGIC the VBA-produced output used in reconciliation).
# MAGIC
# MAGIC Set the `reset` widget to `yes` between recording takes: drops the
# MAGIC `brd_` tables and clears `incoming/` so the demo starts clean.
# MAGIC
# MAGIC > **About this demo.** All data is synthetic; no customer data is used.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("brd_volume_name", "brd_landing")
dbutils.widgets.dropdown("reset", "no", ["no", "yes"])

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
volume = dbutils.widgets.get("brd_volume_name")
fqn = f"{catalog}.{schema}"
vol_path = f"/Volumes/{catalog}/{schema}/{volume}"

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {fqn}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {fqn}.{volume}")
spark.sql(f"""
    COMMENT ON VOLUME {fqn}.{volume} IS
    'Demo 0 (VBA bordereau ETL) landing zone. incoming/ receives the monthly '
    'TPA bordereau CSVs and is watched by the file-arrival job; reference/ '
    'holds the legacy VBA output used for reconciliation.'
""")
dbutils.fs.mkdirs(f"{vol_path}/incoming")
dbutils.fs.mkdirs(f"{vol_path}/reference")
print(f"✓ volume {vol_path} (incoming/, reference/)")

try:
    spark.sql(f"GRANT READ VOLUME ON VOLUME {fqn}.{volume} TO `account users`")
    print("✓ volume grant applied")
except Exception as e:
    print(f"[skip] grants: {str(e)[:120]}")

# COMMAND ----------

if dbutils.widgets.get("reset") == "yes":
    for t in ["brd_bronze_claims", "brd_silver_claims", "brd_quarantine"]:
        spark.sql(f"DROP TABLE IF EXISTS {fqn}.{t}")
        print(f"✓ dropped {fqn}.{t}")
    for f in dbutils.fs.ls(f"{vol_path}/incoming"):
        dbutils.fs.rm(f.path)
        print(f"✓ removed {f.path}")
    print("Reset complete — clean slate for the next take.")
else:
    print("No reset requested (set reset=yes between recording takes).")

# COMMAND ----------

print("Setup complete. Next: upload a bordereau CSV to "
      f"{vol_path}/incoming and run 01_bordereau_etl.")
