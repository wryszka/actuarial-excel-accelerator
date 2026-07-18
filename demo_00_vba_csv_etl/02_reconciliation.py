# Databricks notebook source
# MAGIC %md
# MAGIC # Use Case 1 · Reconciliation — prove it's the same
# MAGIC
# MAGIC The trust step. We load the **Excel macro's output** back into Databricks
# MAGIC as a table, then compare it against the **notebook's output** — row
# MAGIC count and every total, to the penny. Same numbers, produced two ways.
# MAGIC
# MAGIC By default this uses the committed `claims_clean_excel_output.csv` (what
# MAGIC the macro produces, generated identically). To use *your own* macro
# MAGIC output: upload its `_CLEAN.csv` to the volume and set `excel_file_name`.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("brd_volume_name", "brd_landing")
dbutils.widgets.text("excel_file_name", "")   # blank = committed macro output

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
volume = dbutils.widgets.get("brd_volume_name")
excel_file = dbutils.widgets.get("excel_file_name")
fqn = f"{catalog}.{schema}"
vol_path = f"/Volumes/{catalog}/{schema}/{volume}"

from pyspark.sql import functions as F

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load the Excel output as a table

# COMMAND ----------

import os, shutil

if excel_file:
    excel_path = f"{vol_path}/{excel_file}"
else:
    nb_dir = "/Workspace" + os.path.dirname(
        dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get())
    local = f"{nb_dir}/data/claims_clean_excel_output.csv"
    excel_path = f"{vol_path}/claims_clean_excel_output.csv"
    shutil.copyfile(local, excel_path)

(spark.read.format("csv").option("header", "true").option("inferSchema", "true")
    .load(excel_path)
    .write.mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(f"{fqn}.brd_excel_output"))
print(f"✓ loaded Excel output → {fqn}.brd_excel_output")
display(spark.table(f"{fqn}.brd_excel_output").limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Compare the totals — Excel vs Databricks

# COMMAND ----------

def totals(table):
    r = spark.table(f"{fqn}.{table}").agg(
        F.count("*").alias("rows"),
        F.round(F.sum("paid_gbp"), 2).alias("paid"),
        F.round(F.sum("outstanding_gbp"), 2).alias("outstanding"),
        F.round(F.sum("incurred_gbp"), 2).alias("incurred"),
        F.sum(F.when(F.col("large_loss_flag") == "Y", 1).otherwise(0)).alias("large_losses"),
    ).first()
    return {k: (int(r[k]) if k in ("rows", "large_losses") else float(r[k]))
            for k in ["rows", "paid", "outstanding", "incurred", "large_losses"]}

excel = totals("brd_excel_output")
dbx = totals("brd_claims_clean")
print("Excel :", excel)
print("Databx:", dbx)

# COMMAND ----------

rows, ok = [], True
for k in ["rows", "paid", "outstanding", "incurred", "large_losses"]:
    delta = abs(float(excel[k]) - float(dbx[k]))
    tol = 0.01 if k in ("paid", "outstanding", "incurred") else 0
    passed = delta <= tol
    ok = ok and passed
    rows.append((k, float(excel[k]), float(dbx[k]), float(round(delta, 4)),
                 "✓" if passed else "✗ MISMATCH"))

display(spark.createDataFrame(rows, ["metric", "excel", "databricks", "abs_delta", "status"]))
assert ok, "Reconciliation FAILED — the two outputs do not match"
print("✓ RECONCILIATION PASS — Databricks matches the Excel macro to the penny")

# COMMAND ----------

# MAGIC %md
# MAGIC ## …and the rows Excel has been throwing away
# MAGIC The one difference: Databricks kept the unreadable-date rows the macro
# MAGIC silently dropped. They're not lost — they're here, ready to be fixed.

# COMMAND ----------

n = spark.table(f"{fqn}.brd_quarantine").count()
print(f"{n} claims had an unreadable loss date. The macro dropped them silently; here they are:")
display(spark.table(f"{fqn}.brd_quarantine")
        .select("claim_ref", "raw_loss_date", "status", "peril", "incurred_gbp").limit(20))
