# Databricks notebook source
# MAGIC %md
# MAGIC # Use Case 2 · Smoke test
# MAGIC
# MAGIC One row per check, fails loudly. Run after 00 → 01 → 02 → 03 → 04.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("sfm_volume_name", "sfm_assets")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
volume = dbutils.widgets.get("sfm_volume_name")
fqn = f"{catalog}.{schema}"
vol_path = f"/Volumes/{catalog}/{schema}/{volume}"
MODEL_NAME = f"{fqn}.sfm_scr_model"

results = []


def check(name, fn):
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, str(e)[:160]
    results.append((name, "PASS" if ok else "FAIL", str(detail)))

# COMMAND ----------

def volume_files():
    files = {f.name for f in dbutils.fs.ls(vol_path)}
    need = {"SF_Model.xlsx", "sf_inputs.csv", "calibration_2025.json",
            "calibration_2026.json", "expected_entity_001.json"}
    missing = need - files
    return (not missing, f"missing: {missing}" if missing else "all 5 files present")


check("volume has all source files", volume_files)
check("inputs table = 100 entities",
      lambda: (spark.table(f"{fqn}.sfm_inputs").count() == 100,
               spark.table(f"{fqn}.sfm_inputs").count()))


def model_versions():
    import mlflow
    from mlflow import MlflowClient
    mlflow.set_registry_uri("databricks-uc")
    c = MlflowClient()
    v25 = c.get_model_version_by_alias(MODEL_NAME, "cal_2025").version
    v26 = c.get_model_version_by_alias(MODEL_NAME, "cal_2026").version
    ch = c.get_model_version_by_alias(MODEL_NAME, "champion").version
    return (v25 != v26, f"@cal_2025=v{v25} @cal_2026=v{v26} @champion=v{ch}")


check("model registered with both calibration aliases", model_versions)


def results_both_years():
    df = spark.sql(f"SELECT calibration_year, COUNT(*) n FROM {fqn}.sfm_results "
                   "GROUP BY 1 ORDER BY 1").collect()
    got = {r.calibration_year: r.n for r in df}
    return (got.get(2025) == 100 and got.get(2026) == 100, str(got))


check("results scored for both calibrations", results_both_years)


def parity():
    import json
    with open(f"{vol_path}/expected_entity_001.json") as f:
        oracle = json.load(f)
    bad = []
    for yr in (2025, 2026):
        got = spark.sql(f"SELECT scr FROM {fqn}.sfm_results "
                        f"WHERE entity_id='ENT-001' AND calibration_year={yr}").first()[0]
        exp = oracle[f"cal_{yr}"]["scr"]
        if abs(got - exp) > 0.01:
            bad.append(f"{yr}: {got} vs {exp}")
    return (not bad, "; ".join(bad) if bad else "ENT-001 ties out under both calibrations")


check("parity vs workbook oracle (both years)", parity)


def impact_sane():
    r = spark.sql(f"SELECT SUM(scr_delta)/SUM(scr_2025) p, COUNT(*) n "
                  f"FROM {fqn}.sfm_impact").first()
    return (r.n == 100 and 0.02 < r.p < 0.25,
            f"{r.n} entities, group impact {r.p:.1%}")


check("impact table populated and plausible", impact_sane)

# COMMAND ----------

import pandas as pd
df = pd.DataFrame(results, columns=["check", "status", "detail"])
display(spark.createDataFrame(df))
n_fail = (df.status == "FAIL").sum()
print(f"\n{len(df) - n_fail}/{len(df)} checks passed")
assert n_fail == 0, f"{n_fail} checks FAILED"
print("✓ ALL CHECKS PASSED")
