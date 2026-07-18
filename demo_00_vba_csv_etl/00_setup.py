# Databricks notebook source
# MAGIC %md
# MAGIC # Use Case 1 · Setup — put the demo files in place
# MAGIC
# MAGIC **The story:** every month an actuary gets a claims listing as a CSV,
# MAGIC runs an old Excel macro that cleans it up, and sends the result on. This
# MAGIC use case moves that macro to Databricks — same result, in seconds, run
# MAGIC on a schedule.
# MAGIC
# MAGIC This notebook just puts things in place. It:
# MAGIC
# MAGIC 1. creates a **volume** (a folder in Databricks) called `brd_landing`,
# MAGIC 2. copies the raw claims CSV into it, and
# MAGIC 3. loads that CSV into a ready-made table **`brd_claims_raw`** — so in
# MAGIC    the demo you can either upload your own CSV *or* just point at this
# MAGIC    table.
# MAGIC
# MAGIC Everything is named with a `brd_` prefix so it's easy to find. Run it
# MAGIC once (click **Run all** at the top). Set `reset = yes` to start clean.
# MAGIC
# MAGIC > All data is synthetic; no customer data is used.

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
    'Use Case 1 landing folder: the monthly raw claims CSV lands here. '
    'Synthetic data.'
""")
print(f"✓ volume ready: {vol_path}")

try:
    spark.sql(f"GRANT READ VOLUME ON VOLUME {fqn}.{volume} TO `account users`")
except Exception as e:
    print(f"[skip] grant: {str(e)[:120]}")

# COMMAND ----------

if dbutils.widgets.get("reset") == "yes":
    for t in ["brd_claims_raw", "brd_claims_clean", "brd_quarantine", "brd_excel_output"]:
        spark.sql(f"DROP TABLE IF EXISTS {fqn}.{t}")
        print(f"✓ dropped {fqn}.{t}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Copy the raw CSV into the volume
# MAGIC
# MAGIC The file ships next to this notebook; we copy it into the volume so it
# MAGIC behaves exactly like a file you'd upload yourself.

# COMMAND ----------

import os
import shutil

nb_dir = "/Workspace" + os.path.dirname(
    dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get())
src = f"{nb_dir}/data/claims_raw.csv"
dst = f"{vol_path}/claims_raw.csv"
shutil.copyfile(src, dst)
print(f"✓ copied claims_raw.csv → {dst}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load it into a ready-made table
# MAGIC
# MAGIC So the demo can skip the upload and just point at `brd_claims_raw`.
# MAGIC (Read as text — the raw file is deliberately messy; the notebook cleans
# MAGIC it, exactly like the macro does.)

# COMMAND ----------

raw = (spark.read.format("csv").option("header", "true")
       .option("inferSchema", "false")
       .load(dst))
raw.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{fqn}.brd_claims_raw")
spark.sql(f"""
    COMMENT ON TABLE {fqn}.brd_claims_raw IS
    'Raw monthly claims bordereau, exactly as received from the administrator '
    '(messy: mixed date formats, currency symbols, duplicate rows). The '
    'notebook 01 cleans this. Synthetic data.'
""")
n = spark.table(f"{fqn}.brd_claims_raw").count()
print(f"✓ {fqn}.brd_claims_raw — {n:,} rows")

# COMMAND ----------

print("Setup complete.")
print(f"  Raw file:  {dst}")
print(f"  Raw table: {fqn}.brd_claims_raw")
print("Next: open 01_clean_claims and click Run all.")
