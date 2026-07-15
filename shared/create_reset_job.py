# Databricks notebook source
# MAGIC %md
# MAGIC # Create the reset job (backs the app's Reset buttons)
# MAGIC
# MAGIC Creates the Lakeflow job **"Excel Accelerator — Reset"**: one task
# MAGIC running `reset_dispatcher` with a `scenario` job parameter
# MAGIC (`uc1|uc2|uc3|uc4|all`). The app triggers it with run-now; it also runs
# MAGIC fine from the Jobs UI. Idempotent — updates in place.
# MAGIC
# MAGIC If the app is deployed, pass its service principal's **client id** in
# MAGIC the `app_service_principal` widget and this notebook grants it
# MAGIC `CAN_MANAGE_RUN` so the Reset buttons work.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("warehouse_id", "a3b61648ea4809e3")
dbutils.widgets.text("app_service_principal", "")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
warehouse_id = dbutils.widgets.get("warehouse_id")
app_sp = dbutils.widgets.get("app_service_principal").strip()

JOB_NAME = "Excel Accelerator — Reset"

# COMMAND ----------

import os
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import jobs

w = WorkspaceClient()
nb_dir = os.path.dirname(
    dbutils.notebook.entry_point.getDbutils().notebook()
    .getContext().notebookPath().get())

task = jobs.Task(
    task_key="reset",
    notebook_task=jobs.NotebookTask(
        notebook_path=f"{nb_dir}/reset_dispatcher",
        base_parameters={
            "catalog_name": catalog,
            "schema_name": schema,
            "warehouse_id": warehouse_id,
            "scenario": "{{job.parameters.scenario}}",
        },
    ),
    timeout_seconds=5400,
)
params = [jobs.JobParameterDefinition(name="scenario", default="all")]

existing = next((j for j in w.jobs.list(name=JOB_NAME)), None)
if existing:
    w.jobs.reset(job_id=existing.job_id, new_settings=jobs.JobSettings(
        name=JOB_NAME, tasks=[task], parameters=params, max_concurrent_runs=1))
    job_id = existing.job_id
    print(f"Updated job {job_id}")
else:
    job_id = w.jobs.create(name=JOB_NAME, tasks=[task], parameters=params,
                           max_concurrent_runs=1).job_id
    print(f"Created job {job_id}")

host = w.config.host.rstrip("/")
print(f"Job: {host}/jobs/{job_id}")

# COMMAND ----------

if app_sp:
    w.api_client.do("PATCH", f"/api/2.0/permissions/jobs/{job_id}", body={
        "access_control_list": [
            {"service_principal_name": app_sp, "permission_level": "CAN_MANAGE_RUN"}]})
    print(f"✓ granted CAN_MANAGE_RUN on job {job_id} to SP {app_sp}")
else:
    print("No app_service_principal given — grant CAN_MANAGE_RUN later if you deploy the app.")
