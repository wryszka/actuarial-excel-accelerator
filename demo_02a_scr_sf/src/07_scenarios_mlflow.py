# Databricks notebook source
# MAGIC %md
# MAGIC # 07 — Scenario sweep with MLflow
# MAGIC
# MAGIC The migration target for the Excel `RunScenarios()` macro. Runs ~30
# MAGIC shock combinations through the orchestrator. Each scenario is logged
# MAGIC to MLflow as a run with params (shocks) + metrics (sub-module SCRs +
# MAGIC total SCR). Results are also written to `scr_scenarios` for the
# MAGIC dashboard.
# MAGIC
# MAGIC The Excel macro produces 30 rows on the `Scenarios` tab; this notebook
# MAGIC produces 30 MLflow runs you can compare in the experiment UI **and**
# MAGIC 30 rows in the gold table. Same result, governable.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_serverless_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("experiment_name", "")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
fqn = f"{catalog}.{schema}"

me = (
    dbutils.notebook.entry_point.getDbutils().notebook().getContext()
    .userName().getOrElse(None)
)
# Default to a single-folder path directly under /Users/<me>/ — MLflow
# doesn't create intermediate folders. Override via the widget if you
# want to nest under an existing folder.
exp = dbutils.widgets.get("experiment_name").strip() \
      or f"/Users/{me}/scr_sweep_demo_2a"

print(f"Experiment: {exp}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Inline orchestrator (same body as 06_orchestrator.py)

# COMMAND ----------

import math
import datetime as dt

def combined_sigma(sp, sr, vp, vr, alpha=0.5):
    v = vp + vr
    if v == 0:
        return 0.0
    return math.sqrt((sp*vp)**2 + 2*alpha*sp*sr*vp*vr + (sr*vr)**2) / v


def nl_premres_scr(inputs_row, ass_row, lob_uplifts):
    lob_order = list(ass_row["nl_lob_order"])
    sigmas = {r["lob"]: r for r in ass_row["nl_lob_sigmas"]}
    vols = {r["lob"]: r for r in inputs_row["lob_volumes"]}
    rho = [list(row) for row in ass_row["nl_lob_correlation"]]
    sigma_lob, v_lob = [], []
    for lob in lob_order:
        u = 1.0 + lob_uplifts.get(lob, 0.0)
        vp, vr = float(vols[lob]["v_prem"]) * u, float(vols[lob]["v_res"]) * u
        sigma_lob.append(combined_sigma(
            float(sigmas[lob]["sigma_prem"]), float(sigmas[lob]["sigma_res"]), vp, vr))
        v_lob.append(vp + vr)
    v_nl = sum(v_lob)
    if v_nl == 0:
        return 0.0
    inner = sum(rho[i][j]*sigma_lob[i]*v_lob[i]*sigma_lob[j]*v_lob[j]
                for i in range(len(lob_order)) for j in range(len(lob_order)))
    return 3.0 * (math.sqrt(max(inner, 0.0)) / v_nl) * v_nl


def market_ir_scr(inputs_row, ass_row, rfr_rows, ir_bps=None):
    curve = {int(r["maturity_months"]): float(r["spot_rate"]) for r in rfr_rows}
    su = (ir_bps or ass_row["ir_shock_up_bps"]) / 10_000
    sd = float(ass_row["ir_shock_down_bps"]) / 10_000
    floor = float(ass_row["ir_shock_down_floor"])

    def pv(c):
        s = 0.0
        for cf in inputs_row["liability_cash_flows"]:
            yr = int(cf["year"])
            mo = yr * 12
            r = c.get(mo) or c[min(c.keys(), key=lambda m: abs(m - mo))]
            s += float(cf["amount"]) / (1.0 + r) ** yr
        return s

    def sh(d, fl=False):
        return {mo: (max(r + d, floor) if fl else r + d) for mo, r in curve.items()}

    asset = float(inputs_row["asset_value"])
    dur = float(inputs_row["asset_modified_duration"])
    nav_b = asset - pv(curve)
    nav_u = asset * (1 - dur * su) - pv(sh(su))
    nav_d = asset * (1 - dur * sd) - pv(sh(sd, fl=True))
    return max(nav_b - min(nav_u, nav_d), 0.0)


def compute_scr_row(inputs_row, ass_row, rfr_rows, ir_bps, lob_uplifts):
    scr_uw = nl_premres_scr(inputs_row, ass_row, lob_uplifts)
    scr_mkt = market_ir_scr(inputs_row, ass_row, rfr_rows, ir_bps)
    scr_cat = float(ass_row["cat_plug"])
    rho = float(ass_row["bscr_rho_market_uw"])
    bscr = math.sqrt(scr_uw**2 + scr_mkt**2 + 2*rho*scr_uw*scr_mkt) + scr_cat
    op = float(ass_row["op_factor"]) * float(inputs_row["earned_premium"])
    lac = float(ass_row["lacdt"])
    scr = bscr + op - lac
    return scr_uw, scr_mkt, scr_cat, bscr, op, lac, scr


# COMMAND ----------

# MAGIC %md
# MAGIC ## Pull inputs, assumptions, RFR — once

# COMMAND ----------

inputs_row = spark.table(f"{fqn}.scr_inputs").filter("scenario_id = 'base'").collect()[0]
ass_row = spark.table(f"{fqn}.scr_assumptions").filter("is_current = 'true'").collect()[0]
rfr_rows = (spark.table(f"{fqn}.rfr_curves")
            .filter(f"effective_date = '{inputs_row['rfr_effective_date']}'"
                    f" AND currency = '{inputs_row['currency']}'")
            .select("maturity_months", "spot_rate").collect())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Define the scenario grid
# MAGIC
# MAGIC 30 scenarios total: a baseline + 29 single-factor or pair shocks.

# COMMAND ----------

# (id, ir_bps, motor_up, property_up, liability_up, other_up)
SCENARIOS = [
    ("base",                 0,    0.00, 0.00, 0.00, 0.00),
    # IR-only
    ("ir_up_100",            100,  0.00, 0.00, 0.00, 0.00),
    ("ir_up_200",            200,  0.00, 0.00, 0.00, 0.00),
    ("ir_up_300",            300,  0.00, 0.00, 0.00, 0.00),
    ("ir_down_100",         -100,  0.00, 0.00, 0.00, 0.00),
    ("ir_down_200",         -200,  0.00, 0.00, 0.00, 0.00),
    # Single-LoB uplifts
    ("motor_up_5",           0,    0.05, 0.00, 0.00, 0.00),
    ("motor_up_10",          0,    0.10, 0.00, 0.00, 0.00),
    ("motor_up_20",          0,    0.20, 0.00, 0.00, 0.00),
    ("property_up_5",        0,    0.00, 0.05, 0.00, 0.00),
    ("property_up_10",       0,    0.00, 0.10, 0.00, 0.00),
    ("property_up_20",       0,    0.00, 0.20, 0.00, 0.00),
    ("liability_up_10",      0,    0.00, 0.00, 0.10, 0.00),
    ("liability_up_20",      0,    0.00, 0.00, 0.20, 0.00),
    ("other_up_10",          0,    0.00, 0.00, 0.00, 0.10),
    ("other_up_20",          0,    0.00, 0.00, 0.00, 0.20),
    # Combined
    ("ir_up_motor_10",       200,  0.10, 0.00, 0.00, 0.00),
    ("ir_up_property_10",    200,  0.00, 0.10, 0.00, 0.00),
    ("ir_up_all_10",         200,  0.10, 0.10, 0.10, 0.10),
    ("ir_down_motor_10",    -200,  0.10, 0.00, 0.00, 0.00),
    # Stress
    ("stress_recession",     200,  0.10, 0.20, 0.20, 0.15),
    ("stress_soft_market",  -100, -0.05,-0.05,-0.05,-0.05),
    ("stress_hardening_mkt", 0,    0.15, 0.15, 0.10, 0.10),
    # LoB combos
    ("motor_property_10",    0,    0.10, 0.10, 0.00, 0.00),
    ("liability_other_20",   0,    0.00, 0.00, 0.20, 0.20),
    ("motor_liability_10",   0,    0.10, 0.00, 0.10, 0.00),
    # Extreme single-factor
    ("ir_extreme_down",     -300,  0.00, 0.00, 0.00, 0.00),
    ("motor_extreme",        0,    0.50, 0.00, 0.00, 0.00),
    ("liability_extreme",    0,    0.00, 0.00, 0.50, 0.00),
    ("all_LoB_up_15",        0,    0.15, 0.15, 0.15, 0.15),
]
print(f"Scenarios: {len(SCENARIOS)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run the sweep — one MLflow run per scenario

# COMMAND ----------

import mlflow

mlflow.set_experiment(exp)

results = []
with mlflow.start_run(run_name=f"scr_sweep_{dt.datetime.utcnow():%Y%m%dT%H%M%SZ}") as parent:
    for sid, ir, motor, prop, liab, other in SCENARIOS:
        with mlflow.start_run(run_name=sid, nested=True) as child:
            uplifts = {"Motor": motor, "Property": prop, "Liability": liab, "Other": other}
            scr_uw, scr_mkt, scr_cat, bscr, op, lac, scr = compute_scr_row(
                inputs_row, ass_row, rfr_rows, ir, uplifts,
            )
            mlflow.log_params({
                "scenario_id": sid,
                "ir_shock_bps": ir,
                "motor_uplift": motor,
                "property_uplift": prop,
                "liability_uplift": liab,
                "other_uplift": other,
                "assumption_version": ass_row["assumption_version"],
            })
            mlflow.log_metrics({
                "scr_nl_premres": scr_uw,
                "scr_mkt_ir": scr_mkt,
                "scr_cat": scr_cat,
                "bscr": bscr,
                "op_risk": op,
                "lacdt": lac,
                "scr": scr,
            })
            results.append((
                sid, child.info.run_id, ass_row["assumption_version"],
                ir, motor, prop, liab, other,
                scr_uw, scr_mkt, scr_cat, bscr, op, lac, scr,
                dt.datetime.utcnow(),
            ))
    print(f"Parent run: {parent.info.run_id}")
    print(f"Experiment: {exp}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Persist to `scr_scenarios`

# COMMAND ----------

from pyspark.sql.types import (StructType, StructField, StringType, IntegerType,
                                DoubleType, TimestampType)

scr_scenarios_schema = StructType([
    StructField("scenario_id", StringType()),
    StructField("run_id", StringType()),
    StructField("assumption_version", StringType()),
    StructField("shock_ir_bps", IntegerType()),
    StructField("shock_motor_uplift", DoubleType()),
    StructField("shock_property_uplift", DoubleType()),
    StructField("shock_liability_uplift", DoubleType()),
    StructField("shock_other_uplift", DoubleType()),
    StructField("scr_nl_premres", DoubleType()),
    StructField("scr_mkt_ir", DoubleType()),
    StructField("scr_cat", DoubleType()),
    StructField("bscr", DoubleType()),
    StructField("op_risk", DoubleType()),
    StructField("lacdt", DoubleType()),
    StructField("scr", DoubleType()),
    StructField("run_ts", TimestampType()),
])
spark.createDataFrame(results, scr_scenarios_schema) \
    .write.mode("append").saveAsTable(f"{fqn}.scr_scenarios")

print(f"✓ wrote {len(results)} rows → {fqn}.scr_scenarios")

# COMMAND ----------

display(spark.sql(f"""
    SELECT scenario_id, shock_ir_bps,
           ROUND(scr_nl_premres/1e6, 1) AS scr_uw_m,
           ROUND(scr_mkt_ir/1e6, 1)     AS scr_mkt_m,
           ROUND(bscr/1e6, 1)           AS bscr_m,
           ROUND(scr/1e6, 1)            AS scr_m
    FROM {fqn}.scr_scenarios
    ORDER BY scr DESC
    LIMIT 30
"""))
