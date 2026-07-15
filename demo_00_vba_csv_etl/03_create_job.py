# Databricks notebook source
# MAGIC %md
# MAGIC # Demo 0 · Stage 2 — automate it
# MAGIC
# MAGIC Stage 1 replaced the macro with a notebook a human still runs. Stage 2
# MAGIC removes the human: a **Lakeflow job** with a **file-arrival trigger** on
# MAGIC the volume's `incoming/` folder. The vendor file lands (dropped by hand,
# MAGIC SFTP, or pulled from the vendor — doesn't matter), the job fires on its
# MAGIC own, and the same tables grow. Nobody runs anything.
# MAGIC
# MAGIC Idempotent: updates the job in place if it already exists. Serverless
# MAGIC compute; triggers fire within ~a minute of a new file appearing.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("brd_volume_name", "brd_landing")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
volume = dbutils.widgets.get("brd_volume_name")
incoming = f"/Volumes/{catalog}/{schema}/{volume}/incoming/"

JOB_NAME = "Demo 0 — Bordereau ETL (file-arrival)"

# COMMAND ----------

import os
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import jobs

w = WorkspaceClient()

nb_dir = os.path.dirname(
    dbutils.notebook.entry_point.getDbutils().notebook()
    .getContext().notebookPath().get())
etl_path = f"{nb_dir}/01_bordereau_etl"

task = jobs.Task(
    task_key="bordereau_etl",
    notebook_task=jobs.NotebookTask(
        notebook_path=etl_path,
        base_parameters={
            "catalog_name": catalog,
            "schema_name": schema,
            "brd_volume_name": volume,
        },
    ),
)
trigger = jobs.TriggerSettings(
    file_arrival=jobs.FileArrivalTriggerConfiguration(url=incoming),
    pause_status=jobs.PauseStatus.UNPAUSED,
)

existing = next((j for j in w.jobs.list(name=JOB_NAME)), None)
if existing:
    w.jobs.reset(job_id=existing.job_id, new_settings=jobs.JobSettings(
        name=JOB_NAME, tasks=[task], trigger=trigger, max_concurrent_runs=1))
    job_id = existing.job_id
    print(f"Updated job {job_id}")
else:
    job_id = w.jobs.create(name=JOB_NAME, tasks=[task], trigger=trigger,
                           max_concurrent_runs=1).job_id
    print(f"Created job {job_id}")

host = w.config.host.rstrip("/")
print(f"\nJob: {host}/jobs/{job_id}")
print(f"Watching: {incoming}")
print("\nStage-2 demo gesture: drop next month's CSV into incoming/ —")
print("the job fires by itself within ~a minute, then re-run 02_reconciliation")
print("with source_file = the new file name. Same numbers, zero hands.")
