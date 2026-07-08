# Databricks notebook source
# MAGIC %md
# MAGIC # Use Case 4 · Parity — the analyst's canvas equals the engineers' pipeline
# MAGIC
# MAGIC The single most reassuring check in this use case: the table the canvas
# MAGIC produced (**`exp_designer_experience`**) is compared, line of business ×
# MAGIC accident year, against the **coded** pipeline's gold table
# MAGIC (`exp_gold_experience`, aggregated to the same grain). Same numbers, two
# MAGIC completely different personas and tools — one governed platform.
# MAGIC
# MAGIC Run this after building the canvas (README.md, act 2). Tolerance covers
# MAGIC per-claim rounding only.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_serverless_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
fqn = f"{catalog}.{schema}"

assert spark.catalog.tableExists(f"{fqn}.exp_designer_experience"), (
    "exp_designer_experience not found — build the canvas first (README.md act 2) "
    "and write its output to this table name.")

# COMMAND ----------

from pyspark.sql import functions as F

designer = (spark.table(f"{fqn}.exp_designer_experience")
            .select("line_of_business", "accident_year",
                    F.col("earned_premium").cast("double").alias("d_premium"),
                    F.col("incurred").cast("double").alias("d_incurred"),
                    F.col("loss_ratio").cast("double").alias("d_lr")))

gold = spark.sql(f"""
    SELECT line_of_business, accident_year,
           SUM(earned_premium) AS g_premium,
           SUM(incurred)       AS g_incurred,
           SUM(incurred) / SUM(earned_premium) AS g_lr
    FROM {fqn}.exp_gold_experience
    GROUP BY line_of_business, accident_year
""")

cmp = designer.join(gold, ["line_of_business", "accident_year"], "full_outer")

missing = cmp.filter(F.col("d_incurred").isNull() | F.col("g_incurred").isNull()).count()
assert missing == 0, f"{missing} LOB×year cells exist on only one side — check the canvas joins"

checked = (cmp
           .withColumn("premium_ok", F.abs(F.col("d_premium") - F.col("g_premium"))
                       <= F.greatest(F.lit(100.0), F.col("g_premium") * 0.0001))
           .withColumn("incurred_ok", F.abs(F.col("d_incurred") - F.col("g_incurred"))
                       <= F.greatest(F.lit(100.0), F.abs(F.col("g_incurred")) * 0.0001))
           .withColumn("lr_ok", F.abs(F.col("d_lr") - F.col("g_lr")) <= 0.001))

display(checked.select("line_of_business", "accident_year",
                       F.round("d_lr", 4).alias("designer_loss_ratio"),
                       F.round("g_lr", 4).alias("pipeline_loss_ratio"),
                       "premium_ok", "incurred_ok", "lr_ok")
        .orderBy("line_of_business", "accident_year"))

bad = checked.filter(~(F.col("premium_ok") & F.col("incurred_ok") & F.col("lr_ok"))).count()
n = checked.count()
assert bad == 0, f"{bad}/{n} cells mismatch — compare the canvas steps against README act 2"
print(f"✓ PARITY PASS — all {n} LOB × accident-year cells match the coded pipeline")
print("\nNow close the loop (README act 3): open the code behind the canvas, the")
print("lineage graph on exp_designer_experience, and the schedule button.")
