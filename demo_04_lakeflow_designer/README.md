# Use Case 4 — The monthly blend, without the desktop ETL tool

**The act everyone with an Alteryx / Power Query / KNIME licence
recognises:** several sources in, a canvas of join–clean–aggregate steps,
a summary out — every month. **What it becomes:** the same canvas, built
in **Lakeflow Designer** in minutes, except the output is a governed
table in Unity Catalog, the workflow is **backed by real code**, lineage
is automatic, and the schedule button turns it into production.

The closing message, and the reason this use case exists:
**you move from an uncontrolled system to a fully controlled and governed
one — with the code right there behind the canvas.** No-code doesn't mean
no code; it means the code is written *for* you.

## What gets built

The loss-ratio experience summary, visually: claims joined to the segment
lookup (the VLOOKUP), aggregated by line of business × accident year,
premium blended in, `loss_ratio` derived — output to
**`exp_designer_experience`**. The coded pipeline (Use Case 3's world)
already produces the same numbers in `exp_gold_experience`, so the canvas
result can be **proven identical** — the analyst's no-code path and the
engineers' code path meet on one platform.

| Asset (all prefixed `exp_designer_`) | What it is |
|---|---|
| `exp_designer_claims_src` | claim-grain source, deliberately un-enriched (only `policy_segment`) so the lookup join is a real step |
| `exp_designer_premium_src` | earned premium by segment × accident year — the second branch |
| `exp_designer_experience` | the canvas output (you create this in Designer) |
| `01_sources_check.py` / `02_parity.py` / `99_validate.py` | prepare sources · prove parity · smoke test |

Prerequisite: the Use Case 3 world (demo_03 notebooks `00`–`04`, `08`).
Lakeflow Designer must be enabled on the workspace (**New → Data prep**
in the sidebar — it's GA).

## Run it

```bash
databricks bundle deploy -t dev
# open /Workspace/Shared/actuarial-excel-accelerator/demo_04_lakeflow_designer/
```

### Act 1 — frame + sources (3 min)

1. The framing, one sentence: *"If this blend runs in a desktop ETL tool
   today, it runs on somebody's machine, under a per-seat licence, with
   no lineage, and the output gets emailed."*
2. Run `01_sources_check` — builds the two source tables and verifies the
   lookup, the gold benchmark and the Excel extract are in place.

### Act 2 — build the canvas (5–7 min)

Open **New → Data prep** (Lakeflow Designer) and build — each step is a
drag-drop operator, or just describe it to Genie Code in the assistant
pane (the natural-language prompts below work as typed):

1. **Add sources**: `exp_designer_claims_src`, `exp_designer_premium_src`
   and `exp_dim_segment` from the catalog. Optionally also **drag
   `claims_extract_motor_ay2024.csv` from your desktop straight onto the
   canvas** — the "your file is welcome here" gesture (download it from
   the `exp_landing` volume first; park it unconnected, it's just the
   point that files drop in like they do in the desktop tools).
2. **Join** claims → segment lookup: *"join the claims source to the
   segment table on policy_segment"*. (The VLOOKUP.)
3. **Aggregate** the joined claims: *"group by line_of_business and
   accident_year and sum incurred"*. (The pivot.)
4. **Join** premium → segment lookup, then **aggregate**: *"group by
   line_of_business and accident_year and sum earned_premium"*. (The
   second branch — canvases with two branches merging is exactly the
   Alteryx picture.)
5. **Join the two aggregates** on `line_of_business` and `accident_year`.
6. **Derive the measure** — the Genie Code moment: *"add a column
   loss_ratio equal to incurred divided by earned_premium, rounded to 4
   decimals"*.
7. **Preview** the node — Motor's ratio climbing through 2022–23 should
   already be visible in the numbers.
8. **Write the output** to catalog table `exp_designer_experience`
   (columns: `line_of_business`, `accident_year`, `earned_premium`,
   `incurred`, `loss_ratio` — keep these names so the parity check
   matches). Run the pipeline.

### Act 3 — prove it, then the governance close (4 min)

1. Run `02_parity` — every line of business × accident year cell matches
   the coded pipeline. *The analyst's canvas equals the engineers'
   pipeline.*
2. **Open the code behind the canvas.** It's real, readable, and
   versionable in Git. This is the line that lands: the desktop tool's
   workflow file was a binary on a shared drive; this is code you can
   review.
3. **Lineage**: Catalog Explorer → `exp_designer_experience` → Lineage —
   walk the graph back to the sources. "Where did this number come from"
   is now a platform feature, not an archaeology project.
4. **Schedule it**: the canvas becomes a monthly production job —
   monitored, permissioned, serverless. No workflow server, no seat
   licence, nothing on anyone's laptop.
5. `99_validate` for the smoke test (reports the canvas output as
   PENDING until act 2 has been done once on the workspace).

## Bring your own data (the on-ramp, shown in every use case)

Your own extract gets into Databricks in one gesture — no pipeline
needed: Catalog Explorer → your schema → **Create → Table** → drop the
CSV → the UI infers the schema → Create. In this use case there's an even
shorter path: **drag the file directly onto the Designer canvas** and it
becomes a source node.

## About this demo

All data is synthetic — the book resembles a UK general-insurance
portfolio but every value is fabricated. No customer data is used.
Desktop ETL tools are referenced as a workflow *shape* familiar to many
analysts, not as a comparison of specific products.
