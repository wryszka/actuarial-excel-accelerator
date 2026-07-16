# Excel Accelerator — front-door app (optional)

A one-page Databricks App presenting the four use cases: description,
links to the notebooks / walkthrough doc / recordings, live assets
(Genie space, dashboards, registered model), a health chip per scenario,
and **Reset** buttons that bring any scenario back to its original state.

Entirely optional — the accelerator works without it. Deploy only if you
want the front door.

## Deploy

```bash
# 1. Deploy the bundle first (it ships this folder to the shared path)
databricks bundle deploy -t dev

# 2. Create the app (once)
databricks apps create excel-accelerator -p DEV

# 3. Create the reset job and grant the app's service principal:
#    open shared/create_reset_job in the workspace, set widget
#    app_service_principal = the app's client id (shown by
#    `databricks apps get excel-accelerator`), Run All.

# 4. Deploy the app code from the synced workspace folder
databricks apps deploy excel-accelerator \
  --source-code-path /Workspace/Shared/actuarial-excel-accelerator/app -p DEV
```

Configuration is env-var driven (see `app.yaml`): catalog/schema, the
shared folder path, the walkthrough doc URL + tab ids, and the YouTube
links (empty = "coming soon" chip). Compute: use the smallest size
available; if your workspace has the serverless micro-app runtime,
prefer it — this app is idle most of the time and scales to zero there.
Otherwise stop the app when not demoing.

Let everyone in the workspace open and run it:

```bash
databricks permissions update apps excel-accelerator --json \
  '{"access_control_list":[{"group_name":"users","permission_level":"CAN_USE"}]}'
```

## Reset mechanics

The app never drops tables itself: Reset triggers the job
**"Excel Accelerator — Reset"** (created by `shared/create_reset_job.py`)
with a `scenario` parameter — the job runs as its owner, so permissions
stay sane. The app's SP only needs `CAN_MANAGE_RUN` on that job (the
create notebook grants it).
