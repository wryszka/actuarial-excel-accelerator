# Recording Plan — Actuarial Excel Accelerator video series

Four short external-facing videos (~4–5 min each), one per migration
scenario. Everything is recorded live in a Databricks workspace and in
Excel — no slides beyond the end card, no customer names, synthetic data
throughout.

| # | Video | Scenario | The wow moment |
|---|---|---|---|
| 1 | *Who rewrites my VBA?* | EIOPA RFR ETL (demo 1) | Assistant converts a VBA Sub to PySpark live; then the same feed twice — simple notebook, then DLT fully automated |
| 2 | *The model leaves the spreadsheet* | SCR Standard Formula → MLflow (demo 2A) | Type a shock in Excel → Databricks computes SCR → answer lands back in the cell |
| 3 | *Stop emailing the actuary* | Experience analytics → Genie + AI/BI (demo 3) | Ask Genie "why is Motor 2023 worse?" and watch it drill to the answer over a 766k-row book Excel can't open |
| 4 | *Build the next one yourself* | Lakeflow Designer on the demo 3 CSVs | An analyst rebuilds the pipeline visually — no code, same governed numbers |

**Recording order: 3 → 2 → 1 → 4** (3 is fully verified today; 1 and 4
carry prep work).

**Shared story spine** (repeat in every video, ≤20s): the 6-step recipe —
*Inventory → Decompose → Land → Rebuild → Validate parity → Operate* —
with this video's steps highlighted. The message is never "Excel is bad";
it is *"Excel stays as a window — it stops being the database, the ETL
engine and the model host."*

---

## Common production checklist (before every session)

1. **Browser hygiene**: fresh profile/window; hide bookmarks bar; close
   all tabs except the workspace; workspace theme light; zoom 110–125%.
2. **Workspace hygiene**: record on a workspace containing only demo
   assets. All accelerator assets live at
   `/Workspace/Shared/actuarial-excel-accelerator/` — pin that folder.
   No user emails on screen where avoidable (collapse the sidebar
   account chip; crop in edit otherwise).
3. **State reset**: each run sheet below has a *Reset* step. Do a full
   dry run the day before — Genie answers especially.
4. **Excel**: close all other workbooks; hide the ribbon's personal
   account name (Excel → Preferences → General → personalize turned off).
5. **Capture**: 1080p minimum (4K preferred, downscale), 16:9, system
   cursor highlight on clicks, no notification popups (Do Not Disturb).
6. **End card** (same design all four): recipe diagram + repo URL +
   *"About this demo: all data is synthetic; no customer data is used."*

---

## Video 3 — *Stop emailing the actuary* (record first)

Assets: `demo_03_experience_genie/`. Everything verified end-to-end.

**Reset / pre-flight**
1. Run `99_validate` → all checks PASS.
2. Open the AI/BI dashboard once so caches are warm
   (*Demo 3 — Portfolio Experience Monitoring*).
3. Open the Genie space (*Experience Monitoring — Actuarial Excel
   Accelerator*) and dry-run the three questions below; pin them as
   sample questions in the space if not already.
4. Open `excel/Experience_Monitoring.xlsx` locally, on the
   `Pivot_Experience` tab.

**Run sheet**
1. **Cold open — the pain (45s).** Excel full screen. Show the pivot,
   the red "REFRESH MONTHLY … ~half a day" note, flick to `Data_Claims`
   (20k rows) and `Lookup` (the VLOOKUP tab). Say the numbers: this
   workbook holds *one line of business, one region, one year*. The
   full book is ~800,000 transaction rows — Excel tops out at ~1.05M
   rows and grinds long before.
2. **The process (60s).** Switch to the workspace folder
   `demo_03_experience_genie/`. Scroll the folder: numbered notebooks
   `00`→`99`, each header names its recipe step. Open `04_gold` briefly:
   point at the table/column comments — "this documentation is what
   makes Genie work". Then Catalog Explorer → schema
   `actuarial_excel_demo` → filter `exp_` → open `exp_gold_experience`,
   show column comments + lineage tab.
3. **The dashboard (60s).** Open the published dashboard. Walk the KPI
   row (earned premium, incurred, blended loss ratio, large-loss).
   Point at the LOB line chart — Motor climbing 2022→2023. Bar charts:
   Aggregator hottest channel; Scotland region spike. Cross-filter by
   clicking Motor. "This is the board pack. Nobody refreshes it."
4. **Genie (90s — the headline).** Open the Genie space. Ask, in order:
   - *"What is the Motor loss ratio by accident year? Plot it."*
   - *"Why is Motor 2023 worse than 2021 — break the loss ratio down by
     region and channel."*
   - *"Which segment had the biggest large-loss impact in 2023?"*
   After the second answer, click **Show code** — the generated SQL is
   the trust moment for a technical audience.
5. **Trust + Excel stays (60s).** Open `05_parity`, scroll to the
   tie-out table (all ✓): "the new numbers match the old pivot to the
   penny — same data, different engine." Then Excel: **Data → Get Data
   → connect to the Databricks SQL warehouse → select
   `exp_gold_experience` → build a pivot on live data.** Close: "Excel
   is still here. It's a window now, not a database."
6. End card.

---

## Video 2 — *The model leaves the spreadsheet*

Assets: `demo_02a_scr_sf/`. Built and run pre-shared-path-move —
re-verify before recording (prep item P5).

**Reset / pre-flight**
1. Confirm `scr_*` tables exist and `scr_scenarios` has the 30-run sweep;
   re-run `06_orchestrator` + `07_scenarios_mlflow` if stale.
2. Confirm the MLflow experiment renders (open it, sort runs by `scr`).
3. Confirm UC functions `scr_total` etc. exist (Catalog Explorer →
   functions) and the Lakeview dashboard *Demo 2A — SCR Standard
   Formula* opens.
4. Excel: `SCR_StandardFormula.xlsm` open on the `Aggregation` tab;
   Power Query connection to the warehouse configured and dry-run
   (prep item P6).

**Run sheet**
1. **Cold open (45s).** The SCR workbook: `Assumptions` tab (σ values +
   correlation matrix), module tabs, then the `Aggregation` tab's giant
   `=SQRT(...)` formula. Show the `RunScenarios` macro in the VBA editor
   (⌥F11): a hardcoded loop writing rows to a `Scenarios` tab. "This is
   a regulatory capital model living in a file on a laptop."
2. **The rebuild (60s).** Workspace folder `demo_02a_scr_sf/src/`:
   notebooks `01`→`06`, one per module — same maths, versioned, reviewed.
   Open `05_aggregation` and show the same formula as *readable code*
   next to the assumptions coming from a governed Delta table with an
   `effective_date`.
3. **MLflow sweep (75s).** Run (or show the completed) `07_scenarios_mlflow`.
   Open the MLflow experiment: 30 scenario runs, sort by SCR, open the
   worst run, show logged params (shocks) and metrics (module SCRs).
   "The macro wrote rows to a tab. This logs every scenario with full
   lineage — compare any two runs."
4. **Parity (30s).** `08_parity_test` output: Excel oracle ⇄ Databricks
   to the penny.
5. **The round-trip (75s — the headline).** Excel `Round_Trip` tab: type
   an interest-rate shock and a motor uplift, hit **Refresh**. Power
   Query calls the UC `scr_total` function; the SCR breakdown lands back
   in the sheet. "The actuary keeps the Excel front-end. The model now
   runs on the platform — governed, logged, one version of the truth."
6. End card.

---

## Video 1 — *Who rewrites my VBA?* (two builds: simple, then automated)

Assets: `demo_01_rfr_etl/`. Prep items P1–P4 must land first.

**Reset / pre-flight**
1. Volume `rfr_landing` contains only the 2025-09/10/11 sample files —
   keep `EIOPA_RFR_2025_12.xlsx` OFF the volume (it lands on camera).
2. Bronze/silver/gold tables reflect those three months.
3. `RFR_Master.xlsm` (with real VBA, prep P1) open; VBA editor ready.
4. DLT pipeline (prep P3) exists, green from a prior run, file-arrival
   trigger armed.
5. Assistant/Genie Code conversion prompt dry-run (prep P4).

**Run sheet**
1. **Cold open (45s).** `RFR_Master.xlsm`: the `History` tab (curve
   archive), then ⌥F11 → the four Subs: `ImportFile`, `ReshapeCurve`,
   `AppendHistory`, `RefreshChart`. "Every month, someone runs this by
   hand. When they're on holiday, nobody does."
2. **Nobody rewrites it by hand (60s).** In the workspace, open the
   assistant / Genie Code. Paste the `ReshapeCurve` Sub (from
   `VBA_SPEC.md`) with the prompt: *"Convert this Excel VBA to PySpark
   operating on an EIOPA RFR_spot_no_VA sheet read from a Unity Catalog
   volume."* Show the generated PySpark next to the hand-validated
   notebook `02` logic — "the conversion is no longer the project."
3. **Build (a) — simple, no DLT (60s).** Open `02b_silver_simple` (prep
   P2). Drop the December file on camera:
   `databricks fs cp demo_01_rfr_etl/sample_data/EIOPA_RFR_2025_12.xlsx dbfs:/Volumes/<cat>/actuarial_excel_demo/rfr_landing/`
   (or upload via Catalog Explorer → Volume → Upload, more visual).
   Run All on the simple notebook: bronze → silver → gold in one pass;
   show `rfr_curves` now has December. "One notebook already beats the
   macro: typed, governed, re-runnable."
4. **Build (b) — DLT, complex + automated (90s).** Same feed, production
   shape. Open the DLT pipeline graph (`02_silver_dlt.sql`): show the
   **expectations** (data-quality rules Excel can't express) and the
   event log. Reset to pre-December state (reset script), drop the
   December file again — the **file-arrival trigger** starts the
   pipeline unattended. Watch the graph light up; open the expectations
   results (rows passed / quarantined). "Version (a) removes the macro.
   Version (b) removes the human: the file lands, the pipeline runs,
   quality is checked, history grows — and if a file is malformed it's
   quarantined instead of silently wrong."
5. **Close (30s).** Catalog Explorer → `rfr_curves` with four months +
   lineage from volume → bronze → silver → gold. End card.

---

## Video 4 — *Build the next one yourself* (Lakeflow Designer)

Uses demo 3's CSVs as the "real Excel exports" (Designer takes CSV
natively; .xlsx is not a file source — a deliberate reason to use the
demo 3 files). Prep item P7 gates this video.

**Reset / pre-flight**
1. Confirm Lakeflow Designer preview is enabled on the recording
   workspace (P7). Fallback: enroll, or record on a workspace that has it.
2. Volume `exp_landing` has the three CSVs (from demo 3's `01`).
3. Pre-compute the target numbers: total earned premium, incurred and
   blended loss ratio from `exp_gold_experience` (for the parity beat).
4. Delete any `exp_designer_*` tables from prior takes.

**Run sheet**
1. **Cold open (30s).** "Videos 1–3: we migrated it for you. This one:
   your analysts build the next pipeline themselves — no code."
2. **Source (60s).** New pipeline in Lakeflow Designer. Add the three
   CSVs from `exp_landing` as sources (`claims_transactions`,
   `premium_exposure`, `segment_map`) — point out these are literally
   the actuary's monthly system exports.
3. **Transform visually (120s).** Drag-drop, narrating each Excel
   equivalent:
   - join claims → segment_map on `policy_segment` ("the VLOOKUP");
   - derived column `accident_year` from `accident_date` ("the helper
     column");
   - conditional split / expression: payments+recoveries vs reserve
     changes ("the SUMIFS");
   - aggregate by line_of_business × accident_year: incurred, earned
     premium (joined from premium source), loss ratio ("the PivotTable").
4. **Target + run (60s).** Write to
   `actuarial_excel_demo.exp_designer_experience` (keep the `exp_designer_`
   prefix). Run. Open the result table.
5. **Parity + operate (45s).** Side-by-side query: `exp_designer_experience`
   vs `exp_gold_experience` totals — same numbers as the coded pipeline.
   Show the schedule button ("monthly, unattended") and that the output
   is instantly Genie-able because it's a governed UC table.
6. End card: full recipe, all four videos named.

---

## Prep backlog (build before recording)

| # | Task | For | Notes |
|---|---|---|---|
| P1 | Build `RFR_Master.xlsm` with the real VBA modules from `VBA_SPEC.md` (base workbook via `demo_01_rfr_etl/excel/build_excel_data.py`, paste VBA in Excel, save as .xlsm — stays local, `*.xlsm` is sync-excluded) | V1 | Needed on camera for the VBA editor scene |
| P2 | Write `demo_01_rfr_etl/src/02b_silver_simple.py` — plain-notebook silver+gold pass (variant a); today silver exists only as DLT SQL | V1 | Mirror `02_silver_dlt.sql` logic |
| P3 | Restore the DLT pipeline for variant (b): recover `resources/pipelines.yml` from git commit `4d299ff`, re-add `include:`, add file-arrival trigger; re-deploy | V1 | Removal commit was `c4de280` |
| P4 | Dry-run the VBA→PySpark conversion prompt in the workspace assistant / Genie Code; keep the winning prompt in `demo_01_rfr_etl/excel/VBA_SPEC.md` | V1 | Answers vary — rehearse |
| P5 | Re-verify demo 2A end-to-end on the shared path (tables, MLflow experiment, UDFs, dashboard) | V2 | Built before the /Shared move |
| P6 | Configure + dry-run the Excel↔warehouse connections on the recording machine: demo 2A Power Query round-trip AND demo 3 live table connection. **Risk:** Excel for Mac's Get Data has limited connectors — if the Databricks/ODBC path fails on Mac, record the Excel connectivity scenes on a Windows VM (Excel 365 + Databricks ODBC driver) | V2, V3 | Do this first — it's the long pole |
| P7 | Check Lakeflow Designer preview availability on the recording workspace; enroll if needed | V4 | Gates video 4 |
| P8 | Design the shared end card (recipe diagram + repo URL + synthetic-data disclaimer) | all | One asset, reused |
