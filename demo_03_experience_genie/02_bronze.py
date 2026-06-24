# Databricks notebook source
# MAGIC %md
# MAGIC # Demo 3 · Step 2 (Land → Bronze) — Ingest the CSVs
# MAGIC
# MAGIC **Recipe step: Land.** The Excel equivalent is *File → Open → paste into
# MAGIC the Data tab*. Here the three CSVs in the `exp_landing` Volume are read
# MAGIC into bronze Delta tables exactly as-landed, with two pieces of lineage
# MAGIC metadata (`_ingested_at`, `_source_file`) Excel never gives you.
# MAGIC
# MAGIC | Source CSV | Bronze table |
# MAGIC |---|---|
# MAGIC | `claims_transactions.csv` | `exp_bronze_claims_txn` |
# MAGIC | `premium_exposure.csv` | `exp_bronze_premium` |
# MAGIC | `segment_map.csv` | `exp_bronze_segment_map` |

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_serverless_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("exp_volume_name", "exp_landing")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
volume = dbutils.widgets.get("exp_volume_name")
fqn = f"{catalog}.{schema}"
vol_path = f"/Volumes/{catalog}/{schema}/{volume}"

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import (StructType, StructField, StringType, IntegerType,
                               DoubleType, BooleanType)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Explicit schemas — don't let a 800k-row CSV guess its own types

# COMMAND ----------

claims_schema = StructType([
    StructField("claim_id", StringType()),
    StructField("policy_segment", StringType()),
    StructField("peril", StringType()),
    StructField("accident_date", StringType()),
    StructField("report_date", StringType()),
    StructField("transaction_date", StringType()),
    StructField("dev_month", IntegerType()),
    StructField("transaction_type", StringType()),
    StructField("transaction_amount", DoubleType()),
    StructField("large_loss_flag", BooleanType()),
])

premium_schema = StructType([
    StructField("policy_segment", StringType()),
    StructField("earned_month", StringType()),
    StructField("policy_count", IntegerType()),
    StructField("earned_premium", DoubleType()),
    StructField("exposure", DoubleType()),
])

segment_schema = StructType([
    StructField("policy_segment", StringType()),
    StructField("line_of_business", StringType()),
    StructField("region", StringType()),
    StructField("channel", StringType()),
])

# COMMAND ----------


def land(csv_name, schema_def, table):
    df = (spark.read.format("csv")
          .option("header", "true")
          .schema(schema_def)
          .load(f"{vol_path}/{csv_name}")
          .withColumn("_ingested_at", F.current_timestamp())
          .withColumn("_source_file", F.col("_metadata.file_path")))
    df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{fqn}.{table}")
    n = spark.table(f"{fqn}.{table}").count()
    print(f"✓ {fqn}.{table:24s} {n:>10,} rows")
    return n


land("claims_transactions.csv", claims_schema, "exp_bronze_claims_txn")
land("premium_exposure.csv", premium_schema, "exp_bronze_premium")
land("segment_map.csv", segment_schema, "exp_bronze_segment_map")

# COMMAND ----------

display(spark.sql(f"SELECT transaction_type, COUNT(*) n, ROUND(SUM(transaction_amount),0) total "
                  f"FROM {fqn}.exp_bronze_claims_txn GROUP BY transaction_type ORDER BY n DESC"))

# COMMAND ----------

print("Bronze complete. Next: 03_silver.py")
