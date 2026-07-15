# Databricks notebook source
# MAGIC %md
# MAGIC # Demo 3 · Step 4 (Rebuild) — Gold, the tables behind Genie & the dashboard
# MAGIC
# MAGIC **Recipe step: Rebuild.** These three gold tables *are* the PivotTables —
# MAGIC except they're governed, documented, and don't need refreshing by hand.
# MAGIC Every column carries a comment so **AI/BI Genie** can answer questions in
# MAGIC plain English with no further metadata work, and the **AI/BI dashboard**
# MAGIC binds straight to them.
# MAGIC
# MAGIC | Gold table | Grain | Replaces the Excel… |
# MAGIC |---|---|---|
# MAGIC | `exp_gold_experience` | LOB × region × channel × accident year | main loss-ratio PivotTable |
# MAGIC | `exp_gold_triangle` | LOB × accident year × dev month | paid/incurred development triangle |
# MAGIC | `exp_dim_segment` | one row per segment | the VLOOKUP reference tab |

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
fqn = f"{catalog}.{schema}"

# COMMAND ----------

# MAGIC %md
# MAGIC ## `exp_gold_experience` — the loss-ratio fact

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TABLE {fqn}.exp_gold_experience AS
WITH claims AS (
    SELECT line_of_business, region, channel, accident_year,
           COUNT(DISTINCT claim_id)                                   AS reported_claims,
           SUM(paid_amount)                                           AS paid,
           SUM(reserve_change)                                        AS outstanding,
           SUM(paid_amount) + SUM(reserve_change)                     AS incurred,
           SUM(CASE WHEN large_loss_flag THEN paid_amount + reserve_change ELSE 0 END) AS large_loss_incurred,
           COUNT(DISTINCT CASE WHEN large_loss_flag THEN claim_id END) AS large_loss_count
    FROM {fqn}.exp_silver_claims
    GROUP BY line_of_business, region, channel, accident_year
),
prem AS (
    SELECT line_of_business, region, channel, accident_year,
           SUM(earned_premium) AS earned_premium,
           SUM(exposure)       AS exposure,
           SUM(policy_count)   AS policy_count
    FROM {fqn}.exp_silver_premium
    GROUP BY line_of_business, region, channel, accident_year
)
SELECT
    p.line_of_business,
    p.region,
    p.channel,
    p.accident_year,
    ROUND(p.earned_premium, 2)                                       AS earned_premium,
    ROUND(p.exposure, 1)                                             AS exposure,
    p.policy_count,
    COALESCE(c.reported_claims, 0)                                   AS reported_claims,
    ROUND(COALESCE(c.paid, 0), 2)                                    AS paid,
    ROUND(COALESCE(c.outstanding, 0), 2)                             AS outstanding,
    ROUND(COALESCE(c.incurred, 0), 2)                                AS incurred,
    ROUND(COALESCE(c.incurred, 0) / NULLIF(p.earned_premium, 0), 4)  AS loss_ratio,
    ROUND(COALESCE(c.reported_claims, 0) / NULLIF(p.exposure, 0), 4) AS claim_frequency,
    ROUND(COALESCE(c.incurred, 0) / NULLIF(c.reported_claims, 0), 2) AS avg_claim_severity,
    ROUND(COALESCE(c.large_loss_incurred, 0), 2)                     AS large_loss_incurred,
    COALESCE(c.large_loss_count, 0)                                  AS large_loss_count
FROM prem p
LEFT JOIN claims c
  ON  p.line_of_business = c.line_of_business
  AND p.region           = c.region
  AND p.channel          = c.channel
  AND p.accident_year    = c.accident_year
""")
n = spark.table(f"{fqn}.exp_gold_experience").count()
print(f"✓ exp_gold_experience — {n} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `exp_gold_triangle` — paid & incurred development

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TABLE {fqn}.exp_gold_triangle AS
WITH incr AS (
    SELECT line_of_business, accident_year,
           GREATEST(dev_month, 0) AS dev_month,
           SUM(paid_amount)                       AS paid_in_period,
           SUM(paid_amount) + SUM(reserve_change) AS incurred_in_period
    FROM {fqn}.exp_silver_claims
    GROUP BY line_of_business, accident_year, GREATEST(dev_month, 0)
)
SELECT
    line_of_business,
    accident_year,
    dev_month,
    ROUND(paid_in_period, 2)     AS paid_in_period,
    ROUND(incurred_in_period, 2) AS incurred_in_period,
    ROUND(SUM(paid_in_period)     OVER w, 2) AS cumulative_paid,
    ROUND(SUM(incurred_in_period) OVER w, 2) AS cumulative_incurred
FROM incr
WINDOW w AS (PARTITION BY line_of_business, accident_year
             ORDER BY dev_month ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
""")
print(f"✓ exp_gold_triangle — {spark.table(f'{fqn}.exp_gold_triangle').count()} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `exp_dim_segment` — segment reference

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TABLE {fqn}.exp_dim_segment AS
SELECT policy_segment, line_of_business, region, channel
FROM {fqn}.exp_bronze_segment_map
""")
print(f"✓ exp_dim_segment — {spark.table(f'{fqn}.exp_dim_segment').count()} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Table & column comments (Genie-ready)

# COMMAND ----------

spark.sql(f"""
COMMENT ON TABLE {fqn}.exp_gold_experience IS
'Actuarial experience & loss-ratio fact. One row per line of business × region × '
'channel × accident year. Loss ratio = incurred / earned premium, where incurred '
'= paid (net of recoveries) + outstanding case reserves. This table replaces the '
'main loss-ratio PivotTable in the legacy Experience_Monitoring.xlsx workbook and '
'is the primary table for the Experience Monitoring Genie space. Synthetic data.'
""")

EXPERIENCE_COMMENTS = {
    "line_of_business": "Line of business: Motor, Home, CommercialProperty, Liability, Marine.",
    "region": "UK region the policy is written in: London, South, Midlands, North, Scotland.",
    "channel": "Distribution channel: Broker, Direct, Aggregator, Partnership.",
    "accident_year": "Calendar year the claims occurred (accident year), 2019–2025.",
    "earned_premium": "Earned premium for the segment and accident year, GBP. Denominator of loss ratio.",
    "exposure": "Earned exposure (policy-years) for the segment and accident year.",
    "policy_count": "Average in-force policy count contributing to the earned premium.",
    "reported_claims": "Number of distinct claims reported for the accident year as at the extract date.",
    "paid": "Cumulative claim payments net of recoveries, GBP.",
    "outstanding": "Outstanding case reserves (estimated unpaid amounts), GBP.",
    "incurred": "Incurred losses = paid + outstanding, GBP. Numerator of loss ratio.",
    "loss_ratio": "Incurred losses divided by earned premium (e.g. 0.85 = 85%). Key actuarial KPI.",
    "claim_frequency": "Reported claims per unit of exposure.",
    "avg_claim_severity": "Average incurred cost per reported claim, GBP.",
    "large_loss_incurred": "Incurred losses attributable to claims flagged as large losses, GBP.",
    "large_loss_count": "Number of distinct large-loss claims.",
}
for col, c in EXPERIENCE_COMMENTS.items():
    spark.sql(f"ALTER TABLE {fqn}.exp_gold_experience ALTER COLUMN {col} COMMENT '{c}'")

spark.sql(f"""
COMMENT ON TABLE {fqn}.exp_gold_triangle IS
'Claims development triangle by line of business and accident year. dev_month is '
'months since the accident; cumulative_paid / cumulative_incurred are the running '
'totals used to view how a cohort develops over time. Replaces the triangle tab in '
'the legacy Excel workbook. Synthetic data.'
""")
TRIANGLE_COMMENTS = {
    "line_of_business": "Line of business.",
    "accident_year": "Accident year (cohort) the claims belong to.",
    "dev_month": "Development month: whole months elapsed from accident to the transaction.",
    "paid_in_period": "Payments (net of recoveries) made in this development month, GBP.",
    "incurred_in_period": "Change in incurred (paid + reserve movement) in this development month, GBP.",
    "cumulative_paid": "Running total of paid claims up to and including this development month, GBP.",
    "cumulative_incurred": "Running total of incurred claims up to and including this development month, GBP.",
}
for col, c in TRIANGLE_COMMENTS.items():
    spark.sql(f"ALTER TABLE {fqn}.exp_gold_triangle ALTER COLUMN {col} COMMENT '{c}'")

spark.sql(f"""
COMMENT ON TABLE {fqn}.exp_dim_segment IS
'Segment reference: maps a policy_segment code to its line of business, region and '
'channel. This is the lookup table the legacy workbook kept as a VLOOKUP tab.'
""")
print("✓ comments applied to all gold tables")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The headline — Motor loss ratio by accident year

# COMMAND ----------

display(spark.sql(f"""
    SELECT accident_year,
           ROUND(SUM(earned_premium), 0) AS earned_premium,
           ROUND(SUM(incurred), 0)       AS incurred,
           ROUND(SUM(incurred) / SUM(earned_premium), 3) AS loss_ratio
    FROM {fqn}.exp_gold_experience
    WHERE line_of_business = 'Motor'
    GROUP BY accident_year ORDER BY accident_year
"""))

# COMMAND ----------

print("Gold complete. Next: 05_parity.py")
