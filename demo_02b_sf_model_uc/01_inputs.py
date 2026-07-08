# Databricks notebook source
# MAGIC %md
# MAGIC # Use Case 2 · Step 1 — the inputs become a table
# MAGIC
# MAGIC In the workbook world, each entity's inputs live on an `Inputs` tab in
# MAGIC its own file — a group of 100 entities means 100 workbooks. Here the
# MAGIC same inputs are one governed table: **`sfm_inputs`**, one row per
# MAGIC entity, fully commented. `ENT-001` carries exactly the numbers shown in
# MAGIC `SF_Model.xlsx`, so the workbook and the model can be compared
# MAGIC like-for-like later.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_serverless_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("sfm_volume_name", "sfm_assets")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
volume = dbutils.widgets.get("sfm_volume_name")
fqn = f"{catalog}.{schema}"
vol_path = f"/Volumes/{catalog}/{schema}/{volume}"

# COMMAND ----------

from pyspark.sql.types import (StructType, StructField, StringType, DoubleType)

schema_def = StructType([
    StructField("entity_id", StringType()),
    StructField("entity_name", StringType()),
    StructField("line_of_business", StringType()),
    StructField("premium_volume", DoubleType()),
    StructField("reserve_volume", DoubleType()),
    StructField("assets_mv", DoubleType()),
    StructField("asset_duration", DoubleType()),
    StructField("liabilities_bel", DoubleType()),
    StructField("liability_duration", DoubleType()),
])

df = (spark.read.format("csv").option("header", "true").schema(schema_def)
      .load(f"{vol_path}/sf_inputs.csv"))
df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{fqn}.sfm_inputs")
print(f"✓ {fqn}.sfm_inputs — {df.count()} entities")

# COMMAND ----------

spark.sql(f"""
COMMENT ON TABLE {fqn}.sfm_inputs IS
'Standard-Formula model inputs, one row per entity (£m). ENT-001 matches the '
'Inputs tab of the legacy SF_Model.xlsx workbook exactly. Scored by the '
'sfm_scr_model registered model. Synthetic data.'
""")
COMMENTS = {
    "entity_id": "Entity identifier, ENT-001..ENT-100.",
    "entity_name": "Display name of the entity/portfolio.",
    "line_of_business": "Dominant line of business (drives scale only).",
    "premium_volume": "Premium volume Vp, £m — non-life premium risk exposure.",
    "reserve_volume": "Reserve volume Vr, £m — non-life reserve risk exposure.",
    "assets_mv": "Market value of assets, £m.",
    "asset_duration": "Modified duration of assets, years.",
    "liabilities_bel": "Best-estimate liabilities, £m.",
    "liability_duration": "Modified duration of liabilities, years.",
}
for c, txt in COMMENTS.items():
    spark.sql(f"ALTER TABLE {fqn}.sfm_inputs ALTER COLUMN {c} COMMENT '{txt}'")
print("✓ comments applied")

display(spark.table(f"{fqn}.sfm_inputs").orderBy("entity_id").limit(5))

# COMMAND ----------

print("Inputs ready. Next: 02_register_model.py")
