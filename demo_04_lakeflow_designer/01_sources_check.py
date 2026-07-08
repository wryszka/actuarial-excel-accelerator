# Databricks notebook source
# MAGIC %md
# MAGIC # Use Case 4 · Sources — set the canvas table
# MAGIC
# MAGIC **The monthly blend, without the desktop ETL tool.** Lakeflow Designer
# MAGIC rebuilds the classic canvas workflow — sources in, join, aggregate,
# MAGIC summary out — as a governed pipeline. This notebook prepares the two
# MAGIC purpose-built source tables the canvas starts from and verifies
# MAGIC everything else is in place. Requires the Use Case 3 world (demo 3
# MAGIC notebooks `00`–`04` and `08`).
# MAGIC
# MAGIC | Source | Why it exists |
# MAGIC |---|---|
# MAGIC | `exp_designer_claims_src` | claim-grain extract **deliberately un-enriched** (only `policy_segment`) — so the join to the segment lookup is a real step, exactly like the VLOOKUP / Alteryx Join everyone recognises |
# MAGIC | `exp_designer_premium_src` | earned premium at segment × accident-year grain — the second branch of the blend |
# MAGIC | `exp_dim_segment` | already exists — the lookup |
# MAGIC | `claims_extract_motor_ay2024.csv` | already in the `exp_landing` volume — the optional drag-a-file-onto-the-canvas beat |

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
CREATE OR REPLACE TABLE {fqn}.exp_designer_claims_src AS
SELECT claim_id,
       policy_segment,
       accident_year,
       ROUND(SUM(paid_amount), 2)                       AS paid,
       ROUND(SUM(reserve_change), 2)                    AS outstanding,
       ROUND(SUM(paid_amount) + SUM(reserve_change), 2) AS incurred
FROM {fqn}.exp_silver_claims
GROUP BY claim_id, policy_segment, accident_year
""")
spark.sql(f"""
COMMENT ON TABLE {fqn}.exp_designer_claims_src IS
'Use Case 4 canvas source: claim-grain extract, deliberately WITHOUT line of '
'business / region / channel — join it to exp_dim_segment on policy_segment in '
'Lakeflow Designer (the VLOOKUP step). Amounts GBP. Synthetic data.'
""")
print(f"✓ exp_designer_claims_src — {spark.table(f'{fqn}.exp_designer_claims_src').count():,} claims")

spark.sql(f"""
CREATE OR REPLACE TABLE {fqn}.exp_designer_premium_src AS
SELECT policy_segment,
       accident_year,
       ROUND(SUM(earned_premium), 2) AS earned_premium
FROM {fqn}.exp_silver_premium
GROUP BY policy_segment, accident_year
""")
spark.sql(f"""
COMMENT ON TABLE {fqn}.exp_designer_premium_src IS
'Use Case 4 canvas source: earned premium by policy segment and accident year, '
'GBP — the premium branch of the monthly blend. Join to exp_dim_segment and '
'aggregate alongside the claims branch. Synthetic data.'
""")
print(f"✓ exp_designer_premium_src — {spark.table(f'{fqn}.exp_designer_premium_src').count():,} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify the rest of the world

# COMMAND ----------

ok = True
for t in ["exp_dim_segment", "exp_gold_experience"]:
    exists = spark.catalog.tableExists(f"{fqn}.{t}")
    print(("✓" if exists else "✗ MISSING:"), f"{fqn}.{t}")
    ok = ok and exists
files = {f.name for f in dbutils.fs.ls(vol_path)}
has_extract = "claims_extract_motor_ay2024.csv" in files
print(("✓" if has_extract else "✗ MISSING:"), f"{vol_path}/claims_extract_motor_ay2024.csv "
      "(optional drag-onto-canvas beat — run demo 3's 08_claims_listing if absent)")
assert ok, "Run the Use Case 3 notebooks first (demo_03: 00–04, then 08)."

# COMMAND ----------

print("Sources ready. Now build the canvas — follow README.md, then run 02_parity.")
