# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — Cat sub-module (plug pass-through)
# MAGIC
# MAGIC Demo 2A treats Cat risk as a single plug from `scr_assumptions.cat_plug`.
# MAGIC This notebook exists for symmetry with the other sub-modules and to make
# MAGIC the Excel → Databricks structural mapping obvious. The Excel `Cat` tab
# MAGIC does the same thing: `=Assumptions!B12`.
# MAGIC
# MAGIC **Simplification.** A real Standard Formula models Cat per peril with
# MAGIC reinsurance recoveries. The migration pattern shown by demos 2-3 is
# MAGIC indifferent to where the Cat number comes from — replace this notebook
# MAGIC with a per-peril compute and the rest of the pipeline still works.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
fqn = f"{catalog}.{schema}"

# COMMAND ----------

from typing import Any


def cat_scr(ass_row: Any) -> float:
    return float(ass_row["cat_plug"])


# COMMAND ----------

ass_row = spark.table(f"{fqn}.scr_assumptions").filter("is_current = 'true'").collect()[0]
scr = cat_scr(ass_row)
print(f"SCR_cat (plug) = {scr:,.2f}")

dbutils.notebook.exit(str(scr))
