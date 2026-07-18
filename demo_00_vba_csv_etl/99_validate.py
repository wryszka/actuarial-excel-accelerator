# Databricks notebook source
# MAGIC %md
# MAGIC # Use Case 1 · Smoke test
# MAGIC One row per check, fails loudly. Run after 00 → 01 → 02.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
fqn = f"{catalog}.{schema}"

results = []


def check(name, fn):
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, str(e)[:160]
    results.append((name, "PASS" if ok else "FAIL", str(detail)))


def rows(t):
    return spark.table(f"{fqn}.{t}").count()

# COMMAND ----------

check("raw loaded (~200k)", lambda: (rows("brd_claims_raw") > 150_000, f"{rows('brd_claims_raw'):,}"))
check("clean claims produced", lambda: (rows("brd_claims_clean") > 150_000, f"{rows('brd_claims_clean'):,}"))
check("quarantine caught dropped rows", lambda: (rows("brd_quarantine") > 0, f"{rows('brd_quarantine')}"))


def conservation():
    b = spark.table(f"{fqn}.brd_claims_raw").select("ClaimRef").distinct().count()
    c = rows("brd_claims_clean") + rows("brd_quarantine")
    return (b == c, f"distinct raw refs {b} == clean+quarantine {c}")


check("nothing lost (dedup accounted for)", conservation)


def parity():
    from pyspark.sql import functions as F
    if not spark.catalog.tableExists(f"{fqn}.brd_excel_output"):
        return (False, "run 02_reconciliation first")
    e = spark.table(f"{fqn}.brd_excel_output").agg(F.round(F.sum("incurred_gbp"), 2)).first()[0]
    d = spark.table(f"{fqn}.brd_claims_clean").agg(F.round(F.sum("incurred_gbp"), 2)).first()[0]
    return (abs(e - d) <= 0.01, f"excel £{e:,.0f} vs databricks £{d:,.0f}")


check("Excel ⇄ Databricks incurred matches", parity)

# COMMAND ----------

import pandas as pd
df = pd.DataFrame(results, columns=["check", "status", "detail"])
display(spark.createDataFrame(df))
n_fail = (df.status == "FAIL").sum()
print(f"\n{len(df) - n_fail}/{len(df)} passed")
assert n_fail == 0, f"{n_fail} checks FAILED"
print("✓ ALL CHECKS PASSED")
