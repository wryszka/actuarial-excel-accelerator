# Use Case 3 — Ad-hoc analytics: from Excel pivots to Genie & AI/BI

**The act everyone recognises:** a claims listing lands in Excel, and the
ad-hoc questions start — claims by line of business and status, average
severity by region, the ten largest open claims, the monthly trend, and a
chart for the pack. **What it becomes:** the same table, already governed
in Databricks, answered in plain English with **Genie** and published to
the whole company as a live **AI/BI dashboard** — then extended with more
tables for the analysis Excel could never hold.

Two acts, one message: *ad-hoc BI doesn't need a workbook.*

## The data (already in the lakehouse)

A synthetic UK general-insurance book: ~766k claim transactions across
accident years 2019–2025, 5 lines of business × 5 regions × 4 channels,
built by notebooks `00`–`04`. All assets are prefixed **`exp_`** in the
shared schema. Three signals are deliberately baked in (Motor 2022–23
deterioration, a Scotland 2023 windstorm, the Aggregator channel running
hot) so the analysis *finds* something.

| Table | Grain | Used in |
|---|---|---|
| `exp_claims_listing` | one row per claim (~146k) | **act 1** — the relatable table |
| `exp_gold_experience` | LOB × region × channel × accident year (premium, incurred, loss ratio) | act 2 |
| `exp_gold_triangle` | LOB × accident year × development month | act 2 |
| `exp_dim_segment` | segment → LOB/region/channel | act 2 |

## Bring your own data (the on-ramp, shown in every use case)

The extract you'd pivot in Excel gets into Databricks in one gesture —
no pipeline required:

1. Catalog Explorer → your schema → **Create → Table**.
2. Drop the CSV (e.g. `claims_extract_motor_ay2024.csv` from the
   `exp_landing` volume — the same file the Excel act uses).
3. The UI infers the schema; click Create. It's now a governed table you
   can query, comment, share — and point Genie at.

In this use case the full tables are already in the lakehouse (built by
the notebooks); the upload gesture is there to show how *your* file joins
them.

## Run it

The notebooks are in the workspace at
`/Workspace/Shared/actuarial-excel-accelerator/demo_03_experience_genie/`.
Open the folder and run them in order — no deployment needed.

World build (once): `00_setup` → `01_generate_data` → `02_bronze` →
`03_silver` → `04_gold`. Then the use case itself:

| Notebook | Does |
|---|---|
| `08_claims_listing.py` | builds `exp_claims_listing` + writes the Excel extract (Motor AY2024) to the volume |
| `09_genie_starter.py` | `mode=create_starter`: Genie space over **one table**. `mode=extend`: adds the three portfolio tables |
| `10_dashboard_starter.py` | the starter dashboard on the claims listing — **published, shared with all users** |
| `05_parity.py` / `06_genie_space.py` / `07_dashboard.py` | the deeper portfolio layer: pipeline parity, the full experience Genie space and the portfolio dashboard (act 2's destination) |
| `99_validate.py` | smoke test |

## Suggested walkthrough

**Act 0 — Excel, the familiar ritual (2 min).**
Download `claims_extract_motor_ay2024.csv` from the `exp_landing` volume.
Open in Excel. Build the classic pivot: rows = region, columns = status,
values = count + sum of incurred. Sort for the largest claims. Make the
chart. This is comfortable — and it's one line of business, one year,
one person's copy, stale the moment it's saved.

**Act 1 — the same analytics, modern (5 min).**
1. Show the *same data* as a governed table: Catalog Explorer →
   `exp_claims_listing` (column comments, owner, lineage). Mention the
   one-gesture upload path above for bringing your own file.
2. **Genie, quick setup**: run `09_genie_starter` (or click through the
   UI: New Genie space → pick the table → done). Ask the Excel questions
   in English:
   - *How many claims do we have by line of business and status?*
   - *What is the average incurred cost per claim by region?*
   - *Show the ten largest open claims.*
   - *Plot the number of reported claims by month in 2024.*
   Click **Show code** on one answer — the SQL is right there.
3. **The dashboard**: run `10_dashboard_starter` — the pivot pack as a
   live page (KPIs, incurred by LOB, monthly trend, region × status,
   top-10 open). It's **published and shared with every workspace user**:
   send the link, nobody emails a workbook.

**Act 2 — beyond what Excel could hold (5 min).**
1. Re-run `09_genie_starter` with `mode = extend` (or add the tables in
   the Genie UI — Configure → Data → Add table): the space now also knows
   premium, loss ratios and development.
2. Ask the questions one table couldn't answer:
   - *What is the loss ratio by line of business and accident year? Plot it.*
   - *Why is Motor 2023 worse than 2021 — break it down by region and channel.*
   - *Which distribution channel runs the highest loss ratio?*
3. Open the portfolio dashboard (*Demo 3 — Portfolio Experience
   Monitoring*, from `07_dashboard`): the whole 766k-transaction book,
   live — Motor deteriorating, Scotland's 2023 spike, Aggregator running
   hot. The full book physically does not fit in Excel; here it's just
   another page.
4. Close with `05_parity` if trust comes up: the pipeline's numbers tie
   back to the Excel-sized slice to the penny.

## About this demo

All data is synthetic — the book resembles a UK general-insurance
portfolio but every value is fabricated. No customer data is used.
