# Databricks notebook source
# MAGIC %md
# MAGIC # Gold — publish `rfr_curves`
# MAGIC
# MAGIC The reference table demos 2 and 3 will consume. Loaded from silver via
# MAGIC overwrite; primary key (effective_date, currency, maturity_months);
# MAGIC every column has a comment so AI/BI Genie can answer questions like
# MAGIC *"what was the 10-year EUR spot rate in October?"* without further
# MAGIC metadata work.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
fqn = f"{catalog}.{schema}"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Build the gold table from silver

# COMMAND ----------

silver = spark.table(f"{fqn}.silver_rfr_curves")

(silver
    .select(
        "effective_date",
        "currency",
        "maturity_months",
        "spot_rate",
        "forward_rate_1y",
        "_ingested_at",
        "_source_file",
    )
    .write
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(f"{fqn}.rfr_curves")
)

n = spark.table(f"{fqn}.rfr_curves").count()
print(f"✓ {fqn}.rfr_curves — {n} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Table & column comments (Genie-ready)

# COMMAND ----------

spark.sql(f"""
    COMMENT ON TABLE {fqn}.rfr_curves IS
    'EIOPA monthly risk-free interest rate term structures, long form. '
    'One row per (effective_date, currency, maturity_months). Primary key '
    '(effective_date, currency, maturity_months). Source: EIOPA RFR_spot_no_VA '
    'tabs landed in the rfr_landing Volume. Demo 2 (SCR Standard Formula) and '
    'demo 3 (chain ladder reserving) both consume this table.'
""")

COLUMN_COMMENTS = {
    "effective_date":
        "Reference date of the EIOPA monthly publication (last calendar day of the month).",
    "currency":
        "ISO 4217 currency code. Demo 1 carries EUR, GBP, USD.",
    "maturity_months":
        "Maturity in months. Demo 1 covers 12..360 (1y..30y) in 12-month steps.",
    "spot_rate":
        "Risk-free spot rate, no volatility adjustment, decimal (e.g. 0.025 = 2.5%).",
    "forward_rate_1y":
        "1-year forward rate, derived: (1+s_m)^t_m / (1+s_{m-12})^t_{m-12} - 1. "
        "NULL at the 12-month maturity (no preceding point).",
    "_ingested_at":
        "Timestamp the bronze ingestion produced this row.",
    "_source_file":
        "Full Volume path of the EIOPA monthly file the row came from.",
}

for col, comment in COLUMN_COMMENTS.items():
    spark.sql(f"""
        ALTER TABLE {fqn}.rfr_curves
        ALTER COLUMN {col}
        COMMENT '{comment.replace("'", "''")}'
    """)
print("✓ column comments applied")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Sanity check

# COMMAND ----------

display(spark.sql(f"""
    SELECT effective_date, currency, COUNT(*) AS n,
           ROUND(MIN(spot_rate), 4) AS min_rate,
           ROUND(MAX(spot_rate), 4) AS max_rate
    FROM {fqn}.rfr_curves
    GROUP BY effective_date, currency
    ORDER BY effective_date, currency
"""))
