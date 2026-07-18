# Use Case 2 — Move a capital model out of the spreadsheet

![Use Case 2 flow](https://raw.githubusercontent.com/wryszka/actuarial-excel-accelerator/main/docs/img/uc2_flow.png)

## The problem

A lot of actuarial models live in a single Excel workbook: a Solvency II
Standard Formula SCR calculation, a reserving model, a pricing engine. It
works — but it carries real pain:

- **One file per entity.** A group with 100 entities means 100 near-identical
  workbooks, each maintained by hand.
- **Updates are manual and risky.** When the regulator changes a parameter,
  someone retypes the calibration block into every file and hopes no formula
  broke. It takes days each quarter.
- **No version history.** "Which parameters produced last quarter's number?"
  has no reliable answer — the file has been overwritten since.
- **No governance or audit.** The model is a file on a laptop or a shared
  drive. Who ran it, with what inputs, when? Nobody can say.
- **No reuse.** Sharing means emailing the workbook. Everyone ends up with a
  slightly different copy.

## How we solve it

We take the same model and make it a **governed, versioned asset in Unity
Catalog**. The formulas move into a notebook; we register the model so that
**each version is a calibration** (2025, 2026, …); we score the *whole
group* in one run instead of one file at a time; and every result is
permanently traceable to the model version that produced it. Updating the
calibration becomes registering a new version — and comparing the capital
impact of that update takes seconds, not weeks.

You will never touch a command line. Everything is done by opening a notebook
and clicking **Run all**.

Everything in Databricks is prefixed **`sfm_`** so it's easy to find; all
data is synthetic.

**Needs:** serverless compute + Unity Catalog **model registry** (this use
case registers a model). No Genie or Designer required.

## Before you start (once)

> **New here?** Read the one-page **Start here** tab of the demo guide first
> — where the notebooks live, what "Run all" means, running in your own
> workspace, and the glossary. It isn't repeated here.

- **Find the notebooks:** left sidebar → **Workspace** → `Shared` →
  `actuarial-excel-accelerator` → `demo_02b_sf_model_uc` (`00_setup`,
  `01_inputs`, `02_register_model`, `03_score`, `04_recalibrate_2026`,
  `99_validate`).
- **Run `00_setup` once.** Open it, click **Run all** at the top. It creates
  the `sfm_assets` folder, copies in the source files (the workbook, the
  inputs, the two calibrations), and loads the inputs table. (~1 minute.)

---

## The walkthrough

### Step 1 — The model, in Excel (the "before")

1. Download `SF_Model.xlsx`: left sidebar → **Catalog** →
   `lr_dev_aws_us_catalog` → `actuarial_excel_demo` → Volumes → `sfm_assets`
   → click `SF_Model.xlsx` → **Download**. Open it in Excel.
2. Look at the three tabs, the way an actuary would:
   - **Inputs** — this entity's premium, reserves, assets, liabilities.
   - **Calibration** — the regulator's parameters (shocks, correlations).
     This is the block that gets retyped on every update.
   - **Model** — the formulas: three risk modules, aggregated to **SCR**.
     For this entity, SCR ≈ **£125m**.
3. Run it the way you would: change a number on the **Inputs** tab (say,
   bump premium volume) and watch **SCR** recalculate on the Model tab.

**The talk track (the pain):** *"This is one entity. The group has a hundred — so a hundred of these files. Every quarter I retype the calibration into each one, by hand. There's no history, no audit, and it takes days. If someone asks how last year's number was produced, I can't really tell them."*

### Step 2 — The inputs become one governed table

Open **`01_inputs`** and click **Run all**. It loads the inputs for **all
100 entities** into a single table, `sfm_inputs` — the round-numbered entity
`ENT-001` is exactly the one from the workbook, so we can check the two match
later. One table, not a hundred files.

### Step 3 — Register the model in Unity Catalog

Open **`02_register_model`** and click **Run all**. This is the heart of the
use case. It:

- takes the workbook's formulas, written out as a small, readable model;
- attaches the **2025 calibration** to it; and
- **registers it in Unity Catalog** as `sfm_scr_model`, version 1, labelled
  **`@cal_2025`**.

The model has stopped being a file and become a governed asset. See it: left
sidebar → **Catalog** → `lr_dev_aws_us_catalog` → `actuarial_excel_demo` →
**Models** → `sfm_scr_model`. You get a version, an owner, a description, and
full lineage — none of which a spreadsheet has.

### Step 4 — Run the model over the whole group, and check it matches Excel

Open **`03_score`** and click **Run all**. It runs the registered model over
all 100 entities at once and writes `sfm_results` — with the model version
stamped on **every row**, so any number traces back to the exact calibration
that produced it.

The last cell is the **parity check**: for `ENT-001` — the workbook's entity
— the registered model's SCR matches the Excel workbook to four decimal
places. Same maths, now governed.

### Step 5 — The 2026 calibration arrives → add a new version

This is the update that used to mean retyping 100 files. Open
**`04_recalibrate_2026`** and click **Run all**. It:

1. registers **version 2** of the model from the 2026 calibration
   (labelled **`@cal_2026`**) — same formulas, new parameters;
2. re-scores all 100 entities with the new version; and
3. builds `sfm_impact`.

Both versions now exist side by side in Unity Catalog. Nothing was
overwritten; last year's version is still there, exactly as it was.

### Step 6 — Compare the two versions

`04_recalibrate_2026` finishes by showing `sfm_impact`: the capital change
from the 2025 → 2026 calibration, **per entity and per risk module**, with
both versions run over identical inputs. At group level the SCR moves from
about **£11.4bn to £12.5bn (+9.9%)**.

In the spreadsheet world, producing that comparison is weeks of rework. Here
it's one table — and because both sides are registered model versions, it's
permanently reproducible.

### Step 7 (optional) — Run it on a schedule

To show it can run unattended: open `03_score`, top-right, click
**Schedule → Add schedule**, set it to run (say) monthly, and **Create**.
The model now scores the group on its own — no one opens a spreadsheet.

Run `99_validate` for an automated all-green check.

---

## What you end up with

| Asset (`sfm_` prefix) | What it is |
|---|---|
| `sfm_inputs` | all 100 entities' inputs, one governed table |
| **`sfm_scr_model`** | the model, registered in Unity Catalog — v1 `@cal_2025`, v2 `@cal_2026` |
| `sfm_results` | SCR per entity per version, every row traceable to its calibration |
| `sfm_impact` | the 2025 → 2026 capital change, per entity and per module |

Plus a model you can share by permission (not by email), full lineage in
Catalog Explorer, and an optional schedule — none of which a workbook can
give you.

(To run the model on your own entities, see **Bring your own data** on the
demo guide's *Start here* tab; `01_inputs` shows the columns the model
expects.)

## About this demo

All data is synthetic. The model is a deliberately simplified,
Solvency-II-*style* Standard Formula for illustration — it is not the EIOPA
specification. No customer data is used.
