# Recording plan — Bricksurance channel

Six videos: one 60–90s **trailer** that tells the whole arc, then one
**chapter** per use case. Scene lists only — no talk track (you speak to
each scene). Recorded live in Databricks + Excel, no customer names, all
synthetic data. Target **3–4 minutes** per chapter; the trailer under 90s.

**Golden rules for video (different from doing it live):**
- **No dead air.** Anything that takes more than ~5s to run is a hard cut,
  a speed-ramp, or filmed pre-warmed. Never show a progress bar.
- **Nothing appears from nowhere.** Do all prep off-camera; on screen,
  every asset should have been introduced.
- **Warm everything first.** Pre-run Genie questions, open dashboards once,
  pre-build the Excel workbook and the Designer canvas. The camera only
  sees the good take.
- **Open and close on the app** (the tiled landing page) as "home base".
- **Use the flow PNGs** (`docs/img/uc*_flow.png`) as title cards / transitions.

**Record in this order** (easiest/strongest first): UC1 → UC3 → UC5 → UC2
→ UC4. Cut the trailer last, from the best moments.

---

## Trailer (60–90s) — "Everything you do in Excel, on one platform"

1. Montage, 2s each: an Excel macro grinding · a wall of pivot tables · a
   folder full of near-identical workbooks · a desktop ETL canvas.
2. Cut to the app landing page (the five tiles).
3. Five 6-second beats, one per chapter — the *after* shot of each:
   Genie Code explaining VBA · the registered model's versions · Genie
   drawing a chart from a typed question · the Designer canvas · the
   pipeline graph going green.
4. End card: the whole-journey diagram + channel handle.

---

## Chapter 1 — The macro nobody understands  ★ record first, best reveal

*Assets: `demo_00_vba_csv_etl`. Pre-build the `.xlsm` off-camera.*

1. **Cold open (Excel).** The claims CSV open — messy dates, `£` signs.
   Then the macro editor: scroll the wall of old VBA for 3s.
2. **Run the macro — CUT.** Show it start, then hard-cut to "done" (or
   speed-ramp). Never show the 90s grind; the slowness is told in the edit.
3. **The reveal (Databricks).** Paste the VBA into Genie Code; the
   explanation appears and flags *"silently drops rows with bad dates."*
   Hold on that line — this is the hero moment.
4. **The rewrite.** Genie Code returns the notebook; quick scroll of the
   labelled rule-by-rule cells.
5. **Run it — seconds.** `01_clean_claims` Run all; the result table fills
   near-instantly. The visual opposite of scene 2.
6. **Proof.** `02_reconciliation` tie-out table (all ✓) + the quarantine
   rows Excel had been dropping.
7. **Close.** The Schedule dialog set to daily → back to the app tile.

**Tedious/cut:** the macro runtime (scene 2 — edit it away), the `.xlsm`
build (never film), `00_setup`/`99_validate` (never film).
**Gold:** scene 3.

---

## Chapter 3 — From Excel pivots to Genie  ★ most shareable, film second

*Assets: `demo_03_experience_genie`. Pre-run all Genie questions warm.*

1. **Cold open (Excel).** Build the region × status pivot from the extract;
   add a chart. Familiar, comfortable.
2. **The turn.** One line on screen: *bigger? different cut? shareable?*
3. **Same data, bigger (Databricks).** `exp_claims_listing` in Catalog
   Explorer — comments, lineage. "Same data, the whole book."
4. **Genie (the hero).** Type a question → a chart appears. Then the
   money question: *"why is Motor 2023 worse than 2021?"* → Genie draws the
   breakdown. Click **Show code** for 2s.
5. **Dashboard.** The published AI/BI dashboard; point at the shared link.
6. **Close.** Back to the app tile.

**Tedious/cut:** the `00→08` data build (never film). **Watch:** Genie
latency — only use pre-warmed takes; cut any spinner. **Gold:** scene 4.

---

## Chapter 5 — Connect it all  ★ short, satisfying finale (45–75s)

*Assets: `demo_05_orchestration`. Job pre-created; UC1–3 already run once.*

1. **The pipeline.** Open the job graph — three tasks, clean → model →
   report, wired in order.
2. **Run now.** Click it; the tasks light up green one after another
   (speed-ramp if needed).
3. **Schedule.** The schedule dialog → monthly → Create.
4. **Close.** The whole-journey diagram; back to the app.

**Tedious/cut:** `01_create_pipeline_job` Run all (cut straight to the job
graph). **Gold:** the graph going green.

---

## Chapter 2 — The model leaves the spreadsheet  (film fourth)

*Assets: `demo_02b_sf_model_uc`. Weakest visuals — carry it on the outputs,
not the Run-alls.*

1. **Cold open (Excel).** `SF_Model.xlsx`: change an input, SCR recalcs.
   Point at the Calibration tab — "retyped in 100 files every quarter."
2. **The model becomes an asset.** `02_register_model` concept, then cut to
   **Catalog Explorer → Models → sfm_scr_model**: versions, lineage. Visual.
3. **Whole group at once.** `sfm_results` — 100 entities, `model_version`
   on every row. (Don't film the Run-all; cut to the table.)
4. **The payoff.** The 2026 recalibration → `sfm_impact` table: group SCR
   +9.9%, by module. One strong number on screen.
5. **Close.** App tile.

**Tedious/cut:** filming `01`–`04` Run-alls in sequence (monotonous — cut to
outputs only). **Gold:** the impact table.

---

## Chapter 4 — Build a step with no code (Designer)  (film last; edit hard)

*Assets: `demo_04_lakeflow_designer`. The hardest to film — do NOT show the
7 steps or the SQL box in real time.*

1. **Cold open.** A desktop ETL canvas (or a still) — "this lives on one
   laptop."
2. **Build, montage.** Fast-cut the canvas coming together: drop sources,
   the Genie-Code one-liner building the join+aggregate, the boxes named.
   **Show the no-code path only** — do not film the SQL operator or the
   untick-duplicate-keys step; they read as fiddly and off-message.
3. **Result + proof.** The output table; `02_parity` all ✓ — "same numbers
   as the coded pipeline."
4. **Governance beat.** Right-click → code pane (it's real code) → Lineage.
5. **Close.** App tile.

**Bad/tedious:** the full manual build, the SQL box, the duplicate-key
untick — all off-camera or heavily edited. If short on time, **fold this
into Chapter 5** as a 20s "and steps can be built with no code too" rather
than a standalone video.
**Gold:** the boxes assembling + parity ✓.

---

## What's good, bad, useless — summary

- **Good on camera:** UC1's Genie-Code reveal; UC3's type-a-question-get-a-
  chart; UC5's pipeline going green; UC2's impact number. The before→after
  rhythm and the flow PNGs as transitions.
- **Tedious (edit away):** every notebook Run-all wait; the UC2 sequence of
  four near-identical notebook screens; the UC1 macro runtime.
- **Bad for video (reframe/hide):** UC4's manual canvas + SQL box — never
  film in real time; montage the no-code path only.
- **Useless on camera (prep, never film):** all `00_setup`/`99_validate`,
  the `.xlsm` build, UC3's data-generation notebooks, job/space creation
  notebooks — cut straight to the created asset.
