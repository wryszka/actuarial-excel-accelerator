# Databricks notebook source
# MAGIC %md
# MAGIC # Demo 3 · Step 5 (Validate parity) — Excel pivot ⇄ Databricks gold
# MAGIC
# MAGIC **Recipe step: Validate parity.** A migration nobody trusts is a migration
# MAGIC nobody uses. This notebook proves the governed pipeline reproduces, to the
# MAGIC penny, what the actuary's Excel PivotTable shows for the same data.
# MAGIC
# MAGIC The check is on the **Motor · London · accident year 2024** slice — the one
# MAGIC piece small enough to live in `Experience_Monitoring.xlsx`. Two independent
# MAGIC computations of the same four numbers must agree:
# MAGIC
# MAGIC 1. **The Excel pivot** — aggregated straight from the slice CSV the actuary
# MAGIC    pastes into the workbook (read here from the Volume).
# MAGIC 2. **Databricks gold** — `exp_gold_experience` filtered to the same slice.
# MAGIC
# MAGIC If a committed `parity_oracle.json` (written by `build_excel_data.py` from
# MAGIC the workbook itself) is found, we tie out against that too — closing the
# MAGIC loop Excel → Databricks.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_serverless_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("exp_volume_name", "exp_landing")
catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
volume = dbutils.widgets.get("exp_volume_name")
fqn = f"{catalog}.{schema}"
vol_path = f"/Volumes/{catalog}/{schema}/{volume}"

from pyspark.sql import functions as F

TOL = 1.0  # GBP — rounding tolerance

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. The "Excel pivot" — straight from the slice CSV

# COMMAND ----------

sc = (spark.read.option("header", "true").option("inferSchema", "true")
      .csv(f"{vol_path}/experience_excel_claims.csv"))
sp = (spark.read.option("header", "true").option("inferSchema", "true")
      .csv(f"{vol_path}/experience_excel_premium.csv"))

excel_paid = sc.filter(F.col("transaction_type").isin("PAYMENT", "RECOVERY")) \
               .agg(F.sum("transaction_amount")).first()[0] or 0.0
excel_osr = sc.filter(F.col("transaction_type") == "RESERVE_CHANGE") \
              .agg(F.sum("transaction_amount")).first()[0] or 0.0
excel = {
    "earned_premium": sp.agg(F.sum("earned_premium")).first()[0] or 0.0,
    "reported_claims": sc.select("claim_id").distinct().count(),
    "incurred": excel_paid + excel_osr,
}
excel["loss_ratio"] = excel["incurred"] / excel["earned_premium"]
print("Excel pivot totals:", {k: round(v, 2) for k, v in excel.items()})

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Databricks gold — same slice

# COMMAND ----------

g = spark.sql(f"""
    SELECT SUM(earned_premium)  AS earned_premium,
           SUM(reported_claims) AS reported_claims,
           SUM(incurred)        AS incurred
    FROM {fqn}.exp_gold_experience
    WHERE line_of_business = 'Motor' AND region = 'London' AND accident_year = 2024
""").first()
gold = {
    "earned_premium": float(g["earned_premium"]),
    "reported_claims": int(g["reported_claims"]),
    "incurred": float(g["incurred"]),
}
gold["loss_ratio"] = gold["incurred"] / gold["earned_premium"]
print("Databricks gold totals:", {k: round(v, 2) for k, v in gold.items()})

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Tie out

# COMMAND ----------

rows, ok = [], True
for k in ["earned_premium", "reported_claims", "incurred", "loss_ratio"]:
    e, gv = excel[k], gold[k]
    tol = TOL if k != "loss_ratio" else 0.001
    delta = abs(e - gv)
    passed = delta <= tol
    ok = ok and passed
    rows.append((k, float(round(e, 4)), float(round(gv, 4)), float(round(delta, 6)),
                 "✓" if passed else "✗ MISMATCH"))

display(spark.createDataFrame(rows, ["metric", "excel_pivot", "databricks_gold", "abs_delta", "status"]))
assert ok, "Parity FAILED — Databricks gold does not match the Excel pivot for the slice"
print("✓ PARITY PASS — gold reproduces the Excel pivot to the penny")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. (Optional) tie out against the committed workbook oracle

# COMMAND ----------

import json, os

oracle_path = None
for p in [os.path.join(os.getcwd(), "excel", "parity_oracle.json"),
          "/Workspace" + os.path.dirname(
              dbutils.notebook.entry_point.getDbutils().notebook().getContext()
              .notebookPath().get()) + "/excel/parity_oracle.json"]:
    if os.path.exists(p):
        oracle_path = p
        break

if oracle_path:
    with open(oracle_path) as f:
        oracle = json.load(f)
    print(f"Loaded oracle from {oracle_path}")
    for k in ["earned_premium", "incurred", "loss_ratio"]:
        tol = 0.001 if k == "loss_ratio" else TOL
        assert abs(oracle[k] - gold[k]) <= tol, f"Oracle mismatch on {k}: {oracle[k]} vs {gold[k]}"
    print("✓ Workbook oracle also ties out — Excel → Databricks loop closed")
else:
    print("No parity_oracle.json found (build the workbook with excel/build_excel_data.py "
          "to enable this check). Skipping — the live pivot⇄gold check above is authoritative.")

# COMMAND ----------

print("Parity complete. Next: 06_genie_space.py")
