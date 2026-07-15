# Databricks notebook source
# MAGIC %md
# MAGIC # Use Case 3 · The starter dashboard — published for everyone
# MAGIC
# MAGIC The Excel act's pivots and charts, rebuilt once as an **AI/BI
# MAGIC dashboard** on the claims listing — then **published** so the whole
# MAGIC workspace sees the same live view instead of passing a workbook around.
# MAGIC
# MAGIC One page, from one table: KPI row (claims, incurred, average severity,
# MAGIC open share), incurred by line of business, monthly reporting trend,
# MAGIC status split by region, and the top-10 largest open claims. The
# MAGIC portfolio-level dashboard (loss ratios, development) is the separate
# MAGIC *Demo 3 — Portfolio Experience Monitoring* dashboard built by
# MAGIC `07_dashboard` — that's act 2.
# MAGIC
# MAGIC Idempotent — updates in place.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("warehouse_id", "a3b61648ea4809e3")
dbutils.widgets.text("dashboard_name", "Use Case 3 — Claims Ad-hoc Analytics")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
warehouse_id = dbutils.widgets.get("warehouse_id")
dashboard_name = dbutils.widgets.get("dashboard_name")
fqn = f"{catalog}.{schema}"

# COMMAND ----------

import json

DATASETS = [
    {"name": "ds_kpi", "displayName": "Portfolio KPIs", "queryLines": [
        f"SELECT COUNT(*) AS claims, SUM(incurred) AS incurred, "
        f"AVG(incurred) AS avg_severity, "
        f"ROUND(SUM(CASE WHEN status='Open' THEN 1 ELSE 0 END)/COUNT(*), 4) AS open_share "
        f"FROM {fqn}.exp_claims_listing"]},
    {"name": "ds_lob", "displayName": "Incurred by LOB", "queryLines": [
        f"SELECT line_of_business, ROUND(SUM(incurred),0) AS incurred "
        f"FROM {fqn}.exp_claims_listing GROUP BY line_of_business"]},
    {"name": "ds_trend", "displayName": "Monthly reported claims", "queryLines": [
        f"SELECT DATE_TRUNC('month', report_date) AS report_month, COUNT(*) AS claims "
        f"FROM {fqn}.exp_claims_listing GROUP BY 1"]},
    {"name": "ds_region", "displayName": "Status by region", "queryLines": [
        f"SELECT region, status, COUNT(*) AS claims "
        f"FROM {fqn}.exp_claims_listing GROUP BY region, status"]},
    {"name": "ds_top", "displayName": "Largest open claims", "queryLines": [
        f"SELECT claim_id, line_of_business, region, accident_date, "
        f"ROUND(incurred,0) AS incurred, ROUND(outstanding,0) AS outstanding "
        f"FROM {fqn}.exp_claims_listing WHERE status='Open' "
        f"ORDER BY incurred DESC LIMIT 10"]},
]


def _counter(name, ds, field, label, fmt=None):
    enc = {"fieldName": field}
    if fmt:
        enc["format"] = fmt
    return {"name": name, "queries": [{"name": "main_query", "query": {
        "datasetName": ds, "fields": [{"name": field, "expression": f"`{field}`"}],
        "disaggregated": True}}],
        "spec": {"version": 2, "widgetType": "counter",
                 "encodings": {"value": enc},
                 "frame": {"showTitle": True, "title": label}}}


GBP = {"type": "number-currency", "currencyCode": "GBP", "abbreviation": "compact"}

def _bar(name, ds, x, y, title, color=None):
    enc = {"x": {"fieldName": x, "scale": {"type": "categorical"},
                 "displayName": x.replace("_", " ").title()},
           "y": {"fieldName": y, "scale": {"type": "quantitative"},
                 "displayName": y.replace("_", " ").title()}}
    fields = [{"name": x, "expression": f"`{x}`"},
              {"name": y, "expression": f"SUM(`{y}`)"}]
    if color:
        enc["color"] = {"fieldName": color, "scale": {"type": "categorical"}}
        fields.append({"name": color, "expression": f"`{color}`"})
    return {"name": name, "queries": [{"name": "main_query", "query": {
        "datasetName": ds, "fields": fields, "disaggregated": False}}],
        "spec": {"version": 3, "widgetType": "bar", "encodings": enc,
                 "frame": {"showTitle": True, "title": title}}}


def _line(name, ds, x, y, title):
    return {"name": name, "queries": [{"name": "main_query", "query": {
        "datasetName": ds, "fields": [
            {"name": x, "expression": f"`{x}`"},
            {"name": y, "expression": f"SUM(`{y}`)"}], "disaggregated": False}}],
        "spec": {"version": 3, "widgetType": "line",
                 "encodings": {"x": {"fieldName": x, "scale": {"type": "temporal"},
                                     "displayName": "Report month"},
                               "y": {"fieldName": y, "scale": {"type": "quantitative"},
                                     "displayName": "Claims"}},
                 "frame": {"showTitle": True, "title": title}}}


def _table(name, ds, cols, title):
    return {"name": name, "queries": [{"name": "main_query", "query": {
        "datasetName": ds, "fields": [{"name": c, "expression": f"`{c}`"} for c in cols],
        "disaggregated": True}}],
        "spec": {"version": 1, "widgetType": "table",
                 "encodings": {"columns": [{"fieldName": c, "displayName": c} for c in cols]},
                 "frame": {"showTitle": True, "title": title}}}


PAGES = [{"name": "page_1", "displayName": "Claims analytics", "layout": [
    {"widget": _counter("c_n", "ds_kpi", "claims", "Claims"),
     "position": {"x": 0, "y": 0, "width": 2, "height": 3}},
    {"widget": _counter("c_inc", "ds_kpi", "incurred", "Total incurred", GBP),
     "position": {"x": 2, "y": 0, "width": 2, "height": 3}},
    {"widget": _counter("c_sev", "ds_kpi", "avg_severity", "Avg severity", GBP),
     "position": {"x": 4, "y": 0, "width": 2, "height": 3}},
    {"widget": _counter("c_open", "ds_kpi", "open_share", "Open share",
                        {"type": "number-percent"}),
     "position": {"x": 6, "y": 0, "width": 2, "height": 3}},
    {"widget": _bar("b_lob", "ds_lob", "line_of_business", "incurred",
                    "Incurred by line of business"),
     "position": {"x": 0, "y": 3, "width": 4, "height": 6}},
    {"widget": _line("l_trend", "ds_trend", "report_month", "claims",
                     "Reported claims by month"),
     "position": {"x": 4, "y": 3, "width": 4, "height": 6}},
    {"widget": _bar("b_region", "ds_region", "region", "claims",
                    "Claims by region and status", color="status"),
     "position": {"x": 0, "y": 9, "width": 4, "height": 6}},
    {"widget": _table("t_top", "ds_top",
                      ["claim_id", "line_of_business", "region", "accident_date",
                       "incurred", "outstanding"], "Ten largest open claims"),
     "position": {"x": 4, "y": 9, "width": 4, "height": 6}},
]}]

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create / update, publish, share with everyone

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
    out = w.lakeview.update(dashboard_id=existing.dashboard_id, dashboard=dashboards.Dashboard(
        display_name=dashboard_name, serialized_dashboard=json.dumps(spec_payload),
        warehouse_id=warehouse_id))
    print(f"Updated dashboard {out.dashboard_id}")
else:
    out = w.lakeview.create(dashboard=dashboards.Dashboard(
        display_name=dashboard_name, parent_path=parent_path,
        serialized_dashboard=json.dumps(spec_payload), warehouse_id=warehouse_id))
    print(f"Created dashboard {out.dashboard_id}")

# publish with embedded credentials so every viewer sees live data
w.lakeview.publish(dashboard_id=out.dashboard_id, warehouse_id=warehouse_id,
                   embed_credentials=True)

# share: everyone in the workspace can view the published dashboard
try:
    w.api_client.do("PATCH", f"/api/2.0/permissions/dashboards/{out.dashboard_id}", body={
        "access_control_list": [
            {"group_name": "users", "permission_level": "CAN_READ"}]})
    print("✓ shared: all workspace users CAN_READ")
except Exception as e:
    print(f"[share via UI instead: {str(e)[:120]}]")

host = w.config.host.rstrip("/")
print(f"\nPublished: {host}/dashboardsv3/{out.dashboard_id}/published")
print("Act 2 (portfolio view: loss ratios, development) is the dashboard from")
print("07_dashboard — 'Demo 3 — Portfolio Experience Monitoring'.")
