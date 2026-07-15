# Databricks notebook source
# MAGIC %md
# MAGIC # Demo 0 · Reconciliation — "it is the same thing"
# MAGIC
# MAGIC The trust close. Two computations of the same month:
# MAGIC
# MAGIC 1. **The legacy VBA output** — the `*_STANDARDISED.csv` the macro
# MAGIC    exports (upload yours to the volume's `reference/` folder, or leave
# MAGIC    the default: the committed expected output, byte-equivalent to what
# MAGIC    the macro produces).
# MAGIC 2. **`brd_silver_claims`** — the converted notebook's result, filtered
# MAGIC    to the same source file.
# MAGIC
# MAGIC Counts and £ totals must match **to the penny**. Then the kicker: the
# MAGIC quarantine table — rows that are in neither the VBA output *nor* lost,
# MAGIC because Databricks kept what Excel silently threw away.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("source_file", "bordereau_2025_11.csv")
dbutils.widgets.text("vba_output_path", "")  # blank = committed expected output

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
source_file = dbutils.widgets.get("source_file")
vba_output_path = dbutils.widgets.get("vba_output_path")
fqn = f"{catalog}.{schema}"

from pyspark.sql import functions as F
import os

if not vba_output_path:
    nb_path = (dbutils.notebook.entry_point.getDbutils().notebook()
               .getContext().notebookPath().get())
    month_tag = source_file.replace("bordereau_", "").replace(".csv", "")
    vba_output_path = ("/Workspace" + os.path.dirname(nb_path)
                       + f"/data/expected_output_{month_tag}.csv")
print(f"Comparing silver[{source_file}]  ⇄  {vba_output_path}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The VBA side

# COMMAND ----------

import pandas as pd

vba_pd = pd.read_csv(vba_output_path)
vba = {
    "rows": len(vba_pd),
    "paid": round(float(vba_pd.paid_gbp.sum()), 2),
    "outstanding": round(float(vba_pd.outstanding_gbp.sum()), 2),
    "incurred": round(float(vba_pd.incurred_gbp.sum()), 2),
}
print("VBA output:       ", vba)

# COMMAND ----------

# MAGIC %md
# MAGIC ## The Databricks side

# COMMAND ----------

silver = (spark.table(f"{fqn}.brd_silver_claims")
          .filter(F.col("_source_file").endswith(source_file)))
r = silver.agg(
    F.count("*").alias("rows"),
    F.round(F.sum("paid_gbp"), 2).alias("paid"),
    F.round(F.sum("outstanding_gbp"), 2).alias("outstanding"),
    F.round(F.sum("incurred_gbp"), 2).alias("incurred"),
).first()
dbx = {k: (int(r[k]) if k == "rows" else float(r[k])) for k in
       ["rows", "paid", "outstanding", "incurred"]}
print("Databricks silver:", dbx)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Tie-out

# COMMAND ----------

rows, ok = [], True
for k in ["rows", "paid", "outstanding", "incurred"]:
    delta = abs(float(vba[k]) - float(dbx[k]))
    passed = delta <= 0.01
    ok = ok and passed
    rows.append((k, float(vba[k]), float(dbx[k]), float(round(delta, 4)),
                 "✓" if passed else "✗ MISMATCH"))

display(spark.createDataFrame(rows, ["metric", "vba_excel", "databricks", "abs_delta", "status"]))
assert ok, "Reconciliation FAILED — silver does not match the VBA output"
print("✓ RECONCILIATION PASS — same numbers to the penny")

# COMMAND ----------

# MAGIC %md
# MAGIC ## …and the rows Excel has been throwing away

# COMMAND ----------

quar = (spark.table(f"{fqn}.brd_quarantine")
        .filter(F.col("_source_file").endswith(source_file)))
n = quar.count()
inc = quar.agg(F.round(F.sum("incurred_gbp"), 2)).first()[0]
print(f"{n} claims (£{inc:,.2f} incurred) had unusable loss dates.")
print("The VBA skipped them silently. Databricks kept them — visible, fixable:")
display(quar.select("claim_ref", "raw_loss_date", "status", "region",
                    "paid_gbp", "outstanding_gbp", "incurred_gbp").limit(20))
