# Use Case 3 — From Excel BI to Genie and dashboards

![Use Case 3 flow](https://raw.githubusercontent.com/wryszka/actuarial-excel-accelerator/main/docs/img/uc3_flow.png)

## The problem

Most day-to-day insurance reporting still happens in Excel. The routine is
always the same: pull an extract from the data warehouse as a CSV, open it,
and build the pivots — claims by line of business and status, average
severity by region, the ten largest open claims, a monthly trend, a chart
for the pack. It works for a while, but:

- **It's one slice, one moment.** The extract is a snapshot; by tomorrow
  it's stale, and the next question means another extract.
- **It doesn't scale.** A single month of one line of business is fine.
  The whole book — millions of rows — won't open, or grinds Excel to a halt.
- **It's manual and personal.** Every refresh is hand-built, and the result
  is a workbook on one laptop that gets emailed around in copies.
- **It can't really be shared or automated.** No single live version
  everyone sees, and no way to have it just refresh itself.

## How we solve it

We take **the same data** — already sitting in Databricks as a governed
table (far bigger than Excel could open) — and do the analysis two better
ways: ask questions in plain English with **Genie**, and publish a live
**AI/BI dashboard** the whole company sees. No pivots to rebuild, no file to
email, and it works on the full book, not a slice.

You will never touch a command line. Everything is done by opening a
notebook and clicking **Run all**, or clicking in the Databricks UI.

Everything in Databricks is prefixed **`exp_`** so it's easy to find; all
data is synthetic.

**Needs:** serverless compute + **Genie** and **AI/BI dashboards** (both GA).
No model registry or Designer required.

## Before you start (once)

> **New here?** Read the one-page **Start here** tab of the demo guide first
> — where the notebooks live, what "Run all" means, running in your own
> workspace, and the glossary. It isn't repeated in each one.

- **Find the notebooks:** left sidebar → **Workspace** → `Shared` →
  `actuarial-excel-accelerator` → `demo_03_experience_genie`.
- **Build the data once.** Open and **Run all** on each, in order:
  `00_setup` → `01_generate_data` → `02_bronze` → `03_silver` → `04_gold` →
  `08_claims_listing`. This creates the tables the analysis uses (a synthetic
  UK general-insurance book: ~766k claim transactions, 2019–2025, 5 lines of
  business × 5 regions × 4 channels). ~5 minutes total.

| Table (`exp_` prefix) | What it is |
|---|---|
| `exp_claims_listing` | one row per claim (~146k) — the relatable, pivot-style table |
| `exp_gold_experience` | premium, incurred and loss ratio by segment × year |
| `exp_gold_triangle` | claims development by line of business × year |
| `exp_dim_segment` | the segment → line of business / region / channel lookup |

---

## The walkthrough

### Step 1 — BI in Excel today (the "before")

1. Get the extract, the way you do now: download
   `claims_extract_motor_ay2024.csv` — left sidebar → **Catalog** →
   `lr_dev_aws_us_catalog` → `actuarial_excel_demo` → Volumes →
   `exp_landing` → click the file → **Download**. (In real life this is a
   CSV pulled from the data warehouse.)
2. Open it in Excel and build the usual pivot: rows = **region**, columns =
   **status**, values = **count of claims** and **sum of incurred**. Sort
   for the largest claims. Add a chart.

**Say this:** *"This is how we do BI today. But it's one line of business, one year, one snapshot — and it's my personal copy, out of date the moment I save it."*

**"Yes, but can't we do this better?"** — the three questions everyone asks:

- *What if the file is much bigger?* This slice is one line of business for
  one year. The **whole book is millions of rows** — Excel won't open it.
- *What if I want a different cut?* Every new question is a new pivot, by
  hand. Wouldn't it be faster to just *ask*?
- *How do others see it, and can it refresh itself?* Today it's a workbook
  emailed around. There's no single live version, and nothing automatic.

Databricks answers all three. On to it.

### Step 2 — The same data, already a table (and much bigger)

The exact same claims data is already in Databricks as
**`exp_claims_listing`** — but the *whole book*, ~146k claims, not the
one-year slice. See it: left sidebar → **Catalog** → `lr_dev_aws_us_catalog`
→ `actuarial_excel_demo` → `exp_claims_listing`. Note the column comments,
the owner, and the **Lineage** tab — this is a governed table, not a file.

> **The point:** nothing was uploaded for this step. The data already lives
> here; the Excel extract was just a small copy of it.

### Step 3 — Ask questions in plain English with Genie

1. Open **`09_genie_starter`** and click **Run all**. It creates a **Genie
   space** over that one table — the quick-setup moment. (You can also do it
   by hand: left sidebar → **Genie** → **New** → pick `exp_claims_listing`.)
2. Open the space (the notebook prints the link) and type the same questions
   you'd have built pivots for — one at a time:

   *How many claims do we have by line of business and status?*

   *What is the average incurred cost per claim by region?*

   *Show the ten largest open claims.*

   *Plot the number of reported claims by month in 2024.*

3. On any answer, click **Show code** — Genie shows the SQL it wrote. The
   analyst asked in English; the platform did the query.

### Step 4 — Publish a dashboard everyone can see

Open **`10_dashboard_starter`** and click **Run all**. It builds an **AI/BI
dashboard** on the same table — the pivot pack as a live page (headline
numbers, incurred by line of business, the monthly trend, claims by region
and status, the ten largest open claims) — and **publishes it, shared with
everyone in the workspace**. Send the link; nobody emails a workbook, and
everyone sees the same live numbers.

### Step 5 — Go beyond what Excel could hold

Now the payoff for "what if it's bigger / a different cut". Open
**`09_genie_starter`** again, set the `mode` widget (top of the notebook) to
**`extend`**, and **Run all**. The Genie space now also knows premium, loss
ratios and claims development — so you can ask questions a single pivot never
could, across the full book:

*What is the loss ratio by line of business and accident year? Plot it.*

*Why is Motor 2023 worse than 2021 — break it down by region and channel.*

*Which distribution channel has the highest loss ratio?*

Genie finds the story in seconds — here, Motor deteriorating in 2022–23, a
Scotland spike in 2023, and one distribution channel running hot.

Run `99_validate` for an automated all-green check.

---

## What you end up with

| Asset | What it is |
|---|---|
| `exp_claims_listing` | the claims table Genie and the dashboard read |
| **Genie space** | ask the book questions in plain English — no pivots |
| **AI/BI dashboard** | the pack as a live page, published to everyone |

No workbook to refresh, no file to email, and it works on the full book, not
a one-year slice.

## Common questions

- **"Do I have to write SQL?"** No. Genie takes plain English; the dashboard
  is built for you. "Show code" is there if you're curious.
- **"Is this the real data or a copy?"** The real governed table — the Excel
  extract in step 1 was the copy. Everyone querying Genie or the dashboard
  sees the one live source.
- **"How big can it go?"** Far past Excel. This book is ~766k transactions;
  the same approach works on billions of rows.

## About this demo

All data is synthetic — the book resembles a UK general-insurance portfolio
but every value is fabricated. No customer data is used.
