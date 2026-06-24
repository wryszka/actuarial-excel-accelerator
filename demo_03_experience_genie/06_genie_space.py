# Databricks notebook source
# MAGIC %md
# MAGIC # Demo 3 · Step 6 (Operate) — the Genie space
# MAGIC
# MAGIC **Recipe step: Operate.** This is the half that no Excel macro can do. The
# MAGIC `exp_gold_*` tables are fully commented, so **AI/BI Genie** can answer an
# MAGIC actuary's questions in plain English — *"what's the Motor 2023 loss ratio
# MAGIC by region?"* — and the "can you also slice it by…" email never has to be
# MAGIC answered by hand again.
# MAGIC
# MAGIC Creates the **`Experience Monitoring — Actuarial Excel Accelerator`** Genie
# MAGIC space over the three gold tables. Idempotent: skips if it already exists.
# MAGIC
# MAGIC > This API version accepts data sources on create; curated sample questions
# MAGIC > and instructions are added in the Genie UI afterwards. The suggested
# MAGIC > question set is printed below and listed in the README.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_serverless_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
fqn = f"{catalog}.{schema}"

TITLE = "Experience Monitoring — Actuarial Excel Accelerator"

# data_sources.tables must be sorted by identifier (API quirk)
TABLES = sorted([
    f"{fqn}.exp_gold_experience",
    f"{fqn}.exp_gold_triangle",
    f"{fqn}.exp_dim_segment",
])

DESCRIPTION = (
    "Ask questions about a UK general-insurance book's claims experience: loss ratios by "
    "line of business, region, distribution channel and accident year; how a cohort develops "
    "over time (paid and incurred triangles); large-loss impact; frequency and severity. "
    "Loss ratio = incurred (paid + outstanding) / earned premium. This Genie space replaces "
    "the ad-hoc 'can you also show me X by Y' pivot-table requests an actuary fields by email. "
    "Synthetic demo data."
)

SAMPLE_QUESTIONS = [
    "What is the Motor loss ratio by accident year? Plot it.",
    "Why is Motor 2023 worse than 2021 — break the loss ratio down by region and channel.",
    "Which distribution channel has the highest loss ratio across all lines of business?",
    "Show me the Scotland Home and Commercial Property loss ratio by accident year.",
    "Which segment had the biggest large-loss impact in 2023?",
    "Plot cumulative paid vs incurred development for Liability accident year 2021.",
    "Rank lines of business by 2024 loss ratio.",
    "What is the blended loss ratio for the whole book in 2024?",
]

# COMMAND ----------

import json
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# Land the space in this notebook's own workspace folder.
nb_path = (dbutils.notebook.entry_point.getDbutils().notebook()
           .getContext().notebookPath().get())
import os
PARENT = "/Workspace" + os.path.dirname(nb_path)

# COMMAND ----------

existing = w.api_client.do("GET", "/api/2.0/genie/spaces").get("spaces", [])
match = [s for s in existing if s.get("title") == TITLE]
if match:
    space_id = match[0]["space_id"]
    print(f"Genie space already exists: {space_id} — skipping create.")
else:
    warehouses = list(w.warehouses.list())
    wh = next((x for x in warehouses if x.enable_serverless_compute), warehouses[0])
    body = {
        "title": TITLE,
        "description": DESCRIPTION,
        "warehouse_id": wh.id,
        "parent_path": PARENT,
        "serialized_space": json.dumps(
            {"version": 2, "data_sources": {"tables": [{"identifier": t} for t in TABLES]}}
        ),
    }
    resp = w.api_client.do("POST", "/api/2.0/genie/spaces", body=body)
    space_id = resp["space_id"]
    print(f"Created Genie space: {space_id} (warehouse {wh.name})")

host = w.config.host.rstrip("/")
print(f"\nOpen: {host}/genie/rooms/{space_id}")
print("\nQuestions worth asking live (paste these into the space as sample questions):")
for q in SAMPLE_QUESTIONS:
    print(f"  - {q}")

# COMMAND ----------

print("Genie space ready. Next: 07_dashboard.py")
