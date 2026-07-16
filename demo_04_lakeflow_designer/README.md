# Use Case 4 — The monthly blend, without the desktop ETL tool

**Standalone — depends on no other use case.** The act everyone with an
Alteryx / Power Query / KNIME licence recognises: several sources in, a
canvas of join–clean–aggregate steps, a summary out — every month. **What
it becomes:** the same canvas, built in **Lakeflow Designer** in minutes,
except the output is a governed table in Unity Catalog, the workflow is
**backed by real code**, lineage is automatic, and the schedule button
turns it into production.

The closing message, and the reason this use case exists:
**you move from an uncontrolled system to a fully controlled and governed
one — with the code right there behind the canvas.** No-code doesn't mean
no code; it means the code is written *for* you.

## What gets built

The loss-ratio experience summary, visually: claims joined to the segment
lookup (the VLOOKUP), aggregated by line of business × accident year,
premium blended in, `loss_ratio` derived — output to **`dsg_experience`**.
`01_generate_sources` also builds `dsg_benchmark` — the same summary as the
coded pipeline would produce — so the canvas result can be **proven
identical**: the analyst's no-code path and the engineers' code path meet
on one platform.

| Asset (all prefixed `dsg_`) | What it is |
|---|---|
| `dsg_claims_src` | claim-grain source, only `policy_segment` so the lookup join is a real step |
| `dsg_premium_src` | earned premium by segment × accident year — the second branch |
| `dsg_segment` | the segment → LOB/region/channel lookup |
| `dsg_benchmark` | the coded-pipeline answer, for the parity check |
| `dsg_experience` | the canvas output (you create this in Designer) |
| `dsg_landing` volume | holds `claims_extract.csv` for the drag-onto-canvas beat |

Lakeflow Designer must be enabled on the workspace (**New → Data prep** in
the sidebar — it's GA).

## Run it

The notebooks are in the workspace at
`/Workspace/Shared/actuarial-excel-accelerator/demo_04_lakeflow_designer/`.
Open the folder and run them in order — no deployment needed.

### Act 1 — frame + sources (3 min)

1. Framing, one sentence: *"If this blend runs in a desktop ETL tool
   today, it runs on somebody's machine, under a per-seat licence, with no
   lineage, and the output gets emailed."*
2. Run `00_setup`, then `01_generate_sources` — builds the source tables,
   the lookup, the benchmark and the Excel extract.

### Act 2 — build the canvas (5–7 min)

First-time users: read this whole section once before starting. Every
step says exactly what to click. You build a diagram left-to-right —
boxes (called **operators**) joined by arrows — that ends in one output
table.

**Name every box as you go.** Each operator lands with a generic label
(“Join”, “Aggregate 1”…). Rename it so the canvas reads like a story:
double-click the box's title (or open the box and edit the name field at
the top of its panel) and type the name given in each step. A well-named
canvas is the whole point — anyone opening it later sees what it does.

**What we're building, in plain terms.** Our claims table only carries a
`policy_segment` code (like `MOT-LON-BRK`); it doesn't say "Motor / London
/ Broker". A separate table, `dsg_segment`, translates the code into those
words. Joining the two so every claim gets its line of business is exactly
what a **VLOOKUP** does in Excel. We do that for claims *and* for premium,
total each up by line of business × year, put the two totals side by side,
and divide to get the loss ratio.

**Open Designer:** in the workspace left sidebar click **New** (or the **+**),
then **Data prep**. A blank canvas opens with a Genie Code prompt box.

**1. Add the three sources.** Click **Add source** (or the **+** on the
canvas). In the picker, browse to catalog **`lr_dev_aws_us_catalog`** →
schema **`actuarial_excel_demo`** (or paste the full name into the search
box), and select each of these three tables — do it three times:
   - `lr_dev_aws_us_catalog.actuarial_excel_demo.dsg_claims_src`  (the claims)
   - `lr_dev_aws_us_catalog.actuarial_excel_demo.dsg_premium_src` (the premium)
   - `lr_dev_aws_us_catalog.actuarial_excel_demo.dsg_segment`     (the code → LOB/region/channel lookup)

   Tip: type `dsg_` in the picker's search box to filter to just these
   three. If nothing shows, check the catalog/schema selector at the top of
   the picker is pointed at `lr_dev_aws_us_catalog` / `actuarial_excel_demo`.
   You now have three source boxes. *(Optional flourish: instead of adding
   `dsg_claims_src` from the catalog, drag `claims_extract.csv` from your
   computer straight onto the canvas — download it from the `dsg_landing`
   volume first. It becomes a source box the same way. For this build,
   use the table.)*

**2. Join claims to the lookup — the VLOOKUP.** Drag a **Join** operator
onto the canvas. Connect two arrows into it: from `dsg_claims_src` and from
`dsg_segment`. Open the Join (click it) and set:
   - **Join type:** `Inner join`
   - **Join condition:** match `policy_segment` (left) to `policy_segment`
     (right) — pick that column on each side.
   - **Name this block `lookup claims segment`.**

   Result: every claim row now also has `line_of_business`, `region`,
   `channel`. That's the VLOOKUP, done once for the whole table.

**3. Total the claims by LOB and year — the pivot.** Drag an **Aggregate**
operator; connect the Join's output into it. Open it and set:
   - **Group by:** click **+ Add grouping** and pick `line_of_business`;
     **+ Add grouping** again and pick `accident_year`.
   - **Aggregate by:** click **+ Add aggregation**, choose column
     `incurred`, function **SUM**, and name the output column `incurred`.
   - **Name this block `aggregate incurred`.**

   This is a PivotTable: totals of incurred by line of business × year.

**4. Do the same two steps for premium.** Premium also only has the
segment code, so it needs the same VLOOKUP + total:
   - Drag a **second Join**. Connect `dsg_premium_src` and `dsg_segment`
     into it. **Join type:** `Inner join`; **Join condition:**
     `policy_segment` = `policy_segment`. **Name it `lookup premium segment`.**
   - Drag a **second Aggregate**. Connect that join into it. **Group by:**
     `line_of_business`, then `accident_year`. **Aggregate by:** column
     `earned_premium`, function **SUM**, output column `earned_premium`.
     **Name it `aggregate premium`.**

   *Prefer to drive this with Genie Code? In the assistant, type:*
   > *join dsg_premium and dsg_segment, inner join, policy_segment to
   > policy_segment; then add aggregate, group by line_of_business then
   > accident_year, aggregate by earned_premium with SUM and output name
   > earned_premium*
   *— it builds the same two blocks for you.*

   You now have two parallel branches — claims totals and premium totals —
   which is the classic two-streams-merging picture from desktop ETL tools.

**5. Put the two totals side by side.** Drag a **third Join**. Connect
`aggregate incurred` (step 3) and `aggregate premium` (step 4) into it.
   - **Join type:** `Inner join`
   - **Join condition:** match on **both** keys — `line_of_business` =
     `line_of_business` **and** `accident_year` = `accident_year` (click
     **+** to add the second condition).
   - **Name this block `combine claims and premium`.**

   Now each row has one line of business, one year, its total incurred and
   its total earned premium.

**6. Add the loss ratio — with the SQL operator.** Drag a **SQL** operator
onto the canvas and connect `combine claims and premium` into it. It opens
with an editable query against that input; set the query to add the ratio
column (keep every existing column, add one):

   ```sql
   SELECT *, round(incurred / earned_premium, 4) AS loss_ratio
   FROM combine_claims_and_premium
   ```

   The `FROM` name is the input block's name with spaces as underscores —
   if unsure, the SQL editor shows the available input name at the top; use
   that. **Name this block `add loss ratio`.**

   *Prefer no-code? If your workspace shows a **Transform** operator, use it
   instead: connect step 5 in, click **+ Add a custom column**, set the
   Rename field to `loss_ratio`, and type the expression in plain English —
   “incurred divided by earned_premium, rounded to 4 decimals” — and Genie
   Code writes it. Either operator gives the same result.*

**7. Preview.** Click the `add loss ratio` block and use its data preview to
sanity-check. Motor's `loss_ratio` should climb from ~0.75 in 2021 toward
~0.96 in 2023.

**8. Write the output table.** Drag an **Output** (destination) operator;
connect `add loss ratio` into it. Set:
   - **Table name:** `dsg_experience`
   - **Output location:** catalog `lr_dev_aws_us_catalog`, schema
     `actuarial_excel_demo`
   - **Name this block `write dsg_experience`.**

   Keep the column names as built (`line_of_business`, `accident_year`,
   `earned_premium`, `incurred`, `loss_ratio`) so the parity check matches.
   Then click **Run** (top of the canvas). It builds the table.

### Act 3 — prove it, then the governance close (4 min)

1. Run `02_parity` — every LOB × accident-year cell matches the coded
   pipeline benchmark. *The analyst's canvas equals the engineers' pipeline.*
2. **It's all code behind the scenes.** **Right-click anywhere on the
   canvas → Open code pane** (right-click also gives auto-layout, fit view,
   undo/redo). The pane shows the visual flow as the generated, readable
   code that actually runs. That's the point to make: the flow *is* code,
   so it lives in the platform under version control (commit it to Git,
   review it in a pull request, roll it back), instead of a binary workflow
   file copied around desktops. No hidden, unversioned flows multiplying
   across the org — the thing every mature desktop-ETL estate ends up
   fighting.
3. **Share it in one click.** It's a workspace object with normal
   permissions: click **Share** and give a colleague access to open, run
   or edit the exact same flow — no exporting a file, no "which version
   did you send me?". One source of truth, not a copy per person.
4. **Lineage**: Catalog Explorer → `dsg_experience` → Lineage — walk back
   to the sources. "Where did this number come from" is a platform feature.
5. **Schedule it** — the canvas becomes a monthly production job:
   monitored, permissioned, serverless. No workflow server, no seat licence.
6. `99_validate` for the smoke test (canvas output shows PENDING until
   act 2 has been done once).

### Optional — turn the result into a dashboard with Genie Code

The output table is instantly usable by the rest of the platform. To show
that, build a quick AI/BI dashboard on it without writing SQL:

1. Catalog Explorer → open `dsg_experience` → **Create → Dashboard** (this
   drops you into a new AI/BI dashboard wired to the table).
2. In the dashboard's assistant (Genie Code), describe the charts you want,
   e.g.:
   > *bar chart of loss_ratio by line_of_business*
   > *line chart of loss_ratio by accident_year, one line per line_of_business*
3. **Publish** and share the link — the same governed table now feeds a
   live dashboard, no extra pipeline. (Use Case 3 is the full version of
   this story if you want to go deeper.)

## Bring your own data (the on-ramp, shown in every use case)

Your own extract gets into Databricks in one gesture — no pipeline needed:
Catalog Explorer → your schema → **Create → Table** → drop the CSV → the
UI infers the schema → Create. Even shorter here: **drag the file directly
onto the Designer canvas** and it becomes a source node.

## About this demo

All data is synthetic — the book resembles a UK general-insurance
portfolio but every value is fabricated. No customer data is used. Desktop
ETL tools are referenced as a workflow *shape* familiar to many analysts,
not as a comparison of specific products.
