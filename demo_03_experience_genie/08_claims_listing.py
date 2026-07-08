# Databricks notebook source
# MAGIC %md
# MAGIC # Use Case 3 · The claims listing — the table everyone knows
# MAGIC
# MAGIC The most relatable dataset in any insurance company: **one row per
# MAGIC claim**. Every Excel user has pivoted one of these — by line of
# MAGIC business, by status, by region; average severity; top ten largest;
# MAGIC monthly trend.
# MAGIC
# MAGIC This notebook builds **`exp_claims_listing`** (claim grain, ~146k
# MAGIC claims, fully commented for Genie) from the transaction-level silver
# MAGIC table, and writes an Excel-sized extract — **Motor, accident year
# MAGIC 2024** — to the `exp_landing` volume as `claims_extract_motor_ay2024.csv`
# MAGIC so the "before" act (open in Excel, pivot) uses exactly the same data.
# MAGIC
# MAGIC Requires the demo 3 world (notebooks 00–04) to have been run.

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

spark.sql(f"""
CREATE OR REPLACE TABLE {fqn}.exp_claims_listing AS
SELECT
    claim_id,
    line_of_business,
    region,
    channel,
    peril,
    accident_date,
    accident_year,
    report_date,
    report_lag_days,
    large_loss_flag,
    ROUND(SUM(paid_amount), 2)                    AS paid,
    ROUND(SUM(reserve_change), 2)                 AS outstanding,
    ROUND(SUM(paid_amount) + SUM(reserve_change), 2) AS incurred,
    CASE WHEN SUM(reserve_change) <= 1 THEN 'Closed' ELSE 'Open' END AS status
FROM {fqn}.exp_silver_claims
GROUP BY claim_id, line_of_business, region, channel, peril,
         accident_date, accident_year, report_date, report_lag_days, large_loss_flag
""")
n = spark.table(f"{fqn}.exp_claims_listing").count()
print(f"✓ {fqn}.exp_claims_listing — {n:,} claims")

# COMMAND ----------

spark.sql(f"""
COMMENT ON TABLE {fqn}.exp_claims_listing IS
'Claims listing: one row per claim, as at the extract date. The classic ad-hoc '
'analytics dataset — pivot by line of business, region, channel, status or '
'accident year; severity and large-loss analysis; top-N largest claims. '
'Aggregated from exp_silver_claims (transaction grain). Amounts GBP: paid is '
'net of recoveries, outstanding is the remaining case reserve, incurred = paid '
'+ outstanding. Synthetic data.'
""")
COMMENTS = {
    "claim_id": "Unique claim identifier.",
    "line_of_business": "Line of business: Motor, Home, CommercialProperty, Liability, Marine.",
    "region": "UK region: London, South, Midlands, North, Scotland.",
    "channel": "Distribution channel: Broker, Direct, Aggregator, Partnership.",
    "peril": "Peril / cause of loss code (line-specific, e.g. AD, Storm, Fire).",
    "accident_date": "Date the loss occurred.",
    "accident_year": "Calendar year of the accident date (cohort).",
    "report_date": "Date the claim was reported.",
    "report_lag_days": "Days between accident and report.",
    "large_loss_flag": "TRUE if flagged as a large loss.",
    "paid": "Cumulative payments net of recoveries, GBP.",
    "outstanding": "Outstanding case reserve, GBP.",
    "incurred": "Paid + outstanding, GBP.",
    "status": "Open (case reserve remains) or Closed.",
}
for c, txt in COMMENTS.items():
    spark.sql(f"ALTER TABLE {fqn}.exp_claims_listing ALTER COLUMN {c} COMMENT '{txt}'")
print("✓ comments applied (Genie-ready)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The Excel extract — Motor, accident year 2024

# COMMAND ----------

import os
import shutil

slice_pd = (spark.table(f"{fqn}.exp_claims_listing")
            .where("line_of_business = 'Motor' AND accident_year = 2024")
            .orderBy("claim_id")
            .toPandas())
local = "/tmp/claims_extract_motor_ay2024.csv"
slice_pd.to_csv(local, index=False)
dst = f"{vol_path}/claims_extract_motor_ay2024.csv"
shutil.copyfile(local, dst)
print(f"✓ {len(slice_pd):,} Motor AY2024 claims → {dst}")
print("  Download it from Catalog Explorer → the exp_landing volume — that file is")
print("  the 'before' act: open it in Excel and pivot.")

# COMMAND ----------

display(spark.sql(f"""
    SELECT line_of_business, status, COUNT(*) claims,
           ROUND(SUM(incurred)/1e6, 1) AS incurred_m,
           ROUND(AVG(incurred), 0) AS avg_severity
    FROM {fqn}.exp_claims_listing
    GROUP BY line_of_business, status ORDER BY line_of_business, status
"""))

# COMMAND ----------

print("Claims listing ready. Next: 09_genie_starter.py")
