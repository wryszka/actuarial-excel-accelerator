# Databricks notebook source
# MAGIC %md
# MAGIC # Demo 3 · Step 7 (Operate) — the AI/BI dashboard
# MAGIC
# MAGIC **Recipe step: Operate.** This is the board pack — the tab the actuary used
# MAGIC to screenshot into PowerPoint every quarter — rebuilt as a live **AI/BI
# MAGIC dashboard** bound to the `exp_gold_*` tables. It never needs a manual
# MAGIC refresh, and the three baked-in signals are visible at a glance:
# MAGIC
# MAGIC - **Loss ratio by line of business and accident year** — Motor 2022–23 climbs.
# MAGIC - **Loss ratio by channel** — Aggregator runs hot.
# MAGIC - **Loss ratio by region** — Scotland spikes (the 2023 windstorm).
# MAGIC - **Motor development** — cumulative incurred by cohort.
# MAGIC - **Worst segments** — the worklist.
# MAGIC
# MAGIC Published programmatically with the Lakeview API. Idempotent — updates in
# MAGIC place if the dashboard already exists.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_serverless_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("warehouse_id", "a3b61648ea4809e3")
dbutils.widgets.text("dashboard_name", "Demo 3 — Portfolio Experience Monitoring")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
warehouse_id = dbutils.widgets.get("warehouse_id")
dashboard_name = dbutils.widgets.get("dashboard_name")
fqn = f"{catalog}.{schema}"

# COMMAND ----------

import json

DATASETS = [
    {"name": "ds_totals", "displayName": "Portfolio totals", "queryLines": [
        f"SELECT SUM(earned_premium) AS earned_premium, SUM(incurred) AS incurred, "
        f"ROUND(SUM(incurred)/SUM(earned_premium),4) AS loss_ratio, "
        f"SUM(large_loss_incurred) AS large_loss_incurred FROM {fqn}.exp_gold_experience"]},
    {"name": "ds_lr_lob_ay", "displayName": "LR by LOB and accident year", "queryLines": [
        f"SELECT line_of_business, accident_year, "
        f"ROUND(SUM(incurred)/SUM(earned_premium),4) AS loss_ratio "
        f"FROM {fqn}.exp_gold_experience GROUP BY line_of_business, accident_year"]},
    {"name": "ds_lr_channel", "displayName": "LR by channel", "queryLines": [
        f"SELECT channel, ROUND(SUM(incurred)/SUM(earned_premium),4) AS loss_ratio "
        f"FROM {fqn}.exp_gold_experience GROUP BY channel"]},
    {"name": "ds_lr_region", "displayName": "LR by region", "queryLines": [
        f"SELECT region, ROUND(SUM(incurred)/SUM(earned_premium),4) AS loss_ratio "
        f"FROM {fqn}.exp_gold_experience GROUP BY region"]},
    {"name": "ds_motor_dev", "displayName": "Motor development", "queryLines": [
        f"SELECT accident_year, dev_month, cumulative_incurred "
        f"FROM {fqn}.exp_gold_triangle WHERE line_of_business='Motor' AND dev_month <= 48"]},
    {"name": "ds_worst", "displayName": "Worst segments", "queryLines": [
        f"SELECT line_of_business, region, channel, accident_year, "
        f"ROUND(earned_premium,0) AS earned_premium, ROUND(incurred,0) AS incurred, loss_ratio "
        f"FROM {fqn}.exp_gold_experience WHERE earned_premium > 200000 "
        f"ORDER BY loss_ratio DESC LIMIT 12"]},
]


def _counter(name, ds, field, label, pct=False):
    fmt = ({"type": "number-percent"} if pct
           else {"type": "number-currency", "currencyCode": "GBP", "abbreviation": "compact"})
    return {"name": name, "queries": [{"name": "main_query", "query": {
        "datasetName": ds, "fields": [{"name": field, "expression": f"`{field}`"}],
        "disaggregated": True}}],
        "spec": {"version": 2, "widgetType": "counter",
                 "encodings": {"value": {"fieldName": field, "format": fmt}},
                 "frame": {"showTitle": True, "title": label}}}


def _bar(name, ds, x, y, title, pct=True):
    yenc = {"fieldName": y, "scale": {"type": "quantitative"},
            "displayName": y.replace("_", " ").title()}
    if pct:
        yenc["format"] = {"type": "number-percent"}
    return {"name": name, "queries": [{"name": "main_query", "query": {
        "datasetName": ds, "fields": [
            {"name": x, "expression": f"`{x}`"},
            {"name": y, "expression": f"AVG(`{y}`)"}], "disaggregated": False}}],
        "spec": {"version": 3, "widgetType": "bar",
                 "encodings": {"x": {"fieldName": x, "scale": {"type": "categorical"},
                                     "displayName": x.replace("_", " ").title()}, "y": yenc},
                 "frame": {"showTitle": True, "title": title}}}


def _line(name, ds, x, y, color, title, pct=False):
    yenc = {"fieldName": y, "scale": {"type": "quantitative"},
            "displayName": y.replace("_", " ").title()}
    if pct:
        yenc["format"] = {"type": "number-percent"}
    return {"name": name, "queries": [{"name": "main_query", "query": {
        "datasetName": ds, "fields": [
            {"name": x, "expression": f"`{x}`"},
            {"name": y, "expression": f"AVG(`{y}`)"},
            {"name": color, "expression": f"`{color}`"}], "disaggregated": False}}],
        "spec": {"version": 3, "widgetType": "line",
                 "encodings": {"x": {"fieldName": x, "scale": {"type": "categorical"},
                                     "displayName": x.replace("_", " ").title()}, "y": yenc,
                               "color": {"fieldName": color, "scale": {"type": "categorical"},
                                         "displayName": color.replace("_", " ").title()}},
                 "frame": {"showTitle": True, "title": title}}}


def _table(name, ds, cols, title):
    return {"name": name, "queries": [{"name": "main_query", "query": {
        "datasetName": ds, "fields": [{"name": c, "expression": f"`{c}`"} for c in cols],
        "disaggregated": True}}],
        "spec": {"version": 1, "widgetType": "table",
                 "encodings": {"columns": [{"fieldName": c, "displayName": c} for c in cols]},
                 "frame": {"showTitle": True, "title": title}}}


PAGES = [{"name": "page_1", "displayName": "Portfolio experience", "layout": [
    {"widget": _counter("c_ep", "ds_totals", "earned_premium", "Earned premium"),
     "position": {"x": 0, "y": 0, "width": 2, "height": 3}},
    {"widget": _counter("c_inc", "ds_totals", "incurred", "Incurred"),
     "position": {"x": 2, "y": 0, "width": 2, "height": 3}},
    {"widget": _counter("c_lr", "ds_totals", "loss_ratio", "Blended loss ratio", pct=True),
     "position": {"x": 4, "y": 0, "width": 2, "height": 3}},
    {"widget": _counter("c_ll", "ds_totals", "large_loss_incurred", "Large-loss incurred"),
     "position": {"x": 6, "y": 0, "width": 2, "height": 3}},
    {"widget": _line("l_lob", "ds_lr_lob_ay", "accident_year", "loss_ratio", "line_of_business",
                     "Loss ratio by line of business & accident year", pct=True),
     "position": {"x": 0, "y": 3, "width": 4, "height": 6}},
    {"widget": _line("l_motor", "ds_motor_dev", "dev_month", "cumulative_incurred", "accident_year",
                     "Motor development — cumulative incurred by cohort"),
     "position": {"x": 4, "y": 3, "width": 4, "height": 6}},
    {"widget": _bar("b_channel", "ds_lr_channel", "channel", "loss_ratio",
                    "Loss ratio by channel (Aggregator runs hot)"),
     "position": {"x": 0, "y": 9, "width": 4, "height": 6}},
    {"widget": _bar("b_region", "ds_lr_region", "region", "loss_ratio",
                    "Loss ratio by region (Scotland 2023 windstorm)"),
     "position": {"x": 4, "y": 9, "width": 4, "height": 6}},
    {"widget": _table("t_worst", "ds_worst",
                      ["line_of_business", "region", "channel", "accident_year",
                       "earned_premium", "incurred", "loss_ratio"], "Worst segments — the worklist"),
     "position": {"x": 0, "y": 15, "width": 8, "height": 6}},
]}]

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create / update via the Lakeview API

# COMMAND ----------

import os
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import dashboards

w = WorkspaceClient()
nb_path = (dbutils.notebook.entry_point.getDbutils().notebook()
           .getContext().notebookPath().get())
parent_path = "/Workspace" + os.path.dirname(nb_path)

spec_payload = {
    "datasets": [{**ds, "queryLines": [" ".join(ds["queryLines"])]} for ds in DATASETS],
    "pages": PAGES,
}

existing = next((d for d in w.lakeview.list() if d.display_name == dashboard_name), None)
if existing:
    print(f"Updating existing dashboard {existing.dashboard_id}")
    out = w.lakeview.update(dashboard_id=existing.dashboard_id, dashboard=dashboards.Dashboard(
        display_name=dashboard_name, serialized_dashboard=json.dumps(spec_payload),
        warehouse_id=warehouse_id))
else:
    print("Creating new dashboard")
    out = w.lakeview.create(dashboard=dashboards.Dashboard(
        display_name=dashboard_name, parent_path=parent_path,
        serialized_dashboard=json.dumps(spec_payload), warehouse_id=warehouse_id))

w.lakeview.publish(dashboard_id=out.dashboard_id, warehouse_id=warehouse_id)
host = w.config.host.rstrip("/")
print(f"\nDashboard ID: {out.dashboard_id}")
print(f"Open: {host}/dashboardsv3/{out.dashboard_id}/published")

# COMMAND ----------

print("Dashboard ready. Next: 99_validate.py")
