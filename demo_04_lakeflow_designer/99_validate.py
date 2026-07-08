# Databricks notebook source
# MAGIC %md
# MAGIC # Use Case 4 · Smoke test
# MAGIC
# MAGIC Checks the prepared sources and — if the canvas has been built — the
# MAGIC parity of its output. The canvas itself is a UI act, so its output is
# MAGIC reported as **PENDING** (not a failure) until it exists.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_serverless_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("exp_volume_name", "exp_landing")
catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
volume = dbutils.widgets.get("exp_volume_name")
fqn = f"{catalog}.{schema}"
vol_path = f"/Volumes/{catalog}/{schema}/{volume}"

results = []


def check(name, fn):
    try:
        status, detail = fn()
    except Exception as e:
        status, detail = "FAIL", str(e)[:160]
    results.append((name, status, str(detail)))


def rows(t):
    return spark.table(f"{fqn}.{t}").count()

# COMMAND ----------

check("claims source (claim grain)", lambda: (
    "PASS" if rows("exp_designer_claims_src") > 100_000 else "FAIL",
    f"{rows('exp_designer_claims_src'):,}"))
check("premium source (segment × AY)", lambda: (
    "PASS" if rows("exp_designer_premium_src") > 500 else "FAIL",
    f"{rows('exp_designer_premium_src'):,}"))
check("segment lookup", lambda: (
    "PASS" if rows("exp_dim_segment") == 100 else "FAIL", rows("exp_dim_segment")))


def extract_file():
    files = {f.name for f in dbutils.fs.ls(vol_path)}
    ok = "claims_extract_motor_ay2024.csv" in files
    return ("PASS" if ok else "FAIL", "in volume" if ok else "missing — run demo 3's 08")


check("Excel extract for drag-onto-canvas", extract_file)


def canvas_output():
    if not spark.catalog.tableExists(f"{fqn}.exp_designer_experience"):
        return ("PENDING", "canvas not built yet — see README act 2")
    from pyspark.sql import functions as F
    d = spark.sql(f"SELECT SUM(incurred) i, SUM(earned_premium) p "
                  f"FROM {fqn}.exp_designer_experience").first()
    g = spark.sql(f"SELECT SUM(incurred) i, SUM(earned_premium) p "
                  f"FROM {fqn}.exp_gold_experience").first()
    ok = (abs(d.i - g.i) <= max(1000.0, abs(g.i) * 0.0001)
          and abs(d.p - g.p) <= max(1000.0, g.p * 0.0001))
    return ("PASS" if ok else "FAIL",
            f"designer £{d.i:,.0f} vs pipeline £{g.i:,.0f} incurred")


check("canvas output parity (totals)", canvas_output)

# COMMAND ----------

import pandas as pd
df = pd.DataFrame(results, columns=["check", "status", "detail"])
display(spark.createDataFrame(df))
n_fail = (df.status == "FAIL").sum()
n_pending = (df.status == "PENDING").sum()
print(f"\n{(df.status == 'PASS').sum()} passed, {n_pending} pending, {n_fail} failed")
assert n_fail == 0, f"{n_fail} checks FAILED"
print("✓ no failures" + (" (canvas build still pending)" if n_pending else " — fully complete"))
