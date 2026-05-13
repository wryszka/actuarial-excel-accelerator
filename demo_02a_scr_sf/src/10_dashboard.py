# Databricks notebook source
# MAGIC %md
# MAGIC # 10 — Lakeview dashboard
# MAGIC
# MAGIC Creates a one-page AI/BI dashboard with three tiles:
# MAGIC
# MAGIC 1. **SCR waterfall** — BSCR + Op − LACDT = SCR for the base scenario
# MAGIC 2. **SCR breakdown** — bar chart of sub-module contributions
# MAGIC 3. **Top 5 worst scenarios** — table from `scr_scenarios`
# MAGIC
# MAGIC Uses the Databricks SDK's `LakeviewAPI` to publish a dashboard
# MAGIC programmatically. Idempotent — if the dashboard already exists in the
# MAGIC user's home folder it's updated in place.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_serverless_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("warehouse_id", "a3b61648ea4809e3")
dbutils.widgets.text("dashboard_name", "Demo 2A — SCR Standard Formula")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
warehouse_id = dbutils.widgets.get("warehouse_id")
dashboard_name = dbutils.widgets.get("dashboard_name")
fqn = f"{catalog}.{schema}"

# COMMAND ----------

import json

DATASETS = [
    {
        "name": "ds_scenarios",
        "displayName": "Scenario sweep",
        "queryLines": [
            f"SELECT scenario_id, shock_ir_bps, shock_motor_uplift, ",
            f"       shock_property_uplift, shock_liability_uplift, shock_other_uplift, ",
            f"       scr_nl_premres, scr_mkt_ir, scr_cat, bscr, op_risk, lacdt, scr ",
            f"FROM {fqn}.scr_scenarios",
        ],
    },
    {
        "name": "ds_base_breakdown",
        "displayName": "Base scenario breakdown",
        "queryLines": [
            f"SELECT 'NL P&R' AS module, scr_nl_premres AS value FROM {fqn}.scr_scenarios WHERE scenario_id='base' ",
            f"UNION ALL SELECT 'Market IR', scr_mkt_ir FROM {fqn}.scr_scenarios WHERE scenario_id='base' ",
            f"UNION ALL SELECT 'Cat (plug)', scr_cat FROM {fqn}.scr_scenarios WHERE scenario_id='base' ",
            f"UNION ALL SELECT 'Op risk',  op_risk     FROM {fqn}.scr_scenarios WHERE scenario_id='base' ",
            f"UNION ALL SELECT 'LACDT',    -lacdt      FROM {fqn}.scr_scenarios WHERE scenario_id='base'",
        ],
    },
    {
        "name": "ds_base_totals",
        "displayName": "Base totals",
        "queryLines": [
            f"SELECT bscr, op_risk, lacdt, scr ",
            f"FROM {fqn}.scr_scenarios WHERE scenario_id='base'",
        ],
    },
    {
        "name": "ds_worst",
        "displayName": "Top 5 worst",
        "queryLines": [
            f"SELECT scenario_id, shock_ir_bps, shock_motor_uplift, shock_property_uplift, ",
            f"       shock_liability_uplift, shock_other_uplift, ",
            f"       ROUND(bscr/1e6,1) AS bscr_m, ROUND(scr/1e6,1) AS scr_m ",
            f"FROM {fqn}.scr_scenarios ORDER BY scr DESC LIMIT 5",
        ],
    },
]


def _bar_widget(name: str, dataset: str, x_field: str, y_field: str) -> dict:
    return {
        "name": name,
        "queries": [{
            "name": "main_query",
            "query": {
                "datasetName": dataset,
                "fields": [
                    {"name": x_field, "expression": f"`{x_field}`"},
                    {"name": y_field, "expression": f"SUM(`{y_field}`)"},
                ],
                "disaggregated": False,
            },
        }],
        "spec": {
            "version": 3,
            "widgetType": "bar",
            "encodings": {
                "x": {"fieldName": x_field, "scale": {"type": "categorical"},
                      "displayName": x_field.replace("_", " ").title()},
                "y": {"fieldName": y_field, "scale": {"type": "quantitative"},
                      "displayName": y_field.replace("_", " ").title()},
            },
            "frame": {"showTitle": True,
                      "title": f"{y_field.replace('_', ' ').title()} by {x_field.replace('_', ' ').title()}"},
        },
    }


def _counter_widget(name: str, dataset: str, field: str, label: str) -> dict:
    return {
        "name": name,
        "queries": [{
            "name": "main_query",
            "query": {
                "datasetName": dataset,
                "fields": [{"name": field, "expression": f"`{field}`"}],
                "disaggregated": True,
            },
        }],
        "spec": {
            "version": 2,
            "widgetType": "counter",
            "encodings": {"value": {"fieldName": field, "format": {"type": "number-currency",
                                                                    "currencyCode": "EUR",
                                                                    "abbreviation": "compact"}}},
            "frame": {"showTitle": True, "title": label},
        },
    }


def _table_widget(name: str, dataset: str) -> dict:
    cols = ["scenario_id", "shock_ir_bps", "shock_motor_uplift",
            "shock_property_uplift", "shock_liability_uplift",
            "shock_other_uplift", "bscr_m", "scr_m"]
    return {
        "name": name,
        "queries": [{
            "name": "main_query",
            "query": {
                "datasetName": dataset,
                "fields": [{"name": c, "expression": f"`{c}`"} for c in cols],
                "disaggregated": True,
            },
        }],
        "spec": {
            "version": 1,
            "widgetType": "table",
            "encodings": {"columns": [{"fieldName": c, "displayName": c} for c in cols]},
            "frame": {"showTitle": True, "title": "Top 5 worst scenarios"},
        },
    }


PAGES = [{
    "name": "page_1",
    "displayName": "SCR overview",
    "layout": [
        {"widget": _counter_widget("bscr_counter",  "ds_base_totals", "bscr",    "BSCR (base)"),
         "position": {"x": 0, "y": 0, "width": 2, "height": 3}},
        {"widget": _counter_widget("op_counter",    "ds_base_totals", "op_risk", "Op risk (base)"),
         "position": {"x": 2, "y": 0, "width": 2, "height": 3}},
        {"widget": _counter_widget("lacdt_counter", "ds_base_totals", "lacdt",   "LACDT (base)"),
         "position": {"x": 4, "y": 0, "width": 2, "height": 3}},
        {"widget": _counter_widget("scr_counter",   "ds_base_totals", "scr",     "SCR (base)"),
         "position": {"x": 6, "y": 0, "width": 2, "height": 3}},
        {"widget": _bar_widget("breakdown_bar", "ds_base_breakdown", "module", "value"),
         "position": {"x": 0, "y": 3, "width": 4, "height": 6}},
        {"widget": _bar_widget("scenario_bar",  "ds_scenarios",      "scenario_id", "scr"),
         "position": {"x": 4, "y": 3, "width": 4, "height": 6}},
        {"widget": _table_widget("worst_table", "ds_worst"),
         "position": {"x": 0, "y": 9, "width": 8, "height": 5}},
    ],
}]

dashboard_spec = {
    "datasets": DATASETS,
    "pages": PAGES,
}

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create / update via the Lakeview API

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service import dashboards

w = WorkspaceClient()
me = w.current_user.me().user_name
parent_path = f"/Users/{me}"

existing = None
for d in w.lakeview.list():
    if d.display_name == dashboard_name:
        existing = d
        break

# Serialize datasets queryLines into a string the API expects
spec_payload = {
    "datasets": [
        {**ds, "queryLines": [" ".join(ds["queryLines"])]} for ds in DATASETS
    ],
    "pages": PAGES,
}

if existing:
    print(f"Updating existing dashboard {existing.dashboard_id}")
    out = w.lakeview.update(
        dashboard_id=existing.dashboard_id,
        dashboard=dashboards.Dashboard(
            display_name=dashboard_name,
            serialized_dashboard=json.dumps(spec_payload),
            warehouse_id=warehouse_id,
        ),
    )
else:
    print("Creating new dashboard")
    out = w.lakeview.create(
        dashboard=dashboards.Dashboard(
            display_name=dashboard_name,
            parent_path=parent_path,
            serialized_dashboard=json.dumps(spec_payload),
            warehouse_id=warehouse_id,
        )
    )

# Publish so the live link works
w.lakeview.publish(dashboard_id=out.dashboard_id, warehouse_id=warehouse_id)

print(f"\nDashboard ID: {out.dashboard_id}")
print(f"Open from the Databricks workspace UI → Dashboards → search '{dashboard_name}'.")
