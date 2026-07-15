# Databricks notebook source
# MAGIC %md
# MAGIC # Demo 3 · Step 8 — Smoke test
# MAGIC
# MAGIC End-to-end check that the track is healthy: tables exist and are populated,
# MAGIC the three baked-in signals are actually present in gold, and the Genie
# MAGIC space + dashboard were created. One row per check, fails loudly.

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


def rows(table):
    return spark.table(f"{fqn}.{table}").count()

# COMMAND ----------

check("bronze claims rows > 500k", lambda: (rows("exp_bronze_claims_txn") > 500_000,
                                            f"{rows('exp_bronze_claims_txn'):,}"))
check("silver claims rows > 500k", lambda: (rows("exp_silver_claims") > 500_000,
                                            f"{rows('exp_silver_claims'):,}"))
check("gold experience populated", lambda: (rows("exp_gold_experience") > 0,
                                            f"{rows('exp_gold_experience')} rows"))
check("gold triangle populated", lambda: (rows("exp_gold_triangle") > 0,
                                          f"{rows('exp_gold_triangle')} rows"))
check("dim_segment = 100", lambda: (rows("exp_dim_segment") == 100, f"{rows('exp_dim_segment')}"))


def motor_signal():
    df = spark.sql(f"""
        SELECT accident_year, SUM(incurred)/SUM(earned_premium) lr
        FROM {fqn}.exp_gold_experience WHERE line_of_business='Motor'
        GROUP BY accident_year""").toPandas().set_index("accident_year").lr
    return (df[2023] > df[2021] + 0.10, f"Motor LR 2021={df[2021]:.2f} 2023={df[2023]:.2f}")


check("signal 1: Motor 2023 > 2021 by >10pts", motor_signal)


def channel_signal():
    df = spark.sql(f"""
        SELECT channel, SUM(incurred)/SUM(earned_premium) lr
        FROM {fqn}.exp_gold_experience GROUP BY channel""").toPandas().set_index("channel").lr
    return (df["Aggregator"] > df["Broker"], f"Aggregator={df['Aggregator']:.2f} Broker={df['Broker']:.2f}")


check("signal 3: Aggregator > Broker", channel_signal)


def scotland_signal():
    df = spark.sql(f"""
        SELECT accident_year, SUM(incurred)/SUM(earned_premium) lr
        FROM {fqn}.exp_gold_experience
        WHERE region='Scotland' AND line_of_business IN ('Home','CommercialProperty')
        GROUP BY accident_year""").toPandas().set_index("accident_year").lr
    return (df[2023] > df[2022] + 0.15, f"Scotland property LR 2022={df[2022]:.2f} 2023={df[2023]:.2f}")


check("signal 2: Scotland 2023 windstorm spike", scotland_signal)

# COMMAND ----------


def genie_exists():
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient()
    spaces = w.api_client.do("GET", "/api/2.0/genie/spaces").get("spaces", [])
    hit = [s for s in spaces if "Experience Monitoring" in s.get("title", "")]
    return (len(hit) > 0, hit[0]["space_id"] if hit else "not found")


def dashboard_exists():
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient()
    hit = [d for d in w.lakeview.list() if d.display_name == "Demo 3 — Portfolio Experience Monitoring"]
    return (len(hit) > 0, hit[0].dashboard_id if hit else "not found")


check("Genie space created", genie_exists)
check("AI/BI dashboard created", dashboard_exists)

# COMMAND ----------

import pandas as pd
df = pd.DataFrame(results, columns=["check", "status", "detail"])
display(spark.createDataFrame(df))

n_fail = (df.status == "FAIL").sum()
print(f"\n{'='*50}\n{len(df) - n_fail}/{len(df)} checks passed")
assert n_fail == 0, f"{n_fail} checks FAILED — see table above"
print("✓ ALL CHECKS PASSED")
