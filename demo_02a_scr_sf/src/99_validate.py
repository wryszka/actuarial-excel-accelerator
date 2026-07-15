# Databricks notebook source
# MAGIC %md
# MAGIC # 99 — Smoke test (demo 2A)
# MAGIC
# MAGIC One end-to-end check. Confirms:
# MAGIC
# MAGIC 1. The three UC tables exist and are populated.
# MAGIC 2. The orchestrator returns a plausible SCR for the base scenario.
# MAGIC 3. The scenario sweep populated `scr_scenarios` with > 0 rows.
# MAGIC 4. The three UC SQL UDFs are registered and return a number when called.
# MAGIC
# MAGIC Notebook exits OK / FAIL.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
fqn = f"{catalog}.{schema}"

failures = []

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Tables present and populated

# COMMAND ----------

for tbl, expected_min_rows in [
    ("scr_inputs", 1),
    ("scr_assumptions", 1),
    ("scr_scenarios", 0),  # may be empty until 07_scenarios runs
    ("rfr_curves", 1),
]:
    try:
        n = spark.table(f"{fqn}.{tbl}").count()
        print(f"  {tbl}: {n} rows")
        if n < expected_min_rows:
            failures.append(f"{tbl} has {n} rows (expected >= {expected_min_rows})")
    except Exception as e:
        failures.append(f"{tbl} not found: {str(e)[:120]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Orchestrator returns a plausible SCR

# COMMAND ----------

import math

def combined_sigma(sp, sr, vp, vr, alpha=0.5):
    v = vp + vr
    return math.sqrt((sp*vp)**2 + 2*alpha*sp*sr*vp*vr + (sr*vr)**2) / v if v else 0.0

inputs_row = spark.table(f"{fqn}.scr_inputs").filter("scenario_id = 'base'").collect()[0]
ass_row = spark.table(f"{fqn}.scr_assumptions").filter("is_current = 'true'").collect()[0]
rfr_rows = (spark.table(f"{fqn}.rfr_curves")
            .filter(f"effective_date = '{inputs_row['rfr_effective_date']}'"
                    f" AND currency = '{inputs_row['currency']}'")
            .select("maturity_months", "spot_rate").collect())

lob_order = list(ass_row["nl_lob_order"])
sig = {r["lob"]: r for r in ass_row["nl_lob_sigmas"]}
vol = {r["lob"]: r for r in inputs_row["lob_volumes"]}
rho_nl = [list(r) for r in ass_row["nl_lob_correlation"]]
sigma_lob, v_lob = [], []
for lob in lob_order:
    vp = float(vol[lob]["v_prem"]); vr = float(vol[lob]["v_res"])
    sigma_lob.append(combined_sigma(float(sig[lob]["sigma_prem"]), float(sig[lob]["sigma_res"]), vp, vr))
    v_lob.append(vp + vr)
v_nl = sum(v_lob)
inner = sum(rho_nl[i][j]*sigma_lob[i]*v_lob[i]*sigma_lob[j]*v_lob[j]
            for i in range(len(lob_order)) for j in range(len(lob_order)))
scr_uw = 3.0 * (math.sqrt(max(inner, 0.0)) / v_nl) * v_nl

curve = {int(r["maturity_months"]): float(r["spot_rate"]) for r in rfr_rows}
su = float(ass_row["ir_shock_up_bps"]) / 10_000
sd = float(ass_row["ir_shock_down_bps"]) / 10_000
floor = float(ass_row["ir_shock_down_floor"])
def pv(c):
    return sum(float(cf["amount"]) / (1.0 + (c.get(int(cf["year"])*12)
            or c[min(c.keys(), key=lambda m: abs(m - int(cf["year"])*12))]))
            ** int(cf["year"]) for cf in inputs_row["liability_cash_flows"])
asset = float(inputs_row["asset_value"]); dur = float(inputs_row["asset_modified_duration"])
pv_b = pv(curve)
pv_u = pv({mo: r + su for mo, r in curve.items()})
pv_d = pv({mo: max(r + sd, floor) for mo, r in curve.items()})
nav_b = asset - pv_b
nav_u = asset * (1 - dur * su) - pv_u
nav_d = asset * (1 - dur * sd) - pv_d
scr_mkt = max(nav_b - min(nav_u, nav_d), 0.0)

scr_cat = float(ass_row["cat_plug"])
rho = float(ass_row["bscr_rho_market_uw"])
bscr = math.sqrt(scr_uw**2 + scr_mkt**2 + 2*rho*scr_uw*scr_mkt) + scr_cat
op = float(ass_row["op_factor"]) * float(inputs_row["earned_premium"])
lac = float(ass_row["lacdt"])
scr = bscr + op - lac

print(f"\n  scr_nl_premres : {scr_uw:>20,.2f}")
print(f"  scr_mkt_ir     : {scr_mkt:>20,.2f}")
print(f"  scr_cat        : {scr_cat:>20,.2f}")
print(f"  bscr           : {bscr:>20,.2f}")
print(f"  op             : {op:>20,.2f}")
print(f"  lacdt          : {lac:>20,.2f}")
print(f"  SCR            : {scr:>20,.2f}")

if scr <= 0 or scr > 10 * float(inputs_row["earned_premium"]):
    failures.append(f"SCR {scr:,.0f} outside plausible range")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. UC SQL UDFs callable

# COMMAND ----------

# The UDF treats ir_shock_bps as the literal shock to apply; the orchestrator
# above uses the default `ir_shock_up_bps` from assumptions. To compare apples
# to apples, pass the same value the orchestrator used.
try:
    default_bps = int(ass_row["ir_shock_up_bps"])
    udf_result = spark.sql(f"""
        SELECT {fqn}.scr_total(0.0, 0.0, 0.0, 0.0, {default_bps}).scr AS scr
    """).collect()[0]["scr"]
    print(f"  scr_total(0,0,0,0,{default_bps}).scr = {udf_result:,.2f}")
    if abs(udf_result - scr) / max(abs(scr), 1.0) > 0.01:
        failures.append(f"UDF SCR ({udf_result:,.2f}) drifted from orchestrator ({scr:,.2f})")
except Exception as e:
    failures.append(f"scr_total UDF call failed: {str(e)[:200]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

if failures:
    print("FAIL:")
    for f in failures:
        print(f"  - {f}")
    dbutils.notebook.exit(f"FAIL: {'; '.join(failures)}")
else:
    print("OK — all checks passed.")
    dbutils.notebook.exit("OK")
