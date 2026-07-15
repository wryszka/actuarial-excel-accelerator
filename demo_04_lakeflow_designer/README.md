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

```bash
databricks bundle deploy -t dev
# open /Workspace/Shared/actuarial-excel-accelerator/demo_04_lakeflow_designer/
```

### Act 1 — frame + sources (3 min)

1. Framing, one sentence: *"If this blend runs in a desktop ETL tool
   today, it runs on somebody's machine, under a per-seat licence, with no
   lineage, and the output gets emailed."*
2. Run `00_setup`, then `01_generate_sources` — builds the source tables,
   the lookup, the benchmark and the Excel extract.

### Act 2 — build the canvas (5–7 min)

Open **New → Data prep** (Lakeflow Designer) and build — each step is a
drag-drop operator, or describe it to Genie Code in the assistant pane:

1. **Add sources**: `dsg_claims_src`, `dsg_premium_src`, `dsg_segment`.
   Optionally **drag `claims_extract.csv` from your desktop onto the
   canvas** (download it from the `dsg_landing` volume first) — the "your
   file is welcome here" gesture.
2. **Join** claims → `dsg_segment` on `policy_segment` — the VLOOKUP.
3. **Aggregate** the joined claims: group by `line_of_business` and
   `accident_year`, sum `incurred` — the pivot.
4. **Join** premium → `dsg_segment`, then **aggregate**: group by
   `line_of_business` and `accident_year`, sum `earned_premium`. (Two
   branches merging is exactly the Alteryx picture.)
5. **Join the two aggregates** on `line_of_business` and `accident_year`.
6. **Derive the measure** — the Genie Code moment: *"add a column
   loss_ratio equal to incurred divided by earned_premium, rounded to 4
   decimals"*.
7. **Preview** — Motor's ratio climbing through 2022–23 should be visible.
8. **Write the output** to catalog table `dsg_experience` (columns
   `line_of_business`, `accident_year`, `earned_premium`, `incurred`,
   `loss_ratio` — keep these names so the parity check matches). Run.

### Act 3 — prove it, then the governance close (4 min)

1. Run `02_parity` — every LOB × accident-year cell matches the coded
   pipeline benchmark. *The analyst's canvas equals the engineers' pipeline.*
2. **Open the code behind the canvas** — real, readable, versionable in
   Git. The desktop tool's workflow file was a binary on a shared drive;
   this is code you can review.
3. **Lineage**: Catalog Explorer → `dsg_experience` → Lineage — walk back
   to the sources. "Where did this number come from" is a platform feature.
4. **Schedule it** — the canvas becomes a monthly production job:
   monitored, permissioned, serverless. No workflow server, no seat licence.
5. `99_validate` for the smoke test (canvas output shows PENDING until
   act 2 has been done once).

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
