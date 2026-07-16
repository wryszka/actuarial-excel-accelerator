# Use Case 4 — The monthly blend, without the desktop ETL tool

Every insurance analyst knows this workflow: pull a few extracts, join and
clean them, aggregate to a summary, send it out — every month, usually in a
desktop ETL tool (Alteryx, Power Query, KNIME) running on someone's laptop.

Here you build the same thing on a visual canvas in **Lakeflow Designer** —
but the output is a governed table in Unity Catalog, the flow is real code
behind the scenes, lineage is automatic, and one click turns it into a
scheduled production job. You move from an uncontrolled, per-seat tool to a
fully governed platform — and the code is written *for* you.

## What you'll build

The loss-ratio experience summary: claims and premium each joined to a
segment lookup, totalled by line of business × accident year, combined, and
divided to give the loss ratio — written to the table `dsg_experience`.

Everything is synthetic and prefixed `dsg_`:

| Asset | What it is |
|---|---|
| `dsg_claims_src` | claims at claim grain, carrying only a `policy_segment` code |
| `dsg_premium_src` | earned premium by segment × accident year |
| `dsg_segment` | the lookup: `policy_segment` → line of business / region / channel |
| `dsg_benchmark` | the same summary the coded pipeline produces — used to prove the canvas matches |
| `dsg_experience` | the table you create on the canvas |
| `dsg_landing` volume | holds `claims_extract.csv` for the drag-onto-canvas step |

This use case is standalone — it depends on no other use case. Lakeflow
Designer must be enabled on the workspace (look for **New → Data prep** in
the sidebar — it's GA).

## Run it

The notebooks are in the workspace at
`/Workspace/Shared/actuarial-excel-accelerator/demo_04_lakeflow_designer/`.
Open the folder and run them in order — no deployment needed.

### 1. Generate the sources

Run `00_setup`, then `01_generate_sources`. This creates the three source
tables, the benchmark, and the Excel extract in the `dsg_landing` volume.

Framing for a live audience: *"This blend runs in a desktop ETL tool today —
on somebody's machine, under a per-seat licence, with no lineage, and the
output gets emailed around."*

### 2. Build the canvas

Open **New → Data prep** in the sidebar. You get a blank canvas: you'll lay
out boxes (**operators**) left to right, connect them with arrows, and end
at one output table. **Rename each box as you add it** — double-click its
title and use the name given below — so the finished canvas reads like a
story.

**The idea.** The claims table only carries a segment *code* like
`MOT-LON-BRK` — not "Motor / London / Broker". The `dsg_segment` table
translates the code into those words; joining the two is exactly a
**VLOOKUP**. You do that for claims and for premium, total each by line of
business and year, combine the two totals, and divide to get the loss ratio.

**Step 1 — add the three sources.** Click **Add source** and pick each
table (search `dsg_` to filter; if nothing appears, point the picker's
catalog/schema selector at `lr_dev_aws_us_catalog` / `actuarial_excel_demo`):

- `dsg_claims_src`
- `dsg_premium_src`
- `dsg_segment`

*(Optional: instead of the claims table, drag `claims_extract.csv` onto the
canvas — download it from the `dsg_landing` volume first — to show a desktop
file becoming a source. For the build, use the table.)*

**Step 2 — look up the claims' segment (the VLOOKUP).** Drag a **Join** and
connect `dsg_claims_src` and `dsg_segment` into it. Set **Join type** to
`Inner join` and the **condition** to `policy_segment` = `policy_segment`.
Name it **`lookup claims segment`**. Every claim now carries its line of
business, region and channel.

**Step 3 — total the claims (the pivot).** Drag an **Aggregate** and connect
the previous step into it. Under **Group by**, add `line_of_business` and
`accident_year`. Under **Aggregate by**, add `incurred` with function
**SUM**, output name `incurred`. Name it **`aggregate incurred`**.

**Step 4 — do the same for premium.** Repeat steps 2–3 on the premium side:

- A **Join** of `dsg_premium_src` and `dsg_segment`, inner join on
  `policy_segment` — name it **`lookup premium segment`**.
- An **Aggregate** grouped by `line_of_business` and `accident_year`,
  summing `earned_premium` (output name `earned_premium`) — name it
  **`aggregate premium`**.

Or build both in one line with Genie Code:

`join dsg_premium_src and dsg_segment, inner join, policy_segment to policy_segment; then add aggregate, group by line_of_business then accident_year, aggregate by earned_premium with SUM and output name earned_premium`

You now have two branches — claims totals and premium totals — ready to
merge.

**Step 5 — combine the two totals.** Drag a **Join** and connect
`aggregate incurred` and `aggregate premium` into it. Set **Join type** to
`Inner join` and add **two** conditions (click **+** for the second):
`line_of_business` = `line_of_business` and `accident_year` =
`accident_year`. Both inputs carry those two key columns, so in the
**output columns** untick `line_of_business` and `accident_year` from the
premium side, leaving each key once alongside `incurred` and
`earned_premium`. Name it **`combine claims and premium`**.

**Step 6 — add the loss ratio.** Drag a **SQL** operator and connect
`combine claims and premium` into it. Use the input name shown at the top of
the editor in the `FROM` (spaces become underscores), and set the query to:

```sql
SELECT *, round(incurred / earned_premium, 4) AS loss_ratio
FROM combine_claims_and_premium
```

Name it **`add loss ratio`**.

**Step 7 — write the output.** Drag an **Output** operator and connect
`add loss ratio` into it. Set **Table name** to `dsg_experience` and
**Output location** to catalog `lr_dev_aws_us_catalog`, schema
`actuarial_excel_demo`. Name it **`write dsg_experience`**, then click
**Run** at the top of the canvas.

Open the `add loss ratio` preview to sanity-check: Motor's `loss_ratio`
should climb from ~0.75 in 2021 toward ~0.96 in 2023.

### 3. Prove it, then make the governance point

**Run `02_parity`.** Every line-of-business × accident-year cell matches
`dsg_benchmark`, the coded pipeline's answer. The analyst's no-code canvas
and the engineers' pipeline produce the same numbers.

Then the payoff — three things a desktop ETL tool can't do:

- **It's all code.** Right-click the canvas → **Open code pane**. The flow
  you drew is generated, readable code that actually runs — so it lives
  under version control (commit, review in a pull request, roll back)
  instead of as a binary file copied between laptops. No hidden, unversioned
  flows multiplying across the org.
- **Share in one click.** It's a workspace object with normal permissions —
  **Share** it and a colleague opens, runs or edits the same flow. One
  source of truth, not a copy per person.
- **Governed and automatic.** Catalog Explorer → `dsg_experience` →
  **Lineage** walks back to the sources, so "where did this number come
  from" is answered by the platform. And **Schedule** turns the canvas into
  a monitored monthly job — no workflow server, no seat licence.

Run `99_validate` for the smoke test (it reports the canvas output as
pending until you've built it once).

### Optional — a dashboard from the result, with Genie Code

The output table is instantly usable by the rest of the platform. In
Catalog Explorer, open `dsg_experience` → **Create → Dashboard**, then
describe the charts to the assistant, e.g. *"bar chart of loss_ratio by
line_of_business"* and *"line chart of loss_ratio by accident_year, one line
per line_of_business"*. **Publish** and share the link — a live dashboard on
the same governed table, no extra pipeline. (Use Case 3 goes deeper on this.)

## Bring your own data

Getting your own extract into Databricks is one gesture: Catalog Explorer →
your schema → **Create → Table** → drop the CSV → the UI infers the schema →
Create. Or, on the canvas here, drag the file straight on and it becomes a
source.

## About this demo

All data is synthetic — the book resembles a UK general-insurance portfolio
but every value is fabricated. No customer data is used. Desktop ETL tools
are referenced as a familiar workflow *shape*, not as a product comparison.
