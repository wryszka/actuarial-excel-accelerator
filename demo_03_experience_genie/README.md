# Demo 3 — Portfolio Experience & Loss-Ratio Monitoring

**What gets migrated:** the monthly *management-information pack* — the
Excel workbook an actuary keeps as a stack of PivotTables to track loss
ratios across the book. **What it becomes:** a governed pipeline feeding
an **AI/BI dashboard** (the board pack, always current) and a **Genie
space** (ask in plain English, no more "can you also slice it by…").

This is the demo that shows what **Genie + AI/BI Dashboards** replace.

---

## The "before": one actuary, one workbook, every month

`excel/Experience_Monitoring.xlsx` is the legacy artefact. Each month the
actuary:

1. Exports a **claims-transaction** extract and a **premium** extract from
   the policy/claims systems as CSVs.
2. Pastes them into the `Data_Claims` / `Data_Premium` tabs.
3. Fills a **VLOOKUP** column down to map each policy segment to line of
   business / region / channel.
4. **Refreshes a stack of PivotTables** — loss ratio, incurred, paid,
   outstanding, claim counts, by accident year × LOB × region × channel.
5. Screenshots the chart tab into the quarterly board pack.

It takes most of a day, the file groans past a single year of one line of
business, and then the email lands: *"can you also show me Motor by
distribution channel for the London book?"* — which means rebuilding
pivots by hand.

The full synthetic book here is **~800k claim transactions** across
**accident years 2019–2025**, **5 lines of business**, **5 regions**, and
**4 channels**. Excel physically cannot pivot that — it grinds long before,
and tops out at ~1.05M rows on a sheet. That ceiling is the point.

## The "after": assets in Databricks (all prefixed `exp_`)

| Layer | Asset | Replaces |
|---|---|---|
| Volume | `exp_landing` | the "export → folder" step |
| Bronze | `exp_bronze_claims_txn`, `exp_bronze_premium`, `exp_bronze_segment_map` | the pasted Data tabs |
| Silver | `exp_silver_claims`, `exp_silver_premium` | the VLOOKUP + helper columns |
| Gold | `exp_gold_experience`, `exp_gold_triangle`, `exp_dim_segment` | the PivotTables |
| **Genie space** | *Experience Monitoring — Actuarial Excel Accelerator* | the "slice it by…" emails |
| **AI/BI dashboard** | *Demo 3 — Portfolio Experience Monitoring* | the board-pack screenshot |

Three signals are deliberately baked into the data so the demo *reveals*
something — exactly the insights an actuary would otherwise hunt for by
hand:

1. **Motor 2022–2023 deteriorating** — loss ratio climbs from ~70% toward 95%+.
2. **A Scotland Q1-2023 windstorm** — a cluster of large Home / Commercial
   Property losses spikes that region.
3. **The Aggregator channel runs hot** — ~12pts worse than Broker/Direct.

## The notebooks (flat — open and Run All, no `src/` to dig through)

Run in order. Each maps to one step of the
[migration recipe](../MIGRATION_RECIPE.md).

| Notebook | Recipe step | Does |
|---|---|---|
| `00_setup.py` | — | schema + `exp_landing` volume + grants |
| `01_generate_data.py` | Land | generate ~800k-row synthetic CSVs → volume |
| `02_bronze.py` | Land | CSV → bronze Delta + lineage columns |
| `03_silver.py` | Rebuild | VLOOKUP join, typing, DQ gate, paid/outstanding split |
| `04_gold.py` | Rebuild | the loss-ratio fact, triangle, segment dim — Genie-commented |
| `05_parity.py` | Validate parity | Excel pivot ⇄ Databricks gold tie-out |
| `06_genie_space.py` | Operate | create the Genie space |
| `07_dashboard.py` | Operate | publish the AI/BI dashboard |
| `99_validate.py` | — | smoke test (rows, signals, assets) |

## Run it

```bash
# deploy the notebooks to a browsable workspace folder
databricks bundle deploy -t dev

# then open the folder in the workspace and Run All, in order:
#   /Workspace/Users/<you>/actuarial-excel-accelerator/demo_03_experience_genie/
```

Each notebook takes `catalog_name` / `schema_name` widgets (defaults match
`databricks.yml`). After `01` runs, build the "before" workbook locally:

```bash
databricks fs cp dbfs:/Volumes/<cat>/actuarial_excel_demo/exp_landing/experience_excel_claims.csv  data/
databricks fs cp dbfs:/Volumes/<cat>/actuarial_excel_demo/exp_landing/experience_excel_premium.csv data/
uv run --with pandas --with openpyxl python excel/build_excel_data.py
```

## Demo flow (the 5-minute version)

1. **Open `Experience_Monitoring.xlsx`.** Here's the pain: one slice, manual
   refresh, the VLOOKUP, the screenshot ritual.
2. **Open the AI/BI dashboard.** The whole book, every line, every year —
   always current. Point out Motor climbing, Scotland spiking, Aggregator hot.
3. **Open the Genie space.** Ask *"why is Motor 2023 worse than 2021?"* and
   watch it drill to region/channel — the email that used to cost an afternoon,
   answered in seconds.
4. **Show `05_parity`.** The new numbers tie out to the old Excel pivot to the
   penny — so the actuary can trust it.

## Sample Genie questions

- What is the Motor loss ratio by accident year? Plot it.
- Why is Motor 2023 worse than 2021 — break the loss ratio down by region and channel.
- Which distribution channel has the highest loss ratio across all lines of business?
- Show me the Scotland Home and Commercial Property loss ratio by accident year.
- Plot cumulative paid vs incurred development for Liability accident year 2021.
- What is the blended loss ratio for the whole book in 2024?

## About this demo

All data is synthetic. The book of business, claims and premium are
fabricated to resemble a UK general-insurance portfolio; no customer data
is used. Loss ratios were engineered to carry the three signals above.
