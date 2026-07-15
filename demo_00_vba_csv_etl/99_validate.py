# Databricks notebook source
# MAGIC %md
# MAGIC # Demo 0 · Smoke test
# MAGIC
# MAGIC One row per check, fails loudly. Assumes at least one bordereau CSV has
# MAGIC been ingested (00 → upload → 01 → 03).

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

check("bronze populated (>= 44k/file)", lambda: (rows("brd_bronze_claims") >= 44_000,
                                                 f"{rows('brd_bronze_claims'):,}"))
check("silver populated", lambda: (rows("brd_silver_claims") > 40_000,
                                   f"{rows('brd_silver_claims'):,}"))
check("quarantine caught the silent drops", lambda: (rows("brd_quarantine") > 0,
                                                     f"{rows('brd_quarantine')}"))


def conservation():
    # per source file: distinct claim refs in bronze == silver + quarantine
    df = spark.sql(f"""
        WITH b AS (SELECT _source_file f, COUNT(DISTINCT ClaimRef) n
                   FROM {fqn}.brd_bronze_claims GROUP BY 1),
             s AS (SELECT _source_file f, COUNT(*) n
                   FROM {fqn}.brd_silver_claims GROUP BY 1),
             q AS (SELECT _source_file f, COUNT(*) n
                   FROM {fqn}.brd_quarantine GROUP BY 1)
        SELECT b.f, b.n AS bronze_refs,
               COALESCE(s.n,0) + COALESCE(q.n,0) AS silver_plus_quarantine
        FROM b LEFT JOIN s ON b.f = s.f LEFT JOIN q ON b.f = q.f
    """).collect()
    bad = [r for r in df if r.bronze_refs != r.silver_plus_quarantine]
    return (len(bad) == 0, f"{len(df)} file(s), all conserve rows" if not bad else str(bad[0]))


check("row conservation (nothing lost)", conservation)


def no_unparsed_money():
    n = spark.sql(f"SELECT COUNT(*) FROM {fqn}.brd_silver_claims "
                  "WHERE paid_gbp IS NULL OR outstanding_gbp IS NULL").first()[0]
    return (n == 0, f"{n} null amounts")


check("all amounts parsed", no_unparsed_money)


def job_exists():
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient()
    j = next((x for x in w.jobs.list(name="Demo 0 — Bordereau ETL (file-arrival)")), None)
    if not j:
        return (False, "job not found")
    s = w.jobs.get(j.job_id).settings
    has_trigger = s.trigger is not None and s.trigger.file_arrival is not None
    return (has_trigger, f"job {j.job_id}, file-arrival trigger "
            f"{'armed' if has_trigger else 'MISSING'}")


check("file-arrival job exists", job_exists)

# COMMAND ----------

import pandas as pd
df = pd.DataFrame(results, columns=["check", "status", "detail"])
display(spark.createDataFrame(df))
n_fail = (df.status == "FAIL").sum()
print(f"\n{len(df) - n_fail}/{len(df)} checks passed")
assert n_fail == 0, f"{n_fail} checks FAILED"
print("✓ ALL CHECKS PASSED")
