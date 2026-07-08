# Demo 0 — Recording Guide: "The VBA nobody understands"

The complete step-by-step for the first video: a legacy Excel macro
processes the monthly claims bordereau; Genie Code explains it, converts
it, and a file-arrival job makes the pipeline run itself. Two stages on
camera, ~4–5 minutes total. All data is synthetic; no customer names
anywhere.

---

## Part A — One-time setup (before any recording day)

**A1. Build the macro workbook (local, once).**
1. Open `excel/Bordereau_ETL.xlsx` in Excel.
2. ⌥F11 → File → **Import File…** → `excel/ClaimsBordereauETL.bas`.
3. Save As → **Excel Macro-Enabled Workbook** → `Bordereau_ETL.xlsm`
   (same folder; `.xlsm` stays local — it's excluded from git and sync).
4. Dry-run: run macro `RunMonthlyETL`, pick `data/bordereau_2025_11.csv`,
   confirm it reports **44,216 claims standardised** and writes
   `bordereau_2025_11_STANDARDISED.csv` next to the input.

**A2. Deploy and prime Databricks.**
1. `databricks bundle deploy -t dev`
2. Open `/Workspace/Shared/actuarial-excel-accelerator/demo_00_vba_csv_etl/`.
3. Run `00_setup` (creates the `brd_landing` volume with `incoming/`).
4. Run `03_create_job` once so the stage-2 job exists and the trigger is
   armed. **Then pause the job** (Jobs UI → the job → Pause trigger) so it
   doesn't fire during stage-1 takes; unpause for stage 2.

**A3. Stage the props.**
1. Put `bordereau_2025_11.csv` in your local **Downloads** folder (it plays
   the "file the actuary downloads from the TPA portal").
2. Keep `bordereau_2025_12.csv` ready in a second folder — it's "next month".
3. Genie Code dry-run: paste the whole of `ClaimsBordereauETL.bas` into the
   assistant with Prompt 1 below; confirm the explanation calls out the
   silent row-drops. Answers vary — rehearse once.

**A4. Reset between takes.**
Run `00_setup` with widget `reset = yes` (drops the `brd_` tables, clears
`incoming/`), and delete any `*_STANDARDISED.csv` from Downloads. Job stays;
pause its trigger again if you unpaused it.

**A5. Trigger health check (do this the day before).**
Verified behaviour: a **freshly created** job's file-arrival trigger fires
within ~1 minute of a file landing. But a trigger that has been paused,
unpaused and edited repeatedly can wedge silently (observed on dev: armed
but never evaluating). If a test drop doesn't start a run within ~2
minutes: **delete the job** (Jobs UI or
`databricks api post /api/2.2/jobs/delete --json '{"job_id": <id>}'`),
re-run `03_create_job`, wait a minute, then drop the file — it fires
reliably from a clean create. Drop files only *after* the job exists.

---

## Part B — Stage 1: the as-is process, then the migration (~3 min)

**Scene 1 — the monthly ritual (45s).** Screen: Finder + Excel.
1. Show `bordereau_2025_11.csv` in Downloads — "this arrives from our TPA
   every month".
2. Open `Bordereau_ETL.xlsm`. Run `RunMonthlyETL`, pick the CSV.
3. While it runs, one line: "this macro is older than some of our graduates —
   we know what goes in and what comes out, and that's about it."
4. Show the `Standardised` tab, then the exported
   `bordereau_2025_11_STANDARDISED.csv` in Finder: "this gets uploaded into
   the pricing system — not today's topic."

**Scene 2 — what does this thing actually do? (60s).** Screen: Excel VBA
editor → Databricks.
1. ⌥F11, show the module. Scroll slowly — three date formats, `Chr(163)`,
   a `Collection` dedupe, `GoTo NextRow`.
2. Copy the whole module. In Databricks, new notebook → open Genie Code
   (the assistant). Paste and ask:

   > **Prompt 1:** Here is a VBA macro from an old Excel workbook we run
   > every month and nobody fully understands anymore. Explain step by step
   > what it does, and call out anything surprising or risky.

3. Read the reveal out loud when it lands: **rows with unparseable loss
   dates are silently skipped** — no log, no count. "We've been dropping
   claims for years and nobody knew."

**Scene 3 — same thing, on Databricks (45s).**
1. Follow up in Genie Code:

   > **Prompt 2:** Now write PySpark for a Databricks notebook that does the
   > same thing: read the bordereau CSV files from a Unity Catalog volume,
   > apply the same cleaning rules (dedupe on claim ref, the three date
   > formats, £/(x) amount parsing, the status-code mapping, incurred =
   > paid + outstanding), and save the result as a governed Delta table.
   > One improvement: instead of silently dropping rows with unparseable
   > loss dates, keep them in a separate quarantine table.

2. Show the generated code, then switch to `01_bordereau_etl` (the
   validated version of exactly that): "same rules, now in the open — each
   hidden behaviour is a visible, testable transformation."

**Scene 4 — run it (45s).**
1. Catalog Explorer → `brd_landing` volume → `incoming/` → **Upload** →
   pick `bordereau_2025_11.csv` from Downloads (same file the macro just ate).
2. Run All on `01_bordereau_etl`: bronze 45,000 → silver 44,216 +
   quarantine 184.
3. Open `brd_silver_claims` in Catalog Explorer: "governed, documented,
   and anyone I share the schema with can query or download this — no more
   emailing CSVs."

**Scene 5 — it is the same thing (30s).**
1. Run `02_reconciliation` (defaults point at month 11).
2. The tie-out table: rows, paid, outstanding, incurred — all ✓ to the penny.
3. Scroll to the quarantine reveal: "…and here are the 184 claims Excel has
   been throwing away every month. They're not lost anymore."

---

## Part C — Stage 2: automate it (~1.5 min)

**Scene 6 — the job (30s).**
1. Unpause the trigger (Jobs UI). Open the job *Demo 0 — Bordereau ETL
   (file-arrival)*: one task — the same notebook — and a **file-arrival
   trigger** watching `incoming/`.
2. "Stage 1 replaced the macro. This replaces the calendar reminder."

**Scene 7 — next month arrives (60s).**
1. Drop `bordereau_2025_12.csv` into `incoming/` (Catalog Explorer upload —
   the same gesture as an SFTP drop or a vendor pull).
2. Jobs UI: within ~a minute a run starts on its own. Talk over the wait:
   "however the file arrives — portal download, SFTP, vendor API — the
   pipeline doesn't care. It fires when the file lands."
3. When it's green: `brd_silver_claims` now shows two source files.
4. Re-run `02_reconciliation` with `source_file = bordereau_2025_12.csv` →
   ✓ to the penny again.
5. Close: "same numbers, zero hands. The actuary stopped being the pipeline."

**End card.** Recipe diagram + repo URL + "All data in this demo is
synthetic; no customer data is used."

---

## Numbers to expect (seeded, deterministic)

| Metric | Month 2025-11 | Month 2025-12 |
|---|---|---|
| Rows in vendor CSV | 45,000 | 45,000 |
| Exact duplicate rows (deduped) | 600 | 600 |
| Claims standardised (silver / VBA) | 44,216 | 44,186 |
| Quarantined (VBA dropped silently) | 184 | 214 |

If a take produces different numbers, the wrong file went in or a reset
was skipped — run Part A4 and go again.
