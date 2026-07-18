# Use Case 5 — Connect it all into one scheduled pipeline

![Use Case 5 flow](https://raw.githubusercontent.com/wryszka/actuarial-excel-accelerator/main/docs/img/uc5_flow.png)

## The problem

Even once each monthly job has moved off Excel, someone still runs them —
in order, by hand: clean this month's claims, then run the model, then
refresh the reporting. Miss a step, or run them out of order, and the
numbers are wrong. It's the month-end checklist that lives in someone's
head, and it stops if they're on holiday.

## How we solve it

We connect the steps into **one pipeline that runs on a schedule**. A
Lakeflow **Job** chains the three notebooks you already have — clean → model
→ report — so each one starts only when the previous one succeeds. Set it to
run monthly and the whole month-end happens on its own: no spreadsheet, no
checklist, nothing run by hand.

This is the finale of the accelerator's story — chapters 1→3 done as a
single automated flow — but it still stands alone: it just wires together
notebooks that already exist.

## How it relates to Use Case 4

They're two different kinds of automation, and both matter:

- **Use Case 4 (Lakeflow Designer)** is how an analyst *builds one step*
  without writing code — a visual data-prep canvas.
- **Use Case 5 (this one)** is how you *connect the steps* into one
  scheduled pipeline — a Job with tasks that run in order.

Designer builds a box; the Job chains the boxes.

**Needs:** serverless compute + **Lakeflow Jobs** (standard). Because it
chains Use Cases 1–3, those must be runnable — in particular **run UC2 once
first** so the `sfm_scr_model` (with its `@cal_2026` version) exists, or the
model task has nothing to score.

## Before you start (once)

> **New here?** Read the one-page **Start here** tab of the demo guide first
> — running in your own workspace, and the glossary.

- **Run Use Cases 1, 2 and 3 at least once** (each is quick — open the
  folder, Run all). This use case orchestrates their notebooks, so their
  tables and the registered model need to exist. Once they do, the pipeline
  re-runs them on demand or on a schedule.
- **Find the notebook:** left sidebar → **Workspace** → `Shared` →
  `actuarial-excel-accelerator` → `demo_05_orchestration` →
  `01_create_pipeline_job`.

## The walkthrough

### Step 1 — Create the pipeline

Open **`01_create_pipeline_job`** and click **Run all**. It builds a Lakeflow
Job named **Excel Accelerator — Month-end pipeline** with three tasks that
run in order:

1. **clean** — clean the monthly claims (Use Case 1).
2. **model** — score the capital model (Use Case 2).
3. **report** — refresh the reporting table (Use Case 3).

The notebook prints a link to the job.

### Step 2 — Look at the pipeline

Open the job (use the link). You'll see the three tasks as a small diagram,
each connected to the next: **model** waits for **clean**, **report** waits
for **model**. This is the month-end checklist, drawn as a pipeline — and
Databricks enforces the order for you.

### Step 3 — Run it end to end

Click **Run now** (top right). Watch the tasks light up one after another as
each finishes. In a couple of minutes the whole chain — clean, model, report
— has run, with one click.

### Step 4 — Put it on a schedule

Open the job → **Schedules & triggers** → **Add schedule** → set it to run
(say) monthly → **Create**. That's it: every month the full pipeline runs on
its own. The month-end checklist is now the platform's job, not a person's.

## What you end up with

A single scheduled Job that runs the whole flow — clean → model → report —
in the right order, every month, unattended. Each run is logged; if a step
fails, the job tells you and stops before it produces a wrong number.

## About this demo

All data is synthetic; no customer data is used. The job simply orchestrates
the notebooks from Use Cases 1–3.
