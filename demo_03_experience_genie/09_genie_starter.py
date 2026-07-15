# Databricks notebook source
# MAGIC %md
# MAGIC # Use Case 3 · Genie in two acts
# MAGIC
# MAGIC **Act 1 (`mode = create_starter`)** — the "quick setup" moment: a Genie
# MAGIC space over **one table**, the claims listing. That's genuinely all it
# MAGIC takes — a commented table and a warehouse — and the ad-hoc questions an
# MAGIC Excel user answers with pivots become plain English.
# MAGIC
# MAGIC **Act 2 (`mode = extend`)** — the same space grows: the premium /
# MAGIC loss-ratio fact, the development triangle and the segment dimension are
# MAGIC added, and the questions get properly actuarial (loss ratios need
# MAGIC premium — one table can't answer them; four can). In a live walkthrough
# MAGIC you can equally do this in the Genie UI: space → Configure → Data →
# MAGIC **Add table** — that's the whole gesture this notebook automates.
# MAGIC
# MAGIC Idempotent per mode.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.dropdown("mode", "create_starter", ["create_starter", "extend", "reset_starter"])

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
mode = dbutils.widgets.get("mode")
fqn = f"{catalog}.{schema}"

TITLE = "Claims Analytics — Actuarial Excel Accelerator"

STARTER_TABLES = sorted([f"{fqn}.exp_claims_listing"])
EXTENDED_TABLES = sorted([
    f"{fqn}.exp_claims_listing",
    f"{fqn}.exp_gold_experience",
    f"{fqn}.exp_gold_triangle",
    f"{fqn}.exp_dim_segment",
])

DESCRIPTION = (
    "Ask questions about a UK general-insurance claims portfolio in plain English. "
    "Starts from the claims listing (one row per claim: line of business, region, "
    "channel, status, paid/outstanding/incurred, large-loss flag); extended with "
    "earned premium, loss ratios and development triangles for portfolio-level "
    "analysis. Incurred = paid + outstanding; loss ratio = incurred / earned "
    "premium. Synthetic demo data."
)

STARTER_QUESTIONS = [
    "How many claims do we have by line of business and status?",
    "What is the average incurred cost per claim by region?",
    "Show the ten largest open claims.",
    "Plot the number of reported claims by month in 2024.",
    "Which peril drives the most incurred cost for Motor?",
]
EXTENDED_QUESTIONS = [
    "What is the loss ratio by line of business and accident year? Plot it.",
    "Why is Motor 2023 worse than 2021 — break it down by region and channel.",
    "Which distribution channel runs the highest loss ratio?",
    "Plot cumulative paid vs incurred development for Liability accident year 2021.",
]

# COMMAND ----------

import json
import os
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
nb_path = (dbutils.notebook.entry_point.getDbutils().notebook()
           .getContext().notebookPath().get())
PARENT = "/Workspace" + os.path.dirname(nb_path)

tables = EXTENDED_TABLES if mode == "extend" else STARTER_TABLES
serialized = json.dumps(
    {"version": 2, "data_sources": {"tables": [{"identifier": t} for t in tables]}})

existing = [s for s in w.api_client.do("GET", "/api/2.0/genie/spaces").get("spaces", [])
            if s.get("title") == TITLE]

if mode == "reset_starter" and not existing:
    mode = "create_starter"  # nothing to reset — create fresh below

if mode == "reset_starter":
    # bring the space back to its act-1, single-table state
    space_id = existing[0]["space_id"]
    w.api_client.do("PATCH", f"/api/2.0/genie/spaces/{space_id}",
                    body={"serialized_space": serialized})
    print(f"✓ space {space_id} reset to the single-table starter state")
elif mode == "create_starter" and existing:
    space_id = existing[0]["space_id"]
    print(f"Starter space already exists: {space_id} — skipping create.")
elif mode == "create_starter":
    warehouses = list(w.warehouses.list())
    wh = next((x for x in warehouses if x.enable_serverless_compute), warehouses[0])
    resp = w.api_client.do("POST", "/api/2.0/genie/spaces", body={
        "title": TITLE, "description": DESCRIPTION, "warehouse_id": wh.id,
        "parent_path": PARENT, "serialized_space": serialized})
    space_id = resp["space_id"]
    print(f"✓ created starter Genie space over ONE table: {space_id}")
else:
    assert existing, "Run with mode=create_starter first."
    space_id = existing[0]["space_id"]
    try:
        w.api_client.do("PATCH", f"/api/2.0/genie/spaces/{space_id}",
                        body={"serialized_space": serialized})
        print(f"✓ extended space {space_id} to {len(tables)} tables")
    except Exception as e:
        print(f"[PATCH not supported here: {str(e)[:120]}]")
        print("Recreating the space with all four tables instead…")
        w.api_client.do("DELETE", f"/api/2.0/genie/spaces/{space_id}")
        warehouses = list(w.warehouses.list())
        wh = next((x for x in warehouses if x.enable_serverless_compute), warehouses[0])
        resp = w.api_client.do("POST", "/api/2.0/genie/spaces", body={
            "title": TITLE, "description": DESCRIPTION, "warehouse_id": wh.id,
            "parent_path": PARENT, "serialized_space": serialized})
        space_id = resp["space_id"]
        print(f"✓ recreated with 4 tables: {space_id}")

host = w.config.host.rstrip("/")
print(f"\nOpen: {host}/genie/rooms/{space_id}")
qs = EXTENDED_QUESTIONS if mode == "extend" else STARTER_QUESTIONS
print("\nQuestions to ask at this stage:")
for q in qs:
    print(f"  - {q}")
if mode == "create_starter":
    print("\nWhen ready for act 2, re-run this notebook with mode = extend")
    print("(or add the tables in the Genie UI: Configure → Data → Add table).")
