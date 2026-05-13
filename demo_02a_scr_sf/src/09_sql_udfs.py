# Databricks notebook source
# MAGIC %md
# MAGIC # 09 — Register UC Python SQL UDFs for the Excel round-trip
# MAGIC
# MAGIC Creates three Python UDFs in `{catalog}.{schema}`:
# MAGIC
# MAGIC | UDF | Returns | Used by |
# MAGIC | --- | --- | --- |
# MAGIC | `scr_nl_premres(motor, property, liability, other)` | DOUBLE | Excel Power Query (Round_Trip tab) |
# MAGIC | `scr_mkt_ir(ir_shock_bps)` | DOUBLE | Excel Power Query |
# MAGIC | `scr_total(motor, property, liability, other, ir_shock_bps)` | STRUCT<7 fields> | Excel Power Query |
# MAGIC
# MAGIC Python UDFs in UC can't read tables. We work around that by **baking the
# MAGIC current `scr_assumptions` row and `scr_inputs(base)` row into the UDF
# MAGIC body at deploy time**. Re-run this notebook whenever assumptions or
# MAGIC inputs change — UDFs refresh atomically.
# MAGIC
# MAGIC The RFR curve is also baked in (latest effective_date, currency from
# MAGIC the base inputs). That's a real-life trade-off: Excel users get a
# MAGIC fast, stateless function; the cost is that they're working off the
# MAGIC last assumption snapshot. The Lakeview dashboard and `07_scenarios_mlflow`
# MAGIC use the live tables.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_serverless_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
fqn = f"{catalog}.{schema}"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Pull the current snapshot and freeze it into Python literals

# COMMAND ----------

import json

inputs_row = spark.table(f"{fqn}.scr_inputs").filter("scenario_id = 'base'").collect()[0]
ass_row = spark.table(f"{fqn}.scr_assumptions").filter("is_current = 'true'").collect()[0]
rfr_rows = (spark.table(f"{fqn}.rfr_curves")
            .filter(f"effective_date = '{inputs_row['rfr_effective_date']}'"
                    f" AND currency = '{inputs_row['currency']}'")
            .select("maturity_months", "spot_rate").collect())

# Convert Row objects to plain Python so json.dumps works
def row_to_plain(r):
    out = {}
    for f in r.__fields__:
        v = r[f]
        if hasattr(v, "asDict"):
            out[f] = v.asDict()
        elif isinstance(v, list):
            out[f] = [row_to_plain(x) if hasattr(x, "__fields__") else x for x in v]
        elif hasattr(v, "isoformat"):
            out[f] = v.isoformat()
        else:
            out[f] = v
    return out

INPUTS_LITERAL = json.dumps(row_to_plain(inputs_row), default=str)
ASS_LITERAL = json.dumps(row_to_plain(ass_row), default=str)
RFR_LITERAL = json.dumps([(int(r["maturity_months"]), float(r["spot_rate"])) for r in rfr_rows])

print(f"Frozen snapshot:")
print(f"  scenario_id        : {inputs_row['scenario_id']}")
print(f"  assumption_version : {ass_row['assumption_version']}")
print(f"  rfr maturities     : {len(rfr_rows)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `scr_total(...)` — returns the full breakdown as a STRUCT
# MAGIC
# MAGIC The other two UDFs (`scr_nl_premres`, `scr_mkt_ir`) delegate to this
# MAGIC one. Python compute is embedded as a triple-quoted body.

# COMMAND ----------

COMPUTE_BODY = '''
import math, json
INP = json.loads(r"""''' + INPUTS_LITERAL + '''""")
ASS = json.loads(r"""''' + ASS_LITERAL + '''""")
RFR = json.loads(r"""''' + RFR_LITERAL + '''""")

def _scr(motor_uplift, property_uplift, liability_uplift, other_uplift, ir_shock_bps):
    upl = {"Motor": motor_uplift or 0.0, "Property": property_uplift or 0.0,
           "Liability": liability_uplift or 0.0, "Other": other_uplift or 0.0}
    lob_order = list(ASS["nl_lob_order"])
    sig = {r["lob"]: r for r in ASS["nl_lob_sigmas"]}
    vol = {r["lob"]: r for r in INP["lob_volumes"]}
    rho_nl = ASS["nl_lob_correlation"]
    sigma_lob, v_lob = [], []
    for lob in lob_order:
        u = 1.0 + upl.get(lob, 0.0)
        vp = float(vol[lob]["v_prem"]) * u
        vr = float(vol[lob]["v_res"]) * u
        v = vp + vr
        s = (math.sqrt((sig[lob]["sigma_prem"]*vp)**2
                       + 2*0.5*sig[lob]["sigma_prem"]*sig[lob]["sigma_res"]*vp*vr
                       + (sig[lob]["sigma_res"]*vr)**2) / v) if v else 0.0
        sigma_lob.append(s); v_lob.append(v)
    v_nl = sum(v_lob)
    inner = sum(rho_nl[i][j]*sigma_lob[i]*v_lob[i]*sigma_lob[j]*v_lob[j]
                for i in range(len(lob_order)) for j in range(len(lob_order)))
    sigma_nl = math.sqrt(max(inner, 0.0)) / v_nl if v_nl else 0.0
    scr_uw = 3.0 * sigma_nl * v_nl

    curve = {int(m): float(r) for (m, r) in RFR}
    su = (ir_shock_bps if ir_shock_bps is not None else ASS["ir_shock_up_bps"]) / 10000.0
    sd = float(ASS["ir_shock_down_bps"]) / 10000.0
    floor = float(ASS["ir_shock_down_floor"])
    def pv(c):
        out = 0.0
        for cf in INP["liability_cash_flows"]:
            yr = int(cf["year"])
            mo = yr * 12
            r = c.get(mo) or c[min(c.keys(), key=lambda m: abs(m - mo))]
            out += float(cf["amount"]) / (1.0 + r) ** yr
        return out
    asset = float(INP["asset_value"]); dur = float(INP["asset_modified_duration"])
    pv_b = pv(curve)
    pv_u = pv({mo: r + su for mo, r in curve.items()})
    pv_d = pv({mo: max(r + sd, floor) for mo, r in curve.items()})
    nav_b = asset - pv_b
    nav_u = asset * (1 - dur * su) - pv_u
    nav_d = asset * (1 - dur * sd) - pv_d
    scr_mkt = max(nav_b - min(nav_u, nav_d), 0.0)

    scr_cat = float(ASS["cat_plug"])
    rho = float(ASS["bscr_rho_market_uw"])
    bscr = math.sqrt(scr_uw**2 + scr_mkt**2 + 2*rho*scr_uw*scr_mkt) + scr_cat
    op = float(ASS["op_factor"]) * float(INP["earned_premium"])
    lac = float(ASS["lacdt"])
    scr = bscr + op - lac
    return {"scr_uw": float(scr_uw), "scr_mkt": float(scr_mkt), "scr_cat": float(scr_cat),
            "bscr": float(bscr), "op_risk": float(op), "lacdt": float(lac), "scr": float(scr)}
'''

# COMMAND ----------

# `scr_total` — full breakdown STRUCT
spark.sql(f"""
CREATE OR REPLACE FUNCTION {fqn}.scr_total(
    motor_uplift     DOUBLE,
    property_uplift  DOUBLE,
    liability_uplift DOUBLE,
    other_uplift     DOUBLE,
    ir_shock_bps     INT
)
RETURNS STRUCT<
    scr_uw    DOUBLE,
    scr_mkt   DOUBLE,
    scr_cat   DOUBLE,
    bscr      DOUBLE,
    op_risk   DOUBLE,
    lacdt     DOUBLE,
    scr       DOUBLE
>
LANGUAGE PYTHON
COMMENT 'Demo 2A — full SCR breakdown for an Excel round-trip. Snapshot of base scenario assumptions baked in at deploy time. Re-run 09_sql_udfs to refresh.'
AS $$
{COMPUTE_BODY}
return _scr(motor_uplift, property_uplift, liability_uplift, other_uplift, ir_shock_bps)
$$
""")
print("✓ scr_total")

# `scr_nl_premres` — scalar shortcut
spark.sql(f"""
CREATE OR REPLACE FUNCTION {fqn}.scr_nl_premres(
    motor_uplift DOUBLE, property_uplift DOUBLE,
    liability_uplift DOUBLE, other_uplift DOUBLE
)
RETURNS DOUBLE
LANGUAGE PYTHON
COMMENT 'Demo 2A — NL Premium & Reserve sub-module SCR.'
AS $$
{COMPUTE_BODY}
return _scr(motor_uplift, property_uplift, liability_uplift, other_uplift, None)["scr_uw"]
$$
""")
print("✓ scr_nl_premres")

# `scr_mkt_ir` — scalar shortcut
spark.sql(f"""
CREATE OR REPLACE FUNCTION {fqn}.scr_mkt_ir(ir_shock_bps INT)
RETURNS DOUBLE
LANGUAGE PYTHON
COMMENT 'Demo 2A — Market Interest Rate sub-module SCR.'
AS $$
{COMPUTE_BODY}
return _scr(0.0, 0.0, 0.0, 0.0, ir_shock_bps)["scr_mkt"]
$$
""")
print("✓ scr_mkt_ir")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Sanity-call from SQL

# COMMAND ----------

display(spark.sql(f"""
    SELECT
        ROUND({fqn}.scr_nl_premres(0.0, 0.0, 0.0, 0.0)/1e6, 1) AS base_uw_m,
        ROUND({fqn}.scr_nl_premres(0.10, 0.0, 0.0, 0.0)/1e6, 1) AS motor_up_10_uw_m,
        ROUND({fqn}.scr_mkt_ir(200)/1e6, 1)                    AS ir_up_200_m,
        {fqn}.scr_total(0.0, 0.0, 0.0, 0.0, 0).scr             AS base_total
"""))
