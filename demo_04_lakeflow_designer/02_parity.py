# Databricks notebook source
# MAGIC %md
# MAGIC # Use Case 4 · Parity — the analyst's canvas equals the coded pipeline
# MAGIC
# MAGIC The most reassuring check in this use case: the table the Designer
# MAGIC canvas produced (**`dsg_experience`**) is compared, line of business ×
# MAGIC accident year, against **`dsg_benchmark`** — the summary the coded
# MAGIC pipeline produces from the same sources (built in `01_generate_sources`).
# MAGIC Same numbers, two ways of building them, one governed platform.
# MAGIC
# MAGIC Run after building the canvas (README.md) and writing its output to
# MAGIC `dsg_experience`. Tolerance covers per-claim rounding only.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_serverless_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
fqn = f"{catalog}.{schema}"

assert spark.catalog.tableExists(f"{fqn}.dsg_experience"), (
    "dsg_experience not found — build the canvas first (README.md) and write its "
    "output to this table name.")

# COMMAND ----------

from pyspark.sql import functions as F

designer = (spark.table(f"{fqn}.dsg_experience")
            .select("line_of_business", "accident_year",
                    F.col("earned_premium").cast("double").alias("d_premium"),
                    F.col("incurred").cast("double").alias("d_incurred"),
                    F.col("loss_ratio").cast("double").alias("d_lr")))
bench = (spark.table(f"{fqn}.dsg_benchmark")
         .select("line_of_business", "accident_year",
                 F.col("earned_premium").cast("double").alias("b_premium"),
                 F.col("incurred").cast("double").alias("b_incurred"),
                 F.col("loss_ratio").cast("double").alias("b_lr")))

cmp = designer.join(bench, ["line_of_business", "accident_year"], "full_outer")
missing = cmp.filter(F.col("d_incurred").isNull() | F.col("b_incurred").isNull()).count()
assert missing == 0, f"{missing} LOB×year cells exist on only one side — check the canvas joins/aggregation"

checked = (cmp
           .withColumn("premium_ok", F.abs(F.col("d_premium") - F.col("b_premium"))
                       <= F.greatest(F.lit(100.0), F.col("b_premium") * 0.0001))
           .withColumn("incurred_ok", F.abs(F.col("d_incurred") - F.col("b_incurred"))
                       <= F.greatest(F.lit(100.0), F.abs(F.col("b_incurred")) * 0.0001))
           .withColumn("lr_ok", F.abs(F.col("d_lr") - F.col("b_lr")) <= 0.001))

display(checked.select("line_of_business", "accident_year",
                       F.round("d_lr", 4).alias("designer_loss_ratio"),
                       F.round("b_lr", 4).alias("pipeline_loss_ratio"),
                       "premium_ok", "incurred_ok", "lr_ok")
        .orderBy("line_of_business", "accident_year"))

bad = checked.filter(~(F.col("premium_ok") & F.col("incurred_ok") & F.col("lr_ok"))).count()
n = checked.count()
assert bad == 0, f"{bad}/{n} cells mismatch — compare the canvas steps against the README"
print(f"✓ PARITY PASS — all {n} LOB × accident-year cells match the coded pipeline benchmark")
print("\nNow the governance close (README): open the code behind the canvas, the")
print("lineage graph on dsg_experience, and the schedule button.")
