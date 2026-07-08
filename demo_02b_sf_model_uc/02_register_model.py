# Databricks notebook source
# MAGIC %md
# MAGIC # Use Case 2 · Step 2 — the model becomes a governed asset
# MAGIC
# MAGIC This is the conceptual jump: **the model stops being a file and becomes
# MAGIC a versioned asset in Unity Catalog.**
# MAGIC
# MAGIC The workbook's `Model` tab — three module formulas, a correlation
# MAGIC aggregation, an operational-risk add-on — is re-implemented below as a
# MAGIC small, readable Python class wrapped as an **MLflow pyfunc**. The
# MAGIC calibration (the block of parameters the actuary retypes when the
# MAGIC regulator updates them) is logged **with** the model as an artifact, so
# MAGIC a model version *is* a calibration: reproducible, reviewable,
# MAGIC permission-controlled.
# MAGIC
# MAGIC Registers **`sfm_scr_model`** version 1 from `calibration_2025.json`
# MAGIC and points the alias **`@cal_2025`** (and `@champion`) at it.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "lr_serverless_aws_us_catalog")
dbutils.widgets.text("schema_name", "actuarial_excel_demo")
dbutils.widgets.text("sfm_volume_name", "sfm_assets")
dbutils.widgets.text("calibration_file", "calibration_2025.json")

catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")
volume = dbutils.widgets.get("sfm_volume_name")
cal_file = dbutils.widgets.get("calibration_file")
fqn = f"{catalog}.{schema}"
vol_path = f"/Volumes/{catalog}/{schema}/{volume}"
MODEL_NAME = f"{fqn}.sfm_scr_model"

# COMMAND ----------

# MAGIC %md
# MAGIC ## The model — the workbook's formulas, in the open

# COMMAND ----------

import json
import math

import mlflow
import pandas as pd


class SCRStandardFormula(mlflow.pyfunc.PythonModel):
    """Three-module Standard Formula:

        SCR_nl  = 3 · sqrt((σp·Vp)² + 2·ρpr·(σp·Vp)·(σr·Vr) + (σr·Vr)²)
        SCR_mkt = |assets·dur_a − BEL·dur_l| · ir_shock
        SCR_cat = cat_factor · Vp
        BSCR    = sqrt(Σ ρij·SCRi·SCRj)
        Op      = min(op_factor·Vp, cap·BSCR)
        SCR     = BSCR + Op

    The calibration is an artifact of the logged model — a model version
    IS a calibration.
    """

    def load_context(self, context):
        with open(context.artifacts["calibration"]) as f:
            self.cal = json.load(f)

    def predict(self, context, model_input: pd.DataFrame) -> pd.DataFrame:
        c = self.cal
        out = []
        for _, r in model_input.iterrows():
            vp, vr = r["premium_volume"], r["reserve_volume"]
            nl = 3.0 * math.sqrt(
                (c["sigma_premium"] * vp) ** 2
                + 2.0 * c["premium_reserve_corr"]
                * (c["sigma_premium"] * vp) * (c["sigma_reserve"] * vr)
                + (c["sigma_reserve"] * vr) ** 2)
            mkt = abs(r["assets_mv"] * r["asset_duration"]
                      - r["liabilities_bel"] * r["liability_duration"]) * c["ir_shock"]
            cat = c["cat_factor"] * vp
            bscr = math.sqrt(nl ** 2 + mkt ** 2 + cat ** 2
                             + 2.0 * (c["corr_nl_mkt"] * nl * mkt
                                      + c["corr_nl_cat"] * nl * cat
                                      + c["corr_mkt_cat"] * mkt * cat))
            op = min(c["op_factor"] * vp, c["op_cap_of_bscr"] * bscr)
            out.append({
                "entity_id": r["entity_id"],
                "scr_nl": round(nl, 4), "scr_mkt": round(mkt, 4),
                "scr_cat": round(cat, 4), "bscr": round(bscr, 4),
                "op_risk": round(op, 4), "scr": round(bscr + op, 4),
                "calibration_year": int(c["calibration_year"]),
            })
        return pd.DataFrame(out)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Log + register in Unity Catalog

# COMMAND ----------

from mlflow.models.signature import infer_signature

mlflow.set_registry_uri("databricks-uc")

with open(f"{vol_path}/{cal_file}") as f:
    cal = json.load(f)
cal_year = cal["calibration_year"]

example = spark.table(f"{fqn}.sfm_inputs").orderBy("entity_id").limit(3).toPandas()
model = SCRStandardFormula()

# dry-fire locally so the signature reflects real output
class _Ctx:
    artifacts = {"calibration": f"{vol_path}/{cal_file}"}
model.load_context(_Ctx())
preview = model.predict(_Ctx(), example)
signature = infer_signature(example, preview)

with mlflow.start_run(run_name=f"sfm_scr_model_cal_{cal_year}") as run:
    mlflow.log_params({k: v for k, v in cal.items() if k != "description"})
    info = mlflow.pyfunc.log_model(
        artifact_path="model",
        python_model=SCRStandardFormula(),
        artifacts={"calibration": f"{vol_path}/{cal_file}"},
        signature=signature,
        input_example=example,
        registered_model_name=MODEL_NAME,
    )
version = info.registered_model_version
print(f"✓ registered {MODEL_NAME} version {version} (calibration {cal_year})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Aliases + descriptions — the governance layer

# COMMAND ----------

from mlflow import MlflowClient

client = MlflowClient()
client.set_registered_model_alias(MODEL_NAME, f"cal_{cal_year}", version)
client.set_registered_model_alias(MODEL_NAME, "champion", version)
client.update_model_version(
    name=MODEL_NAME, version=version,
    description=(f"Standard Formula SCR model, {cal_year} calibration. "
                 f"{cal.get('description', '')} Calibration JSON is logged as a "
                 "model artifact; parameters are logged to the MLflow run."))
client.update_registered_model(
    name=MODEL_NAME,
    description=("Simple three-module Solvency-II-style Standard Formula SCR model "
                 "(non-life premium & reserve, market interest-rate, catastrophe; "
                 "correlation aggregation + operational risk). One version per "
                 "calibration year — see aliases. Replaces the per-entity "
                 "SF_Model.xlsx workbook. Synthetic demo asset."))
print(f"✓ aliases @cal_{cal_year} and @champion → version {version}")
print(f"\nOpen the model: Catalog Explorer → {catalog} → {schema} → Models → sfm_scr_model")

# COMMAND ----------

print("Model registered. Next: 03_score.py")
