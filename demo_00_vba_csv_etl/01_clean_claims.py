# Databricks notebook source
# MAGIC %md
# MAGIC # Use Case 1 · Clean the claims — the macro, rebuilt on Databricks
# MAGIC
# MAGIC This notebook does **exactly what the Excel macro does** — dedupe, parse
# MAGIC dates, tidy money, map status codes, work out incurred, flag large
# MAGIC losses — but on the whole file at once instead of row by row. The macro
# MAGIC takes a couple of minutes; this runs in seconds.
# MAGIC
# MAGIC This is the code **Genie Code wrote** when we pasted in the VBA and
# MAGIC asked it to do the same thing here. Each block below is one rule from
# MAGIC the macro, labelled so you can see the mapping. One improvement: instead
# MAGIC of *silently dropping* rows with an unreadable loss date (which the
# MAGIC macro has quietly done for years), we keep them in a separate
# MAGIC `brd_quarantine` table so nothing disappears.
# MAGIC
# MAGIC | Table it writes | What it is |
# MAGIC |---|---|
# MAGIC | `brd_claims_clean` | the cleaned, enriched claims — same as the macro's output |
# MAGIC | `brd_quarantine` | rows the macro would have silently dropped |

# COMMAND ----------

# MAGIC %md
# MAGIC ## Pick your input
# MAGIC
# MAGIC `source = table` uses the ready-made `brd_claims_raw` (from `00_setup`).
# MAGIC `source = file` reads a CSV you uploaded to the volume — set
# MAGIC `upload_file_name` to its name. Either way the rest is identical.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("brd_volume_name", "brd_landing")
dbutils.widgets.dropdown("source", "table", ["table", "file"])
dbutils.widgets.text("upload_file_name", "claims_raw.csv")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
volume = dbutils.widgets.get("brd_volume_name")
source = dbutils.widgets.get("source")
upload_file = dbutils.widgets.get("upload_file_name")
fqn = f"{catalog}.{schema}"
vol_path = f"/Volumes/{catalog}/{schema}/{volume}"

from pyspark.sql import functions as F

# COMMAND ----------

if source == "file":
    raw = (spark.read.format("csv").option("header", "true")
           .option("inferSchema", "false").load(f"{vol_path}/{upload_file}"))
    print(f"Reading uploaded file: {vol_path}/{upload_file}")
else:
    raw = spark.table(f"{fqn}.brd_claims_raw")
    print(f"Reading table: {fqn}.brd_claims_raw")

print(f"{raw.count():,} raw rows in")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Rule 1 — remove duplicate rows
# MAGIC The vendor extract double-fires, so the macro keeps the first row per
# MAGIC claim. `dropDuplicates` does the same.

# COMMAND ----------

deduped = raw.dropDuplicates(["ClaimRef"])
print(f"{deduped.count():,} rows after removing duplicates")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Rule 2 — read the three date formats
# MAGIC The macro's `ParseDateISO` accepts `dd/mm/yyyy`, `yyyy-mm-dd` and
# MAGIC `dd-Mon-yy`. `try_to_date` tries each; anything unreadable becomes NULL
# MAGIC (we deal with those rows below).

# COMMAND ----------

def parse_date(col):
    return F.expr(f"""
        coalesce(try_to_date(trim({col}), 'dd/MM/yyyy'),
                 try_to_date(trim({col}), 'yyyy-MM-dd'),
                 try_to_date(trim({col}), 'dd-MMM-yy'))
    """)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Rule 3 — tidy the money
# MAGIC Strip the `£`, treat `-` and blank as zero, read `(123.45)` as negative.

# COMMAND ----------

def parse_amount(col):
    t = F.trim(F.coalesce(F.col(col), F.lit("")))
    bare = F.regexp_replace(t, "[£,()]", "")
    value = F.when((t == "") | (t == "-"), F.lit(0.0)) \
             .otherwise(F.round(bare.cast("double"), 2))
    return F.when(t.startswith("("), -value).otherwise(value)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Rule 4 — standardise the status codes
# MAGIC The macro's `Select Case`: `O`/`OPEN` → Open, `C`/`CLOSED` → Closed, etc.

# COMMAND ----------

status_clean = F.upper(F.trim(F.col("Status")))
status = (F.when(status_clean.isin("O", "OPEN"), "Open")
          .when(status_clean.isin("RO", "REOPENED"), "Reopened")
          .when(status_clean.isin("C", "CLOSED"), "Closed")
          .when(status_clean == "CWP", "ClosedWithoutPayment")
          .otherwise("UNKNOWN"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Put it together — clean + enrich in one pass
# MAGIC Drop the `Handler` column (the macro does), compute `incurred = paid +
# MAGIC outstanding`, and flag large losses (> £100k).

# COMMAND ----------

cleaned = (deduped
    .withColumn("claim_ref", F.trim("ClaimRef"))
    .withColumn("policy_ref", F.trim("PolicyRef"))
    .withColumn("loss_date", parse_date("LossDate"))
    .withColumn("report_date", parse_date("ReportDate"))
    .withColumn("status", status)
    .withColumn("peril", F.trim("Peril"))
    .withColumn("paid_gbp", parse_amount("PaidGBP"))
    .withColumn("outstanding_gbp", parse_amount("OutstandingGBP"))
    .withColumn("incurred_gbp", F.round(F.col("paid_gbp") + F.col("outstanding_gbp"), 2))
    .withColumn("large_loss_flag", F.when(F.col("incurred_gbp") > 100000, "Y").otherwise("N"))
)

OUT_COLS = ["claim_ref", "policy_ref", "loss_date", "report_date", "status",
            "peril", "paid_gbp", "outstanding_gbp", "incurred_gbp", "large_loss_flag"]

# COMMAND ----------

# MAGIC %md
# MAGIC ## The improvement — keep the rows the macro throws away
# MAGIC Good loss date → the clean table. Unreadable loss date → quarantine
# MAGIC (the macro just skipped these, with no record).

# COMMAND ----------

good = cleaned.filter(F.col("loss_date").isNotNull())
bad = cleaned.filter(F.col("loss_date").isNull())

good.select(*OUT_COLS).write.mode("overwrite").option("overwriteSchema", "true") \
    .saveAsTable(f"{fqn}.brd_claims_clean")
bad.select(F.col("LossDate").alias("raw_loss_date"), *OUT_COLS) \
    .write.mode("overwrite").option("overwriteSchema", "true") \
    .saveAsTable(f"{fqn}.brd_quarantine")

n_clean = spark.table(f"{fqn}.brd_claims_clean").count()
n_quar = spark.table(f"{fqn}.brd_quarantine").count()
print(f"✓ {fqn}.brd_claims_clean  {n_clean:,} claims")
print(f"✓ {fqn}.brd_quarantine    {n_quar:,} rows the macro would have dropped silently")

# COMMAND ----------

spark.sql(f"""
    COMMENT ON TABLE {fqn}.brd_claims_clean IS
    'Cleaned, enriched monthly claims — the governed replacement for the Excel '
    'macro output. incurred = paid + outstanding; large_loss_flag = incurred > 100k. '
    'Synthetic data.'
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## A look at the result

# COMMAND ----------

display(spark.sql(f"""
    SELECT status,
           COUNT(*)                         AS claims,
           ROUND(SUM(incurred_gbp), 0)      AS incurred_gbp,
           SUM(CASE WHEN large_loss_flag='Y' THEN 1 ELSE 0 END) AS large_losses
    FROM {fqn}.brd_claims_clean
    GROUP BY status ORDER BY claims DESC
"""))

# COMMAND ----------

print("Done. Next: 02_reconciliation to prove it matches the Excel output.")
