# Databricks notebook source
# MAGIC %md
# MAGIC # Use Case 4 · Smoke test
# MAGIC
# MAGIC Checks the generated sources and — if the canvas has been built — the
# MAGIC parity of its output. The canvas is a UI act, so its output is reported
# MAGIC as **PENDING** (not a failure) until it exists. Standalone: depends on
# MAGIC nothing but this use case's own `00`/`01`.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("dsg_volume_name", "dsg_landing")
catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
volume = dbutils.widgets.get("dsg_volume_name")
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

check("claims source", lambda: ("PASS" if rows("dsg_claims_src") > 10_000 else "FAIL",
                                 f"{rows('dsg_claims_src'):,}"))
check("premium source", lambda: ("PASS" if rows("dsg_premium_src") > 400 else "FAIL",
                                  f"{rows('dsg_premium_src'):,}"))
check("segment lookup = 100", lambda: ("PASS" if rows("dsg_segment") == 100 else "FAIL",
                                       rows("dsg_segment")))
check("benchmark populated", lambda: ("PASS" if rows("dsg_benchmark") > 0 else "FAIL",
                                      rows("dsg_benchmark")))


def extract_file():
    files = {f.name for f in dbutils.fs.ls(vol_path)}
    ok = "claims_extract.csv" in files
    return ("PASS" if ok else "FAIL", "in volume" if ok else "missing — run 01")


check("Excel extract for drag-onto-canvas", extract_file)


def canvas_output():
    if not spark.catalog.tableExists(f"{fqn}.dsg_experience"):
        return ("PENDING", "canvas not built yet — see README")
    d = spark.sql(f"SELECT SUM(incurred) i, SUM(earned_premium) p FROM {fqn}.dsg_experience").first()
    b = spark.sql(f"SELECT SUM(incurred) i, SUM(earned_premium) p FROM {fqn}.dsg_benchmark").first()
    ok = (abs(d.i - b.i) <= max(1000.0, abs(b.i) * 0.0001)
          and abs(d.p - b.p) <= max(1000.0, b.p * 0.0001))
    return ("PASS" if ok else "FAIL", f"designer £{d.i:,.0f} vs benchmark £{b.i:,.0f} incurred")


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
