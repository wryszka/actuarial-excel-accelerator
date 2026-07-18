# Chapter 1 — The macro nobody understands (3–4 min)

*The strongest reveal. Record first. .xlsm pre-built off-camera.*

**Scene 1 — the monthly ritual (Excel) — 20s.**
[SCREEN] the messy claims CSV (mixed dates, £ signs), then Excel with the
macro workbook open.
[DO] kick off the macro (Developer → Macros → CleanBordereau → Run).

**Scene 2 — it grinds — 5s on screen.**
[SCREEN] the macro processing, status ticking.
[CUT] hard-cut from "started" to "finished / _CLEAN.csv saved". Never show
the full ~90s run — the slowness is told by the cut, not the clock.

**Scene 3 — what does this thing even do? (Databricks) — 30s. [★]**
[SCREEN] a notebook with Genie Code open; paste the VBA in.
[DO] send the "explain what this does" prompt.
[SCREEN] the explanation lands and flags *"silently drops rows with
unreadable dates."* Hold on that line — the hero shot.

**Scene 4 — rewrite it — 15s.**
[DO] send the "rewrite as a notebook, quarantine the bad rows" prompt.
[SCREEN] Genie returns the code; scroll `01_clean_claims` — each cell
labelled as one rule from the macro.

**Scene 5 — run it, seconds not minutes — 15s.**
[DO] `01_clean_claims` → Run all.
[SCREEN] the result table fills near-instantly — the visual opposite of
Scene 2.

**Scene 6 — prove it's the same — 20s.**
[DO] `02_reconciliation` → Run all.
[SCREEN] the tie-out table (all ✓), then the quarantine rows Excel had been
dropping.

**Scene 7 — set it and forget it — 15s.**
[DO] open the Schedule dialog, set daily, Create.
[CUT] close on the app tile.

**Cut / never film:** the .xlsm build; `00_setup`; `99_validate`; the full
macro runtime.
