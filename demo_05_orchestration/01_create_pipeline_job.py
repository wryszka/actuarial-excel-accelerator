# Databricks notebook source
# MAGIC %md
# MAGIC # Use Case 5 · Connect it all — one scheduled pipeline
# MAGIC
# MAGIC The first four use cases each fixed one job an actuary does in Excel:
# MAGIC clean the data (UC1), run the model (UC2), report on it (UC3), build a
# MAGIC step with no code (UC4). This one **connects them into a single pipeline
# MAGIC that runs on a schedule** — the whole month-end, start to finish, with no
# MAGIC one opening a spreadsheet.
# MAGIC
# MAGIC It creates a **Lakeflow Job** called *Excel Accelerator — Month-end
# MAGIC pipeline* with three tasks that run in order:
# MAGIC
# MAGIC | Order | Task | Notebook | What it does |
# MAGIC |---|---|---|---|
# MAGIC | 1 | **clean** | `demo_00.../01_clean_claims` | clean the monthly claims (UC1) |
# MAGIC | 2 | **model** | `demo_02b.../03_score` | score the capital model (UC2) |
# MAGIC | 3 | **report** | `demo_03.../08_claims_listing` | refresh the reporting table (UC3) |
# MAGIC
# MAGIC Each task only starts when the one before it succeeds. The tasks are the
# MAGIC exact notebooks from UC1–UC3 — nothing new to maintain; the job just
# MAGIC wires them together. Run this notebook (**Run all**) once to create the
# MAGIC job, then open it from the link it prints.
# MAGIC
# MAGIC > This use case is the finale of the story, but it still stands alone: it
# MAGIC > just needs UC1–UC3's notebooks to exist in the workspace (they do).

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")

JOB_NAME = "Excel Accelerator — Month-end pipeline"
BASE = "/Workspace/Shared/actuarial-excel-accelerator"

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service import jobs

w = WorkspaceClient()

common = {"catalog_name": catalog, "schema_name": schema}


def nb_task(key, path, params, depends=None):
    return jobs.Task(
        task_key=key,
        notebook_task=jobs.NotebookTask(notebook_path=path, base_parameters=params),
        depends_on=[jobs.TaskDependency(task_key=d) for d in (depends or [])],
        timeout_seconds=3600,
    )


tasks = [
    nb_task("clean",  f"{BASE}/demo_00_vba_csv_etl/01_clean_claims",
            {**common, "brd_volume_name": "brd_landing", "source": "table"}),
    nb_task("model",  f"{BASE}/demo_02b_sf_model_uc/03_score",
            {**common, "sfm_volume_name": "sfm_assets", "model_alias": "cal_2026"},
            depends=["clean"]),
    nb_task("report", f"{BASE}/demo_03_experience_genie/08_claims_listing",
            {**common, "exp_volume_name": "exp_landing"},
            depends=["model"]),
]

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create (or update) the job

# COMMAND ----------

existing = next((j for j in w.jobs.list(name=JOB_NAME)), None)
settings = dict(name=JOB_NAME, tasks=tasks, max_concurrent_runs=1)

if existing:
    w.jobs.reset(job_id=existing.job_id, new_settings=jobs.JobSettings(**settings))
    job_id = existing.job_id
    print(f"Updated job {job_id}")
else:
    job_id = w.jobs.create(**settings).job_id
    print(f"Created job {job_id}")

host = w.config.host.rstrip("/")
print(f"\nOpen the job: {host}/jobs/{job_id}")
print("It runs three tasks in order — clean → model → report.")
print("\nTo automate it: open the job → Schedules & triggers → Add schedule →")
print("e.g. monthly. To run it now: click Run now. No spreadsheet involved.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## (Optional) run it once now, end to end

# COMMAND ----------

# Uncomment to trigger a run from here (or just click Run now in the Jobs UI).
# run = w.jobs.run_now(job_id=job_id)
# print(f"Started run {run.run_id} — watch it at {host}/jobs/{job_id}/runs/{run.run_id}")

# COMMAND ----------

print("Pipeline job ready.")
