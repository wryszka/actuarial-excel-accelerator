# Databricks notebook source
# MAGIC %md
# MAGIC # Validate — demo 1 smoke test
# MAGIC
# MAGIC One end-to-end check that the full pipeline produced sensible output.
# MAGIC Not a parity test against the source Excel — that would belong in a
# MAGIC production-grade build. For demo purposes this confirms:
# MAGIC
# MAGIC 1.  `rfr_curves` exists and has rows
# MAGIC 2.  Each (effective_date, currency) has 30 maturity points
# MAGIC 3.  All spot rates are inside the expectation range
# MAGIC 4.  The forward-rate column is mostly populated (NULL only at the
# MAGIC     12-month tenor)
# MAGIC
# MAGIC Prints results and `dbutils.notebook.exit("OK"|"FAIL: ...")` so the
# MAGIC job task surfaces the verdict.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_serverless_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
fqn = f"{catalog}.{schema}"

# COMMAND ----------

from pyspark.sql import functions as F

curves = spark.table(f"{fqn}.rfr_curves")
n = curves.count()
print(f"Total rows: {n}")

failures = []
if n == 0:
    failures.append("rfr_curves is empty")

# Check 30 maturities per (date, currency)
shape = (curves
    .groupBy("effective_date", "currency")
    .agg(F.count("*").alias("n"))
    .filter("n != 30")
    .collect()
)
if shape:
    failures.append(f"{len(shape)} (date, currency) groups have != 30 maturities: {shape[:3]}")

# Rate range
out_of_range = curves.filter("spot_rate < -0.05 OR spot_rate > 0.20").count()
if out_of_range > 0:
    failures.append(f"{out_of_range} rows have spot_rate outside [-5%, 20%]")

# Forward rate populated except at 12mo
fwd_null_non12 = curves.filter("forward_rate_1y IS NULL AND maturity_months != 12").count()
if fwd_null_non12 > 0:
    failures.append(f"{fwd_null_non12} rows have NULL forward_rate_1y at maturity != 12mo")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

print("=" * 60)
print("Smoke test summary")
print("=" * 60)
print(f"  catalog.schema     : {fqn}")
print(f"  rfr_curves rowcount: {n}")
print()
print("Per (effective_date, currency):")
display(spark.sql(f"""
    SELECT effective_date, currency,
           COUNT(*)                    AS n_rows,
           ROUND(MIN(spot_rate), 4)    AS min_spot,
           ROUND(MAX(spot_rate), 4)    AS max_spot,
           ROUND(AVG(forward_rate_1y), 4) AS avg_fwd_1y
    FROM {fqn}.rfr_curves
    GROUP BY effective_date, currency
    ORDER BY effective_date, currency
"""))

# COMMAND ----------

if failures:
    print("FAIL:")
    for f in failures:
        print(f"  - {f}")
    dbutils.notebook.exit(f"FAIL: {'; '.join(failures)}")
else:
    print("OK — all checks passed.")
    dbutils.notebook.exit("OK")
