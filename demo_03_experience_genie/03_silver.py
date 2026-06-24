# Databricks notebook source
# MAGIC %md
# MAGIC # Demo 3 · Step 3 (Rebuild) — Silver
# MAGIC
# MAGIC **Recipe step: Rebuild.** This is the VLOOKUP-and-helper-columns tab of the
# MAGIC Excel workbook, done properly:
# MAGIC
# MAGIC - **The VLOOKUP** (`policy_segment` → line of business / region / channel)
# MAGIC   becomes a governed join to `exp_bronze_segment_map`.
# MAGIC - **The helper columns** (accident year, reporting lag, "is this a payment
# MAGIC   or a reserve move?", paid vs outstanding split) become typed, documented
# MAGIC   columns — not formulas hidden three columns off-screen.
# MAGIC - **Data-quality checks** that Excel can't express (every transaction must
# MAGIC   map to a known segment; dates must parse) are asserted explicitly.
# MAGIC
# MAGIC Outputs: `exp_silver_claims` (one row per transaction, enriched) and
# MAGIC `exp_silver_premium` (earned premium by segment × month, enriched).

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_serverless_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
fqn = f"{catalog}.{schema}"

from pyspark.sql import functions as F

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver — claims transactions, enriched

# COMMAND ----------

seg = spark.table(f"{fqn}.exp_bronze_segment_map")
txn = spark.table(f"{fqn}.exp_bronze_claims_txn")

silver_claims = (
    txn
    .withColumn("accident_date", F.to_date("accident_date"))
    .withColumn("report_date", F.to_date("report_date"))
    .withColumn("transaction_date", F.to_date("transaction_date"))
    .join(F.broadcast(seg.select("policy_segment", "line_of_business", "region", "channel")),
          on="policy_segment", how="left")
    .withColumn("accident_year", F.year("accident_date"))
    .withColumn("accident_month", F.date_trunc("month", F.col("accident_date")).cast("date"))
    .withColumn("report_lag_days", F.datediff("report_date", "accident_date"))
    # paid = payments net of recoveries; outstanding move = reserve changes
    .withColumn("paid_amount",
                F.when(F.col("transaction_type").isin("PAYMENT", "RECOVERY"),
                       F.col("transaction_amount")).otherwise(F.lit(0.0)))
    .withColumn("reserve_change",
                F.when(F.col("transaction_type") == "RESERVE_CHANGE",
                       F.col("transaction_amount")).otherwise(F.lit(0.0)))
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Data-quality gate — fail loudly, the way `=IFERROR(…,"")` never does

# COMMAND ----------

unmapped = silver_claims.filter(F.col("line_of_business").isNull()).count()
bad_dates = silver_claims.filter(F.col("accident_date").isNull()
                                 | F.col("transaction_date").isNull()).count()
print(f"unmapped segments: {unmapped}   unparseable dates: {bad_dates}")
assert unmapped == 0, "Some transactions did not map to a segment — check segment_map.csv"
assert bad_dates == 0, "Some dates failed to parse"

(silver_claims.write.mode("overwrite").option("overwriteSchema", "true")
 .saveAsTable(f"{fqn}.exp_silver_claims"))
print(f"✓ {fqn}.exp_silver_claims  {spark.table(f'{fqn}.exp_silver_claims').count():,} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver — premium, enriched

# COMMAND ----------

prem = spark.table(f"{fqn}.exp_bronze_premium")
silver_premium = (
    prem
    .withColumn("earned_month", F.to_date("earned_month"))
    .join(F.broadcast(seg.select("policy_segment", "line_of_business", "region", "channel")),
          on="policy_segment", how="left")
    .withColumn("accident_year", F.year("earned_month"))
)
assert silver_premium.filter(F.col("line_of_business").isNull()).count() == 0

(silver_premium.write.mode("overwrite").option("overwriteSchema", "true")
 .saveAsTable(f"{fqn}.exp_silver_premium"))
print(f"✓ {fqn}.exp_silver_premium  {spark.table(f'{fqn}.exp_silver_premium').count():,} rows")

# COMMAND ----------

print("Silver complete. Next: 04_gold.py")
