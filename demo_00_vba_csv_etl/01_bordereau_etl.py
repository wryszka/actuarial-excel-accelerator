# Databricks notebook source
# MAGIC %md
# MAGIC # Demo 0 · The converted notebook — bordereau ETL
# MAGIC
# MAGIC This is what Genie Code produces when you paste in
# MAGIC `ClaimsBordereauETL.bas` and ask it to (1) explain the macro and
# MAGIC (2) do the same thing on Databricks. It applies **exactly the VBA's
# MAGIC rules** — dedupe on claim ref, the three date formats, £/`(x)` money
# MAGIC parsing, the status-code map, `incurred = paid + outstanding` — with
# MAGIC **one improvement**: the rows the VBA silently threw away are kept in a
# MAGIC quarantine table instead.
# MAGIC
# MAGIC | Table | Grain | VBA equivalent |
# MAGIC |---|---|---|
# MAGIC | `brd_bronze_claims` | one row per landed CSV row | the `Raw` tab |
# MAGIC | `brd_silver_claims` | one clean row per claim | the `Standardised` tab / export CSV |
# MAGIC | `brd_quarantine` | rows with unusable loss dates | **nothing — the VBA dropped them silently** |
# MAGIC
# MAGIC Runs the same way by hand (stage 1) and from the file-arrival job
# MAGIC (stage 2): it ingests any CSV in `incoming/` that bronze hasn't seen yet,
# MAGIC then rebuilds silver + quarantine from the full bronze. Idempotent.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_serverless_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("brd_volume_name", "brd_landing")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
volume = dbutils.widgets.get("brd_volume_name")
fqn = f"{catalog}.{schema}"
incoming = f"/Volumes/{catalog}/{schema}/{volume}/incoming"

from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bronze — land new files as-is (the `Raw` tab, but with lineage)

# COMMAND ----------

RAW_SCHEMA = StructType([StructField(c, StringType()) for c in [
    "ClaimRef", "PolicyNo", "LossDate", "ReportDate", "Status",
    "PerilCode", "Region", "Handler", "PaidGBP", "OutstandingGBP"]])

all_files = [f.path for f in dbutils.fs.ls(incoming) if f.path.endswith(".csv")]

already = set()
if spark.catalog.tableExists(f"{fqn}.brd_bronze_claims"):
    already = {r[0] for r in spark.table(f"{fqn}.brd_bronze_claims")
               .select("_source_file").distinct().collect()}

new_files = [p for p in all_files if p.replace("dbfs:", "") not in already]
print(f"{len(all_files)} file(s) in incoming/, {len(new_files)} new")

for path in new_files:
    df = (spark.read.format("csv").option("header", "true").schema(RAW_SCHEMA)
          .load(path)
          .withColumn("_ingested_at", F.current_timestamp())
          .withColumn("_source_file", F.col("_metadata.file_path")))
    df.write.mode("append").saveAsTable(f"{fqn}.brd_bronze_claims")
    print(f"✓ landed {path.split('/')[-1]}  ({df.count():,} rows)")

if not spark.catalog.tableExists(f"{fqn}.brd_bronze_claims"):
    raise ValueError(f"No CSVs found in {incoming} — upload a bordereau file first.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver — the VBA's rules, in the open
# MAGIC
# MAGIC Each transformation below is one of the macro's hidden behaviours,
# MAGIC now visible, testable and governed.

# COMMAND ----------

bronze = spark.table(f"{fqn}.brd_bronze_claims")

# --- dedupe: vendor extract double-fires; keep one row per claim ref ------
# (duplicates are exact copies, so "which one" doesn't matter)
deduped = bronze.dropDuplicates(["ClaimRef"])

# --- the three date formats ParseDateISO accumulated over the years -------
def parse_date(col):
    return F.expr(f"""
        coalesce(try_to_date(trim({col}), 'dd/MM/yyyy'),
                 try_to_date(trim({col}), 'yyyy-MM-dd'),
                 try_to_date(trim({col}), 'dd-MMM-yy'))
    """)

# --- ParseAmount: £, blank/'-' as zero, (x) as negative -------------------
def parse_amount(col):
    # blank CSV fields arrive as NULL — treat them as empty, like the VBA does
    t = F.trim(F.coalesce(F.col(col), F.lit("")))
    bare = F.regexp_replace(t, "[£,()]", "")
    value = F.when((t == "") | (t == "-"), F.lit(0.0)) \
             .otherwise(F.round(bare.cast("double"), 2))
    return F.when(t.startswith("("), -value).otherwise(value)

# --- MapStatus: the hardcoded Select Case ----------------------------------
status_map = F.when(F.upper(F.trim(F.col("Status"))).isin("O", "OPEN"), "Open") \
    .when(F.upper(F.trim(F.col("Status"))).isin("RO", "REOPENED"), "Reopened") \
    .when(F.upper(F.trim(F.col("Status"))).isin("C", "CLOSED"), "Closed") \
    .when(F.upper(F.trim(F.col("Status"))) == "CWP", "ClosedWithoutPayment") \
    .otherwise("UNKNOWN")

standardised = (
    deduped
    .withColumn("claim_ref", F.trim("ClaimRef"))
    .withColumn("policy_no", F.trim("PolicyNo"))
    .withColumn("loss_date", parse_date("LossDate"))
    .withColumn("report_date", parse_date("ReportDate"))
    .withColumn("status", status_map)
    .withColumn("peril_code", F.trim("PerilCode"))
    .withColumn("region", F.trim("Region"))
    .withColumn("paid_gbp", parse_amount("PaidGBP"))
    .withColumn("outstanding_gbp", parse_amount("OutstandingGBP"))
    .withColumn("incurred_gbp", F.round(F.col("paid_gbp") + F.col("outstanding_gbp"), 2))
)

OUT_COLS = ["claim_ref", "policy_no", "loss_date", "report_date", "status",
            "peril_code", "region", "paid_gbp", "outstanding_gbp",
            "incurred_gbp", "_source_file", "_ingested_at"]

# --- the improvement: quarantine instead of the silent drop ---------------
good = standardised.filter(F.col("loss_date").isNotNull())
bad = standardised.filter(F.col("loss_date").isNull())

(good.select(*OUT_COLS).write.mode("overwrite")
 .option("overwriteSchema", "true").saveAsTable(f"{fqn}.brd_silver_claims"))

(bad.select(F.col("LossDate").alias("raw_loss_date"), *OUT_COLS)
 .write.mode("overwrite").option("overwriteSchema", "true")
 .saveAsTable(f"{fqn}.brd_quarantine"))

n_silver = spark.table(f"{fqn}.brd_silver_claims").count()
n_quar = spark.table(f"{fqn}.brd_quarantine").count()
print(f"✓ {fqn}.brd_silver_claims  {n_silver:,} rows")
print(f"✓ {fqn}.brd_quarantine     {n_quar:,} rows — the VBA dropped these silently")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Governance — comments so the tables explain themselves

# COMMAND ----------

spark.sql(f"""
COMMENT ON TABLE {fqn}.brd_silver_claims IS
'Standardised monthly TPA claims bordereau — the governed replacement for the '
'legacy Excel macro output (Bordereau_ETL.xlsm). One row per claim; dates ISO; '
'amounts GBP; incurred = paid + outstanding. Anyone the schema is shared with '
'can query or download this — no more emailing CSVs. Synthetic data.'
""")
spark.sql(f"""
COMMENT ON TABLE {fqn}.brd_quarantine IS
'Bordereau rows with unusable loss dates. The legacy VBA skipped these '
'silently; here they are kept, visible and fixable. Synthetic data.'
""")
print("✓ table comments applied")

# COMMAND ----------

display(spark.sql(f"""
    SELECT _source_file, COUNT(*) AS claims,
           ROUND(SUM(paid_gbp), 2) AS paid,
           ROUND(SUM(outstanding_gbp), 2) AS outstanding,
           ROUND(SUM(incurred_gbp), 2) AS incurred
    FROM {fqn}.brd_silver_claims
    GROUP BY _source_file ORDER BY _source_file
"""))

# COMMAND ----------

print("ETL complete. Next: 02_reconciliation.py")
